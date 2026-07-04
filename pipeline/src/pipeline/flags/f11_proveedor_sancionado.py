"""
F11 -- Proveedor sancionado (contract level, weight 20 -- the heaviest flag).

PLAN.md definition: supplier doc in L1/L2/L3/L4 (`sanciones`, joined on
`doc_norm`; the mart has no `nit_base` column so `doc_proveedor_norm` <->
`doc_norm` is the only usable key). Only sanctions dated *before* signing
count for the `fired` (scoring-relevant) value; any-date matches are also
surfaced in the evidence as context, per PLAN.md ("any-date version shown
as context").

A supplier can have multiple sanciones rows (45,621 rows / 16,005 distinct
`doc_norm` in the sample), so a naive `fct_contrato JOIN sanciones` fans
out to one row per (contract, sanction) pair. Aggregated here to one row
per physical contract row via a `ROW_NUMBER() OVER ()` surrogate key rather
than grouping by `id_contrato` directly, because `id_contrato` itself is
not perfectly unique in fct_contrato (300,349 distinct of 300,498 rows --
a preexisting M2-level artifact, most of it from the un-deduplicated
SECOP1 slice union in build.py) and grouping on it would silently merge
two different physical contracts that happen to share a reported number.

Applicable population = contracts with a usable supplier document number.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql

FLAG_ID = "F11"

_SQL = """
WITH pop AS (
    SELECT ROW_NUMBER() OVER () AS _rid, id_contrato, fecha_firma, doc_proveedor_norm
    FROM fct_contrato
    WHERE doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != ''
),
agg AS (
    SELECT p._rid,
        COUNT(*) FILTER (WHERE s.fecha_sancion < p.fecha_firma) AS n_sanciones_antes_firma,
        COUNT(*) AS n_sanciones_total,
        STRING_AGG(DISTINCT s.fuente, ', ') FILTER (WHERE s.fecha_sancion < p.fecha_firma) AS fuentes_antes_firma,
        STRING_AGG(DISTINCT s.fuente, ', ') AS fuentes_total_contexto,
        MAX(s.fecha_sancion) FILTER (WHERE s.fecha_sancion < p.fecha_firma) AS sancion_mas_reciente_antes_firma
    FROM pop p
    JOIN sanciones s ON s.doc_norm = p.doc_proveedor_norm
    GROUP BY p._rid
)
SELECT
    p.id_contrato AS key,
    COALESCE(a.n_sanciones_antes_firma, 0) > 0 AS fired,
    COALESCE(a.n_sanciones_antes_firma, 0) AS n_sanciones_antes_firma,
    COALESCE(a.n_sanciones_total, 0) AS n_sanciones_total_contexto,
    a.fuentes_antes_firma AS fuentes_antes_firma,
    a.fuentes_total_contexto AS fuentes_total_contexto,
    a.sancion_mas_reciente_antes_firma AS sancion_mas_reciente_antes_firma
FROM pop p
LEFT JOIN agg a ON a._rid = p._rid
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
