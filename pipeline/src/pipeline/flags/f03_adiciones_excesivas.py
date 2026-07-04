"""
F03 -- Adiciones excesivas (contract level, weight 12).

PLAN.md definition, refined by M2's docs/PROFILING.md column-profiling
(SECOP II has no direct money-addition column):

  - Time sub-flag (both sources): dias_adicionados >= 0.5 * duracion_dias_inicial.
  - Money sub-flag (SECOP2): requires the contract<->process join;
    valor_contrato / valor_adjudicacion - 1 >= 0.4.
  - Money sub-flag (SECOP1): direct columns
    valor_total_de_adiciones / cuantia_contrato >= 0.4.
  - Fires if EITHER sub-flag is true, evaluated over whichever sub-flags are
    computable for that row (a row with only the time sub-flag computable is
    still in the applicable population; it just can't fire on money).

Three data-quality / performance wrinkles found while building this against
the real M2 mart (not just PROFILING.md's recommendation) required a fix:

1. fct_contrato does NOT carry `valor_total_de_adiciones` /
   `valor_contrato_con_adiciones` forward for SECOP1 rows (build.py's
   secop1_base CTE drops them). They still exist on `stg_secop1`, a table
   in the same mart, so the SECOP1 money sub-flag is recovered by joining
   fct_contrato.row_id back to stg_secop1.":id" instead of giving up on it.
2. stg_secop1 is NOT deduplicated by ":id" (527 rows / 327 distinct in the
   sample) the way stg_s1/stg_s2 are -- joining directly would fan out and
   double count a handful of contracts. Deduplicated here defensively
   before the join (arbitrary-but-stable tie-break; this slice is tiny and
   only used for known-case backtesting per PLAN.md).
3. The two joins are source-specific (SECOP2 rows join proceso_dedup,
   SECOP1 rows join secop1_dedup). Expressing that as
   `LEFT JOIN ... ON fc.source = 'SECOP2' AND fc.key = other.key` measured
   at ~95s on the sample mart: DuckDB falls back to a blockwise nested-loop
   join (verified via EXPLAIN) because the ON clause mixes a same-table
   filter into the join condition, so it can't hash on a pure equality.
   Splitting fct_contrato into two single-source CTEs *before* joining (each
   joined with a pure-equality ON clause, then UNION ALL'd back together)
   lets DuckDB pick a hash join instead -- same result, ~0.05s.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import PROCESO_DEDUP_CTE, FlagRow, rows_from_sql
from pipeline.flags.params import F03_MONEY_ADDITION_RATIO, F03_TIME_ADDITION_RATIO

FLAG_ID = "F03"

_SQL = f"""
WITH {PROCESO_DEDUP_CTE},
secop1_dedup AS (
    SELECT * EXCLUDE (_rn) FROM (
        SELECT s1.*,
            ROW_NUMBER() OVER (PARTITION BY ":id" ORDER BY ":id") AS _rn
        FROM stg_secop1 s1
    )
    WHERE _rn = 1
),
base_secop2 AS (
    SELECT
        fc.id_contrato, fc.source, fc.dias_adicionados, fc.duracion_dias_inicial, fc.valor_contrato,
        fp.valor_adjudicacion,
        NULL::DOUBLE AS s1_valor_adiciones
    FROM (SELECT * FROM fct_contrato WHERE source = 'SECOP2') fc
    LEFT JOIN proceso_dedup fp ON fc.proceso_de_compra = fp.referencia
),
base_secop1 AS (
    SELECT
        fc.id_contrato, fc.source, fc.dias_adicionados, fc.duracion_dias_inicial, fc.valor_contrato,
        NULL::DOUBLE AS valor_adjudicacion,
        TRY_CAST(s1.valor_total_de_adiciones AS DOUBLE) AS s1_valor_adiciones
    FROM (SELECT * FROM fct_contrato WHERE source = 'SECOP1') fc
    LEFT JOIN secop1_dedup s1 ON fc.row_id = s1.":id"
),
base AS (
    SELECT * FROM base_secop2
    UNION ALL
    SELECT * FROM base_secop1
),
calc AS (
    SELECT
        *,
        (duracion_dias_inicial IS NOT NULL AND duracion_dias_inicial > 0) AS time_computable,
        (source = 'SECOP2' AND valor_adjudicacion IS NOT NULL AND valor_adjudicacion > 0) AS money_computable_secop2,
        (source = 'SECOP1' AND s1_valor_adiciones IS NOT NULL AND valor_contrato > 0) AS money_computable_secop1
    FROM base
),
flagged AS (
    SELECT
        *,
        (time_computable AND dias_adicionados >= {F03_TIME_ADDITION_RATIO} * duracion_dias_inicial) AS f03_tiempo,
        (
            money_computable_secop2
            AND (valor_contrato / NULLIF(valor_adjudicacion, 0) - 1) >= {F03_MONEY_ADDITION_RATIO}
        ) AS f03_dinero_secop2,
        (
            money_computable_secop1
            AND (s1_valor_adiciones / NULLIF(valor_contrato, 0)) >= {F03_MONEY_ADDITION_RATIO}
        ) AS f03_dinero_secop1
    FROM calc
)
SELECT
    id_contrato AS key,
    (COALESCE(f03_tiempo, false) OR COALESCE(f03_dinero_secop2, false) OR COALESCE(f03_dinero_secop1, false)) AS fired,
    source AS source,
    dias_adicionados AS dias_adicionados,
    duracion_dias_inicial AS duracion_dias_inicial,
    f03_tiempo AS f03_tiempo,
    CASE WHEN money_computable_secop2 THEN valor_contrato / NULLIF(valor_adjudicacion, 0) - 1
         WHEN money_computable_secop1 THEN s1_valor_adiciones / NULLIF(valor_contrato, 0)
         ELSE NULL END AS ratio_adicion_dinero,
    (COALESCE(f03_dinero_secop2, false) OR COALESCE(f03_dinero_secop1, false)) AS f03_dinero,
    CASE WHEN money_computable_secop2 THEN 'secop2_join'
         WHEN money_computable_secop1 THEN 'secop1_directo'
         ELSE NULL END AS fuente_dinero
FROM flagged
WHERE time_computable OR money_computable_secop2 OR money_computable_secop1
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
