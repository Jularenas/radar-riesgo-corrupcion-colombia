"""
Shared plumbing for the 14 red-flag modules (M3).

Interface convention (applied uniformly across f01..f14):

    def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]

Each module's SQL selects exactly the *applicable population* for that flag
(contracts or entities for which the flag is computable at all) with a
`fired` boolean and whatever raw evidence columns matter. Rows that are not
testable (missing inputs) are simply excluded from the result set -- this is
what lets the scorer (M5) drop unknown inputs out of its denominator instead
of penalizing them, per PLAN.md.

No dataframe library (polars/pandas) is used: the rest of the pipeline
(clean/build.py, clean/profile.py) is plain DuckDB SQL + stdlib, and neither
polars nor pandas is a project dependency. `FlagRow` + `fetchall()` keeps
M3 consistent with that and keeps synthetic-fixture unit tests trivial
(plain dataclass equality, no dataframe assertions).
"""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import logging
from dataclasses import dataclass
from typing import Any

import duckdb

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FlagRow:
    """One evaluation of one flag against one contract or entity."""

    flag_id: str
    key: str  # id_contrato for contract-level flags, nit_entidad_norm for entity-level
    fired: bool
    evidence: dict[str, Any]  # JSON-serializable (see `jsonable`)


def jsonable(value: Any) -> Any:
    """Coerce a DuckDB-returned Python value into something json.dumps can handle."""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.isoformat()
    if isinstance(value, _decimal.Decimal):
        return float(value)
    return value


def rows_from_sql(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    flag_id: str,
    key_col: str = "key",
    fired_col: str = "fired",
) -> list[FlagRow]:
    """
    Execute `sql` (must project at least `key_col` and `fired_col`) and turn
    every other column into the evidence dict for that row.
    """
    rel = con.sql(sql)
    cols = [d[0] for d in rel.description]
    evidence_cols = [c for c in cols if c not in (key_col, fired_col)]
    out: list[FlagRow] = []
    for record in rel.fetchall():
        row = dict(zip(cols, record, strict=True))
        evidence = {c: jsonable(row[c]) for c in evidence_cols}
        out.append(
            FlagRow(
                flag_id=flag_id,
                key=str(row[key_col]),
                fired=bool(row[fired_col]),
                evidence=evidence,
            )
        )
    return out


def empty_result() -> list[FlagRow]:
    """Canonical empty result for a flag whose required input isn't available yet."""
    return []


def table_columns(con: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    """Column names of `table`, e.g. to detect optional columns not yet backfilled (F02, F04)."""
    return {r[1] for r in con.execute(f"PRAGMA table_info('{table}')").fetchall()}


# ---------------------------------------------------------------------------
# Shared SQL fragments
# ---------------------------------------------------------------------------

# fct_proceso.referencia (== S2 id_del_portafolio) is NOT unique in the M2
# mart (300,000 rows / 287,137 distinct in the sample -- ~4.3% duplicated,
# likely multiple `fase` snapshots of the same process). Joining
# fct_contrato to fct_proceso directly on this key fans out and silently
# double-counts contracts. Every flag that needs the contract<->process
# join (F01, F03, F07, F08) must join against this deduplicated view
# instead of the raw table. One row per `referencia`, preferring the most
# recently published snapshot.
PROCESO_DEDUP_CTE = """
    proceso_dedup AS (
        SELECT * EXCLUDE (_rn) FROM (
            SELECT fp.*,
                ROW_NUMBER() OVER (
                    PARTITION BY referencia
                    ORDER BY fecha_publicacion DESC NULLS LAST, row_id DESC
                ) AS _rn
            FROM fct_proceso fp
            WHERE referencia IS NOT NULL
        )
        WHERE _rn = 1
    )
"""

CONTRATO_PROCESO_JOIN = "fct_contrato fc JOIN proceso_dedup fp ON fc.proceso_de_compra = fp.referencia"
