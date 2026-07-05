"""
M6 web-artifact export: reads `corruption.duckdb`, writes the JSON artifacts
described in PLAN.md's "Web artifact contract" (meta.json, resumen_nacional,
departamentos/*, casos_prioritarios/*, entidades_top, proveedores_top).

Usage:
    uv run python -m pipeline.export.build_artifacts [--db PATH] [--out DIR] [--no-validate]

Design note: every `build_*` function below is a pure function of a duckdb
connection (`con`) -- it reads, computes, and returns plain dicts/lists, with
NO file I/O of its own. All writing, schema validation, and size-budget
enforcement happens in `run()`. This is deliberate: `build_fixtures.py` calls
this module's `run()` directly against a small synthetic in-memory mart
instead of duplicating the artifact-shaping logic, so the fixtures shipped to
the frontend are guaranteed to match the real artifact shape exactly (same
code, different data).
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

import duckdb

from pipeline.config import MARTS_DIR, WEB_PUBLIC_DATA_DIR
from pipeline.export.common import (
    FLAG_DESCRIPTIONS,
    chunk_list,
    git_short_hash,
    load_banderas,
    pad_dpto,
    pad_mpio,
    utc_now_iso,
    write_json,
)
from pipeline.export.validate import validate_artifact, validate_many
from pipeline.flags.params import FLAG_META
from pipeline.score import backtest as backtest_mod
from pipeline.score.scorer import shrink
from pipeline.score.weights import MIN_CONTRATOS_RANK, SHRINKAGE_K, TIERS, tier_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (also echoed into meta.json's "artefactos" block -- see build_meta)
# ---------------------------------------------------------------------------

TOP_N_CASOS_PRIORITARIOS = 2500
CHUNK_SIZE_CASOS_PRIORITARIOS = 500
TOP_N_ENTIDADES = 300
TOP_N_PROVEEDORES = 300
TOP_N_ENTIDADES_POR_DEPARTAMENTO = 50

MAX_TOTAL_BYTES = 60 * 1024 * 1024  # 60 MB, PLAN.md "Web artifact contract"
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB per lazy-loaded file, PLAN.md id.

# Landmark cases confirmed, by manual review, to be FALSE POSITIVES of the
# automated name+period matching in pipeline.score.backtest.match_landmark_case
# -- see docs/METHODOLOGY.md 5.3 ("Nota critica sobre UNGRD"): the 195 matched
# rows for "ungrd-carrotanques" are three unrelated *departmental* disaster-risk
# offices, not the national UNGRD entity (which never appears in this sample).
# Excluded here from the "casos emblematicos" validation counts so the
# dashboard doesn't present a documented false positive as a successful
# validation. This is the one piece of the backtest summary that requires
# human judgment and can't be re-derived mechanically -- every other number in
# `_build_backtest_summary` comes straight from a fresh `backtest.run()` call.
LANDMARK_CASE_FALSE_POSITIVES = {"ungrd-carrotanques"}

# Mirrors scorer.py's `_contrato_dedup` temp table exactly (same ORDER BY), so
# any raw fct_contrato column pulled here (e.g. modalidad_norm, which isn't
# denormalized onto contrato_score) always resolves to the SAME canonical
# physical row scorer.py used to build contrato_score -- see that module's
# docstring for why fct_contrato.id_contrato is not perfectly unique.
_CONTRATO_DEDUP_SQL = """
    SELECT * EXCLUDE (_rn) FROM (
        SELECT fc.*,
            ROW_NUMBER() OVER (
                PARTITION BY id_contrato
                ORDER BY fecha_firma DESC NULLS LAST, row_id DESC NULLS LAST
            ) AS _rn
        FROM fct_contrato fc
    ) WHERE _rn = 1
"""


class SizeBudgetExceeded(Exception):
    """Raised by `check_size_budget` when the output directory violates PLAN.md's size budget."""


# ---------------------------------------------------------------------------
# meta.json
# ---------------------------------------------------------------------------

