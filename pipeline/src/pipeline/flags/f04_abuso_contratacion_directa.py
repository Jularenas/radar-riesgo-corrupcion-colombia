"""
F04 -- Abuso de contratación directa (entity level, weight 8).

PLAN.md definition: entity's share of value via contratación directa >= 2
z-scores above its peer group (same entity level + department).

`dim_entidad` has no `nivel_entidad` column in the M2 mart (verified via
PRAGMA table_info), so the peer group falls back to "same department"
(`cod_dpto`) alone, per the milestone instructions. If a future milestone
adds `nivel_entidad` to dim_entidad, this module picks it up automatically
(peer group becomes nivel_entidad x cod_dpto) with no code change needed.

Adaptation: z-scores need a peer group with actual spread. Entities with
very few contracts (a 1-contract entity is trivially 0% or 100% direct) and
tiny peer groups produce unstable/meaningless z-scores, so both the
evaluated entity and its peer group are required to clear a minimum size
(params.F04_MIN_CONTRATOS_ENTIDAD / F04_MIN_PEER_GROUP_SIZE). This isn't in
PLAN.md; documented deviation.
"""

from __future__ import annotations

import duckdb

from pipeline.flags.common import FlagRow, rows_from_sql, table_columns
from pipeline.flags.params import (
    F04_MIN_CONTRATOS_ENTIDAD,
    F04_MIN_PEER_GROUP_SIZE,
    F04_Z_SCORE_THRESHOLD,
)

FLAG_ID = "F04"


def compute(con: duckdb.DuckDBPyConnection) -> list[FlagRow]:
    cols = table_columns(con, "dim_entidad")
    peer_cols = ["nivel_entidad", "cod_dpto"] if "nivel_entidad" in cols else ["cod_dpto"]
    peer_using = ", ".join(peer_cols)
    not_null_guard = " AND ".join(f"d.{c} IS NOT NULL" for c in peer_cols)

    sql = f"""
    WITH ent_directa AS (
        SELECT
            nit_entidad_norm,
            SUM(valor_contrato) FILTER (WHERE modalidad_norm = 'CONTRATACION_DIRECTA') AS valor_directa,
            SUM(valor_contrato) AS valor_total_calc,
            COUNT(*) AS n_contratos_calc
        FROM fct_contrato
        WHERE nit_entidad_norm IS NOT NULL AND nit_entidad_norm != '' AND valor_contrato IS NOT NULL
        GROUP BY 1
    ),
    ent_share AS (
        SELECT
            e.nit_entidad_norm, {peer_using}, d.nombre_entidad,
            COALESCE(e.valor_directa, 0) / NULLIF(e.valor_total_calc, 0) AS share_directa,
            e.n_contratos_calc
        FROM ent_directa e
        JOIN dim_entidad d ON d.nit_entidad_norm = e.nit_entidad_norm
        WHERE {not_null_guard}
          AND e.n_contratos_calc >= {F04_MIN_CONTRATOS_ENTIDAD}
    ),
    peer_stats AS (
        SELECT {peer_using},
            AVG(share_directa) AS mean_share,
            STDDEV_POP(share_directa) AS sd_share,
            COUNT(*) AS n_peers
        FROM ent_share
        GROUP BY {peer_using}
    ),
    z AS (
        SELECT es.*, ps.mean_share, ps.sd_share, ps.n_peers,
            (es.share_directa - ps.mean_share) / NULLIF(ps.sd_share, 0) AS z_score
        FROM ent_share es
        JOIN peer_stats ps USING ({peer_using})
        WHERE ps.n_peers >= {F04_MIN_PEER_GROUP_SIZE}
    )
    SELECT
        nit_entidad_norm AS key,
        (z_score >= {F04_Z_SCORE_THRESHOLD}) AS fired,
        nombre_entidad AS nombre_entidad,
        {peer_using},
        share_directa AS share_directa,
        mean_share AS mean_share_peers,
        sd_share AS sd_share_peers,
        n_peers AS n_peers,
        n_contratos_calc AS n_contratos,
        z_score AS z_score
    FROM z
    WHERE z_score IS NOT NULL
    """
    return rows_from_sql(con, sql, FLAG_ID)
