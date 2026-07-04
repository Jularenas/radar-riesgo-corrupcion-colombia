"""
M4: RUES coverage measurement.

Measures what share of dim_proveedor's suppliers (both by plain count and by contract
value, since a handful of huge suppliers matching matters more than covering many tiny
ones — see PLAN.md M4) find a fecha_matricula match in e1_rues_ibague UNION e1_rues_santarosa,
broken down by the persona natural / juridica heuristic already computed in dim_proveedor.

This is a read-only, side-effect-free measurement (connects to the mart with read_only=True)
that reuses the exact same matching logic (`nit_base` macro + build_rues_resolved()) that
enrich_rues.py uses to actually populate dim_proveedor.fecha_matricula, so the reported
percentages always describe what enrichment would do / has done — there is no separate
"coverage-estimation" logic to drift out of sync with the real enrichment.

Usage:
    uv run python -m pipeline.clean.rues_coverage [--mart PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from pipeline.clean.enrich_rues import (
    IBAGUE_GLOB,
    SANTAROSA_GLOB,
    build_rues_resolved,
)
from pipeline.config import DATA_DIR, MARTS_DIR, RAW_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Repo root is two levels above pipeline/data (pipeline/data -> pipeline -> repo root).
# Derived from config.DATA_DIR (already fixed for the parents[]-index bug that previously
# sent pipeline output to a stray top-level data/ — see git history) rather than
# re-deriving our own Path(__file__).resolve().parents[N] arithmetic.
DOCS_DIR = DATA_DIR.parent.parent / "docs"

DATASET_IDS = {
    "e1_rues_ibague": "gwqv-sqvs",
    "e1_rues_santarosa": "c82u-588k",
}


def _read_manifest_entry(name: str) -> dict:
    """Read (never write) the pull manifest for a dataset's live-count/status bookkeeping."""
    manifest_path = RAW_DIR / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text())
    return manifest.get(name, {})


def _source_completeness(con: duckdb.DuckDBPyConnection, name: str, glob: str) -> dict:
    """Rows currently readable on disk for a source vs. its known live total from manifest.json."""
    rows_on_disk = con.execute(f"SELECT COUNT(*) FROM read_parquet('{glob}', union_by_name=true)").fetchone()[0]
    entry = _read_manifest_entry(name)
    live_total = entry.get("live_count_at_start")
    pct = (rows_on_disk * 100.0 / live_total) if live_total else None
    return {
        "name": name,
        "dataset_id": DATASET_IDS.get(name, entry.get("dataset_id", "?")),
        "rows_on_disk": rows_on_disk,
        "live_total": live_total,
        "pct_of_live_total": pct,
        "status": entry.get("status", "unknown"),
    }


def _match_breakdown(con: duckdb.DuckDBPyConnection) -> dict:
    """Overall + persona-natural-vs-juridica match rate, simple and value-weighted."""
    overall = con.execute("""
        WITH sup AS (
            SELECT nit_base(doc_proveedor_norm) AS nit_base, n_contratos, valor_total
            FROM dim_proveedor
        )
        SELECT
            COUNT(*) AS n_suppliers,
            SUM(CASE WHEN r.fecha_matricula IS NOT NULL THEN 1 ELSE 0 END) AS n_matched,
            SUM(sup.valor_total) AS valor_total,
            SUM(CASE WHEN r.fecha_matricula IS NOT NULL THEN sup.valor_total ELSE 0 END) AS valor_matched
        FROM sup
        LEFT JOIN rues_resolved r USING (nit_base)
    """).fetchone()

    by_tipo = con.execute("""
        WITH sup AS (
            SELECT nit_base(doc_proveedor_norm) AS nit_base, es_persona_natural, n_contratos, valor_total
            FROM dim_proveedor
        )
        SELECT
            sup.es_persona_natural,
            COUNT(*) AS n_suppliers,
            SUM(CASE WHEN r.fecha_matricula IS NOT NULL THEN 1 ELSE 0 END) AS n_matched,
            SUM(sup.valor_total) AS valor_total,
            SUM(CASE WHEN r.fecha_matricula IS NOT NULL THEN sup.valor_total ELSE 0 END) AS valor_matched
        FROM sup
        LEFT JOIN rues_resolved r USING (nit_base)
        GROUP BY 1
        ORDER BY 1
    """).fetchall()

    return {
        "overall": {
            "n_suppliers": overall[0],
            "n_matched": overall[1] or 0,
            "valor_total": overall[2] or 0.0,
            "valor_matched": overall[3] or 0.0,
        },
        "by_tipo": [
            {
                "es_persona_natural": row[0],
                "n_suppliers": row[1],
                "n_matched": row[2] or 0,
                "valor_total": row[3] or 0.0,
                "valor_matched": row[4] or 0.0,
            }
            for row in by_tipo
        ],
    }


