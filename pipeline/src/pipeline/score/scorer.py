"""
M5 scorer: contract-, entity-, and municipality-level risk scores computed
from the M3 flag tables (`flag_contrato` / `flag_entidad`).

Formula (PLAN.md "Red-flag catalog (v1)"):

    score = 100 x sum(weights of fired flags) / sum(weights of applicable flags)

"Applicable" means a (key, flag_id) row exists at all in flag_contrato /
flag_entidad -- fired or not. A key with zero applicable flags gets
score = NULL (excluded from ranking entirely, never treated as 0).

Entity/municipio aggregation (PLAN.md): value-weighted mean of the group's
own contract-level scores (+ entity-level flags for entities), shrunk via
empirical Bayes toward the department mean:

    shrunk = (n / (n+k)) * own_mean + (k / (n+k)) * dept_mean

`k` and the flag weights are read from `weights.yaml` (see
`pipeline.score.weights`). Entities/municipios with fewer than
`MIN_CONTRATOS_RANK` contracts get `datos_insuficientes = true` (still
scored, just flagged low-confidence per PLAN.md).

Usage:
    uv run python -m pipeline.score.scorer

Writes three tables into the same DuckDB mart:
  - contrato_score   (grain: id_contrato)
  - entidad_score    (grain: nit_entidad_norm)
  - municipio_score  (grain: cod_dpto, cod_mpio)

Data-quality note (not fixed here, see docs/METHODOLOGY.md "Limitaciones"):
`fct_contrato.id_contrato` is not perfectly unique (~0.03% of the sample --
a handful of SECOP I rows reporting the same contract number twice with
different dates/values, a pre-existing M2 artifact). flag_contrato is
already keyed by id_contrato (M3's design), so a duplicated id_contrato can
have more than one physical row per flag_id; this module resolves that via
BOOL_OR (fired if ANY underlying row fired) before computing weights, and
picks one deterministic canonical row for descriptive fields (value, date,
entity/supplier names). F12 has one analogous, legitimate (non-artifact)
case: it is computed per entity-year but keyed by entity only, so an entity
active across multiple sample years can have >1 row for F12 -- resolved the
same way.
"""

from __future__ import annotations

import json
import logging
import time

import duckdb
import pyarrow as pa

from pipeline.config import MARTS_DIR
from pipeline.flags.params import FLAG_META
from pipeline.score.weights import MIN_CONTRATOS_RANK, SHRINKAGE_K, tier_for, total_weight

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table DDL
# ---------------------------------------------------------------------------

_CONTRATO_SCORE_DDL = """
    CREATE TABLE contrato_score (
        id_contrato VARCHAR,
        nit_entidad_norm VARCHAR,
        nombre_entidad VARCHAR,
        doc_proveedor_norm VARCHAR,
        nombre_proveedor VARCHAR,
        cod_dpto VARCHAR,
        cod_mpio VARCHAR,
        valor_contrato DOUBLE,
        fecha_firma DATE,
        anio INTEGER,
        urlproceso VARCHAR,
        source VARCHAR,
        n_flags_aplicables INTEGER,
        n_flags_disparados INTEGER,
        score DOUBLE,
        tier VARCHAR,
        flags_disparados VARCHAR
    )
"""
_CONTRATO_SCORE_COLUMNS = [
    "id_contrato", "nit_entidad_norm", "nombre_entidad", "doc_proveedor_norm", "nombre_proveedor",
    "cod_dpto", "cod_mpio", "valor_contrato", "fecha_firma", "anio", "urlproceso", "source",
    "n_flags_aplicables", "n_flags_disparados", "score", "tier", "flags_disparados",
]

_ENTIDAD_SCORE_DDL = """
    CREATE TABLE entidad_score (
        nit_entidad_norm VARCHAR,
        nombre_entidad VARCHAR,
        cod_dpto VARCHAR,
        cod_mpio VARCHAR,
        n_contratos BIGINT,
        valor_total DOUBLE,
        contract_component DOUBLE,
        entity_component DOUBLE,
        combined_raw_score DOUBLE,
        dept_mean_score DOUBLE,
        k_shrinkage DOUBLE,
        score DOUBLE,
        tier VARCHAR,
        datos_insuficientes BOOLEAN,
        n_flags_aplicables INTEGER,
        n_flags_disparados INTEGER,
        flags_disparados VARCHAR
    )
"""
_ENTIDAD_SCORE_COLUMNS = [
    "nit_entidad_norm", "nombre_entidad", "cod_dpto", "cod_mpio", "n_contratos", "valor_total",
    "contract_component", "entity_component", "combined_raw_score", "dept_mean_score", "k_shrinkage",
    "score", "tier", "datos_insuficientes", "n_flags_aplicables", "n_flags_disparados", "flags_disparados",
]

