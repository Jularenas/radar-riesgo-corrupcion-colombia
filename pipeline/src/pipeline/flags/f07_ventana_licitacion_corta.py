"""
F07 -- Ventana de licitación corta (contract level, weight 8).

PLAN.md definition: days(publication -> bid deadline) below a per-modality
floor (licitación <10, abreviada <5). Bid deadline = fct_proceso's
`fecha_recepcion_respuestas` (S2's "fecha de recepción de ofertas" column,
truncated by Socrata to `fecha_de_recepcion_de`; 87% null in the sample per
docs/PROFILING.md, so this flag's applicable population is small).

Needs the contract<->process join (see common.PROCESO_DEDUP_CTE). Only
modalities with a floor defined in PLAN.md (params.F07_FLOOR_DAYS) are in
scope; other competitive modalities (e.g. concurso de méritos) have no
defined floor and are excluded rather than guessed at.

Data-quality guard: a couple of rows in the sample have
fecha_recepcion_respuestas *before* fecha_publicacion (negative day count),
which is a contradictory/bad timestamp pair, not a genuine short window --
those are excluded from the applicable population rather than counted as
fired (a negative gap trivially satisfies "< floor" and would be a false
positive).
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import CONTRATO_PROCESO_JOIN, PROCESO_DEDUP_CTE, FlagRow, rows_from_sql
from pipeline.flags.params import F07_FLOOR_DAYS

FLAG_ID = "F07"

_MODALIDAD_LIST = ", ".join(f"'{m}'" for m in F07_FLOOR_DAYS)
_FLOOR_CASE = " ".join(f"WHEN '{m}' THEN {d}" for m, d in F07_FLOOR_DAYS.items())

_SQL = f"""
WITH {PROCESO_DEDUP_CTE}
SELECT
    fc.id_contrato AS key,
    (DATE_DIFF('day', fp.fecha_publicacion, fp.fecha_recepcion_respuestas) < (CASE fc.modalidad_norm {_FLOOR_CASE} END)) AS fired,
    fc.modalidad_norm AS modalidad_norm,
    fp.fecha_publicacion AS fecha_publicacion,
    fp.fecha_recepcion_respuestas AS fecha_recepcion_respuestas,
    DATE_DIFF('day', fp.fecha_publicacion, fp.fecha_recepcion_respuestas) AS dias_ventana,
    (CASE fc.modalidad_norm {_FLOOR_CASE} END) AS piso_dias
FROM {CONTRATO_PROCESO_JOIN}
WHERE fc.es_competitiva
  AND fc.modalidad_norm IN ({_MODALIDAD_LIST})
  AND fp.fecha_publicacion IS NOT NULL
  AND fp.fecha_recepcion_respuestas IS NOT NULL
  AND DATE_DIFF('day', fp.fecha_publicacion, fp.fecha_recepcion_respuestas) >= 0
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
