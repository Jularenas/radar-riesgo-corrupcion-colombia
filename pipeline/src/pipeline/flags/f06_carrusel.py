"""
F06 -- Carrusel (contract level, weight 12).

PLAN.md definition: within entity (or municipality x UNSPSC) over a rolling
24-month window: 2-4 distinct winners, >=8 competitive processes, each
winner share >=15%, alternation index >=0.6 -> flag member contracts.

Two simplifications from the literal PLAN.md wording, made for
tractability in SQL and documented as deviations:

1. Group = (entity, UNSPSC segment), not (municipality, UNSPSC). Entity is
   the more direct interpretation of "within entity" and is what the other
   entity-scoped flags (F04, F12) use.
2. "Rolling 24 months" is implemented as sequential, non-overlapping
   730-day buckets anchored at each group's first competitive contract,
   rather than a true sliding window over every possible 24-month start
   date. A true rolling window would let a single long-running rotation
   pattern qualify under many overlapping windows simultaneously, which
   makes "does this contract belong to a carousel, yes/no" ambiguous
   (which window's evidence do you show?). Discrete buckets give each
   contract exactly one group to be judged against, at the cost of
   occasionally splitting a real cross-boundary rotation into two buckets
   that individually fall short of the >=8-process floor.

Alternation index = (number of winner switches between consecutive
contracts, ordered by signature date, within the bucket) / (n - 1).

Applicable population = competitive contracts with a full identity key
(entity, supplier, UNSPSC segment, signature date). Observed on the sample
mart: every (entity, UNSPSC, bucket) group with >=8 processes has 10-49
distinct winners -- i.e. genuinely competitive/diverse markets, not a
tight 2-4-supplier rotation -- so F06 fires zero times on the sample. See
the M3 report for why that's treated as a legitimate finding rather than a
bug (covered instead by a synthetic positive fixture in the unit tests).
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import (
    F06_MAX_WINNERS,
    F06_MIN_ALTERNATION_INDEX,
    F06_MIN_PROCESOS,
    F06_MIN_WINNER_SHARE,
    F06_MIN_WINNERS,
    F06_WINDOW_DAYS,
)

FLAG_ID = "F06"

_SQL = f"""
WITH competitive AS (
    SELECT id_contrato, nit_entidad_norm, unspsc_segmento, doc_proveedor_norm, fecha_firma, valor_contrato
    FROM fct_contrato
    WHERE es_competitiva
      AND nit_entidad_norm IS NOT NULL AND nit_entidad_norm != ''
      AND doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != ''
      AND unspsc_segmento IS NOT NULL
      AND fecha_firma IS NOT NULL
),
bucketed AS (
    SELECT *,
        CAST(FLOOR(
            DATE_DIFF('day', MIN(fecha_firma) OVER (PARTITION BY nit_entidad_norm, unspsc_segmento), fecha_firma)
            / {F06_WINDOW_DAYS}.0
        ) AS INTEGER) AS bucket
    FROM competitive
),
with_switch AS (
    SELECT *,
        CASE
            WHEN doc_proveedor_norm != LAG(doc_proveedor_norm) OVER (
                PARTITION BY nit_entidad_norm, unspsc_segmento, bucket ORDER BY fecha_firma, id_contrato
            ) THEN 1 ELSE 0
        END AS switched
    FROM bucketed
),
group_stats AS (
    SELECT nit_entidad_norm, unspsc_segmento, bucket,
        COUNT(*) AS n_procesos,
        COUNT(DISTINCT doc_proveedor_norm) AS n_winners,
        SUM(switched) AS n_switches,
        COUNT(*) - 1 AS n_transitions
    FROM with_switch
    GROUP BY 1, 2, 3
),
winner_shares AS (
    SELECT nit_entidad_norm, unspsc_segmento, bucket, doc_proveedor_norm, COUNT(*) AS n_contratos_winner
    FROM bucketed
    GROUP BY 1, 2, 3, 4
),
winner_min_share AS (
    SELECT ws.nit_entidad_norm, ws.unspsc_segmento, ws.bucket,
        MIN(ws.n_contratos_winner * 1.0 / gs.n_procesos) AS min_share
    FROM winner_shares ws
    JOIN group_stats gs USING (nit_entidad_norm, unspsc_segmento, bucket)
    GROUP BY 1, 2, 3
),
bucket_eval AS (
    SELECT gs.nit_entidad_norm, gs.unspsc_segmento, gs.bucket, gs.n_procesos, gs.n_winners, wms.min_share,
        CASE WHEN gs.n_transitions > 0 THEN gs.n_switches * 1.0 / gs.n_transitions ELSE 0 END AS alternation_index,
        (
            gs.n_procesos >= {F06_MIN_PROCESOS}
            AND gs.n_winners BETWEEN {F06_MIN_WINNERS} AND {F06_MAX_WINNERS}
            AND wms.min_share >= {F06_MIN_WINNER_SHARE}
            AND (CASE WHEN gs.n_transitions > 0 THEN gs.n_switches * 1.0 / gs.n_transitions ELSE 0 END) >= {F06_MIN_ALTERNATION_INDEX}
        ) AS bucket_fired
    FROM group_stats gs
    JOIN winner_min_share wms USING (nit_entidad_norm, unspsc_segmento, bucket)
)
SELECT
    b.id_contrato AS key,
    COALESCE(be.bucket_fired, false) AS fired,
    b.nit_entidad_norm AS nit_entidad_norm,
    b.unspsc_segmento AS unspsc_segmento,
    b.bucket AS bucket_24m,
    b.doc_proveedor_norm AS doc_proveedor_norm,
    be.n_procesos AS n_procesos_grupo,
    be.n_winners AS n_ganadores_distintos,
    be.min_share AS participacion_minima_ganador,
    be.alternation_index AS indice_alternancia
FROM bucketed b
JOIN bucket_eval be USING (nit_entidad_norm, unspsc_segmento, bucket)
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
