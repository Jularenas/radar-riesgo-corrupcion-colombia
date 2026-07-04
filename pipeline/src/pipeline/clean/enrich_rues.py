"""
M4: RUES enrichment — populate dim_proveedor.fecha_matricula.

Sources (E1 in PLAN.md, both pulled by pipeline.extract.pull into data/raw/):
  - e1_rues_ibague     (gwqv-sqvs): Camara de Comercio de Ibague only. COMPLETE (90,937 rows).
  - e1_rues_santarosa  (c82u-588k): Camara de Comercio de Santa Rosa de Cabal, but per its own
    metadata syncs the NATIONAL RUES registry. ~9.29M rows live; may still be mid-pull when this
    module runs (a background `pull --dataset e1_rues_santarosa` can be appending part files).
    We always glob `part-*.parquet` fresh at call time, so a partial pull is safe to read (each
    part file is only written after a full page fetch completes) and re-running this module later
    picks up more coverage automatically — no code change needed when the pull finishes.

Schema notes (discovered via DESCRIBE — differ from the "likely FECHA_MATRICULA" guess in the
milestone brief):
  - e1_rues_ibague:    NIT column is literally `nit` (already includes the DIAN check digit for
    NIT-type registrants, e.g. '8090031820'); registration-date column is `fecha_de_matricula`
    (not `fecha_matricula`). Both are ALL-CAPS-sentinel-free VARCHAR except a literal string
    'NO APLICA' used for N/A (e.g. `nit`='NO APLICA' for ESTABLECIMIENTO DE COMERCIO rows, which
    are branch/storefront records with no NIT of their own — they naturally drop out of matching).
    Dates are 8-digit `YYYYMMDD` strings, e.g. '19720114' — NOT ISO format.
  - e1_rues_santarosa: NIT is split across `nit` + `digito_verificacion` for NIT-class registrants
    (entities); persona-natural registrants instead carry their cedula in `numero_identificacion`
    with `nit` NULL. Registration date column IS named `fecha_matricula` (matches the brief).
    Same YYYYMMDD string format, with a small (~0.5%) rate of malformed/blank values.

Matching key: NIT "base" (9 digits, check-digit stripped) via the `nit_base` SQL macro below,
which mirrors `pipeline.clean.normalize.normalize_doc()`'s nit_base rule. We deliberately do NOT
call the Python normalizer as a DuckDB UDF here: DuckDB's Python UDF path requires numpy, which
is not (and should not need to become) a pipeline dependency just for this, and a row-by-row
Python UDF would be materially slower than a vectorized SQL CASE expression over a 9M+ row,
still-growing table. Instead the SQL is treated as an accelerated re-expression of the single
canonical rule in normalize.py, and kept honest two ways:
  1. test_rues_enrichment.py asserts SQL-vs-Python parity on a battery of synthetic values.
  2. `_assert_nit_base_parity_on_sample()` re-checks that parity against a live sample of the
     actual raw data every time this module runs, and raises loudly on any drift.
Matching on the 9-digit base (rather than the raw string) is safe, not just convenient: per
normalize.py's own is_persona_natural heuristic, a 9-or-10-digit id starting with 8/9 is *always*
entity territory (DIAN reserves that numbering space for NITs; personal cedulas don't live there),
so truncating the redundant DIAN check digit cannot collide two unrelated documents together.

Conflict resolution (explicit product decision, see PLAN.md M4 acceptance + milestone brief):
  - Within one source, the same nit_base can legitimately appear on multiple physical
    registration rows (most commonly a persona natural who has registered more than one separate
    commercial activity over the years — confirmed in e1_rues_santarosa). We collapse to one row
    per (source, nit_base) by taking MIN(fecha) — see docs/RUES_COVERAGE.md for the count this
    affects and the trade-off it implies (a long-registered individual's very first registration
    can mask a *new* registration used to front a specific bid; we accept this because the
    alternative — taking the latest — would manufacture false "empresa exprés" positives against
    ordinary long-established persons/entities, which is the worse failure mode for a tool whose
    output is described to auditors as risk evidence, not proof).
  - Across sources, if both e1_rues_ibague and e1_rues_santarosa resolve a date for the same
    nit_base and they disagree, we keep the earlier date and count it as a logged conflict.
    If only one source has a (non-null) date, we use it — there is no "more complete record" to
    prefer beyond non-nullness, since fecha_matricula is the only field we carry through.

NULL semantics: NULL always means "no registration date found," never "not an express company."
F02 (empresa exprés) must treat NULL as *not applicable* and exclude the contract from its
denominator rather than treating a NULL as a negative signal — this module only ever writes a
real DATE or leaves the column NULL, never a sentinel value.

Usage:
    uv run python -m pipeline.clean.enrich_rues [--mart PATH]
"""

