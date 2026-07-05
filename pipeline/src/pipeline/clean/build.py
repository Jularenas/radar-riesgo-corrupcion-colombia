"""
M2 canonical marts builder.

Usage:
    uv run python -m pipeline.clean.build          # sample mode (default)
    uv run python -m pipeline.clean.build --sample  # same
    uv run python -m pipeline.clean.build --full    # use full raw datasets

Output: data/marts/corruption.duckdb
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
_PIPELINE_ROOT = _HERE.parents[3]  # src/pipeline/clean/build.py → pipeline/
_DATA_ROOT = _PIPELINE_ROOT / "data"
_REFS_DIR = _HERE.parent.parent / "refs"  # src/pipeline/refs/

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DuckDB helpers
# ---------------------------------------------------------------------------

def _glob(db: duckdb.DuckDBPyConnection, pattern: str, union_by_name: bool = True) -> str:
    """Return a read_parquet(...) expression string."""
    flag = ", union_by_name=true" if union_by_name else ""
    return f"read_parquet('{pattern}'{flag})"


def _run(db: duckdb.DuckDBPyConnection, sql: str, description: str = "") -> None:
    if description:
        log.info("%s", description)
    db.execute(sql)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(mode: str = "sample") -> None:
    raw_base = _DATA_ROOT / "raw"
    if mode == "sample":
        s1_glob = str(raw_base / "sample/s1_secop2_contratos/part-*.parquet")
        s2_glob = str(raw_base / "sample/s2_secop2_procesos/part-*.parquet")
    else:
        s1_glob = str(raw_base / "s1_secop2_contratos/part-*.parquet")
        s2_glob = str(raw_base / "s2_secop2_procesos/part-*.parquet")

    l1_glob = str(raw_base / "l1_responsabilidad_fiscal/part-*.parquet")
    l2_glob = str(raw_base / "l2_multas_secop1/part-*.parquet")
    l3_glob = str(raw_base / "l3_multas_secop2/part-*.parquet")
    l4_glob = str(raw_base / "l4_siri/part-*.parquet")
    divipola_glob = str(raw_base / "e2_divipola/part-*.parquet")
    monitor_dir = raw_base / "monitor_ciudadano"

    db_path = _DATA_ROOT / "marts" / "corruption.duckdb"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    log.info("Building %s (mode=%s)", db_path, mode)

    db = duckdb.connect(str(db_path))

    # Install/load ICU extension for Unicode-aware string ops
    try:
        db.execute("INSTALL icu; LOAD icu;")
    except Exception:
        pass  # already installed

    # ---------------------------------------------------------------------------
    # 0. Drop existing marts (idempotent)
    # ---------------------------------------------------------------------------
    for tbl in [
        "fct_contrato", "fct_proceso", "dim_entidad", "dim_proveedor",
        "sanciones", "monitor_ciudadano_hechos", "divipola",
        "stg_s1", "stg_s2", "stg_secop1",
        "ref_modalidades", "ref_smmlv", "ref_ventanas",
        "quarantine",
    ]:
        db.execute(f"DROP TABLE IF EXISTS {tbl}")

    # ---------------------------------------------------------------------------
    # 1. Reference tables
    # ---------------------------------------------------------------------------
    log.info("Loading reference tables")

    db.execute(f"""
        CREATE TABLE ref_modalidades AS
        SELECT * FROM read_csv('{_REFS_DIR}/modalidades.csv', header=true, auto_detect=true)
    """)

    db.execute(f"""
        CREATE TABLE ref_smmlv AS
        SELECT * FROM read_csv('{_REFS_DIR}/smmlv.csv', header=true, auto_detect=true)
    """)

    db.execute(f"""
        CREATE TABLE ref_ventanas AS
        SELECT * FROM read_csv('{_REFS_DIR}/ventanas_electorales.csv', header=true, auto_detect=true)
    """)

    # ---------------------------------------------------------------------------
    # 2. DIVIPOLA
    # ---------------------------------------------------------------------------
    log.info("Building divipola")
    db.execute(f"""
        CREATE TABLE divipola AS
        SELECT
            cod_dpto,
            dpto,
            cod_mpio,
            nom_mpio AS municipio,
            -- Normalized dept for joining
            upper(regexp_replace(
                translate(dpto, 'ÁÉÍÓÚÜÑ', 'AEIOUUN'),
            '[^A-Z0-9 ,.]', '', 'g')) AS dpto_norm,
            upper(regexp_replace(
                translate(nom_mpio, 'ÁÉÍÓÚÜÑ', 'AEIOUUN'),
            '[^A-Z0-9 ,.]', '', 'g')) AS mpio_norm
        FROM {_glob(db, divipola_glob)}
    """)
    n_divipola = db.execute("SELECT COUNT(*) FROM divipola").fetchone()[0]
    log.info("  divipola rows: %d", n_divipola)

    # ---------------------------------------------------------------------------
    # 3. Quarantine table
    # ---------------------------------------------------------------------------
    db.execute("""
        CREATE TABLE quarantine (
            source VARCHAR,
            row_id VARCHAR,
            reason VARCHAR,
            raw_valor VARCHAR,
            raw_fecha VARCHAR
        )
    """)

    # ---------------------------------------------------------------------------
    # 4. Staging S1 (SECOP II Contratos)
    # ---------------------------------------------------------------------------
    log.info("Staging S1 (SECOP II contratos)")

    # Dedup by :id — keep highest part-file number (done via ROW_NUMBER on filename)
    db.execute(f"""
        CREATE TABLE stg_s1 AS
        WITH raw AS (
            SELECT *,
                filename
            FROM read_parquet('{s1_glob}', union_by_name=true, filename=true)
        ),
        deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY ":id"
                    ORDER BY filename DESC  -- higher part file wins
                ) AS rn
            FROM raw
            WHERE ":id" IS NOT NULL
        )
        SELECT * EXCLUDE (rn, filename)
        FROM deduped
        WHERE rn = 1
    """)
    n_raw_s1 = db.execute(f"SELECT COUNT(*) FROM {_glob(db, s1_glob)}").fetchone()[0]
    n_stg_s1 = db.execute("SELECT COUNT(*) FROM stg_s1").fetchone()[0]
    log.info("  S1 raw=%d  after dedup=%d  removed=%d", n_raw_s1, n_stg_s1, n_raw_s1 - n_stg_s1)

    # Quarantine S1 rows with bad valor or fecha
    db.execute("""
        INSERT INTO quarantine
        SELECT
            'S1',
            ":id",
            CASE
                WHEN TRY_CAST(valor_del_contrato AS DOUBLE) IS NULL
                     AND valor_del_contrato IS NOT NULL
                     AND trim(valor_del_contrato) != ''
                THEN 'bad_valor_del_contrato'
                WHEN TRY_CAST(fecha_de_firma AS DATE) IS NULL
                     AND fecha_de_firma IS NOT NULL
                     AND trim(fecha_de_firma) != ''
                THEN 'bad_fecha_de_firma'
                ELSE NULL
            END AS reason,
            valor_del_contrato,
            fecha_de_firma
        FROM stg_s1
        WHERE (
            (TRY_CAST(valor_del_contrato AS DOUBLE) IS NULL
                AND valor_del_contrato IS NOT NULL
                AND trim(valor_del_contrato) != '')
            OR
            (TRY_CAST(fecha_de_firma AS DATE) IS NULL
                AND fecha_de_firma IS NOT NULL
                AND trim(fecha_de_firma) != '')
        )
    """)
    n_q_s1 = db.execute("SELECT COUNT(*) FROM quarantine WHERE source='S1'").fetchone()[0]
    log.info("  S1 quarantine rows: %d", n_q_s1)

    # ---------------------------------------------------------------------------
    # 5. Staging S2 (SECOP II Procesos)
    # ---------------------------------------------------------------------------
    log.info("Staging S2 (SECOP II procesos)")
    db.execute(f"""
        CREATE TABLE stg_s2 AS
        WITH raw AS (
            SELECT *,
                filename
            FROM read_parquet('{s2_glob}', union_by_name=true, filename=true)
        ),
        deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY ":id"
                    ORDER BY filename DESC
                ) AS rn
            FROM raw
            WHERE ":id" IS NOT NULL
        )
        SELECT * EXCLUDE (rn, filename)
        FROM deduped
        WHERE rn = 1
    """)
    n_raw_s2 = db.execute(f"SELECT COUNT(*) FROM {_glob(db, s2_glob)}").fetchone()[0]
    n_stg_s2 = db.execute("SELECT COUNT(*) FROM stg_s2").fetchone()[0]
    log.info("  S2 raw=%d  after dedup=%d  removed=%d", n_raw_s2, n_stg_s2, n_raw_s2 - n_stg_s2)

    # ---------------------------------------------------------------------------
    # 6. SECOP I slices staging (union all available datasets into common schema)
    # ---------------------------------------------------------------------------
    log.info("Staging SECOP I slices")
    secop1_parts: list[str] = []
    slice_base = raw_base / "secop1_slices"
    for case_dir in sorted(slice_base.iterdir()) if slice_base.exists() else []:
        if not case_dir.is_dir():
            continue
        for dataset_dir in sorted(case_dir.iterdir()):
            if not dataset_dir.is_dir():
                continue
            parts = list(dataset_dir.glob("part-*.parquet"))
            if not parts:
                continue
            # Check row count > 0
            try:
                n = db.execute(
                    f"SELECT COUNT(*) FROM read_parquet('{dataset_dir}/part-*.parquet', union_by_name=true)"
                ).fetchone()[0]
                if n == 0:
                    log.info("  skipping %s (0 rows)", dataset_dir)
                    continue
            except Exception as e:
                log.warning("  cannot read %s: %s", dataset_dir, e)
                continue
            secop1_parts.append(str(dataset_dir))
            log.info("  SECOP1 slice: %s (%d rows)", dataset_dir.name, n)

    # Build union of SECOP I slices with best-effort column mapping
    # Both s3 (f789-7hwg) and s4 (79ga-5jck) have similar schemas
    if secop1_parts:
        union_sqls = []
        for d in secop1_parts:
            g = f"'{d}/part-*.parquet'"
            # Get actual columns to build safe COALESCE expressions
            actual_cols = {
                r[0] for r in db.execute(
                    f"DESCRIBE SELECT * FROM read_parquet({g}, union_by_name=true) LIMIT 0"
                ).fetchall()
            }

            def _coalesce(*candidates: str) -> str:
                present = [c for c in candidates if c in actual_cols]
                if not present:
                    return "NULL::VARCHAR"
                return f"COALESCE({', '.join(present)})"

            union_sqls.append(f"""
                SELECT
                    {_coalesce('":id"', "uid")} AS ":id",
                    {_coalesce('numero_de_contrato', 'numero_del_contrato', 'numero_de_constancia')} AS id_contrato,
                    {_coalesce('numero_de_proceso')} AS proceso_de_compra,
                    {_coalesce('nit_de_la_entidad', 'nit_entidad')} AS nit_entidad,
                    {_coalesce('nombre_entidad', 'nombre_de_la_entidad')} AS nombre_entidad,
                    NULL::VARCHAR AS departamento,
                    {_coalesce('municipio_entidad', 'dpto_y_muni_contratista')} AS ciudad,
                    {_coalesce('modalidad_de_contratacion', 'tipo_de_proceso', 'regimen_de_contratacion')} AS modalidad_de_contratacion,
                    {_coalesce('tipo_de_contrato')} AS tipo_de_contrato,
                    {_coalesce('detalle_del_objeto_a_contratar', 'objeto_del_contrato_a_la', 'objeto_a_contratar')} AS objeto_del_contrato,
                    NULL::VARCHAR AS codigo_de_categoria_principal,
                    {_coalesce('fecha_de_firma_del_contrato')} AS fecha_de_firma,
                    {_coalesce('fecha_ini_ejec_contrato')} AS fecha_de_inicio_del_contrato,
                    {_coalesce('fecha_fin_ejec_contrato')} AS fecha_de_fin_del_contrato,
                    {_coalesce('identificacion_del_contratista')} AS documento_proveedor,
                    {_coalesce('nom_razon_social_contratista', 'nom_raz_social_contratista')} AS proveedor_adjudicado,
                    {_coalesce('cuantia_contrato')} AS valor_del_contrato,
                    NULL::VARCHAR AS valor_pagado,
                    {_coalesce('tiempo_adiciones_en_dias')} AS dias_adicionados,
                    {_coalesce('valor_total_de_adiciones')} AS valor_total_de_adiciones,
                    {_coalesce('valor_contrato_con_adiciones')} AS valor_contrato_con_adiciones,
                    {_coalesce('ruta_proceso_en_secop_i')} AS urlproceso,
                    {_coalesce('estado_del_proceso')} AS estado_contrato,
                    'SECOP1'::VARCHAR AS source
                FROM read_parquet({g}, union_by_name=true)
            """)

        union_sql = " UNION ALL ".join(union_sqls)
        db.execute(f"CREATE TABLE stg_secop1 AS {union_sql}")
        n_secop1 = db.execute("SELECT COUNT(*) FROM stg_secop1").fetchone()[0]
        log.info("  SECOP1 total staging rows: %d", n_secop1)
    else:
        db.execute("""
            CREATE TABLE stg_secop1 (
                ":id" VARCHAR, id_contrato VARCHAR, proceso_de_compra VARCHAR,
                nit_entidad VARCHAR, nombre_entidad VARCHAR,
                departamento VARCHAR, ciudad VARCHAR,
                modalidad_de_contratacion VARCHAR, tipo_de_contrato VARCHAR,
                objeto_del_contrato VARCHAR, codigo_de_categoria_principal VARCHAR,
                fecha_de_firma VARCHAR, fecha_de_inicio_del_contrato VARCHAR,
                fecha_de_fin_del_contrato VARCHAR,
                documento_proveedor VARCHAR, proveedor_adjudicado VARCHAR,
                valor_del_contrato VARCHAR, valor_pagado VARCHAR,
                dias_adicionados VARCHAR, valor_total_de_adiciones VARCHAR,
                valor_contrato_con_adiciones VARCHAR,
                urlproceso VARCHAR, estado_contrato VARCHAR, source VARCHAR
            )
        """)
        n_secop1 = 0
        log.info("  No SECOP1 slices found")

    # ---------------------------------------------------------------------------
    # 7. fct_contrato
    # ---------------------------------------------------------------------------
    log.info("Building fct_contrato")

    # Helper SQL for dept normalization (inline)
    _dpto_norm_expr = """
        upper(regexp_replace(
            translate(trim(departamento), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'),
        '[^A-Z0-9a-z ,.]', '', 'g'))
    """

    db.execute("""
        CREATE TABLE fct_contrato AS
        WITH s1_base AS (
            SELECT
                'SECOP2'::VARCHAR AS source,
                ":id" AS row_id,
                id_contrato,
                proceso_de_compra,
                -- NIT normalization: strip non-digits
                regexp_replace(COALESCE(nit_entidad, ''), '[^0-9]', '', 'g') AS nit_entidad_norm,
                nombre_entidad,
                regexp_replace(COALESCE(documento_proveedor, ''), '[^0-9]', '', 'g') AS doc_proveedor_norm,
                proveedor_adjudicado AS nombre_proveedor,
                modalidad_de_contratacion AS modalidad_raw,
                tipo_de_contrato,
                objeto_del_contrato,
                -- UNSPSC: strip 'V1.' prefix, take first 2 digits
                TRY_CAST(
                    LEFT(regexp_replace(COALESCE(codigo_de_categoria_principal, ''), '^V[0-9]+[.]', ''), 2)
                AS INTEGER) AS unspsc_segmento,
                TRY_CAST(fecha_de_firma AS DATE) AS fecha_firma,
                TRY_CAST(fecha_de_inicio_del_contrato AS DATE) AS fecha_inicio,
                TRY_CAST(fecha_de_fin_del_contrato AS DATE) AS fecha_fin,
                TRY_CAST(COALESCE(dias_adicionados, '0') AS INTEGER) AS dias_adicionados,
                TRY_CAST(valor_del_contrato AS DOUBLE) AS valor_contrato,
                TRY_CAST(valor_pagado AS DOUBLE) AS valor_pagado,
                urlproceso,
                estado_contrato AS estado,
                -- Dept for DIVIPOLA join
                upper(regexp_replace(
                    translate(trim(COALESCE(departamento, '')), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'),
                '[^A-Za-z0-9 ,.]', '', 'g')) AS dpto_raw_norm,
                upper(regexp_replace(
                    translate(trim(COALESCE(ciudad, '')), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'),
                '[^A-Za-z0-9 ,.]', '', 'g')) AS mpio_raw_norm
            FROM stg_s1
            -- Exclude quarantine rows
            WHERE ":id" NOT IN (SELECT row_id FROM quarantine WHERE source='S1')
              AND TRY_CAST(valor_del_contrato AS DOUBLE) IS NOT NULL
              AND TRY_CAST(fecha_de_firma AS DATE) IS NOT NULL
        ),
        s1_modal AS (
            SELECT s1_base.*,
                COALESCE(m.modalidad_norm, 'OTRO') AS modalidad_norm,
                COALESCE(m.es_competitiva, false) AS es_competitiva,
                COALESCE(m.es_abierta, false) AS es_abierta
            FROM s1_base
            LEFT JOIN ref_modalidades m ON s1_base.modalidad_raw = m.raw_value
        ),
        s1_geo AS (
            SELECT s1_modal.*,
                d.cod_dpto,
                d.cod_mpio
            FROM s1_modal
            LEFT JOIN divipola d
                ON upper(regexp_replace(
                       translate(d.dpto, 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'),
                   '[^A-Za-z0-9 ,.]', '', 'g')) = s1_modal.dpto_raw_norm
                AND upper(regexp_replace(
                       translate(d.municipio, 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'),
                   '[^A-Za-z0-9 ,.]', '', 'g')) = s1_modal.mpio_raw_norm
        ),
        secop1_base AS (
            SELECT
                'SECOP1'::VARCHAR AS source,
                ":id" AS row_id,
                id_contrato,
                proceso_de_compra,
                regexp_replace(COALESCE(nit_entidad, ''), '[^0-9]', '', 'g') AS nit_entidad_norm,
                nombre_entidad,
                regexp_replace(COALESCE(documento_proveedor, ''), '[^0-9]', '', 'g') AS doc_proveedor_norm,
                proveedor_adjudicado AS nombre_proveedor,
                modalidad_de_contratacion AS modalidad_raw,
                tipo_de_contrato,
                objeto_del_contrato,
                NULL::INTEGER AS unspsc_segmento,
                TRY_CAST(fecha_de_firma AS DATE) AS fecha_firma,
                TRY_CAST(fecha_de_inicio_del_contrato AS DATE) AS fecha_inicio,
                TRY_CAST(fecha_de_fin_del_contrato AS DATE) AS fecha_fin,
                TRY_CAST(COALESCE(dias_adicionados, '0') AS INTEGER) AS dias_adicionados,
                TRY_CAST(valor_del_contrato AS DOUBLE) AS valor_contrato,
                TRY_CAST(valor_pagado AS DOUBLE) AS valor_pagado,
                urlproceso,
                estado_contrato AS estado,
                NULL::VARCHAR AS dpto_raw_norm,
                NULL::VARCHAR AS mpio_raw_norm
            FROM stg_secop1
            WHERE TRY_CAST(valor_del_contrato AS DOUBLE) IS NOT NULL
              AND TRY_CAST(fecha_de_firma AS DATE) IS NOT NULL
        ),
        secop1_modal AS (
            SELECT secop1_base.*,
                COALESCE(m.modalidad_norm, 'OTRO') AS modalidad_norm,
                COALESCE(m.es_competitiva, false) AS es_competitiva,
                COALESCE(m.es_abierta, false) AS es_abierta,
                NULL::VARCHAR AS cod_dpto,
                NULL::VARCHAR AS cod_mpio
            FROM secop1_base
            LEFT JOIN ref_modalidades m ON secop1_base.modalidad_raw = m.raw_value
        ),
        combined AS (
            SELECT * FROM s1_geo
            UNION ALL
            SELECT * FROM secop1_modal
        )
        SELECT
            source,
            row_id,
            id_contrato,
            proceso_de_compra,
            nit_entidad_norm,
            nombre_entidad,
            doc_proveedor_norm,
            nombre_proveedor,
            cod_dpto,
            cod_mpio,
            modalidad_norm,
            es_competitiva,
            es_abierta,
            tipo_de_contrato,
            objeto_del_contrato,
            unspsc_segmento,
            fecha_firma,
            fecha_inicio,
            fecha_fin,
            CASE
                WHEN fecha_inicio IS NOT NULL AND fecha_fin IS NOT NULL
                THEN CAST((fecha_fin - fecha_inicio) AS INTEGER)
                ELSE NULL
            END AS duracion_dias_inicial,
            dias_adicionados,
            valor_contrato,
            valor_pagado,
            EXTRACT(YEAR FROM fecha_firma)::INTEGER AS anio,
            urlproceso,
            estado
        FROM combined
    """)

    n_fct_contrato = db.execute("SELECT COUNT(*) FROM fct_contrato").fetchone()[0]
    log.info("  fct_contrato rows: %d", n_fct_contrato)

    # DIVIPOLA geo match rate for S2 contracts
    geo_match = db.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN cod_dpto IS NOT NULL THEN 1 ELSE 0 END) AS n_matched,
            SUM(CASE WHEN cod_dpto IS NOT NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct
        FROM fct_contrato WHERE source='SECOP2'
    """).fetchone()
    log.info("  DIVIPOLA geo match rate: %.1f%% (%d/%d)", geo_match[2], geo_match[1], geo_match[0])

    # Contract↔process join coverage
    join_cov = db.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN s2.id_del_proceso IS NOT NULL THEN 1 ELSE 0 END) AS n_matched,
            SUM(CASE WHEN s2.id_del_proceso IS NOT NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct
        FROM fct_contrato fc
        LEFT JOIN stg_s2 s2 ON fc.proceso_de_compra = s2.id_del_portafolio
        WHERE fc.source = 'SECOP2'
    """).fetchone()
    log.info("  Contract↔process join coverage: %.1f%% (%d/%d)", join_cov[2], join_cov[1], join_cov[0])

    # ---------------------------------------------------------------------------
    # 8. fct_proceso
    # ---------------------------------------------------------------------------
    log.info("Building fct_proceso")
    db.execute("""
        CREATE TABLE fct_proceso AS
        WITH base AS (
            SELECT
                id_del_proceso,
                id_del_portafolio AS referencia,
                referencia_del_proceso,
                entidad AS nombre_entidad,
                regexp_replace(COALESCE(nit_entidad, ''), '[^0-9]', '', 'g') AS nit_entidad_norm,
                departamento_entidad,
                ciudad_entidad,
                modalidad_de_contratacion AS modalidad_raw,
                TRY_CAST(precio_base AS DOUBLE) AS precio_base,
                TRY_CAST(fecha_de_publicacion_del AS DATE) AS fecha_publicacion,
                TRY_CAST(fecha_de_recepcion_de AS DATE) AS fecha_recepcion_respuestas,
                TRY_CAST(duracion AS INTEGER) AS duracion,
                unidad_de_duracion,
                TRY_CAST(proveedores_invitados AS INTEGER) AS num_invitados,
                TRY_CAST(respuestas_al_procedimiento AS INTEGER) AS num_respuestas,
                TRY_CAST(proveedores_unicos_con AS INTEGER) AS num_oferentes_unicos,
                CASE WHEN upper(COALESCE(adjudicado, '')) IN ('TRUE', 'SI', '1', 'YES', 'VERDADERO')
                     THEN true ELSE false END AS adjudicado,
                TRY_CAST(valor_total_adjudicacion AS DOUBLE) AS valor_adjudicacion,
                nombre_del_adjudicador,
                ":id" AS row_id
            FROM stg_s2
        )
        SELECT
            base.*,
            COALESCE(m.modalidad_norm, 'OTRO') AS modalidad_norm,
            COALESCE(m.es_competitiva, false) AS es_competitiva,
            EXTRACT(YEAR FROM fecha_publicacion)::INTEGER AS anio
        FROM base
        LEFT JOIN ref_modalidades m ON base.modalidad_raw = m.raw_value
    """)
    n_fct_proceso = db.execute("SELECT COUNT(*) FROM fct_proceso").fetchone()[0]
    log.info("  fct_proceso rows: %d", n_fct_proceso)

    # ---------------------------------------------------------------------------
    # 9. dim_entidad
    # ---------------------------------------------------------------------------
    log.info("Building dim_entidad")
    db.execute("""
        CREATE TABLE dim_entidad AS
        SELECT
            nit_entidad_norm,
            -- Mode of name (most frequent)
            (SELECT nombre_entidad FROM fct_contrato fc2
             WHERE fc2.nit_entidad_norm = fc.nit_entidad_norm
             GROUP BY nombre_entidad ORDER BY COUNT(*) DESC LIMIT 1) AS nombre_entidad,
            -- Mode of dept
            (SELECT cod_dpto FROM fct_contrato fc2
             WHERE fc2.nit_entidad_norm = fc.nit_entidad_norm
               AND cod_dpto IS NOT NULL
             GROUP BY cod_dpto ORDER BY COUNT(*) DESC LIMIT 1) AS cod_dpto,
            -- Mode of mpio
            (SELECT cod_mpio FROM fct_contrato fc2
             WHERE fc2.nit_entidad_norm = fc.nit_entidad_norm
               AND cod_mpio IS NOT NULL
             GROUP BY cod_mpio ORDER BY COUNT(*) DESC LIMIT 1) AS cod_mpio,
            COUNT(*) AS n_contratos,
            SUM(valor_contrato) AS valor_total
        FROM fct_contrato fc
        WHERE nit_entidad_norm IS NOT NULL AND nit_entidad_norm != ''
        GROUP BY nit_entidad_norm
    """)
    n_dim_entidad = db.execute("SELECT COUNT(*) FROM dim_entidad").fetchone()[0]
    log.info("  dim_entidad rows: %d", n_dim_entidad)

    # ---------------------------------------------------------------------------
    # 10. dim_proveedor
    # ---------------------------------------------------------------------------
    log.info("Building dim_proveedor")
    db.execute("""
        CREATE TABLE dim_proveedor AS
        SELECT
            doc_proveedor_norm,
            (SELECT nombre_proveedor FROM fct_contrato fc2
             WHERE fc2.doc_proveedor_norm = fc.doc_proveedor_norm
             GROUP BY nombre_proveedor ORDER BY COUNT(*) DESC LIMIT 1) AS nombre_proveedor,
            -- Persona natural heuristic:
            -- length <= 8: likely cédula (old format) → natural
            -- length == 10 AND starts with 8 or 9: NIT with check digit → entity
            -- length == 9 AND starts with 8 or 9: NIT no check digit → entity
            -- length == 10 AND starts with 1: cédula nueva → natural
            CASE
                WHEN length(doc_proveedor_norm) <= 8 THEN true
                WHEN length(doc_proveedor_norm) = 9
                     AND LEFT(doc_proveedor_norm,1) IN ('8','9') THEN false
                WHEN length(doc_proveedor_norm) = 10
                     AND LEFT(doc_proveedor_norm,1) IN ('8','9') THEN false
                WHEN length(doc_proveedor_norm) = 10
                     AND LEFT(doc_proveedor_norm,1) = '1' THEN true
                ELSE NULL
            END AS es_persona_natural,
            COUNT(*) AS n_contratos,
            SUM(valor_contrato) AS valor_total
        FROM fct_contrato fc
        WHERE doc_proveedor_norm IS NOT NULL AND doc_proveedor_norm != ''
        GROUP BY doc_proveedor_norm
    """)
    n_dim_proveedor = db.execute("SELECT COUNT(*) FROM dim_proveedor").fetchone()[0]
    log.info("  dim_proveedor rows: %d", n_dim_proveedor)

    # ---------------------------------------------------------------------------
    # 11. sanciones
    # ---------------------------------------------------------------------------
    log.info("Building sanciones")
    db.execute(f"""
        CREATE TABLE sanciones AS

        -- L1: Responsabilidad Fiscal (CGR)
        SELECT
            regexp_replace(COALESCE("n_mero_de_identificaci_n", ''), '[^0-9]', '', 'g') AS doc_norm,
            "raz_n_social_de_la_entidad" AS nombre,
            'CGR'::VARCHAR AS fuente,
            TRY_CAST("fecha_de_resoluci_n_de_la" AS DATE) AS fecha_sancion,
            COALESCE("descripci_n_o_detalle_resumen", "tipo_de_sanci_n_multa") AS detalle
        FROM read_parquet('{l1_glob}', union_by_name=true)

        UNION ALL

        -- L2: Multas SECOP I
        SELECT
            regexp_replace(COALESCE(documento_contratista, ''), '[^0-9]', '', 'g') AS doc_norm,
            nombre_contratista AS nombre,
            'MULTA_SECOP1'::VARCHAR AS fuente,
            TRY_CAST(COALESCE(fecha_de_firmeza, fecha_de_publicacion) AS DATE) AS fecha_sancion,
            CONCAT('Contrato: ', COALESCE(numero_de_contrato, ''), ' | Resolución: ', COALESCE(numero_de_resolucion, '')) AS detalle
        FROM read_parquet('{l2_glob}', union_by_name=true)

        UNION ALL

        -- L3: Multas SECOP II
        SELECT
            regexp_replace(COALESCE(as_codigo_proveedor_objeto, ''), '[^0-9]', '', 'g') AS doc_norm,
            nombre_proveedor_objeto_de AS nombre,
            'MULTA_SECOP2'::VARCHAR AS fuente,
            TRY_CAST(fecha_evento AS DATE) AS fecha_sancion,
            CONCAT(COALESCE(tipo_de_sancion, ''), ' | ', COALESCE(descripcion_otro_tipo_de, '')) AS detalle
        FROM read_parquet('{l3_glob}', union_by_name=true)

        UNION ALL

        -- L4: SIRI (Procuraduría)
        SELECT
            regexp_replace(COALESCE(numero_identificacion, ''), '[^0-9]', '', 'g') AS doc_norm,
            CONCAT(
                COALESCE(primer_nombre, ''), ' ',
                COALESCE(segundo_nombre, ''), ' ',
                COALESCE(primer_apellido, ''), ' ',
                COALESCE(segundo_apellido, '')
            ) AS nombre,
            'SIRI'::VARCHAR AS fuente,
            TRY_CAST(fecha_efectos_juridicos AS DATE) AS fecha_sancion,
            CONCAT(COALESCE(tipo_inhabilidad, ''), ' | ', COALESCE(sanciones, '')) AS detalle
        FROM read_parquet('{l4_glob}', union_by_name=true)
    """)

    sancion_counts = db.execute("""
        SELECT fuente, COUNT(*) as n FROM sanciones GROUP BY fuente ORDER BY fuente
    """).fetchall()
    for row in sancion_counts:
        log.info("  sanciones [%s]: %d rows", row[0], row[1])

    # ---------------------------------------------------------------------------
    # 12. monitor_ciudadano_hechos
    # ---------------------------------------------------------------------------
    log.info("Building monitor_ciudadano_hechos")
    hechos_path = monitor_dir / "Base_de_datos_hechos_2016_2022.xlsx"
    if hechos_path.exists():
        try:
            import openpyxl  # noqa: F401 — just checking availability
            _build_monitor_hechos(db, hechos_path)
        except ImportError:
            log.warning("openpyxl not installed — skipping monitor_ciudadano_hechos")
            db.execute("""
                CREATE TABLE monitor_ciudadano_hechos (
                    departamento VARCHAR, municipio VARCHAR, anio INTEGER,
                    tipo_corrupcion VARCHAR, sector VARCHAR, descripcion VARCHAR
                )
            """)
    else:
        log.warning("Monitor Ciudadano hechos file not found: %s", hechos_path)
        db.execute("""
            CREATE TABLE monitor_ciudadano_hechos (
                departamento VARCHAR, municipio VARCHAR, anio INTEGER,
                tipo_corrupcion VARCHAR, sector VARCHAR, descripcion VARCHAR
            )
        """)

    n_mc = db.execute("SELECT COUNT(*) FROM monitor_ciudadano_hechos").fetchone()[0]
    log.info("  monitor_ciudadano_hechos rows: %d", n_mc)

    # ---------------------------------------------------------------------------
    # 13. DQ summary
    # ---------------------------------------------------------------------------
    _write_dq_report(db, mode, n_raw_s1, n_stg_s1, n_raw_s2, n_stg_s2, n_secop1,
                     n_fct_contrato, n_fct_proceso, n_dim_entidad, n_dim_proveedor,
                     geo_match, join_cov, sancion_counts, n_mc)

    db.close()
    log.info("Done. DB: %s", db_path)


def _build_monitor_hechos(db: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Parse Monitor Ciudadano hechos xlsx and load into DuckDB.

    The workbook opens with a multi-row title banner (merged cells, no data)
    before the real header row — its length isn't guaranteed to be stable
    across re-downloads, so the header row is located by content (a cell
    reading "Departamento") rather than a hardcoded row index.
    """
    import openpyxl

    from pipeline.clean.normalize import strip_accents

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        db.execute("""
            CREATE TABLE monitor_ciudadano_hechos (
                departamento VARCHAR, municipio VARCHAR, anio INTEGER,
                tipo_corrupcion VARCHAR, sector VARCHAR, descripcion VARCHAR
            )
        """)
        return

    def _norm_header(h: object) -> str:
        s = strip_accents(str(h).strip().lower()) if h is not None else ""
        return s.replace(" ", "_").strip("_")

    header_idx = next(
        (i for i, row in enumerate(rows)
         if any(_norm_header(c) == "departamento" for c in row)),
        0,
    )
    headers = [_norm_header(h) or f"col_{i}" for i, h in enumerate(rows[header_idx])]

    # Map to canonical names (keys are accent-stripped, per _norm_header above)
    _HEADER_MAP = {
        "departamento": "departamento",
        "municipio": "municipio",
        "ano_inicial_hecho": "anio",
        "ano": "anio",
        "anio": "anio",
        "year": "anio",
        "tipo_de_corrupcion": "tipo_corrupcion",
        "tipo_corrupcion": "tipo_corrupcion",
        "tipo": "tipo_corrupcion",
        "sector": "sector",
        "resumen": "descripcion",
        "hecho": "descripcion",
        "descripcion": "descripcion",
        "descripcion_del_hecho": "descripcion",
        "hecho_de_corrupcion": "descripcion",
    }

    canonical = [_HEADER_MAP.get(h, h) for h in headers]

    data_rows = []
    for row in rows[header_idx + 1:]:
        if all(v is None for v in row):
            continue
        d = dict(zip(canonical, row))
        data_rows.append({
            "departamento": str(d.get("departamento", "") or ""),
            "municipio": str(d.get("municipio", "") or ""),
            "anio": int(d["anio"]) if d.get("anio") and str(d["anio"]).isdigit() else None,
            "tipo_corrupcion": str(d.get("tipo_corrupcion", "") or ""),
            "sector": str(d.get("sector", "") or ""),
            "descripcion": str(d.get("descripcion", "") or ""),
        })

    wb.close()

    db.execute("""
        CREATE TABLE monitor_ciudadano_hechos (
            departamento VARCHAR, municipio VARCHAR, anio INTEGER,
            tipo_corrupcion VARCHAR, sector VARCHAR, descripcion VARCHAR
        )
    """)
    if data_rows:
        db.executemany(
            "INSERT INTO monitor_ciudadano_hechos VALUES (?,?,?,?,?,?)",
            [(r["departamento"], r["municipio"], r["anio"],
              r["tipo_corrupcion"], r["sector"], r["descripcion"])
             for r in data_rows],
        )


def _write_dq_report(
    db: duckdb.DuckDBPyConnection,
    mode: str,
    n_raw_s1: int, n_stg_s1: int,
    n_raw_s2: int, n_stg_s2: int,
    n_secop1: int,
    n_fct_contrato: int, n_fct_proceso: int,
    n_dim_entidad: int, n_dim_proveedor: int,
    geo_match: tuple, join_cov: tuple,
    sancion_counts: list, n_mc: int,
) -> None:
    """Generate docs/DQ_REPORT.md."""
    docs_dir = _PIPELINE_ROOT.parent / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    out_path = docs_dir / "DQ_REPORT.md"

    q_by_reason = db.execute("""
        SELECT reason, COUNT(*) FROM quarantine GROUP BY reason ORDER BY COUNT(*) DESC
    """).fetchall()
    n_q_total = db.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0]
    q_pct = n_q_total * 100.0 / n_stg_s1 if n_stg_s1 > 0 else 0

    # fct_contrato null rates
    null_rates = db.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN nit_entidad_norm IS NULL OR nit_entidad_norm='' THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_null_nit,
            SUM(CASE WHEN doc_proveedor_norm IS NULL OR doc_proveedor_norm='' THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_null_doc,
            SUM(CASE WHEN fecha_firma IS NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_null_fecha,
            SUM(CASE WHEN valor_contrato IS NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_null_valor,
            SUM(CASE WHEN modalidad_norm IS NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_null_modal,
            SUM(CASE WHEN cod_dpto IS NULL THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_null_geo
        FROM fct_contrato WHERE source='SECOP2'
    """).fetchone()

    # Value distribution
    val_dist = db.execute("""
        SELECT
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY valor_contrato) AS p50,
            PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY valor_contrato) AS p95,
            PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY valor_contrato) AS p99,
            MIN(valor_contrato) AS min_val,
            MAX(valor_contrato) AS max_val
        FROM fct_contrato WHERE source='SECOP2' AND valor_contrato > 0
    """).fetchone()

    # Date range
    date_range = db.execute("""
        SELECT MIN(fecha_firma), MAX(fecha_firma)
        FROM fct_contrato WHERE source='SECOP2'
    """).fetchone()

    lines = [
        "# DQ Report — Radar de Riesgo de Corrupción",
        "",
        f"**Build mode:** `{mode}`  ",
        "**Generated:** pipeline/clean/build.py  ",
        "",
        "## 1. Row Reconciliation",
        "",
        "| Stage | Dataset | Rows |",
        "|-------|---------|------|",
        f"| Raw | S1 SECOP II Contratos | {n_raw_s1:,} |",
        f"| Staged (dedup :id) | stg_s1 | {n_stg_s1:,} |",
        f"| Dedup removed | S1 | {n_raw_s1 - n_stg_s1:,} |",
        f"| Raw | S2 SECOP II Procesos | {n_raw_s2:,} |",
        f"| Staged (dedup :id) | stg_s2 | {n_stg_s2:,} |",
        f"| Dedup removed | S2 | {n_raw_s2 - n_stg_s2:,} |",
        f"| SECOP I slices | stg_secop1 | {n_secop1:,} |",
        "",
        "## 2. Quarantine",
        "",
        f"**Total quarantine rows (S1):** {n_q_total:,} ({q_pct:.2f}% of staged)",
        f"**Target:** <5% — {'PASS' if q_pct < 5 else 'FAIL (see reasons below)'}",
        "",
        "| Reason | Count |",
        "|--------|-------|",
    ]
    for reason, cnt in q_by_reason:
        lines.append(f"| {reason} | {cnt:,} |")

    lines += [
        "",
        "## 3. Mart Row Counts",
        "",
        "| Mart | Rows |",
        "|------|------|",
        f"| fct_contrato (SECOP2) | {null_rates[0]:,} |",
        f"| fct_contrato (all sources) | {n_fct_contrato:,} |",
        f"| fct_proceso | {n_fct_proceso:,} |",
        f"| dim_entidad | {n_dim_entidad:,} |",
        f"| dim_proveedor | {n_dim_proveedor:,} |",
        f"| monitor_ciudadano_hechos | {n_mc:,} |",
        "",
        "**Sanciones by fuente:**",
        "",
        "| Fuente | Rows |",
        "|--------|------|",
    ]
    for fuente, cnt in sancion_counts:
        lines.append(f"| {fuente} | {cnt:,} |")

    lines += [
        "",
        "## 4. Null Rates — fct_contrato (SECOP2)",
        "",
        "| Field | Null % |",
        "|-------|--------|",
        f"| nit_entidad_norm | {null_rates[1]:.1f}% |",
        f"| doc_proveedor_norm | {null_rates[2]:.1f}% |",
        f"| fecha_firma | {null_rates[3]:.1f}% |",
        f"| valor_contrato | {null_rates[4]:.1f}% |",
        f"| modalidad_norm | {null_rates[5]:.1f}% |",
        f"| cod_dpto (geo) | {null_rates[6]:.1f}% |",
        "",
        "## 5. DIVIPOLA Geo Match Rate",
        "",
        f"**Match rate (S2 contracts):** {geo_match[2]:.1f}% ({geo_match[1]:,} of {geo_match[0]:,})",
        "",
        "> Note: Low match rate expected when entity department name uses alternate forms",
        "> (e.g., 'Distrito Capital de Bogotá' vs 'BOGOTÁ, D.C.'). The normalize_dpto_name()",
        "> function in normalize.py handles the most common aliases.",
        "",
        "## 6. Contract↔Process Join Coverage",
        "",
        "**Join key:** `fct_contrato.proceso_de_compra` → `stg_s2.id_del_portafolio`",
        f"**Coverage:** {join_cov[2]:.1f}% ({join_cov[1]:,} of {join_cov[0]:,} SECOP2 contracts)",
        "",
        "> Key discovery: S1 contratos uses `proceso_de_compra` with prefix `CO1.BDOS.*`",
        "> while S2 uses `id_del_proceso` with prefix `CO1.REQ.*`. The join key is",
        "> `id_del_portafolio` in S2 (also `CO1.BDOS.*` prefix). Coverage in the 300k sample",
        "> is lower than full-dataset expectation because the sample covers only 2023 and",
        "> many processes from that year may have been captured in different S2 parts.",
        "",
        "## 7. Value Distribution — fct_contrato (SECOP2, valor_contrato > 0)",
        "",
        "| Percentile | Value (COP) |",
        "|------------|-------------|",
        f"| P50 | {val_dist[0]:,.0f} |" if val_dist[0] else "| P50 | N/A |",
        f"| P95 | {val_dist[1]:,.0f} |" if val_dist[1] else "| P95 | N/A |",
        f"| P99 | {val_dist[2]:,.0f} |" if val_dist[2] else "| P99 | N/A |",
        f"| Min | {val_dist[3]:,.0f} |" if val_dist[3] else "| Min | N/A |",
        f"| Max | {val_dist[4]:,.0f} |" if val_dist[4] else "| Max | N/A |",
        "",
        "## 8. Date Sanity",
        "",
        f"**fecha_firma range:** {date_range[0]} → {date_range[1]}",
        "",
        "---",
        "*Generated by `uv run python -m pipeline.clean.build`*",
    ]

    out_path.write_text("\n".join(lines) + "\n")
    log.info("DQ report: %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DuckDB marts (M2)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sample", action="store_true", default=True,
                       help="Use sample data (default)")
    group.add_argument("--full", action="store_true",
                       help="Use full raw data")
    args = parser.parse_args()
    mode = "full" if args.full else "sample"
    build(mode)


if __name__ == "__main__":
    main()
