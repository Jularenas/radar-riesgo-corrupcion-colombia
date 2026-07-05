"""
M5 backtest: validates `contrato_score` against already-identified corruption
cases. Labels are used for VALIDATION ONLY, never to fit `weights.yaml`
(PLAN.md "Risks & mitigations" -- label bias, only caught cases are labeled).

Three validation sources, per PLAN.md:

  - L1-L4 (`sanciones`): a contract's supplier or entity gets a positive
    label if `sanciones.fecha_sancion` is AFTER `fct_contrato.fecha_firma`.
    Strictly after (never <=) to avoid leakage -- a sanction dated before or
    on the signing date is context (already captured by F11), not an
    outcome the score should be "predicting". Used for ROC-AUC,
    precision@k, lift@top-decile.
  - V2 (`refs/known_cases.yaml`): curated landmark cases, matched to
    contrato_score via normalized (accent/case-insensitive) entity-name LIKE
    patterns AND the case's period (inclusive year range) -- see
    `match_landmark_case`. Reports each case's matched contract(s), score,
    tier, and percentile rank among all scored contracts signed the same
    year.
  - V1 (`monitor_ciudadano_hechos`): best-effort dept+municipio+year match
    (no `sector` column survives into the canonical mart, so that dimension
    is dropped -- see `match_monitor_ciudadano`). As of this run the source
    table's departamento/municipio/anio fields are empty/NULL for 100% of
    its rows (a pre-existing M1/M2 extraction bug, documented in
    `match_monitor_ciudadano` and in docs/METHODOLOGY.md); the matching
    logic is implemented and ready but cannot produce real matches until
    that upstream bug is fixed.

Usage:
    uv run python -m pipeline.score.backtest

PLAN.md targets: AUC > 0.60, lift@10% > 1.5, landmark cases in top quartile.
Exactly one documented weight-iteration is allowed if a first run misses a
target (see docs/METHODOLOGY.md for whether one was needed here and why).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import yaml

from pipeline.clean.normalize import strip_accents
from pipeline.config import MARTS_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

_REFS_DIR = Path(__file__).resolve().parent.parent / "refs"
_KNOWN_CASES_PATH = _REFS_DIR / "known_cases.yaml"

TARGET_AUC_MIN = 0.60
TARGET_LIFT_MIN = 1.5


# ---------------------------------------------------------------------------
# Contract-level labels + ranking metrics (L1-L4)
# ---------------------------------------------------------------------------

def fetch_contract_labels(con: duckdb.DuckDBPyConnection) -> list[tuple[str, float, bool]]:
    """
    (id_contrato, score, is_positive) for every scored contract with a known
    signing date. `is_positive` = supplier OR entity has a `sanciones` row
    whose `fecha_sancion` is strictly AFTER this contract's `fecha_firma`
    (leakage guard: `>`, never `>=` or `<`).
    """
    sql = """
        WITH doc_max AS (
            SELECT doc_norm, MAX(fecha_sancion) AS max_fecha_sancion
            FROM sanciones
            GROUP BY 1
        )
        SELECT
            cs.id_contrato,
            cs.score,
            (
                (dm_sup.max_fecha_sancion IS NOT NULL AND dm_sup.max_fecha_sancion > cs.fecha_firma)
                OR (dm_ent.max_fecha_sancion IS NOT NULL AND dm_ent.max_fecha_sancion > cs.fecha_firma)
            ) AS is_positive
        FROM contrato_score cs
        LEFT JOIN doc_max dm_sup ON dm_sup.doc_norm = cs.doc_proveedor_norm
        LEFT JOIN doc_max dm_ent ON dm_ent.doc_norm = cs.nit_entidad_norm
        WHERE cs.score IS NOT NULL AND cs.fecha_firma IS NOT NULL
    """
    return [(r[0], r[1], bool(r[2])) for r in con.execute(sql).fetchall()]


def compute_auc(scores: list[float], labels: list[bool]) -> dict[str, Any]:
    """
    ROC-AUC via the Mann-Whitney U / rank-sum statistic, with ties resolved
    by average rank. Implemented from scratch (no numpy/sklearn in this
    project) but numerically equivalent to sklearn.metrics.roc_auc_score.

        U   = sum(ranks of positives) - n_pos*(n_pos+1)/2
        AUC = U / (n_pos * n_neg)
    """
    n = len(scores)
    if n != len(labels):
        raise ValueError("scores and labels must be the same length")

    order = sorted(range(n), key=lambda i: scores[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-based average rank shared by the tie block order[i..j]
        for t in range(i, j + 1):
            ranks[order[t]] = avg_rank
        i = j + 1

    n_pos = sum(1 for lab in labels if lab)
    n_neg = n - n_pos
    if n_pos == 0 or n_neg == 0:
        return {
            "auc": None, "n": n, "n_pos": n_pos, "n_neg": n_neg,
            "note": "AUC indefinido: se requiere al menos un positivo y un negativo",
        }

    sum_ranks_pos = sum(r for r, lab in zip(ranks, labels, strict=True) if lab)
    u = sum_ranks_pos - n_pos * (n_pos + 1) / 2
    auc = u / (n_pos * n_neg)
    return {"auc": auc, "n": n, "n_pos": n_pos, "n_neg": n_neg}


def precision_at_k(labels_sorted_desc: list[bool], k: int) -> float | None:
    """Fraction of positives among the top `k` (by score, descending). None if k<=0 or empty input."""
    if k <= 0 or not labels_sorted_desc:
        return None
    top = labels_sorted_desc[:k]
    return sum(top) / len(top)


def lift_at_top_decile(labels_sorted_desc: list[bool]) -> dict[str, Any]:
    """lift = precision@top-10% / overall positive rate. >1 means the top decile concentrates positives."""
    n = len(labels_sorted_desc)
    if n == 0:
        return {"k": 0, "top_rate": None, "overall_rate": None, "lift": None}
    k = max(1, round(n * 0.10))
    overall_rate = sum(labels_sorted_desc) / n
    top_rate = precision_at_k(labels_sorted_desc, k)
    lift = (top_rate / overall_rate) if overall_rate else None
    return {"k": k, "top_rate": top_rate, "overall_rate": overall_rate, "lift": lift}


def run_ranking_metrics(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    rows = fetch_contract_labels(con)
    scores = [r[1] for r in rows]
    labels = [r[2] for r in rows]

    auc_result = compute_auc(scores, labels)

    order_desc = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)
    labels_sorted = [labels[i] for i in order_desc]

    precision_at_fixed_k = {k: precision_at_k(labels_sorted, k) for k in (50, 100, 500) if k <= len(labels_sorted)}
    precision_at_pct = {}
    for pct in (0.01, 0.05, 0.10):
        k = max(1, round(len(labels_sorted) * pct))
        precision_at_pct[f"top_{pct:.0%}"] = {"k": k, "precision": precision_at_k(labels_sorted, k)}
    lift = lift_at_top_decile(labels_sorted)

    return {
        "n_contratos_evaluados": len(rows),
        "n_positivos": auc_result["n_pos"],
        "auc": auc_result,
        "precision_at_k": precision_at_fixed_k,
        "precision_at_pct": precision_at_pct,
        "lift_top_decile": lift,
    }


# ---------------------------------------------------------------------------
# V2: curated landmark cases (refs/known_cases.yaml)
# ---------------------------------------------------------------------------

def load_known_cases(path: Path = _KNOWN_CASES_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _norm_name_sql(col: str) -> str:
    """
    Upper-case + accent-strip + punctuation-strip a name column, mirroring
    clean/build.py's own department-name normalization exactly (same
    translate/regexp_replace pattern) so this module doesn't invent a
    second normalization convention.
    """
    return (
        f"upper(regexp_replace(translate(trim(COALESCE({col}, '')), "
        "'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'), '[^A-Za-z0-9 ,.]', '', 'g'))"
    )


def match_landmark_case(con: duckdb.DuckDBPyConnection, case: dict, ignore_period: bool = False) -> list[dict]:
    """
    Match one known_cases.yaml entry to contrato_score rows via normalized
    entity-name LIKE patterns (`hint_entidad_like`, already upper/unaccented
    with '%' wildcards in the YAML) AND the case's period (inclusive `anio`
    range) -- per the M5 brief: "match ... via entity/supplier name LIKE
    patterns (case-insensitive, accent-insensitive) and period".

    The period filter is not just a data restriction: some entity hints are
    deliberately broad (e.g. "%IDU%" for Bogota's Instituto de Desarrollo
    Urbano) and can coincidentally substring-match unrelated entities in the
    full national mart (e.g. a school named "...Fontidueno..."); requiring
    the row to also fall in the case's historical period reliably excludes
    those false positives because they only ever appear in the 2023 SECOP II
    sample, never inside any pre-2020 landmark case's window.

    Supplier-name hints (`proveedores[].nombre`), when the case names one,
    are checked too and surfaced per-row as `coincide_proveedor` -- but do
    NOT gate inclusion, both because several cases name no supplier at all
    and because the entity+period combination is already precise (see
    above). `ignore_period=True` drops the period filter, used only to
    produce an honest diagnostic ("0 matches" vs "0 matches in this period,
    N in other years") for cases with zero matches.

    A second, stricter signal is also computed per row: `coincide_nombre_exacto`
    -- whether the row's entity name contains one of the case's *exact*
    official names (`entidades[].nombre`), not just a broad hint substring.
    This matters because some hints are intentionally generic (e.g. "%IDU%",
    "%GESTION DEL RIESGO DE DESASTRES%") to tolerate spelling variants, and
    on the full national mart that genericity can match a same-worded but
    different real entity (observed live: "%GESTION DEL RIESGO DE
    DESASTRES%" also matches unrelated departmental disaster-risk offices
    in Cundinamarca/Valle del Cauca/Casanare that are not UNGRD, the
    national entity the ungrd-carrotanques case is actually about, and
    which never appears in this sample). The period filter alone does not
    catch this when the false-positive entity happens to also have
    contracts inside the case's period. `summarize_case` uses this signal
    to avoid reporting a generic same-wording match as if it confirmed the
    case.
    """
    entidad_patterns = case.get("hint_entidad_like") or []
    if not entidad_patterns:
        return []
    periodo = case["periodo"]

    proveedor_names = [p["nombre"] for p in (case.get("proveedores") or []) if p.get("nombre")]
    proveedor_patterns = [f"%{strip_accents(n).upper()}%" for n in proveedor_names]
    exact_entidad_names = [
        e["nombre"] for e in (case.get("entidades") or []) if e.get("nombre")
    ]
    exact_entidad_patterns = [f"%{strip_accents(n).upper()}%" for n in exact_entidad_names]

    entidad_sql = _norm_name_sql("nombre_entidad")
    proveedor_sql = _norm_name_sql("nombre_proveedor")

    params: list[Any] = []
    if proveedor_patterns:
        proveedor_cond = " OR ".join([f"{proveedor_sql} LIKE ?"] * len(proveedor_patterns))
        select_extra = f"({proveedor_cond}) AS coincide_proveedor, "
        params.extend(proveedor_patterns)
    else:
        select_extra = "CAST(NULL AS BOOLEAN) AS coincide_proveedor, "

    if exact_entidad_patterns:
        exact_cond = " OR ".join([f"{entidad_sql} LIKE ?"] * len(exact_entidad_patterns))
        select_extra += f"({exact_cond}) AS coincide_nombre_exacto"
        params.extend(exact_entidad_patterns)
    else:
        select_extra += "CAST(NULL AS BOOLEAN) AS coincide_nombre_exacto"

    entidad_cond = " OR ".join([f"{entidad_sql} LIKE ?"] * len(entidad_patterns))
    params.extend(entidad_patterns)

    where_period = ""
    if not ignore_period:
        where_period = " AND anio BETWEEN ? AND ?"
        params.extend([periodo[0], periodo[1]])

    sql = f"""
        SELECT id_contrato, nombre_entidad, nombre_proveedor, anio, valor_contrato,
               score, tier, urlproceso, {select_extra}
        FROM contrato_score
        WHERE ({entidad_cond}){where_period}
        ORDER BY score DESC NULLS LAST
    """
    cur = con.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def fetch_year_percentiles(con: duckdb.DuckDBPyConnection) -> dict[str, float]:
    """
    {id_contrato: percentile [0,1]} within its OWN signing year -- PLAN.md
    asks for landmark cases' "percentile rank among all scored contracts
    that year", not against the whole multi-year mart (which would mix the
    randomly-sampled 2023 SECOP II population with deliberately-targeted,
    non-representative SECOP I landmark-case slices from other years -- see
    docs/METHODOLOGY.md limitations).
    """
    sql = """
        SELECT id_contrato, PERCENT_RANK() OVER (PARTITION BY anio ORDER BY score) AS pct
        FROM contrato_score
        WHERE score IS NOT NULL AND anio IS NOT NULL
    """
    return {r[0]: r[1] for r in con.execute(sql).fetchall()}


def summarize_case(con: duckdb.DuckDBPyConnection, case: dict, year_pct: dict[str, float]) -> dict[str, Any]:
    matches = match_landmark_case(con, case)
    for m in matches:
        m["percentil_anio"] = year_pct.get(m["id_contrato"])
    matches.sort(key=lambda m: (m["score"] if m["score"] is not None else -1.0), reverse=True)

    if matches:
        best = matches[0]
        top_quartile_reached = any((m["percentil_anio"] or 0.0) >= 0.75 for m in matches)
    else:
        best = None
        top_quartile_reached = None

    # Diagnostic only (see match_landmark_case docstring): counts how many of
    # `matches` also contain one of the case's *exact* official entity
    # names, vs. matching only the broader hint. Deliberately NOT used to
    # filter `matches`/`n_matched` -- the exact-name check has false
    # negatives of its own (e.g. the IDU Bogota slice stores the entity as
    # the abbreviation "BOGOTA DC IDU", which does not contain the full
    # official name "INSTITUTO DE DESARROLLO URBANO"), so gating on it would
    # trade one class of error for another. A human reviewer inspecting
    # `matches[].nombre_entidad` (and docs/METHODOLOGY.md's discussion of
    # this specific known case) is more reliable than a second heuristic.
    n_confirmed_exact_name = sum(1 for m in matches if m.get("coincide_nombre_exacto"))

    result: dict[str, Any] = {
        "slug": case["slug"],
        "nombre": case["nombre"],
        "periodo": case["periodo"],
        "secop1": case.get("secop1"),
        "n_matched": len(matches),
        "n_confirmed_exact_name": n_confirmed_exact_name,
        "matches": matches,
        "best_score": best["score"] if best else None,
        "best_tier": best["tier"] if best else None,
        "best_percentil_anio": best["percentil_anio"] if best else None,
        "top_quartile_reached": top_quartile_reached,
    }
    if not matches:
        result["n_matched_ignoring_period"] = len(match_landmark_case(con, case, ignore_period=True))
    return result


def run_landmark_cases(con: duckdb.DuckDBPyConnection) -> list[dict]:
    year_pct = fetch_year_percentiles(con)
    return [summarize_case(con, case, year_pct) for case in load_known_cases()]


# ---------------------------------------------------------------------------
# V1: Monitor Ciudadano (coarse dept+municipio+year matching)
# ---------------------------------------------------------------------------

def match_monitor_ciudadano(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """
    Best-effort match: normalize monitor_ciudadano_hechos.departamento/
    municipio the same way `divipola` is normalized, recover (cod_dpto,
    cod_mpio), then check whether contrato_score has any contract in that
    same municipio and year. `sector` is dropped: it does not survive M2's
    canonical `fct_contrato` schema, so it cannot be joined.

    Documents (rather than hides) an upstream data problem: as of this
    mart, monitor_ciudadano_hechos has departamento/municipio empty and
    anio NULL for 100% of its 1245 rows (the real xlsx header row was
    misread as a title banner during M1/M2 extraction -- see
    `pipeline.clean.build._build_monitor_hechos`). That is a pre-existing
    bug outside M5's scope (M5 does not rebuild marts); flagged separately.
    Real matching still runs whenever usable rows exist, so this becomes
    live the moment that upstream bug is fixed.
    """
    n_total = con.execute("SELECT COUNT(*) FROM monitor_ciudadano_hechos").fetchone()[0]
    if n_total == 0:
        return {
            "n_total": 0, "n_usable_join_keys": 0, "n_matched": 0, "match_rate_pct": None,
            "note": "monitor_ciudadano_hechos esta vacia (0 filas) en el mart actual.",
        }

    n_usable = con.execute("""
        SELECT COUNT(*) FROM monitor_ciudadano_hechos
        WHERE COALESCE(departamento, '') != '' AND COALESCE(municipio, '') != '' AND anio IS NOT NULL
    """).fetchone()[0]

    if n_usable == 0:
        return {
            "n_total": n_total,
            "n_usable_join_keys": 0,
            "n_matched": 0,
            "match_rate_pct": 0.0,
            "note": (
                f"Las {n_total} filas de monitor_ciudadano_hechos tienen departamento/municipio/anio "
                "vacios o nulos en el 100% de los casos -- no es un limite del metodo de match, es un "
                "bug de extraccion preexistente (M1/M2), fuera del alcance de M5: "
                "_build_monitor_hechos() en pipeline/src/pipeline/clean/build.py lee la fila 0 del "
                "xlsx 'Base_de_datos_hechos_2016_2022.xlsx' como fila de encabezados, pero esa fila "
                "es en realidad el titulo del reporte (banner); el encabezado real esta en la fila "
                "(0-indexada) 16 de la hoja 'Hechos'. Reportado por separado para su correccion; la "
                "logica de match de abajo esta lista para ejecutarse en cuanto se corrija la "
                "extraccion -- no se fuerzan coincidencias debiles para compensar."
            ),
        }

    sql = f"""
        WITH mc_norm AS (
            SELECT
                anio,
                {_norm_name_sql("departamento")} AS dpto_norm,
                {_norm_name_sql("municipio")} AS mpio_norm
            FROM monitor_ciudadano_hechos
            WHERE COALESCE(departamento, '') != '' AND COALESCE(municipio, '') != '' AND anio IS NOT NULL
        ),
        mc_geo AS (
            SELECT mc.anio, d.cod_dpto, d.cod_mpio
            FROM mc_norm mc
            JOIN (SELECT DISTINCT dpto_norm, mpio_norm, cod_dpto, cod_mpio FROM divipola) d
                ON d.dpto_norm = mc.dpto_norm AND d.mpio_norm = mc.mpio_norm
        )
        SELECT
            COUNT(*) AS n_geo_matched,
            COALESCE(SUM((EXISTS (
                SELECT 1 FROM contrato_score cs
                WHERE cs.cod_dpto = mc_geo.cod_dpto AND cs.cod_mpio = mc_geo.cod_mpio AND cs.anio = mc_geo.anio
            ))::INT), 0) AS n_contract_matched
        FROM mc_geo
    """
    n_geo_matched, n_contract_matched = con.execute(sql).fetchone()
    return {
        "n_total": n_total,
        "n_usable_join_keys": n_usable,
        "n_geo_matched": n_geo_matched,
        "n_matched": n_contract_matched,
        "match_rate_pct": round(100.0 * n_contract_matched / n_total, 2),
        "note": (
            "Match grueso por departamento+municipio+anio (sin 'sector': esa columna no sobrevive "
            "al esquema canonico de fct_contrato). Un match confirma solo que la misma "
            "geografia/anio tiene contratos en la muestra, no que sean el mismo hecho."
        ),
    }


# ---------------------------------------------------------------------------
# Target check + orchestration
# ---------------------------------------------------------------------------

def check_targets(metrics: dict, landmark_summaries: list[dict]) -> dict[str, Any]:
    auc = metrics["auc"]["auc"]
    lift = metrics["lift_top_decile"]["lift"]
    auc_ok = auc is not None and auc > TARGET_AUC_MIN
    lift_ok = lift is not None and lift > TARGET_LIFT_MIN

    cases_with_data = [c for c in landmark_summaries if c["n_matched"] > 0]
    cases_top_quartile = [c for c in cases_with_data if c["top_quartile_reached"]]
    landmark_ok = len(cases_with_data) > 0 and len(cases_top_quartile) == len(cases_with_data)

    return {
        "auc_ok": auc_ok,
        "lift_ok": lift_ok,
        "landmark_ok": landmark_ok,
        "all_targets_met": auc_ok and lift_ok and landmark_ok,
        "n_landmark_cases_with_data": len(cases_with_data),
        "n_landmark_cases_top_quartile": len(cases_top_quartile),
        "n_landmark_cases_total": len(landmark_summaries),
    }


def run(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    log.info("Computing ranking metrics (AUC / precision@k / lift@decile) vs L1-L4 labels...")
    metrics = run_ranking_metrics(con)
    log.info("  AUC=%s  lift@10%%=%s", metrics["auc"].get("auc"), metrics["lift_top_decile"].get("lift"))

    log.info("Matching V2 landmark cases (refs/known_cases.yaml)...")
    landmark_summaries = run_landmark_cases(con)
    log.info("  %d cases, %d with >=1 matched contract", len(landmark_summaries), sum(1 for c in landmark_summaries if c["n_matched"] > 0))

    log.info("Matching V1 Monitor Ciudadano (best-effort)...")
    monitor = match_monitor_ciudadano(con)
    log.info("  %s", {k: v for k, v in monitor.items() if k != "note"})

    targets = check_targets(metrics, landmark_summaries)
    return {"metrics": metrics, "landmark_cases": landmark_summaries, "monitor_ciudadano": monitor, "targets": targets}


def print_report(result: dict[str, Any]) -> None:
    m = result["metrics"]
    print()
    print("=== Metricas de ranking (L1-L4: sancion posterior a la firma) ===")
    print(f"n contratos evaluados: {m['n_contratos_evaluados']}  |  n positivos: {m['n_positivos']}")
    auc = m["auc"]
    if auc["auc"] is not None:
        print(f"AUC-ROC: {auc['auc']:.4f}  (target > {TARGET_AUC_MIN})")
    else:
        print(f"AUC-ROC: indefinido ({auc.get('note')})")
    for label, p in m["precision_at_pct"].items():
        print(f"  precision@{label} (k={p['k']}): {p['precision']}")
    lift = m["lift_top_decile"]
    print(f"Lift@top-decil (k={lift['k']}): {lift['lift']}  (target > {TARGET_LIFT_MIN})"
          if lift["lift"] is not None else "Lift@top-decil: indefinido")

    print()
    print("=== Casos emblematicos (V2, known_cases.yaml) ===")
    for c in result["landmark_cases"]:
        print(f"- {c['nombre']} [{c['periodo'][0]}-{c['periodo'][1]}]: {c['n_matched']} contrato(s) coincidente(s)")
        if c["n_matched"] == 0:
            extra = c.get("n_matched_ignoring_period", 0)
            note = (
                f" ({extra} coincidencia(s) de entidad fuera del periodo del caso)"
                if extra else " (sin coincidencias de entidad en ningun anio)"
            )
            print(f"    sin datos en la muestra actual{note}")
        else:
            print(f"    mejor score={c['best_score']:.2f} tier={c['best_tier']} percentil_anio={c['best_percentil_anio']:.3f} "
                  f"top_quartile={c['top_quartile_reached']}  (nombre_exacto_confirmado={c['n_confirmed_exact_name']}/{c['n_matched']})")

    print()
    print("=== Monitor Ciudadano (V1) ===")
    mc = result["monitor_ciudadano"]
    print(f"n_total={mc['n_total']}  n_usable_join_keys={mc.get('n_usable_join_keys')}  "
          f"n_matched={mc['n_matched']}  match_rate={mc['match_rate_pct']}%")
    print(f"  {mc['note']}")

    print()
    print("=== Cumplimiento de objetivos (PLAN.md) ===")
    t = result["targets"]
    print(f"AUC > {TARGET_AUC_MIN}: {'OK' if t['auc_ok'] else 'NO'}")
    print(f"Lift@10% > {TARGET_LIFT_MIN}: {'OK' if t['lift_ok'] else 'NO'}")
    print(f"Casos emblematicos en cuartil superior: {'OK' if t['landmark_ok'] else 'NO'} "
          f"({t['n_landmark_cases_top_quartile']}/{t['n_landmark_cases_with_data']} con datos, "
          f"{t['n_landmark_cases_total']} casos en total)")
    print(f"Todos los objetivos cumplidos: {t['all_targets_met']}")
    print()


def main() -> None:
    db_path = MARTS_DIR / "corruption.duckdb"
    log.info("Connecting to %s", db_path)
    con = duckdb.connect(str(db_path))
    try:
        result = run(con)
    finally:
        con.close()
    print_report(result)


if __name__ == "__main__":
    main()