_MUNICIPIO_SCORE_DDL = """
    CREATE TABLE municipio_score (
        cod_dpto VARCHAR,
        cod_mpio VARCHAR,
        dpto VARCHAR,
        municipio VARCHAR,
        n_contratos BIGINT,
        valor_total DOUBLE,
        raw_score DOUBLE,
        dept_mean_score DOUBLE,
        k_shrinkage DOUBLE,
        score DOUBLE,
        tier VARCHAR,
        datos_insuficientes BOOLEAN
    )
"""
_MUNICIPIO_SCORE_COLUMNS = [
    "cod_dpto", "cod_mpio", "dpto", "municipio", "n_contratos", "valor_total",
    "raw_score", "dept_mean_score", "k_shrinkage", "score", "tier", "datos_insuficientes",
]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _weights_values_sql(nivel: str) -> str:
    """A `(VALUES ...) AS w(flag_id, peso)` SQL fragment for one nivel ('contract'/'entity')."""
    rows = ", ".join(f"('{fid}', {meta['peso']})" for fid, meta in FLAG_META.items() if meta["nivel"] == nivel)
    return f"(VALUES {rows}) AS w(flag_id, peso)"


def _fetch_flag_agg(con: duckdb.DuckDBPyConnection, table: str, key_col: str, nivel: str) -> dict[str, dict]:
    """
    {key: {"n_flags_aplicables", "n_flags_disparados", "peso_aplicable", "peso_disparado"}}
    for every key with >=1 applicable flag in `table` (flag_contrato/flag_entidad).

    Dedupes (key, flag_id) via BOOL_OR first -- see module docstring for why
    that can be necessary even though each flag module's SQL already writes
    one row per (key, flag_id) in the common case.
    """
    weights_sql = _weights_values_sql(nivel)
    sql = f"""
        WITH flag_dedup AS (
            SELECT {key_col} AS key, flag_id, BOOL_OR(fired) AS fired
            FROM {table}
            GROUP BY 1, 2
        ),
        joined AS (
            SELECT fd.key, fd.flag_id, fd.fired, w.peso
            FROM flag_dedup fd
            JOIN {weights_sql} USING (flag_id)
        )
        SELECT
            key,
            COUNT(*) AS n_flags_aplicables,
            COUNT(*) FILTER (WHERE fired) AS n_flags_disparados,
            SUM(peso) AS peso_aplicable,
            COALESCE(SUM(peso) FILTER (WHERE fired), 0) AS peso_disparado
        FROM joined
        GROUP BY key
    """  # noqa: S608 -- table is always one of two fixed constants (flag_contrato/flag_entidad)
    out: dict[str, dict] = {}
    for key, n_ap, n_di, p_ap, p_di in con.execute(sql).fetchall():
        out[key] = {
            "n_flags_aplicables": n_ap,
            "n_flags_disparados": n_di,
            "peso_aplicable": p_ap,
            "peso_disparado": p_di,
        }
    return out


def _fetch_fired_evidence(con: duckdb.DuckDBPyConnection, table: str, key_col: str) -> dict[str, list[dict]]:
    """
    {key: [{"flag_id", "nombre", "peso", "evidence": {...}}, ...]} for every
    key with >=1 fired flag in `table`. Same BOOL_OR dedup as `_fetch_flag_agg`;
    when duplicate rows disagree on evidence, the evidence from a fired row
    wins (falls back to any row's evidence otherwise).
    """
    sql = f"""
        SELECT key, flag_id, evidence_json
        FROM (
            SELECT {key_col} AS key, flag_id, BOOL_OR(fired) AS fired,
                   COALESCE(MAX(evidence_json) FILTER (WHERE fired), MAX(evidence_json)) AS evidence_json
            FROM {table}
            GROUP BY 1, 2
        )
        WHERE fired
    """  # noqa: S608
    out: dict[str, list[dict]] = {}
    for key, flag_id, evidence_json in con.execute(sql).fetchall():
        meta = FLAG_META[flag_id]
        out.setdefault(key, []).append(
            {
                "flag_id": flag_id,
                "nombre": meta["nombre"],
                "peso": meta["peso"],
                "evidence": json.loads(evidence_json) if evidence_json else {},
            }
        )
    return out