def compute_coverage(
    mart_path: Path | None = None,
    ibague_glob: str = IBAGUE_GLOB,
    santarosa_glob: str = SANTAROSA_GLOB,
) -> dict:
    if mart_path is None:
        mart_path = MARTS_DIR / "corruption.duckdb"

    con = duckdb.connect(str(mart_path), read_only=True)
    try:
        build_stats = build_rues_resolved(con, ibague_glob, santarosa_glob)
        completeness = {
            "e1_rues_ibague": _source_completeness(con, "e1_rues_ibague", ibague_glob),
            "e1_rues_santarosa": _source_completeness(con, "e1_rues_santarosa", santarosa_glob),
        }
        match = _match_breakdown(con)
    finally:
        con.close()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mart_path": str(mart_path),
        "build_stats": build_stats,
        "completeness": completeness,
        "match": match,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def _pct(n: float, d: float) -> str:
    if not d:
        return "N/A"
    return f"{n * 100.0 / d:.1f}%"


def _tipo_label(v) -> str:
    return {True: "Persona natural", False: "Persona juridica", None: "Desconocido (heuristica ambigua)"}[v]


def write_report(stats: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    c_ib = stats["completeness"]["e1_rues_ibague"]
    c_sr = stats["completeness"]["e1_rues_santarosa"]
    m = stats["match"]["overall"]
    bs = stats["build_stats"]

    lines = [
        "# RUES Coverage Report — M4",
        "",
        "Regenerate any time with:",
        "```",
        "uv run python -m pipeline.clean.rues_coverage",
        "```",
        "This file always reflects whatever `part-*.parquet` files are currently on disk for",
        "`e1_rues_ibague` / `e1_rues_santarosa` — it is a live measurement, not a one-time snapshot.",
        "",
        f"**Generated:** {stats['generated_at']}  ",
        f"**Mart:** `{stats['mart_path']}`",
        "",
        "## 1. Source completeness",
        "",
        "| Source | Dataset ID | Rows on disk now | Known live total | % of live total | Pull status |",
        "|--------|-----------|------------------:|------------------:|-----------------:|-------------|",
        f"| e1_rues_ibague | `{c_ib['dataset_id']}` | {c_ib['rows_on_disk']:,} | "
        f"{c_ib['live_total']:,} | {_pct(c_ib['rows_on_disk'], c_ib['live_total'])} | {c_ib['status']} |",
        f"| e1_rues_santarosa | `{c_sr['dataset_id']}` | {c_sr['rows_on_disk']:,} | "
        f"{c_sr['live_total']:,} | {_pct(c_sr['rows_on_disk'], c_sr['live_total'])} | {c_sr['status']} |",
        "",
    ]

    if c_sr["status"] == "in_progress":
        lines += [
            "> **e1_rues_santarosa is a partial snapshot.** Per its own dataset metadata it syncs the",
            "> *national* RUES registry (not just the Santa Rosa de Cabal chamber), so it is the dominant",
            "> coverage driver, and a background pull was still appending part files when this report was",
            "> generated. All match-rate numbers below are therefore a **lower bound**: they will only ever",
            "> go up as more of the national registry lands on disk. Re-run the command above once the pull",
            "> reaches `status: complete` in `data/raw/manifest.json` for an updated (and final) number.",
            "",
        ]

    lines += [
        "## 2. Match rate — dim_proveedor -> fecha_matricula",
        "",
        "Two metrics are reported because a handful of very large suppliers matching (or not)",
        "matters more to the eventual F02 (\"empresa exprés\") flag's usefulness than the raw count",
        "of small suppliers matched:",
        "",
        "| Metric | Matched | Total | Match rate |",
        "|--------|--------:|------:|-----------:|",
        f"| Distinct suppliers (simple %) | {m['n_matched']:,} | {m['n_suppliers']:,} | "
        f"{_pct(m['n_matched'], m['n_suppliers'])} |",
        f"| Contract value (value-weighted %) | {m['valor_matched']:,.0f} COP | "
        f"{m['valor_total']:,.0f} COP | {_pct(m['valor_matched'], m['valor_total'])} |",
        "",
        "### 2.1 Breakdown by supplier type (dim_proveedor.es_persona_natural heuristic)",
        "",
        "| Tipo | Suppliers matched / total | Match rate (suppliers) | Value matched / total (COP) | Match rate (value) |",
        "|------|---------------------------:|------------------------:|------------------------------:|--------------------:|",
    ]
    for row in stats["match"]["by_tipo"]:
        label = _tipo_label(row["es_persona_natural"])
        lines.append(
            f"| {label} | {row['n_matched']:,} / {row['n_suppliers']:,} | "
            f"{_pct(row['n_matched'], row['n_suppliers'])} | "
            f"{row['valor_matched']:,.0f} / {row['valor_total']:,.0f} | "
            f"{_pct(row['valor_matched'], row['valor_total'])} |"
        )

    lines += [
        "",
        "## 3. Match quality notes",
        "",
        f"- **Cross-source conflicts:** {bs['n_conflicts']:,} NITs matched in *both* e1_rues_ibague and",
        "  e1_rues_santarosa with disagreeing dates. Resolution: earliest date kept (see",
        "  `pipeline/src/pipeline/clean/enrich_rues.py` module docstring for the full policy).",
        f"- **Multi-registration suppliers:** {bs['n_multi_registro_ibague']:,} NITs in e1_rues_ibague and",
        f"  {bs['n_multi_registro_santarosa']:,} in e1_rues_santarosa have more than one historical",
        "  registration row under the same document number (most commonly a persona natural who has",
        "  registered multiple separate commercial activities over the years). We keep the earliest",
        "  registration per document per source — a deliberate, conservative choice: it avoids",
        "  manufacturing false \"empresa exprés\" positives against long-established persons/entities,",
        "  at the cost of possibly missing a genuinely new registration used to front a specific bid.",
        "  See the enrich_rues.py docstring for the full reasoning.",
        "- **NULL means \"unknown,\" never \"not express.\"** Unmatched suppliers get `fecha_matricula = NULL`",
        "  in `dim_proveedor`. F02 must exclude NULL from its denominator rather than treat it as a",
        "  negative signal — an unmatched supplier is not evidence of an old, legitimate company.",
        "",
        "## 4. Tiered per-NIT fallback",
        "",
        "For suppliers still unmatched after the above (and meeting the PLAN.md M4 threshold — a",
        "contract >= 200M COP, or an already-fired red flag once M3's `flag_contrato` exists), a",
        "throttled, cached, currently-a-documented-no-op fallback is available at",
        "`pipeline.extract.rues_lookup.lookup_fecha_matricula()`. See that module's docstring for why",
        "no live RUES/Confecámaras API is wired in yet.",
        "",
        "---",
        "*Generated by `uv run python -m pipeline.clean.rues_coverage`*",
    ]

    out_path.write_text("\n".join(lines) + "\n")
    log.info("Coverage report written: %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="M4: measure RUES chamber-data coverage of dim_proveedor")
    parser.add_argument("--mart", type=Path, default=None, help="Path to corruption.duckdb")
    parser.add_argument("--out", type=Path, default=None, help="Output path for RUES_COVERAGE.md")
    args = parser.parse_args()

    stats = compute_coverage(mart_path=args.mart)
    out_path = args.out or (DOCS_DIR / "RUES_COVERAGE.md")
    write_report(stats, out_path)

    m = stats["match"]["overall"]
    print("\n=== RUES coverage summary ===")
    print(f"Suppliers matched: {m['n_matched']:,} / {m['n_suppliers']:,} ({_pct(m['n_matched'], m['n_suppliers'])})")
    print(f"Value matched:     {_pct(m['valor_matched'], m['valor_total'])}")
    print(f"Report:            {out_path}")


if __name__ == "__main__":
    main()
