"""
F14 -- Valor redondo (contract level, weight 2).

PLAN.md definition: value >= 1,000M COP and a multiple of 100M COP. Simple
predicate on fct_contrato.valor_contrato; no join needed. Applicable
population = contracts with a non-null value.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import F14_MIN_VALUE, F14_ROUND_UNIT

FLAG_ID = "F14"

_SQL = f"""
SELECT
    id_contrato AS key,
    (valor_contrato >= {F14_MIN_VALUE} AND MOD(CAST(valor_contrato AS BIGINT), {F14_ROUND_UNIT}) = 0) AS fired,
    valor_contrato AS valor_contrato
FROM fct_contrato
WHERE valor_contrato IS NOT NULL
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