def _build_backtest_summary(con: duckdb.DuckDBPyConnection) -> dict:
    """
    Runs `pipeline.score.backtest.run()` fresh against `con` and reshapes its
    output into the compact block meta.json exposes to the Metodologia page.
    Reusing the real backtest module (instead of hand-transcribing numbers
    from docs/METHODOLOGY.md) means this can never silently drift from
    whatever the mart currently scores -- the one exception is the manual
    false-positive exclusion documented at `LANDMARK_CASE_FALSE_POSITIVES`.
    """
    result = backtest_mod.run(con)
    metrics = result["metrics"]
    auc = metrics["auc"].get("auc")
    lift = metrics["lift_top_decile"].get("lift")
    prec = metrics["precision_at_pct"]

    landmark = result["landmark_cases"]
    genuine = [c for c in landmark if c["n_matched"] > 0 and c["slug"] not in LANDMARK_CASE_FALSE_POSITIVES]
    n_top_quartile = sum(1 for c in genuine if c["top_quartile_reached"])

    casos_emblematicos = [
        {
            "slug": c["slug"],
            "nombre": c["nombre"],
            "periodo": list(c["periodo"]),
            "n_matched": c["n_matched"],
            "mejor_score": c["best_score"],
            "mejor_tier": c["best_tier"],
            "percentil_anio": c["best_percentil_anio"],
            "cuartil_superior": c["top_quartile_reached"],
            "confirmado_manualmente": c["n_matched"] > 0 and c["slug"] not in LANDMARK_CASE_FALSE_POSITIVES,
        }
        for c in landmark
    ]

    mc = result["monitor_ciudadano"]

    if auc is not None and lift is not None:
        resumen = (
            f"AUC-ROC={auc:.4f} y lift@top-decil={lift:.3f} sobre {metrics['n_contratos_evaluados']} "
            f"contratos evaluados ({metrics['n_positivos']} positivos L1-L4) -- por debajo de las metas de "
            f"PLAN.md (AUC>{backtest_mod.TARGET_AUC_MIN}, lift>{backtest_mod.TARGET_LIFT_MIN}). Causa "
            "documentada en docs/METHODOLOGY.md 5.1: en esta muestra de un solo anio, casi todos los "
            "positivos disponibles son contratos SECOP I de un unico caso emblematico, sin los campos de "
            "proceso que activarian la mayoria de las banderas -- no es un problema de calibracion de "
            f"pesos. De los {len(genuine)} casos emblematicos con coincidencias genuinas en la muestra, "
            f"{n_top_quartile} alcanzan el cuartil superior de riesgo de su propio anio."
        )
    else:
        resumen = (
            "AUC/lift indefinidos en esta corrida (no hay suficientes positivos y negativos en la "
            "muestra para calcularlos). Ver docs/METHODOLOGY.md seccion 5."
        )

    return {
        "auc_roc": auc,
        "objetivo_auc_roc": backtest_mod.TARGET_AUC_MIN,
        "lift_top_decil": lift,
        "objetivo_lift_top_decil": backtest_mod.TARGET_LIFT_MIN,
        "cumple_objetivos": bool(result["targets"]["all_targets_met"]),
        "n_contratos_evaluados": metrics["n_contratos_evaluados"],
        "n_positivos_l1_l4": metrics["n_positivos"],
        "precision_top_1pct": prec.get("top_1%", {}).get("precision"),
        "precision_top_5pct": prec.get("top_5%", {}).get("precision"),
        "precision_top_10pct": prec.get("top_10%", {}).get("precision"),
        "casos_emblematicos": casos_emblematicos,
        "n_casos_emblematicos_total": len(landmark),
        "n_casos_emblematicos_con_coincidencias_genuinas": len(genuine),
        "n_casos_emblematicos_en_percentil_superior": n_top_quartile,
        "monitor_ciudadano": {
            "n_total": mc["n_total"],
            "n_matched": mc["n_matched"],
            "match_rate_pct": mc.get("match_rate_pct"),
            "nota": mc["note"],
        },
        "resumen": resumen,
    }


