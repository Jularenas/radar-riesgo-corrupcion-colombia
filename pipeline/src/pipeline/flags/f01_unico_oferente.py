"""
F01 -- Único oferente (contract level, weight 15).

PLAN.md definition: competitive modality (licitación, selección abreviada,
concurso de méritos) AND `proveedores_unicos_con_respuestas` = 1.

That bidder count lives on the *process*, not the contract, so this flag
needs the fct_contrato <-> fct_proceso join (via proceso_dedup, see
common.PROCESO_DEDUP_CTE -- the raw join key fans out ~4% of the time).
Applicable population = contracts that (a) join to a process at all and
(b) are flagged competitive. Coverage of that join is the real bottleneck:
see run_all's summary output / M3 report for the observed rate.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import CONTRATO_PROCESO_JOIN, PROCESO_DEDUP_CTE, FlagRow, rows_from_sql
from pipeline.flags.params import F01_MIN_OFERENTES_UNICOS

FLAG_ID = "F01"

_SQL = f"""
WITH {PROCESO_DEDUP_CTE}
SELECT
    fc.id_contrato AS key,
    (fp.num_oferentes_unicos = {F01_MIN_OFERENTES_UNICOS}) AS fired,
    fp.num_oferentes_unicos AS num_oferentes_unicos,
    fc.modalidad_norm AS modalidad_norm,
    fp.num_invitados AS num_invitados,
    fp.num_respuestas AS num_respuestas,
    fp.id_del_proceso AS id_del_proceso
FROM {CONTRATO_PROCESO_JOIN}
WHERE fc.es_competitiva
  AND fp.num_oferentes_unicos IS NOT NULL
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
