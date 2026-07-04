"""
F13 -- Objeto vago (contract level, weight 3).

PLAN.md definition: contract object < 40 chars OR top-decile boilerplate
similarity. See params.py for how "top-decile boilerplate similarity" is
concretely operationalized (exact-text repetition frequency, top decile by
row over the whole mart) -- a cheap, well-defined proxy for fuzzy text
similarity, which isn't practical to compute in plain SQL at this scale.

Applicable population = contracts with a non-null object description (100%
of the sample).
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import F13_BOILERPLATE_PERCENTILE, F13_MIN_LENGTH

FLAG_ID = "F13"

_SQL = f"""
WITH norm AS (
    SELECT id_contrato,
        trim(objeto_del_contrato) AS objeto_trim,
        upper(trim(regexp_replace(objeto_del_contrato, '\\s+', ' ', 'g'))) AS objeto_norm
    FROM fct_contrato
    WHERE objeto_del_contrato IS NOT NULL
),
freq AS (
    SELECT *, COUNT(*) OVER (PARTITION BY objeto_norm) AS freq_objeto
    FROM norm
),
thr AS (
    SELECT PERCENTILE_CONT({F13_BOILERPLATE_PERCENTILE}) WITHIN GROUP (ORDER BY freq_objeto) AS p90
    FROM freq
)
SELECT
    freq.id_contrato AS key,
    (LENGTH(freq.objeto_trim) < {F13_MIN_LENGTH} OR freq.freq_objeto >= thr.p90) AS fired,
    LENGTH(freq.objeto_trim) AS longitud_objeto,
    freq.freq_objeto AS frecuencia_objeto,
    thr.p90 AS umbral_decil_superior,
    (LENGTH(freq.objeto_trim) < {F13_MIN_LENGTH}) AS objeto_muy_corto,
    (freq.freq_objeto >= thr.p90) AS objeto_repetitivo
FROM freq, thr
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