def build_meta(con: duckdb.DuckDBPyConnection, *, n_casos_prioritarios: int, n_chunks: int) -> dict:
    """
    `n_casos_prioritarios`/`n_chunks` are passed in (rather than recomputed
    from the module constants) so meta.json always reflects what `run()`
    actually wrote -- e.g. a fixture mart with far fewer than 2500 scoreable
    contracts produces fewer chunks, and meta.json must say so honestly.
    """
    banderas = [
        {"id": fid, "nombre": meta["nombre"], "nivel": meta["nivel"], "peso": meta["peso"], "descripcion": FLAG_DESCRIPTIONS[fid]}
        for fid, meta in sorted(FLAG_META.items())
    ]
    niveles_riesgo = [{"id": t.id, "nombre": t.nombre, "min_score": t.min_score, "max_score": t.max_score} for t in TIERS]

    return {
        "generado_en": utc_now_iso(),
        "version": {"git_commit": git_short_hash()},
        "banderas": banderas,
        "niveles_riesgo": niveles_riesgo,
        "formula_score": "100 x (suma de pesos de banderas disparadas) / (suma de pesos de banderas aplicables)",
        "shrinkage": {"k": SHRINKAGE_K, "min_contratos_rank": MIN_CONTRATOS_RANK},
        "backtest": _build_backtest_summary(con),
        "artefactos": {
            "casos_prioritarios": {
                "top_n": TOP_N_CASOS_PRIORITARIOS,
                "chunk_size": CHUNK_SIZE_CASOS_PRIORITARIOS,
                "n_chunks": n_chunks,
                "patron_archivo": (
                    "casos_prioritarios/{idx:03d}.json, idx = 000, 001, ... -- indice secuencial de 3 "
                    f"digitos, {CHUNK_SIZE_CASOS_PRIORITARIOS} filas por archivo salvo el ultimo "
                    f"(en esta corrida: {n_casos_prioritarios} contratos en {n_chunks} archivo(s))"
                ),
            },
            "entidades_top": {
                "top_n": TOP_N_ENTIDADES,
                "criterio": (
                    "score desc (shrinkage empirico-bayesiano hacia el departamento, M5); "
                    "empate: valor_total desc, nit_entidad_norm asc"
                ),
            },
            "proveedores_top": {
                "top_n": TOP_N_PROVEEDORES,
                "criterio": (
                    "media de contrato_score.score ponderada por valor, shrunk empirico-bayesianamente "
                    "hacia la media nacional (adaptacion M6 -- M5 no define un proveedor_score dedicado); "
                    "empate: valor_total desc, doc_proveedor_norm asc"
                ),
            },
            "departamentos": {
                "patron_archivo": "departamentos/{cod_dpto}.json, 2 digitos con cero a la izquierda (codigo DIVIPOLA)",
                "top_n_entidades_por_departamento": TOP_N_ENTIDADES_POR_DEPARTAMENTO,
            },
        },
    }


# ---------------------------------------------------------------------------
# resumen_nacional.json
# ---------------------------------------------------------------------------

