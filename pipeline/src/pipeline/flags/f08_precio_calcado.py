"""
F08 -- Precio calcado (contract level, weight 6).

PLAN.md definition: awarded value within +-0.5% of `precio_base` in a
competitive process. Needs the contract<->process join (see
common.PROCESO_DEDUP_CTE); applicable population = joined competitive
contracts with a positive process budget (`precio_base`).
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import CONTRATO_PROCESO_JOIN, PROCESO_DEDUP_CTE, FlagRow, rows_from_sql
from pipeline.flags.params import F08_TOLERANCE

FLAG_ID = "F08"

_SQL = f"""
WITH {PROCESO_DEDUP_CTE}
SELECT
    fc.id_contrato AS key,
    (ABS(fc.valor_contrato / fp.precio_base - 1) <= {F08_TOLERANCE}) AS fired,
    fc.valor_contrato AS valor_contrato,
    fp.precio_base AS precio_base,
    ABS(fc.valor_contrato / fp.precio_base - 1) AS desviacion_pct
FROM {CONTRATO_PROCESO_JOIN}
WHERE fc.es_competitiva
  AND fp.precio_base IS NOT NULL AND fp.precio_base > 0
  AND fc.valor_contrato IS NOT NULL
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