def _write_table(con: duckdb.DuckDBPyConnection, table: str, ddl_sql: str, columns: dict[str, list]) -> None:
    """
    DROP+CREATE `table` per `ddl_sql`, bulk-load `columns` (name -> list of
    values, all same length) via a registered pyarrow Table. Mirrors
    flags/run_all.py's `_write_rows`: `executemany` measured minutes for
    ~300k rows; this does the same load in well under a second.
    """
    con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute(ddl_sql)
    arrow_tbl = pa.table(columns)
    con.register("_score_rows_tmp", arrow_tbl)
    try:
        con.execute(f"INSERT INTO {table} SELECT * FROM _score_rows_tmp")  # noqa: S608 -- table is a fixed constant
    finally:
        con.unregister("_score_rows_tmp")


def _rows_to_columns(rows: list[dict], column_order: list[str]) -> dict[str, list]:
    return {c: [r.get(c) for r in rows] for c in column_order}


# ---------------------------------------------------------------------------
# Empirical-Bayes shrinkage
# ---------------------------------------------------------------------------

def shrink(own_mean: float | None, group_mean: float | None, n: float, k: float) -> float | None:
    """
    shrunk = (n/(n+k)) * own_mean + (k/(n+k)) * group_mean.

    As n grows relative to k, weight shifts toward `own_mean` (the entity's
    own track record); as n shrinks, weight shifts toward `group_mean` (the
    department, or the national mean when department is unknown), damping
    small-sample noise. Falls back gracefully when either mean is missing
    (no own data at all, or no peers at all) instead of raising.
    """
    if own_mean is None and group_mean is None:
        return None
    if own_mean is None:
        return group_mean
    if group_mean is None:
        return own_mean
    w = n / (n + k)
    return w * own_mean + (1 - w) * group_mean


def combine_components(contract_component: float | None, entity_component: float | None, cw: float, ew: float) -> float | None:
    """
    Blend an entity's contract-level component and entity-level-flag
    component into one pre-shrinkage "own mean", weighted by each
    component's total weight mass in the catalog (`cw`=contract flags total,
    `ew`=entity flags total -- see docs/METHODOLOGY.md for the rationale).
    Falls back to whichever component is available if the other is missing.
    """
    if contract_component is None and entity_component is None:
        return None
    if contract_component is None:
        return entity_component
    if entity_component is None:
        return contract_component
    return (cw * contract_component + ew * entity_component) / (cw + ew)


# ---------------------------------------------------------------------------
# Contract-level scoring
# ---------------------------------------------------------------------------

