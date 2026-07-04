"""
F12 -- Concentración/dependencia (entity level, weight 8).

PLAN.md definition (two independent conditions, either fires the flag):
  (a) a single supplier captures >50% of the entity's annual value
      (entity has >=5 contracts that year).
  (b) that supplier gets >80% of its own annual SECOP revenue from this one
      entity.

Grain = (entity, year), evaluated against that entity-year's single largest
supplier by value -- i.e. "does this entity's top supplier that year look
like a captured/dependent relationship". Both conditions are checked
against the same top supplier rather than independently against "any"
supplier, which keeps the flag to one evaluation per entity-year (avoids
the ambiguity of two different suppliers each partially qualifying).

Adaptation (real-data): PLAN.md gives condition (a) a ">=5 contracts" floor
on the entity but gives condition (b) none. Applied to the supplier side
literally, condition (b) alone fires for ~59% of entity-years in the
sample, because most suppliers in a single-year sample only ever work with
one entity and are trivially "100% dependent" on it by coincidence, not by
any meaningful pattern. Reusing the same >=5-contracts floor on the
supplier's *own* annual contract count (params.F12_MIN_CONTRATOS_PROVEEDOR)
brings that down to a defensible rate (see M3 report) -- a supplier needs
an actual track record before "dependency" is a meaningful signal.
Documented deviation from the literal PLAN.md wording.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql
from pipeline.flags.params import (
    F12_ENTITY_SHARE_THRESHOLD,
    F12_MIN_CONTRATOS_ENTIDAD,
    F12_MIN_CONTRATOS_PROVEEDOR,
    F12_SUPPLIER_DEPENDENCE_THRESHOLD,
)

FLAG_ID = "F12"

_SQL = f"""
WITH ent_year AS (
    SELECT nit_entidad_norm, anio, SUM(valor_contrato) AS valor_anual, COUNT(*) AS n_contratos_anual
    FROM fct_contrato
    WHERE nit_entidad_norm IS NOT NULL AND nit_entidad_norm != '' AND valor_contrato IS NOT NULL AND anio IS NOT NULL
    GROUP BY 1, 2
),
sup_year AS (
    SELECT doc_proveedor_norm, anio, SUM(valor_contrato) AS valor_anual_proveedor, COUNT(*) AS n_contratos_proveedor_anual
    FROM fct_contrato
    WHERE doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != '' AND valor_contrato IS NOT NULL AND anio IS NOT NULL
    GROUP BY 1, 2
),
ent_sup_year AS (
    SELECT nit_entidad_norm, doc_proveedor_norm, anio, SUM(valor_contrato) AS valor
    FROM fct_contrato
    WHERE nit_entidad_norm IS NOT NULL AND nit_entidad_norm != ''
      AND doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != ''
      AND valor_contrato IS NOT NULL AND anio IS NOT NULL
    GROUP BY 1, 2, 3
),
ranked AS (
    SELECT
        esy.nit_entidad_norm, esy.anio, esy.doc_proveedor_norm, esy.valor,
        ey.valor_anual AS valor_anual_entidad, ey.n_contratos_anual AS n_contratos_entidad,
        esy.valor / NULLIF(ey.valor_anual, 0) AS share_entidad,
        sy.valor_anual_proveedor, sy.n_contratos_proveedor_anual,
        esy.valor / NULLIF(sy.valor_anual_proveedor, 0) AS share_proveedor,
        ROW_NUMBER() OVER (PARTITION BY esy.nit_entidad_norm, esy.anio ORDER BY esy.valor DESC) AS rn
    FROM ent_sup_year esy
    JOIN ent_year ey USING (nit_entidad_norm, anio)
    JOIN sup_year sy ON sy.doc_proveedor_norm = esy.doc_proveedor_norm AND sy.anio = esy.anio
    WHERE ey.n_contratos_anual >= {F12_MIN_CONTRATOS_ENTIDAD}
),
top_sup AS (
    SELECT * FROM ranked WHERE rn = 1
)
SELECT
    nit_entidad_norm AS key,
    (
        share_entidad > {F12_ENTITY_SHARE_THRESHOLD}
        OR (share_proveedor > {F12_SUPPLIER_DEPENDENCE_THRESHOLD} AND n_contratos_proveedor_anual >= {F12_MIN_CONTRATOS_PROVEEDOR})
    ) AS fired,
    anio AS anio,
    doc_proveedor_norm AS doc_proveedor_dominante,
    n_contratos_entidad AS n_contratos_entidad_anual,
    share_entidad AS participacion_proveedor_en_entidad,
    (share_entidad > {F12_ENTITY_SHARE_THRESHOLD}) AS condicion_a_captura_entidad,
    n_contratos_proveedor_anual AS n_contratos_proveedor_anual,
    share_proveedor AS dependencia_proveedor_en_entidad,
    (
        share_proveedor > {F12_SUPPLIER_DEPENDENCE_THRESHOLD}
        AND n_contratos_proveedor_anual >= {F12_MIN_CONTRATOS_PROVEEDOR}
    ) AS condicion_b_dependencia_proveedor
FROM top_sup
"""


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    return rows_from_sql(con, _SQL, FLAG_ID)
