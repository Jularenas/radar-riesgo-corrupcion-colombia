"""
F10 -- Ventana electoral (contract level, weight 6).

PLAN.md definition: direct contract signed inside a Ley de Garantías
restricted window (refs/ventanas_electorales.csv, loaded as `ref_ventanas`).
Applicable population = direct contracts (`modalidad_norm =
'CONTRATACION_DIRECTA'`) with a signature date.

Sample-specific note (see M3 report): the 2023 sample is dominated by a
single year, and one election window (VE2023T, ~4 months) falls inside it,
so the observed fire rate on the sample (~19%) is not representative of a
real multi-year dataset, where restricted windows cover a much smaller
fraction of total contracting time. Documented, not "fixed", since it's a
property of the sample rather than a bug.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import F10_MODALIDAD

FLAG_ID = "F10"

_SQL = f"""
-- ref_ventanas windows are curated and verified non-overlapping (see
-- refs/ventanas_electorales.csv), so a plain LEFT JOIN is safe here: at
-- most one window can match a given fecha_firma, no fan-out risk.
SELECT
    fc.id_contrato AS key,
    (v.window_id IS NOT NULL) AS fired,
    fc.fecha_firma AS fecha_firma,
    v.window_id AS window_id,
    v.tipo AS tipo_ventana,
    v.descripcion AS descripcion_ventana
FROM fct_contrato fc
LEFT JOIN ref_ventanas v ON fc.fecha_firma BETWEEN v.inicio AND v.fin
WHERE fc.modalidad_norm = '{F10_MODALIDAD}' AND fc.fecha_firma IS NOT NULL
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
