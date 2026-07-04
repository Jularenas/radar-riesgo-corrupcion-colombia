"""
F09 -- Afán de diciembre (contract level, weight 4).

PLAN.md definition: signed Dec 15-31. Simple date predicate on
fct_contrato.fecha_firma; no join needed. Applicable population = every
contract with a non-null signature date.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import F09_MONTH, F09_START_DAY

FLAG_ID = "F09"

_SQL = f"""
SELECT
    id_contrato AS key,
    (EXTRACT(MONTH FROM fecha_firma) = {F09_MONTH} AND EXTRACT(DAY FROM fecha_firma) >= {F09_START_DAY}) AS fired,
    fecha_firma AS fecha_firma
FROM fct_contrato
WHERE fecha_firma IS NOT NULL
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