def compute_contract_scores(con: duckdb.DuckDBPyConnection) -> dict:
    t0 = time.time()

    agg = _fetch_flag_agg(con, "flag_contrato", "id_contrato", "contract")
    fired_evidence = _fetch_fired_evidence(con, "flag_contrato", "id_contrato")

    con.execute("""
        CREATE OR REPLACE TEMP TABLE _contrato_dedup AS
        SELECT * EXCLUDE (_rn) FROM (
            SELECT fc.*,
                ROW_NUMBER() OVER (
                    PARTITION BY id_contrato
                    ORDER BY fecha_firma DESC NULLS LAST, row_id DESC NULLS LAST
                ) AS _rn
            FROM fct_contrato fc
        )
        WHERE _rn = 1
    """)

    cur = con.execute("""
        SELECT id_contrato, nit_entidad_norm, nombre_entidad, doc_proveedor_norm, nombre_proveedor,
               cod_dpto, cod_mpio, valor_contrato, fecha_firma, anio, urlproceso, source
        FROM _contrato_dedup
    """)
    cols = [d[0] for d in cur.description]
    base_rows = cur.fetchall()

    out_cols: dict[str, list] = {c: [] for c in _CONTRATO_SCORE_COLUMNS}
    n_null_score = 0
    for row in base_rows:
        rec = dict(zip(cols, row, strict=True))
        key = rec["id_contrato"]
        a = agg.get(key)
        if a is None:
            n_aplic, n_disp, score = 0, 0, None
        else:
            n_aplic, n_disp = a["n_flags_aplicables"], a["n_flags_disparados"]
            score = (100.0 * a["peso_disparado"] / a["peso_aplicable"]) if a["peso_aplicable"] else None
        if score is None:
            n_null_score += 1

        for c in cols:
            out_cols[c].append(rec[c])
        out_cols["n_flags_aplicables"].append(n_aplic)
        out_cols["n_flags_disparados"].append(n_disp)
        out_cols["score"].append(score)
        out_cols["tier"].append(tier_for(score))
        out_cols["flags_disparados"].append(json.dumps(fired_evidence.get(key, []), ensure_ascii=False, default=str))

    _write_table(con, "contrato_score", _CONTRATO_SCORE_DDL, out_cols)

    return {
        "n_contratos": len(base_rows),
        "n_null_score": n_null_score,
        "seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Entity-level scoring
# ---------------------------------------------------------------------------

def compute_entity_scores(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Requires `contrato_score` to already exist (run `compute_contract_scores`
    first) -- the contract component of an entity's score is the
    value-weighted mean of its own contracts' `contrato_score.score`.
    """
    t0 = time.time()
    cw = total_weight("contract")
    ew = total_weight("entity")

    contract_agg: dict[str, dict] = {}
    for nit, valor, score in con.execute("""
        SELECT nit_entidad_norm, valor_contrato, score
        FROM contrato_score
        WHERE nit_entidad_norm IS NOT NULL AND nit_entidad_norm != '' AND score IS NOT NULL
    """).fetchall():
        d = contract_agg.setdefault(nit, {"vsum": 0.0, "vwsum": 0.0, "ssum": 0.0, "n": 0})
        v = valor or 0.0
        d["vsum"] += v
        d["vwsum"] += v * score
        d["ssum"] += score
        d["n"] += 1

    flag_agg = _fetch_flag_agg(con, "flag_entidad", "nit_entidad_norm", "entity")
    fired_evidence = _fetch_fired_evidence(con, "flag_entidad", "nit_entidad_norm")

    dim_rows = con.execute("""
        SELECT nit_entidad_norm, nombre_entidad, cod_dpto, cod_mpio, n_contratos, valor_total
        FROM dim_entidad
    """).fetchall()

    entities: list[dict] = []
    for nit, nombre, cod_dpto, cod_mpio, n_contratos, valor_total in dim_rows:
        ca = contract_agg.get(nit)
        if ca and ca["vsum"] > 0:
            contract_component = ca["vwsum"] / ca["vsum"]
        elif ca and ca["n"] > 0:
            # All of this entity's scored contracts have valor_contrato == 0 -- fall back to a
            # plain (unweighted) mean rather than leaving the entity unscored.
            contract_component = ca["ssum"] / ca["n"]
        else:
            contract_component = None

        fa = flag_agg.get(nit)
        entity_component = (100.0 * fa["peso_disparado"] / fa["peso_aplicable"]) if fa and fa["peso_aplicable"] else None

        entities.append(
            {
                "nit_entidad_norm": nit,
                "nombre_entidad": nombre,
                "cod_dpto": cod_dpto,
                "cod_mpio": cod_mpio,
                "n_contratos": n_contratos,
                "valor_total": valor_total,
                "contract_component": contract_component,
                "entity_component": entity_component,
                "combined_raw_score": combine_components(contract_component, entity_component, cw, ew),
                "n_flags_aplicables": fa["n_flags_aplicables"] if fa else 0,
                "n_flags_disparados": fa["n_flags_disparados"] if fa else 0,
            }
        )

    # Department means (value-weighted over entities' own combined_raw_score), + national fallback
    # for entities whose department is unknown or whose department has no other scored entity.
    dept_acc: dict[str | None, dict] = {}
    nat = {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0}
    for e in entities:
        if e["combined_raw_score"] is None:
            continue
        v = e["valor_total"] or 0.0
        d = dept_acc.setdefault(e["cod_dpto"], {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0})
        for acc in (d, nat):
            acc["vwsum"] += v * e["combined_raw_score"]
            acc["vsum"] += v
            acc["ssum"] += e["combined_raw_score"]
            acc["n"] += 1

    def _mean(acc: dict | None) -> float | None:
        if not acc or acc["n"] == 0:
            return None
        return acc["vwsum"] / acc["vsum"] if acc["vsum"] > 0 else acc["ssum"] / acc["n"]

    national_mean = _mean(nat)

    n_insuf = 0
    for e in entities:
        dept_mean = _mean(dept_acc.get(e["cod_dpto"])) or national_mean
        e["dept_mean_score"] = dept_mean
        e["k_shrinkage"] = SHRINKAGE_K
        e["score"] = shrink(e["combined_raw_score"], dept_mean, e["n_contratos"], SHRINKAGE_K)
        e["tier"] = tier_for(e["score"])
        e["datos_insuficientes"] = e["n_contratos"] < MIN_CONTRATOS_RANK
        e["flags_disparados"] = json.dumps(fired_evidence.get(e["nit_entidad_norm"], []), ensure_ascii=False, default=str)
        if e["datos_insuficientes"]:
            n_insuf += 1

    _write_table(con, "entidad_score", _ENTIDAD_SCORE_DDL, _rows_to_columns(entities, _ENTIDAD_SCORE_COLUMNS))

    return {
        "n_entidades": len(entities),
        "n_datos_insuficientes": n_insuf,
        "seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Municipio-level scoring
# ---------------------------------------------------------------------------

def compute_municipio_scores(con: duckdb.DuckDBPyConnection) -> dict:
    """Requires `contrato_score` to already exist. Grain: (cod_dpto, cod_mpio)."""
    t0 = time.time()

    rows = con.execute("""
        SELECT cod_dpto, cod_mpio, valor_contrato, score
        FROM contrato_score
        WHERE cod_dpto IS NOT NULL AND cod_mpio IS NOT NULL AND score IS NOT NULL
    """).fetchall()

    muni_acc: dict[tuple[str, str], dict] = {}
    dept_acc: dict[str, dict] = {}
    nat = {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0}
    for cod_dpto, cod_mpio, valor, score in rows:
        v = valor or 0.0
        m = muni_acc.setdefault((cod_dpto, cod_mpio), {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0})
        d = dept_acc.setdefault(cod_dpto, {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0})
        for acc in (m, d, nat):
            acc["vwsum"] += v * score
            acc["vsum"] += v
            acc["ssum"] += score
            acc["n"] += 1

    def _mean(acc: dict | None) -> float | None:
        if not acc or acc["n"] == 0:
            return None
        return acc["vwsum"] / acc["vsum"] if acc["vsum"] > 0 else acc["ssum"] / acc["n"]

    national_mean = _mean(nat)

    dpto_name_by_cod = dict(con.execute("SELECT DISTINCT cod_dpto, dpto FROM divipola").fetchall())
    muni_name: dict[tuple[str, str], str] = {}
    for cod_dpto, cod_mpio, nombre in con.execute("SELECT DISTINCT cod_dpto, cod_mpio, municipio FROM divipola").fetchall():
        muni_name[(cod_dpto, cod_mpio)] = nombre

    result: list[dict] = []
    n_insuf = 0
    for (cod_dpto, cod_mpio), m in muni_acc.items():
        raw_score = _mean(m)
        dept_mean = _mean(dept_acc.get(cod_dpto)) or national_mean
        n = m["n"]
        score = shrink(raw_score, dept_mean, n, SHRINKAGE_K)
        datos_insuficientes = n < MIN_CONTRATOS_RANK
        if datos_insuficientes:
            n_insuf += 1
        result.append(
            {
                "cod_dpto": cod_dpto,
                "cod_mpio": cod_mpio,
                "dpto": dpto_name_by_cod.get(cod_dpto),
                "municipio": muni_name.get((cod_dpto, cod_mpio)),
                "n_contratos": n,
                "valor_total": m["vsum"],
                "raw_score": raw_score,
                "dept_mean_score": dept_mean,
                "k_shrinkage": SHRINKAGE_K,
                "score": score,
                "tier": tier_for(score),
                "datos_insuficientes": datos_insuficientes,
            }
        )

    _write_table(con, "municipio_score", _MUNICIPIO_SCORE_DDL, _rows_to_columns(result, _MUNICIPIO_SCORE_COLUMNS))

    return {
        "n_municipios": len(result),
        "n_datos_insuficientes": n_insuf,
        "seconds": round(time.time() - t0, 2),
    }


# ---------------------------------------------------------------------------
# Orchestration + CLI
# ---------------------------------------------------------------------------

def run(con: duckdb.DuckDBPyConnection) -> dict:
    """Run all three scoring stages against `con`. Order matters: contrato_score first."""
    log.info("Scoring contracts (contrato_score)...")
    contrato_summary = compute_contract_scores(con)
    log.info("  %s", contrato_summary)

    log.info("Scoring entities (entidad_score)...")
    entidad_summary = compute_entity_scores(con)
    log.info("  %s", entidad_summary)

    log.info("Scoring municipios (municipio_score)...")
    municipio_summary = compute_municipio_scores(con)
    log.info("  %s", municipio_summary)

    return {"contrato": contrato_summary, "entidad": entidad_summary, "municipio": municipio_summary}


def print_report(con: duckdb.DuckDBPyConnection) -> None:
    print()
    print("=== contrato_score ===")
    total, n_null = con.execute("SELECT COUNT(*), SUM((score IS NULL)::INT) FROM contrato_score").fetchone()
    print(f"Total contratos: {total}  |  score NULL (0 flags aplicables): {n_null}")
    for tier, c in con.execute("""
        SELECT tier, COUNT(*) FROM contrato_score GROUP BY 1 ORDER BY
            CASE tier WHEN 'critico' THEN 0 WHEN 'alto' THEN 1 WHEN 'medio' THEN 2 WHEN 'bajo' THEN 3 ELSE 4 END
    """).fetchall():
        print(f"  tier={(tier or 'NULL'):10s} n={c}")
    p = con.execute("""
        SELECT approx_quantile(score,0.10), approx_quantile(score,0.25), approx_quantile(score,0.50),
               approx_quantile(score,0.75), approx_quantile(score,0.90), approx_quantile(score,0.95),
               approx_quantile(score,0.99), min(score), max(score), avg(score)
        FROM contrato_score WHERE score IS NOT NULL
    """).fetchone()
    print(f"  p10={p[0]:.2f} p25={p[1]:.2f} p50={p[2]:.2f} p75={p[3]:.2f} p90={p[4]:.2f} "
          f"p95={p[5]:.2f} p99={p[6]:.2f} min={p[7]:.2f} max={p[8]:.2f} mean={p[9]:.2f}")

    print()
    print("=== entidad_score ===")
    total_e, n_insuf_e = con.execute("SELECT COUNT(*), SUM(datos_insuficientes::INT) FROM entidad_score").fetchone()
    print(f"Total entidades: {total_e}  |  datos_insuficientes (<{MIN_CONTRATOS_RANK} contratos): {n_insuf_e}")
    for tier, c in con.execute("""
        SELECT tier, COUNT(*) FROM entidad_score GROUP BY 1 ORDER BY
            CASE tier WHEN 'critico' THEN 0 WHEN 'alto' THEN 1 WHEN 'medio' THEN 2 WHEN 'bajo' THEN 3 ELSE 4 END
    """).fetchall():
        print(f"  tier={(tier or 'NULL'):10s} n={c}")

    print()
    print("=== municipio_score ===")
    total_m, n_insuf_m = con.execute("SELECT COUNT(*), SUM(datos_insuficientes::INT) FROM municipio_score").fetchone()
    print(f"Total municipios: {total_m}  |  datos_insuficientes (<{MIN_CONTRATOS_RANK} contratos): {n_insuf_m}")
    for tier, c in con.execute("""
        SELECT tier, COUNT(*) FROM municipio_score GROUP BY 1 ORDER BY
            CASE tier WHEN 'critico' THEN 0 WHEN 'alto' THEN 1 WHEN 'medio' THEN 2 WHEN 'bajo' THEN 3 ELSE 4 END
    """).fetchall():
        print(f"  tier={(tier or 'NULL'):10s} n={c}")
    print()


def main() -> None:
    db_path = MARTS_DIR / "corruption.duckdb"
    log.info("Connecting to %s", db_path)
    con = duckdb.connect(str(db_path))
    try:
        run(con)
        print_report(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