def build_resumen_nacional(con: duckdb.DuckDBPyConnection) -> dict:
    contratos_analizados, valor_total_cop, casos_criticos, n_sin_dpto = con.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(valor_contrato), 0),
            COUNT(*) FILTER (WHERE tier = 'critico'),
            COUNT(*) FILTER (WHERE cod_dpto IS NULL)
        FROM contrato_score
    """).fetchone()

    n_entidades = con.execute(
        "SELECT COUNT(DISTINCT nit_entidad_norm) FROM contrato_score WHERE nit_entidad_norm IS NOT NULL AND nit_entidad_norm != ''"
    ).fetchone()[0]
    n_proveedores = con.execute(
        "SELECT COUNT(DISTINCT doc_proveedor_norm) FROM contrato_score WHERE doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != ''"
    ).fetchone()[0]

    modalidad_rows = con.execute(f"""
        WITH dedup AS ({_CONTRATO_DEDUP_SQL})
        SELECT cs.anio, dedup.modalidad_norm, COUNT(*), COALESCE(SUM(cs.valor_contrato), 0)
        FROM contrato_score cs
        JOIN dedup ON dedup.id_contrato = cs.id_contrato
        WHERE cs.anio IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 1, 2
    """).fetchall()  # noqa: S608 -- _CONTRATO_DEDUP_SQL is a fixed module constant, no user input
    serie_anio_modalidad = [
        {"anio": anio, "modalidad": modalidad, "n_contratos": n, "valor_total": valor}
        for anio, modalidad, n, valor in modalidad_rows
    ]
    n_directa = sum(r["n_contratos"] for r in serie_anio_modalidad if r["modalidad"] == "CONTRATACION_DIRECTA")

    pct_contratacion_directa = (100.0 * n_directa / contratos_analizados) if contratos_analizados else 0.0
    pct_geolocalizado = (100.0 * (contratos_analizados - n_sin_dpto) / contratos_analizados) if contratos_analizados else 0.0

    dept_rows = con.execute("""
        WITH agg AS (
            SELECT
                cod_dpto,
                COUNT(*) AS n_contratos,
                COALESCE(SUM(valor_contrato), 0) AS valor_total,
                SUM(COALESCE(valor_contrato, 0) * score) FILTER (WHERE score IS NOT NULL) AS vw_sum,
                SUM(COALESCE(valor_contrato, 0)) FILTER (WHERE score IS NOT NULL) AS vw_denom,
                AVG(score) AS simple_avg_score,
                COUNT(*) FILTER (WHERE tier = 'bajo') AS n_bajo,
                COUNT(*) FILTER (WHERE tier = 'medio') AS n_medio,
                COUNT(*) FILTER (WHERE tier = 'alto') AS n_alto,
                COUNT(*) FILTER (WHERE tier = 'critico') AS n_criticos
            FROM contrato_score
            WHERE cod_dpto IS NOT NULL
            GROUP BY cod_dpto
        ),
        depts AS (SELECT DISTINCT cod_dpto, dpto FROM divipola)
        SELECT
            depts.cod_dpto, depts.dpto,
            COALESCE(agg.n_contratos, 0), COALESCE(agg.valor_total, 0),
            CASE WHEN agg.vw_denom > 0 THEN agg.vw_sum / agg.vw_denom ELSE agg.simple_avg_score END,
            COALESCE(agg.n_bajo, 0), COALESCE(agg.n_medio, 0), COALESCE(agg.n_alto, 0), COALESCE(agg.n_criticos, 0)
        FROM depts
        LEFT JOIN agg ON agg.cod_dpto = depts.cod_dpto
        ORDER BY depts.cod_dpto
    """).fetchall()

    departamentos = [
        {
            "cod_dpto": pad_dpto(cod_dpto),
            "dpto": dpto,
            "n_contratos": n_contratos,
            "valor_total": valor_total,
            "score_promedio": score_promedio,
            "n_bajo": n_bajo,
            "n_medio": n_medio,
            "n_alto": n_alto,
            "n_criticos": n_criticos,
        }
        for cod_dpto, dpto, n_contratos, valor_total, score_promedio, n_bajo, n_medio, n_alto, n_criticos in dept_rows
    ]

    return {
        "generado_en": utc_now_iso(),
        "kpis": {
            "contratos_analizados": contratos_analizados,
            "valor_total_cop": valor_total_cop,
            "casos_criticos": casos_criticos,
            "pct_contratacion_directa": pct_contratacion_directa,
            "n_entidades": n_entidades,
            "n_proveedores": n_proveedores,
            "n_contratos_sin_departamento": n_sin_dpto,
            "pct_geolocalizado": pct_geolocalizado,
        },
        "serie_anio_modalidad": serie_anio_modalidad,
        "departamentos": departamentos,
    }


# ---------------------------------------------------------------------------
# Shared row shapers (entidad / municipio) -- reused by build_entidades_top
# and build_departamentos so the two never disagree about field names/order.
# ---------------------------------------------------------------------------

_ENTIDAD_SELECT_COLUMNS = """
    es.nit_entidad_norm, es.nombre_entidad, es.cod_dpto, dv.dpto, es.n_contratos, es.valor_total,
    es.score, es.tier, es.datos_insuficientes, es.n_flags_aplicables, es.n_flags_disparados, es.flags_disparados
