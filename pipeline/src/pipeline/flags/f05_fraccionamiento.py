"""
F05 -- Fraccionamiento (contract level, weight 12).

PLAN.md definition: >=3 direct contracts, same entity+supplier, same UNSPSC
segment, within 90 days, summing > 280 SMMLV (most conservative
menor-cuantía bracket; SMMLV value looked up by the contract's own year from
refs/smmlv.csv).

Implementation note: rather than enumerating every possible 90-day window
(an "islands" problem), each contract gets a window *centered on itself*:
DuckDB's `RANGE BETWEEN INTERVAL 90 DAYS PRECEDING AND INTERVAL 90 DAYS
FOLLOWING`, partitioned by (entity, supplier, UNSPSC segment) and ordered by
signature date. A contract fires if the contracts within +-90 days of it
(inclusive, same group) number >=3 and their combined value crosses the
SMMLV threshold. This is a defensible, cheap-to-compute approximation of
"clustered within a 90-day window" -- every member of a genuine cluster
satisfies it, since any two contracts in a <=90-day-wide cluster are within
90 days of each other by construction.

Applicable population = direct contracts with a full identity key (entity,
supplier, UNSPSC, date, value all present) AND a resolvable SMMLV value for
their signature year (a handful of contracts have corrupt dates far outside
[2011, 2026] -- see docs/PROFILING.md date-sanity section -- and are
excluded rather than guessed at).
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import F05_MIN_CONTRATOS, F05_SMMLV_MULTIPLE, F05_WINDOW_DAYS

FLAG_ID = "F05"

_SQL = f"""
WITH directa AS (
    SELECT id_contrato, nit_entidad_norm, doc_proveedor_norm, unspsc_segmento, fecha_firma, valor_contrato, anio
    FROM fct_contrato
    WHERE modalidad_norm = 'CONTRATACION_DIRECTA'
      AND nit_entidad_norm IS NOT NULL AND nit_entidad_norm != ''
      AND doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != ''
      AND unspsc_segmento IS NOT NULL
      AND fecha_firma IS NOT NULL
      AND valor_contrato IS NOT NULL
),
win AS (
    SELECT d.*,
        COUNT(*) OVER w AS n_en_ventana,
        SUM(valor_contrato) OVER w AS suma_en_ventana
    FROM directa d
    WINDOW w AS (
        PARTITION BY nit_entidad_norm, doc_proveedor_norm, unspsc_segmento
        ORDER BY fecha_firma
        RANGE BETWEEN INTERVAL {F05_WINDOW_DAYS} DAYS PRECEDING AND INTERVAL {F05_WINDOW_DAYS} DAYS FOLLOWING
    )
)
SELECT
    w.id_contrato AS key,
    (w.n_en_ventana >= {F05_MIN_CONTRATOS} AND w.suma_en_ventana > {F05_SMMLV_MULTIPLE} * s.value_cop) AS fired,
    w.nit_entidad_norm AS nit_entidad_norm,
    w.doc_proveedor_norm AS doc_proveedor_norm,
    w.unspsc_segmento AS unspsc_segmento,
    w.n_en_ventana AS n_contratos_ventana,
    w.suma_en_ventana AS suma_valor_ventana,
    {F05_SMMLV_MULTIPLE} * s.value_cop AS umbral_smmlv_cop
FROM win w
JOIN ref_smmlv s ON w.anio = s.year
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
