"""
Shared synthetic-fixture builders for flag unit tests.

Each helper creates an in-memory DuckDB table with the *real* mart schema
(column names/types verified live against pipeline/data/marts/corruption.duckdb
via DESCRIBE, per the M3 brief) and inserts the given rows, leaving any
column not mentioned in a row as NULL. This lets each test spell out only
the columns that matter for the scenario being tested, instead of 20+
boilerplate columns every time.
"""

from __future__ import annotations

import duckdb
import pytest

FCT_CONTRATO_COLUMNS: dict[str, str] = {
    "source": "VARCHAR",
    "row_id": "VARCHAR",
    "id_contrato": "VARCHAR",
    "proceso_de_compra": "VARCHAR",
    "nit_entidad_norm": "VARCHAR",
    "nombre_entidad": "VARCHAR",
    "doc_proveedor_norm": "VARCHAR",
    "nombre_proveedor": "VARCHAR",
    "cod_dpto": "VARCHAR",
    "cod_mpio": "VARCHAR",
    "modalidad_norm": "VARCHAR",
    "es_competitiva": "BOOLEAN",
    "es_abierta": "BOOLEAN",
    "tipo_de_contrato": "VARCHAR",
    "objeto_del_contrato": "VARCHAR",
    "unspsc_segmento": "INTEGER",
    "fecha_firma": "DATE",
    "fecha_inicio": "DATE",
    "fecha_fin": "DATE",
    "duracion_dias_inicial": "INTEGER",
    "dias_adicionados": "INTEGER",
    "valor_contrato": "DOUBLE",
    "valor_pagado": "DOUBLE",
    "anio": "INTEGER",
    "urlproceso": "VARCHAR",
    "estado": "VARCHAR",
}

FCT_PROCESO_COLUMNS: dict[str, str] = {
    "id_del_proceso": "VARCHAR",
    "referencia": "VARCHAR",
    "referencia_del_proceso": "VARCHAR",
    "nombre_entidad": "VARCHAR",
    "nit_entidad_norm": "VARCHAR",
    "departamento_entidad": "VARCHAR",
    "ciudad_entidad": "VARCHAR",
    "modalidad_raw": "VARCHAR",
    "precio_base": "DOUBLE",
    "fecha_publicacion": "DATE",
    "fecha_recepcion_respuestas": "DATE",
    "duracion": "INTEGER",
    "unidad_de_duracion": "VARCHAR",
    "num_invitados": "INTEGER",
    "num_respuestas": "INTEGER",
    "num_oferentes_unicos": "INTEGER",
    "adjudicado": "BOOLEAN",
    "valor_adjudicacion": "DOUBLE",
    "nombre_del_adjudicador": "VARCHAR",
    "row_id": "VARCHAR",
    "modalidad_norm": "VARCHAR",
    "es_competitiva": "BOOLEAN",
    "anio": "INTEGER",
}

DIM_ENTIDAD_COLUMNS: dict[str, str] = {
    "nit_entidad_norm": "VARCHAR",
    "nombre_entidad": "VARCHAR",
    "cod_dpto": "VARCHAR",
    "cod_mpio": "VARCHAR",
    "n_contratos": "BIGINT",
    "valor_total": "DOUBLE",
}

DIM_PROVEEDOR_COLUMNS: dict[str, str] = {
    "doc_proveedor_norm": "VARCHAR",
    "nombre_proveedor": "VARCHAR",
    "es_persona_natural": "BOOLEAN",
    "n_contratos": "BIGINT",
    "valor_total": "DOUBLE",
}

SANCIONES_COLUMNS: dict[str, str] = {
    "doc_norm": "VARCHAR",
    "nombre": "VARCHAR",
    "fuente": "VARCHAR",
    "fecha_sancion": "DATE",
    "detalle": "VARCHAR",
}

REF_SMMLV_COLUMNS: dict[str, str] = {
    "year": "BIGINT",
    "value_cop": "BIGINT",
    "source_url": "VARCHAR",
}

REF_VENTANAS_COLUMNS: dict[str, str] = {
    "window_id": "VARCHAR",
    "tipo": "VARCHAR",
    "inicio": "DATE",
    "fin": "DATE",
    "descripcion": "VARCHAR",
    "fuente": "VARCHAR",
}

STG_SECOP1_COLUMNS: dict[str, str] = {
    ":id": "VARCHAR",
    "valor_total_de_adiciones": "VARCHAR",
    "valor_contrato_con_adiciones": "VARCHAR",
}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def make_table(con: duckdb.DuckDBPyConnection, table: str, columns: dict[str, str], rows: list[dict]) -> None:
    """Create `table` with `columns` (name -> SQL type) and insert `rows` (missing keys -> NULL)."""
    col_names = list(columns)
    ddl_cols = ", ".join(f"{_quote(c)} {t}" for c, t in columns.items())
    con.execute(f"CREATE TABLE {table} ({ddl_cols})")
    if not rows:
        return
    insert_cols = ", ".join(_quote(c) for c in col_names)
    placeholders = ", ".join(["?"] * len(col_names))
    payload = [tuple(row.get(c) for c in col_names) for row in rows]
    con.executemany(f"INSERT INTO {table} ({insert_cols}) VALUES ({placeholders})", payload)


def make_fct_contrato(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "fct_contrato", FCT_CONTRATO_COLUMNS, rows)


def make_fct_proceso(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "fct_proceso", FCT_PROCESO_COLUMNS, rows)


def make_dim_entidad(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "dim_entidad", DIM_ENTIDAD_COLUMNS, rows)


def make_dim_proveedor(con: duckdb.DuckDBPyConnection, rows: list[dict], with_fecha_matricula: bool = False) -> None:
    cols = dict(DIM_PROVEEDOR_COLUMNS)
    if with_fecha_matricula:
        cols["fecha_matricula"] = "DATE"
    make_table(con, "dim_proveedor", cols, rows)


def make_sanciones(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "sanciones", SANCIONES_COLUMNS, rows)


def make_ref_smmlv(con: duckdb.DuckDBPyConnection, rows: list[dict] | None = None) -> None:
    if rows is None:
        # Default: mirror refs/smmlv.csv for the years the tests use.
        rows = [
            {"year": 2022, "value_cop": 1_000_000, "source_url": "test"},
            {"year": 2023, "value_cop": 1_160_000, "source_url": "test"},
            {"year": 2024, "value_cop": 1_300_000, "source_url": "test"},
        ]
    make_table(con, "ref_smmlv", REF_SMMLV_COLUMNS, rows)


def make_ref_ventanas(con: duckdb.DuckDBPyConnection, rows: list[dict] | None = None) -> None:
    if rows is None:
        rows = [
            {
                "window_id": "VE2023T",
                "tipo": "territorial",
                "inicio": "2023-06-29",
                "fin": "2023-10-29",
                "descripcion": "test window",
                "fuente": "test",
            }
        ]
    make_table(con, "ref_ventanas", REF_VENTANAS_COLUMNS, rows)


def make_stg_secop1(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "stg_secop1", STG_SECOP1_COLUMNS, rows)


@pytest.fixture
def mem_con():
    con = duckdb.connect(":memory:")
    yield con
    con.close()