"""


def _entidad_row(
    nit, nombre, cod_dpto, dpto, n_contratos, valor_total, score, tier, datos_insuficientes, n_ap, n_di, flags_json
) -> dict:
    return {
        "nit_entidad": nit,
        "nombre_entidad": nombre,
        "cod_dpto": pad_dpto(cod_dpto),
        "dpto": dpto,
        "n_contratos": n_contratos or 0,
        "valor_total": valor_total,
        "score": score,
        "tier": tier,
        "datos_insuficientes": bool(datos_insuficientes),
        "n_flags_aplicables": n_ap or 0,
        "n_flags_disparados": n_di or 0,
        "banderas": load_banderas(flags_json),
    }


def _municipio_row(cod_mpio, municipio, n_contratos, valor_total, score, tier, datos_insuficientes) -> dict:
    return {
        "cod_mpio": pad_mpio(cod_mpio),
        "municipio": municipio,
        "n_contratos": n_contratos or 0,
        "valor_total": valor_total if valor_total is not None else 0.0,
        "score": score,
        "tier": tier,
        "datos_insuficientes": bool(datos_insuficientes),
    }


# ---------------------------------------------------------------------------
# entidades_top.json
# ---------------------------------------------------------------------------

def build_entidades_top(con: duckdb.DuckDBPyConnection, top_n: int = TOP_N_ENTIDADES) -> list[dict]:
    rows = con.execute(f"""
        SELECT {_ENTIDAD_SELECT_COLUMNS}
        FROM entidad_score es
        LEFT JOIN (SELECT DISTINCT cod_dpto, dpto FROM divipola) dv ON dv.cod_dpto = es.cod_dpto
        ORDER BY es.score DESC NULLS LAST, es.valor_total DESC NULLS LAST, es.nit_entidad_norm ASC
        LIMIT {int(top_n)}
    """).fetchall()  # noqa: S608 -- top_n is an int cast from a module constant/CLI int arg, not raw user SQL
    return [_entidad_row(*row) for row in rows]


# ---------------------------------------------------------------------------
# proveedores_top.json
# ---------------------------------------------------------------------------
# M5 does not compute a supplier-level score table (only contrato_score /
# entidad_score / municipio_score) -- PLAN.md's flag catalog defines no
# supplier-level flag either (F04/F12 are entity-level; nothing analogous
# ties a flag directly to doc_proveedor_norm's own key). This is a M6
# addition, deliberately mirroring M5's method as closely as it can:
# value-weighted mean of the supplier's own contrato_score.score, shrunk via
# the *same* empirical-Bayes formula and k -- but toward the NATIONAL mean
# rather than a department mean, since suppliers (unlike entities/municipios)
# aren't geographically bound to one department the way PLAN.md's F04 peer
# grouping assumes. Documented as a deviation in the M6 report.

def build_proveedores_top(con: duckdb.DuckDBPyConnection, top_n: int = TOP_N_PROVEEDORES) -> list[dict]:
    rows = con.execute("""
        SELECT doc_proveedor_norm, valor_contrato, score
        FROM contrato_score
        WHERE doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != '' AND score IS NOT NULL
    """).fetchall()

    acc: dict[str, dict] = {}
    nat = {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0}
    for doc, valor, score in rows:
        v = valor or 0.0
        d = acc.setdefault(doc, {"vwsum": 0.0, "vsum": 0.0, "ssum": 0.0, "n": 0})
        for a in (d, nat):
            a["vwsum"] += v * score
            a["vsum"] += v
            a["ssum"] += score
            a["n"] += 1

    def _mean(a: dict | None) -> float | None:
        if not a or a["n"] == 0:
            return None
        return a["vwsum"] / a["vsum"] if a["vsum"] > 0 else a["ssum"] / a["n"]

    national_mean = _mean(nat)

    dim_rows = con.execute(
        "SELECT doc_proveedor_norm, nombre_proveedor, es_persona_natural, n_contratos, valor_total FROM dim_proveedor"
    ).fetchall()

    out: list[dict] = []
    for doc, nombre, es_persona_natural, n_contratos, valor_total in dim_rows:
        raw = _mean(acc.get(doc))
        if raw is None:
            # No scored contracts for this supplier -- excluded from ranking
            # (same NULL-score convention as contrato_score/entidad_score).
            continue
        n = n_contratos or 0
        score = shrink(raw, national_mean, n, SHRINKAGE_K)
        out.append(
            {
                "doc_proveedor": doc,
                "nombre_proveedor": nombre,
                "es_persona_natural": es_persona_natural,
                "n_contratos": n,
                "valor_total": valor_total,
                "score": score,
                "tier": tier_for(score),
                "datos_insuficientes": n < MIN_CONTRATOS_RANK,
            }
        )

    out.sort(key=lambda r: (-r["score"], -(r["valor_total"] or 0.0), r["doc_proveedor"]))
    return out[:top_n]


# ---------------------------------------------------------------------------
# departamentos/{cod_dpto}.json
# ---------------------------------------------------------------------------

def build_departamentos(con: duckdb.DuckDBPyConnection, top_n_entidades: int = TOP_N_ENTIDADES_POR_DEPARTAMENTO) -> list[dict]:
    """One file per DIVIPOLA department (all 33, including any with zero contracts in this mart)."""
    depts = con.execute("SELECT DISTINCT cod_dpto, dpto FROM divipola ORDER BY cod_dpto").fetchall()

    results: list[dict] = []
    for cod_dpto, dpto in depts:
        n_contratos, valor_total, vw_sum, vw_denom, n_bajo, n_medio, n_alto, n_criticos = con.execute(
            """
            SELECT
                COUNT(*), COALESCE(SUM(valor_contrato), 0),
                SUM(COALESCE(valor_contrato, 0) * score) FILTER (WHERE score IS NOT NULL),
                SUM(COALESCE(valor_contrato, 0)) FILTER (WHERE score IS NOT NULL),
                COUNT(*) FILTER (WHERE tier = 'bajo'), COUNT(*) FILTER (WHERE tier = 'medio'),
                COUNT(*) FILTER (WHERE tier = 'alto'), COUNT(*) FILTER (WHERE tier = 'critico')
            FROM contrato_score WHERE cod_dpto = ?
            """,
            [cod_dpto],
        ).fetchone()
        score_promedio = (vw_sum / vw_denom) if vw_denom else None

        municipio_rows = con.execute(
            """
            SELECT cod_mpio, municipio, n_contratos, valor_total, score, tier, datos_insuficientes
            FROM municipio_score
            WHERE cod_dpto = ?
            ORDER BY score DESC NULLS LAST, valor_total DESC NULLS LAST, cod_mpio ASC
            """,
            [cod_dpto],
        ).fetchall()

        entidad_rows = con.execute(
            f"""
            SELECT {_ENTIDAD_SELECT_COLUMNS}
            FROM entidad_score es
            LEFT JOIN (SELECT DISTINCT cod_dpto, dpto FROM divipola) dv ON dv.cod_dpto = es.cod_dpto
            WHERE es.cod_dpto = ?
            ORDER BY es.score DESC NULLS LAST, es.valor_total DESC NULLS LAST, es.nit_entidad_norm ASC
            LIMIT {int(top_n_entidades)}
            """,  # noqa: S608 -- top_n_entidades is an int, cod_dpto is bound as a parameter
            [cod_dpto],
        ).fetchall()

        serie_rows = con.execute(
            """
            SELECT
                anio, COUNT(*), COALESCE(SUM(valor_contrato), 0),
                SUM(COALESCE(valor_contrato, 0) * score) FILTER (WHERE score IS NOT NULL),
                SUM(COALESCE(valor_contrato, 0)) FILTER (WHERE score IS NOT NULL)
            FROM contrato_score
            WHERE cod_dpto = ? AND anio IS NOT NULL
            GROUP BY anio
            ORDER BY anio
            """,
            [cod_dpto],
        ).fetchall()

        results.append(
            {
                "cod_dpto": pad_dpto(cod_dpto),
                "dpto": dpto,
                "n_contratos": n_contratos,
                "valor_total": valor_total,
                "score_promedio": score_promedio,
                "n_bajo": n_bajo,
                "n_medio": n_medio,
                "n_alto": n_alto,
                "n_criticos": n_criticos,
                "municipios": [_municipio_row(*row) for row in municipio_rows],
                "top_entidades": [_entidad_row(*row) for row in entidad_rows],
                "serie_anio": [
                    {
                        "anio": anio,
                        "n_contratos": n,
                        "valor_total": valor,
                        "score_promedio": (s_sum / s_denom) if s_denom else None,
                    }
                    for anio, n, valor, s_sum, s_denom in serie_rows
                ],
            }
        )

    return results


# ---------------------------------------------------------------------------
# casos_prioritarios/{idx}.json
# ---------------------------------------------------------------------------

def build_casos_prioritarios(con: duckdb.DuckDBPyConnection, top_n: int = TOP_N_CASOS_PRIORITARIOS) -> list[dict]:
    """
    Top `top_n` contracts by score. Deterministic tie-break (PLAN.md): score
    desc, then valor_contrato desc, then id_contrato asc -- so re-running the
    export against an unchanged mart always yields byte-identical chunks.
    """
    rows = con.execute(
        f"""
        WITH dedup AS ({_CONTRATO_DEDUP_SQL})
        SELECT
            cs.id_contrato, cs.nit_entidad_norm, cs.nombre_entidad, cs.doc_proveedor_norm, cs.nombre_proveedor,
            cs.cod_dpto, dv_d.dpto, cs.cod_mpio, dv_m.municipio,
            dedup.modalidad_norm, cs.anio, cs.valor_contrato, cs.fecha_firma, cs.source,
            cs.score, cs.tier, cs.urlproceso, cs.n_flags_aplicables, cs.n_flags_disparados, cs.flags_disparados
        FROM contrato_score cs
        JOIN dedup ON dedup.id_contrato = cs.id_contrato
        LEFT JOIN (SELECT DISTINCT cod_dpto, dpto FROM divipola) dv_d ON dv_d.cod_dpto = cs.cod_dpto
        LEFT JOIN (SELECT DISTINCT cod_dpto, cod_mpio, municipio FROM divipola) dv_m
            ON dv_m.cod_dpto = cs.cod_dpto AND dv_m.cod_mpio = cs.cod_mpio
        WHERE cs.score IS NOT NULL
        ORDER BY cs.score DESC, cs.valor_contrato DESC NULLS LAST, cs.id_contrato ASC
        LIMIT {int(top_n)}
        """  # noqa: S608 -- _CONTRATO_DEDUP_SQL/top_n are fixed constants, not user input
    ).fetchall()

    items = []
    for (
        id_contrato, nit_entidad, nombre_entidad, doc_proveedor, nombre_proveedor,
        cod_dpto, dpto, cod_mpio, municipio, modalidad, anio, valor_contrato, fecha_firma, source,
        score, tier, urlproceso, n_ap, n_di, flags_json,
    ) in rows:
        items.append(
            {
                "id_contrato": id_contrato,
                "nit_entidad": nit_entidad,
                "nombre_entidad": nombre_entidad,
                "doc_proveedor": doc_proveedor,
                "nombre_proveedor": nombre_proveedor,
                "cod_dpto": pad_dpto(cod_dpto),
                "dpto": dpto,
                "cod_mpio": pad_mpio(cod_mpio),
                "municipio": municipio,
                "modalidad": modalidad,
                "anio": anio,
                "valor_contrato": valor_contrato,
                "fecha_firma": fecha_firma.isoformat() if fecha_firma is not None else None,
                "source": source,
                "score": score,
                "tier": tier,
                "urlproceso": urlproceso,
                "n_flags_aplicables": n_ap or 0,
                "n_flags_disparados": n_di or 0,
                "banderas": load_banderas(flags_json),
            }
        )
    return items


# ---------------------------------------------------------------------------
# Size-budget enforcement
# ---------------------------------------------------------------------------

def check_size_budget(out_dir: Path) -> dict:
    """
    Enforce PLAN.md's size budget (<=60MB total, <=5MB/file). Raises
    `SizeBudgetExceeded` with a message naming exactly which file(s) and by
    how much -- never silently truncates data to fit.
    """
    files = sorted(out_dir.rglob("*.json"))
    total = 0
    oversized = []
    for p in files:
        size = p.stat().st_size
        total += size
        if size > MAX_FILE_BYTES:
            oversized.append((p, size))

    problems = []
    if oversized:
        detail = ", ".join(f"{p.relative_to(out_dir)} ({size / (1024 * 1024):.2f}MB)" for p, size in oversized)
        problems.append(f"Archivo(s) que superan el limite individual de {MAX_FILE_BYTES / (1024 * 1024):.0f}MB: {detail}")
    if total > MAX_TOTAL_BYTES:
        problems.append(
            f"Tamano total {total / (1024 * 1024):.2f}MB supera el presupuesto de {MAX_TOTAL_BYTES / (1024 * 1024):.0f}MB "
            f"({len(files)} archivos)."
        )
    if problems:
        raise SizeBudgetExceeded(
            "Presupuesto de tamano de web/public/data excedido -- reduce el contenido (mas paginacion, "
            "menos campos por fila, listas mas cortas); no truncar datos silenciosamente:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
    return {"total_bytes": total, "n_files": len(files)}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _clean_out_dir(out_dir: Path) -> None:
    """
    Remove previously-generated artifacts before a fresh run so a shrinking
    top-N/chunk-size never leaves stale orphan files behind (which would
    silently inflate the size-budget check and could be served to the
    frontend). Only touches the *.json files and subdirectories this module
    writes -- leaves anything else (e.g. a `.gitkeep`) untouched.
    """
    if not out_dir.exists():
        return
    for p in out_dir.glob("*.json"):
        p.unlink()
    for sub in ("departamentos", "casos_prioritarios"):
        sub_dir = out_dir / sub
        if sub_dir.exists():
            shutil.rmtree(sub_dir)


def run(con: duckdb.DuckDBPyConnection, out_dir: Path, *, validate: bool = True) -> dict:
    """
    Build and write every artifact into `out_dir`. `con` is caller-owned (not
    closed here) so this same function can run against either the real
    read-only mart connection (`build_artifacts.main`) or a synthetic
    in-memory one (`build_fixtures.main`).
    """
    out_dir = Path(out_dir)
    _clean_out_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Fetching casos_prioritarios (top %d by score)...", TOP_N_CASOS_PRIORITARIOS)
    cp_items = build_casos_prioritarios(con, TOP_N_CASOS_PRIORITARIOS)
    chunks = chunk_list(cp_items, CHUNK_SIZE_CASOS_PRIORITARIOS)
    if validate:
        validate_many(
            "casos_prioritarios_chunk",
            [
                (
                    {"chunk_index": idx, "n_chunks": len(chunks), "n_items_total": len(cp_items), "items": chunk},
                    f"casos_prioritarios/{idx:03d}.json",
                )
                for idx, chunk in enumerate(chunks)
            ],
        )
    for idx, chunk in enumerate(chunks):
        payload = {"chunk_index": idx, "n_chunks": len(chunks), "n_items_total": len(cp_items), "items": chunk}
        write_json(out_dir / "casos_prioritarios" / f"{idx:03d}.json", payload)
    log.info("  %d contratos en %d chunk(s)", len(cp_items), len(chunks))

    log.info("Building meta.json...")
    meta = build_meta(con, n_casos_prioritarios=len(cp_items), n_chunks=len(chunks))
    if validate:
        validate_artifact("meta", meta, source="meta.json")
    write_json(out_dir / "meta.json", meta)

    log.info("Building resumen_nacional.json...")
    resumen = build_resumen_nacional(con)
    if validate:
        validate_artifact("resumen_nacional", resumen, source="resumen_nacional.json")
    write_json(out_dir / "resumen_nacional.json", resumen)

    log.info("Building departamentos/*.json...")
    departamentos = build_departamentos(con)
    if validate:
        validate_many("departamento", [(d, f"departamentos/{d['cod_dpto']}.json") for d in departamentos])
    for d in departamentos:
        write_json(out_dir / "departamentos" / f"{d['cod_dpto']}.json", d)
    log.info("  %d departamentos", len(departamentos))

    log.info("Building entidades_top.json...")
    entidades = build_entidades_top(con)
    entidades_payload = {"n_items": len(entidades), "items": entidades}
    if validate:
        validate_artifact("entidades_top", entidades_payload, source="entidades_top.json")
    write_json(out_dir / "entidades_top.json", entidades_payload)

    log.info("Building proveedores_top.json...")
    proveedores = build_proveedores_top(con)
    proveedores_payload = {"n_items": len(proveedores), "items": proveedores}
    if validate:
        validate_artifact("proveedores_top", proveedores_payload, source="proveedores_top.json")
    write_json(out_dir / "proveedores_top.json", proveedores_payload)

    log.info("Checking size budget (<=%dMB total, <=%dMB/file)...", MAX_TOTAL_BYTES // (1024 * 1024), MAX_FILE_BYTES // (1024 * 1024))
    budget = check_size_budget(out_dir)
    log.info("  total=%.2fMB across %d files", budget["total_bytes"] / (1024 * 1024), budget["n_files"])

    return {
        "n_casos_prioritarios": len(cp_items),
        "n_chunks": len(chunks),
        "n_departamentos": len(departamentos),
        "n_entidades": len(entidades),
        "n_proveedores": len(proveedores),
        **budget,
    }


def print_report(summary: dict) -> None:
    print()
    print("=== M6 export ===")
    print(f"casos_prioritarios: {summary['n_casos_prioritarios']} contratos en {summary['n_chunks']} chunk(s)")
    print(f"departamentos: {summary['n_departamentos']}")
    print(f"entidades_top: {summary['n_entidades']}")
    print(f"proveedores_top: {summary['n_proveedores']}")
    print(
        f"tamano total: {summary['total_bytes'] / (1024 * 1024):.2f} MB en {summary['n_files']} archivo(s) "
        f"(presupuesto: {MAX_TOTAL_BYTES / (1024 * 1024):.0f} MB)"
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build M6 web artifacts from corruption.duckdb into web/public/data/.")
    parser.add_argument("--db", type=Path, default=MARTS_DIR / "corruption.duckdb", help="Path to the DuckDB mart (default: %(default)s)")
    parser.add_argument("--out", type=Path, default=WEB_PUBLIC_DATA_DIR, help="Output directory (default: %(default)s)")
    parser.add_argument("--no-validate", dest="validate", action="store_false", help="Skip JSON-Schema validation (validated by default)")
    parser.set_defaults(validate=True)
    args = parser.parse_args()

    log.info("Connecting to %s (read-only)", args.db)
    con = duckdb.connect(str(args.db), read_only=True)
    try:
        summary = run(con, args.out, validate=args.validate)
    finally:
        con.close()

    print_report(summary)


if __name__ == "__main__":
    main()