from __future__ import annotations

import argparse
import logging
import random
from pathlib import Path

import duckdb

from pipeline.clean.normalize import normalize_doc
from pipeline.config import MARTS_DIR, RAW_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source locations (always globbed fresh — safe to read while santarosa is
# still being pulled in the background; see module docstring)
# ---------------------------------------------------------------------------

IBAGUE_GLOB = str(RAW_DIR / "e1_rues_ibague" / "part-*.parquet")
SANTAROSA_GLOB = str(RAW_DIR / "e1_rues_santarosa" / "part-*.parquet")

# ---------------------------------------------------------------------------
# NIT-base macro — single source of truth for the SQL side of the match key.
# Mirrors pipeline.clean.normalize.normalize_doc()'s nit_base rule exactly:
# 10-digit ids starting with 8/9 → strip the trailing DIAN check digit;
# everything else → unchanged. See module docstring for why this is safe.
# ---------------------------------------------------------------------------

NIT_BASE_MACRO_SQL = """
    CREATE OR REPLACE TEMP MACRO nit_base(digits) AS
        CASE
            WHEN digits IS NULL OR digits = '' THEN NULL
            WHEN length(digits) = 10 AND left(digits, 1) IN ('8', '9')
            THEN left(digits, 9)
            ELSE digits
        END
"""


def install_macros(con: duckdb.DuckDBPyConnection) -> None:
    """Install the nit_base SQL macro on the given connection (idempotent)."""
    con.execute(NIT_BASE_MACRO_SQL)


# ---------------------------------------------------------------------------
# Per-source resolution SQL
# ---------------------------------------------------------------------------


def _ibague_resolved_sql(glob: str) -> str:
    """One row per nit_base for e1_rues_ibague: earliest fecha_de_matricula wins."""
    return f"""
        SELECT
            nit_base(doc_digits) AS nit_base,
            MIN(fecha) AS fecha_matricula,
            COUNT(*) AS n_registros
        FROM (
            SELECT
                regexp_replace(nit, '[^0-9]', '', 'g') AS doc_digits,
                TRY_STRPTIME(fecha_de_matricula, '%Y%m%d')::DATE AS fecha
            FROM read_parquet('{glob}', union_by_name=true)
            -- 'NO APLICA' is this source's explicit N/A sentinel (e.g. ESTABLECIMIENTO
            -- DE COMERCIO branch rows, which have no NIT of their own)
            WHERE nit IS NOT NULL AND upper(trim(nit)) NOT IN ('NO APLICA', '')
        )
        WHERE doc_digits != '' AND fecha IS NOT NULL
        GROUP BY 1
    """


def _santarosa_resolved_sql(glob: str) -> str:
    """One row per nit_base for e1_rues_santarosa: earliest fecha_matricula wins.

    NIT-class registrants carry nit + digito_verificacion separately; persona-natural
    registrants carry their cedula in numero_identificacion with nit NULL.
    """
    return f"""
        SELECT
            nit_base(doc_digits) AS nit_base,
            MIN(fecha) AS fecha_matricula,
            COUNT(*) AS n_registros
        FROM (
            SELECT
                CASE
                    WHEN nit IS NOT NULL AND trim(nit) != ''
                    THEN regexp_replace(nit || COALESCE(digito_verificacion, ''), '[^0-9]', '', 'g')
                    ELSE regexp_replace(COALESCE(numero_identificacion, ''), '[^0-9]', '', 'g')
                END AS doc_digits,
                TRY_STRPTIME(fecha_matricula, '%Y%m%d')::DATE AS fecha
            FROM read_parquet('{glob}', union_by_name=true)
        )
        WHERE doc_digits != '' AND fecha IS NOT NULL
        GROUP BY 1
    """


def build_rues_resolved(
    con: duckdb.DuckDBPyConnection,
    ibague_glob: str = IBAGUE_GLOB,
    santarosa_glob: str = SANTAROSA_GLOB,
    table_name: str = "rues_resolved",
) -> dict:
    """
    Build a TEMP TABLE `table_name` with one row per nit_base seen in either chamber
    source, with cross-source conflict resolution (see module docstring).

    Columns: nit_base, fecha_ibague, fecha_santarosa, fecha_matricula (resolved),
    is_conflict, n_sources_matched, n_registros_ibague, n_registros_santarosa.

    Works fine against a read_only connection to the mart (TEMP tables are not part of
    the persistent file), so the coverage report never needs write access.
    """
    install_macros(con)

    con.execute(f"CREATE OR REPLACE TEMP TABLE _rues_ibague_resolved AS {_ibague_resolved_sql(ibague_glob)}")
    con.execute(f"CREATE OR REPLACE TEMP TABLE _rues_santarosa_resolved AS {_santarosa_resolved_sql(santarosa_glob)}")

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE {table_name} AS
        SELECT
            nit_base,
            i.fecha_matricula AS fecha_ibague,
            s.fecha_matricula AS fecha_santarosa,
            CASE
                WHEN i.fecha_matricula IS NULL THEN s.fecha_matricula
                WHEN s.fecha_matricula IS NULL THEN i.fecha_matricula
                WHEN i.fecha_matricula <= s.fecha_matricula THEN i.fecha_matricula
                ELSE s.fecha_matricula
            END AS fecha_matricula,
            (i.fecha_matricula IS NOT NULL AND s.fecha_matricula IS NOT NULL
                AND i.fecha_matricula != s.fecha_matricula) AS is_conflict,
            (CASE WHEN i.fecha_matricula IS NOT NULL THEN 1 ELSE 0 END
                + CASE WHEN s.fecha_matricula IS NOT NULL THEN 1 ELSE 0 END) AS n_sources_matched,
            COALESCE(i.n_registros, 0) AS n_registros_ibague,
            COALESCE(s.n_registros, 0) AS n_registros_santarosa
        FROM _rues_ibague_resolved i
        FULL OUTER JOIN _rues_santarosa_resolved s USING (nit_base)
    """)

    stats = con.execute(f"""
        SELECT
            COUNT(*) AS n_nit_base,
            SUM(CASE WHEN is_conflict THEN 1 ELSE 0 END) AS n_conflicts,
            SUM(CASE WHEN n_registros_ibague > 1 THEN 1 ELSE 0 END) AS n_multi_registro_ibague,
            SUM(CASE WHEN n_registros_santarosa > 1 THEN 1 ELSE 0 END) AS n_multi_registro_santarosa
        FROM {table_name}
    """).fetchone()

    return {
        "n_nit_base": stats[0],
        "n_conflicts": stats[1] or 0,
        "n_multi_registro_ibague": stats[2] or 0,
        "n_multi_registro_santarosa": stats[3] or 0,
    }


# ---------------------------------------------------------------------------
# Runtime parity self-check: SQL nit_base macro vs. the canonical Python
# normalizer, sampled from the actual raw data (belt-and-suspenders on top
# of the synthetic-fixture unit tests in test_rues_enrichment.py).
# ---------------------------------------------------------------------------


def _assert_nit_base_parity_on_sample(
    con: duckdb.DuckDBPyConnection,
    ibague_glob: str = IBAGUE_GLOB,
    santarosa_glob: str = SANTAROSA_GLOB,
    sample_n: int = 500,
    seed: int = 42,
) -> None:
    """Raise if the SQL nit_base macro ever disagrees with normalize_doc() on real data."""
    install_macros(con)

    raw_ibague = [
        r[0] for r in con.execute(f"""
            SELECT DISTINCT regexp_replace(nit, '[^0-9]', '', 'g') AS d
            FROM read_parquet('{ibague_glob}', union_by_name=true)
            WHERE nit IS NOT NULL AND upper(trim(nit)) NOT IN ('NO APLICA', '')
            USING SAMPLE {sample_n} ROWS
        """).fetchall()
        if r[0]
    ]
    raw_santarosa = [
        r[0] for r in con.execute(f"""
            SELECT DISTINCT
                CASE
                    WHEN nit IS NOT NULL AND trim(nit) != ''
                    THEN regexp_replace(nit || COALESCE(digito_verificacion, ''), '[^0-9]', '', 'g')
                    ELSE regexp_replace(COALESCE(numero_identificacion, ''), '[^0-9]', '', 'g')
                END AS d
            FROM read_parquet('{santarosa_glob}', union_by_name=true)
            USING SAMPLE {sample_n} ROWS
        """).fetchall()
        if r[0]
    ]

    rng = random.Random(seed)
    sample = raw_ibague + raw_santarosa
    rng.shuffle(sample)

    for digits in sample[: sample_n * 2]:
        sql_result = con.execute("SELECT nit_base(?)", [digits]).fetchone()[0]
        py_result = normalize_doc(digits)["nit_base"]
        if sql_result != py_result:
            raise RuntimeError(
                f"nit_base parity check FAILED for raw value {digits!r}: "
                f"SQL macro gave {sql_result!r}, normalize_doc() gave {py_result!r}. "
                "The SQL macro in enrich_rues.py has drifted from "
                "pipeline.clean.normalize.normalize_doc() — fix the macro before trusting "
                "any RUES match built from it."
            )


# ---------------------------------------------------------------------------
# Enrichment: write dim_proveedor.fecha_matricula
# ---------------------------------------------------------------------------


def enrich(
    mart_path: Path | None = None,
    ibague_glob: str = IBAGUE_GLOB,
    santarosa_glob: str = SANTAROSA_GLOB,
) -> dict:
    """
    Populate dim_proveedor.fecha_matricula from the resolved RUES tables.

    Idempotent / fully re-derived each run: every dim_proveedor row is explicitly set to
    either a matched DATE or NULL based on the *current* raw data snapshot, so re-running
    this after e1_rues_santarosa's background pull makes more progress simply picks up
    more matches (never leaves a stale value from a smaller earlier snapshot).
    """
    if mart_path is None:
        mart_path = MARTS_DIR / "corruption.duckdb"

    log.info("Connecting to mart: %s", mart_path)
    con = duckdb.connect(str(mart_path))
    try:
        _assert_nit_base_parity_on_sample(con, ibague_glob, santarosa_glob)

        build_stats = build_rues_resolved(con, ibague_glob, santarosa_glob)
        log.info(
            "RUES resolved: %d distinct nit_base (%d cross-source conflicts, "
            "%d/%d nit_base with >1 raw registro in ibague/santarosa)",
            build_stats["n_nit_base"],
            build_stats["n_conflicts"],
            build_stats["n_multi_registro_ibague"],
            build_stats["n_multi_registro_santarosa"],
        )

        con.execute("ALTER TABLE dim_proveedor ADD COLUMN IF NOT EXISTS fecha_matricula DATE")

        n_before = con.execute(
            "SELECT COUNT(*) FROM dim_proveedor WHERE fecha_matricula IS NOT NULL"
        ).fetchone()[0]
        n_suppliers = con.execute("SELECT COUNT(*) FROM dim_proveedor").fetchone()[0]

        # Explicit LEFT JOIN (rather than a bare UPDATE...FROM on the matched rows only)
        # so every row is set to either a fresh match or NULL — fully idempotent re-runs.
        con.execute("""
            UPDATE dim_proveedor
            SET fecha_matricula = sub.fecha_matricula
            FROM (
                SELECT dp.doc_proveedor_norm AS doc_proveedor_norm, r.fecha_matricula AS fecha_matricula
                FROM dim_proveedor dp
                LEFT JOIN rues_resolved r ON nit_base(dp.doc_proveedor_norm) = r.nit_base
            ) sub
            WHERE dim_proveedor.doc_proveedor_norm = sub.doc_proveedor_norm
        """)

        n_after = con.execute(
            "SELECT COUNT(*) FROM dim_proveedor WHERE fecha_matricula IS NOT NULL"
        ).fetchone()[0]

        log.info(
            "dim_proveedor.fecha_matricula: %d/%d suppliers matched (was %d before this run)",
            n_after, n_suppliers, n_before,
        )

        return {
            "n_suppliers": n_suppliers,
            "n_matched_before": n_before,
            "n_matched_after": n_after,
            **build_stats,
        }
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="M4: enrich dim_proveedor.fecha_matricula from RUES")
    parser.add_argument("--mart", type=Path, default=None, help="Path to corruption.duckdb (default: data/marts/corruption.duckdb)")
    args = parser.parse_args()
    stats = enrich(mart_path=args.mart)
    print("\n=== RUES enrichment summary ===")
    for k, v in stats.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
