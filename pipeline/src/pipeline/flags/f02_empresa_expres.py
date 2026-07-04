"""
F02 -- Empresa exprés (contract level, weight 15).

PLAN.md definition: supplier `fecha_matricula` (RUES) within 90 days before
process publication.

RUES enrichment is M4's job. As of M3, `dim_proveedor` has no
`fecha_matricula` column (verified live against the M2 sample mart via
PRAGMA table_info -- see docs/PROFILING.md / DQ_REPORT.md for what
`dim_proveedor` currently has). This module detects that at runtime rather
than hardcoding "not implemented": if the column is missing it logs a clear
message and returns an empty, correctly-typed result so run_all reports
population=0 for F02 without erroring, and M4 can add the column without
touching this file. The real logic below is exercised by
tests/test_flags/test_f02_empresa_expres.py against a synthetic
`dim_proveedor` that *does* have `fecha_matricula`, so the join/threshold
logic is proven correct ahead of M4.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import (
    CONTRATO_PROCESO_JOIN,
    PROCESO_DEDUP_CTE,
    FlagRow,
    empty_result,
    rows_from_sql,
    table_columns,
)
from pipeline.flags.params import F02_EXPRESS_DAYS

FLAG_ID = "F02"

log = __import__("logging").getLogger(__name__)

_SQL = f"""
WITH {PROCESO_DEDUP_CTE}
SELECT
    fc.id_contrato AS key,
    (
        dp.fecha_matricula IS NOT NULL
        AND fp.fecha_publicacion IS NOT NULL
        AND dp.fecha_matricula <= fp.fecha_publicacion
        AND DATE_DIFF('day', dp.fecha_matricula, fp.fecha_publicacion) <= {F02_EXPRESS_DAYS}
    ) AS fired,
    dp.fecha_matricula AS fecha_matricula,
    fp.fecha_publicacion AS fecha_publicacion,
    DATE_DIFF('day', dp.fecha_matricula, fp.fecha_publicacion) AS dias_desde_matricula
FROM {CONTRATO_PROCESO_JOIN}
JOIN dim_proveedor dp ON dp.doc_proveedor_norm = fc.doc_proveedor_norm
WHERE dp.fecha_matricula IS NOT NULL
  AND fp.fecha_publicacion IS NOT NULL
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    if "fecha_matricula" not in table_columns(con, "dim_proveedor"):
        log.warning(
            "F02: dim_proveedor.fecha_matricula not present (RUES enrichment is M4's "
            "job) -- returning an empty, not-applicable result. Wire up M4 by adding "
            "a DATE column `fecha_matricula` to dim_proveedor; no change needed here."
        )
        return empty_result()
    return rows_from_sql(con, _SQL, FLAG_ID)
