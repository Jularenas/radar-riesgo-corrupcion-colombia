"""
Shared synthetic-fixture builders for M5 (score/backtest) unit tests.

Mirrors tests/test_flags/conftest.py's approach: real mart column
names/types (verified live via DESCRIBE against pipeline/data/marts/
corruption.duckdb), scoped down to the tables scorer.py / backtest.py
actually touch, so each test only has to spell out the columns that matter
for its scenario.

Deliberately NOT named `conftest.py` and deliberately has NO conftest.py
sibling in this directory at all: tests/test_flags/ already has its own
conftest.py, and neither test directory is a package (no __init__.py). In
pytest's default "prepend" import mode, two sibling directories that each
contain a file literally named `conftest.py` collide -- pytest's own
conftest-loading machinery imports every conftest.py it discovers under a
bare top-level name, so a *second* one anywhere under `tests/` clobbers
`sys.modules["conftest"]` for every `from conftest import ...` statement in
the whole suite, including test_flags'. (Verified: even an otherwise-empty
tests/test_score/conftest.py containing only the `mem_con` fixture broke
every tests/test_flags/test_*.py's `from conftest import make_fct_contrato`
-- the collision is triggered by the filename existing at all, independent
of its contents.)

Each test module defines its own tiny `mem_con` fixture locally (not
exported from here) rather than importing a shared one: ruff's F811 flags
every `def test_x(self, mem_con):` as "redefining" an imported `mem_con`
name, since a fixture parameter is (correctly, from a plain-Python-scoping
view) a local shadow of it. A four-line fixture duplicated across two files
is cheaper than blanket noqa's on every test method.
"""

from __future__ import annotations

import duckdb

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

FLAG_CONTRATO_COLUMNS: dict[str, str] = {
    "id_contrato": "VARCHAR",
    "flag_id": "VARCHAR",
    "fired": "BOOLEAN",
    "evidence_json": "VARCHAR",
}

FLAG_ENTIDAD_COLUMNS: dict[str, str] = {
    "nit_entidad_norm": "VARCHAR",
    "flag_id": "VARCHAR",
    "fired": "BOOLEAN",
    "evidence_json": "VARCHAR",
}

DIM_ENTIDAD_COLUMNS: dict[str, str] = {
    "nit_entidad_norm": "VARCHAR",
    "nombre_entidad": "VARCHAR",
    "cod_dpto": "VARCHAR",
    "cod_mpio": "VARCHAR",
    "n_contratos": "BIGINT",
    "valor_total": "DOUBLE",
}

DIVIPOLA_COLUMNS: dict[str, str] = {
    "cod_dpto": "VARCHAR",
    "dpto": "VARCHAR",
    "cod_mpio": "VARCHAR",
    "municipio": "VARCHAR",
    "dpto_norm": "VARCHAR",
    "mpio_norm": "VARCHAR",
}

SANCIONES_COLUMNS: dict[str, str] = {
    "doc_norm": "VARCHAR",
    "nombre": "VARCHAR",
    "fuente": "VARCHAR",
    "fecha_sancion": "DATE",
    "detalle": "VARCHAR",
}

MONITOR_CIUDADANO_COLUMNS: dict[str, str] = {
    "departamento": "VARCHAR",
    "municipio": "VARCHAR",
    "anio": "INTEGER",
    "tipo_corrupcion": "VARCHAR",
    "sector": "VARCHAR",
    "descripcion": "VARCHAR",
}

# Mirrors scorer._CONTRATO_SCORE_DDL -- kept independent (not imported) so a
# typo in the production DDL doesn't silently "fix itself" in the test copy,
# same convention as tests/test_flags/conftest.py.
CONTRATO_SCORE_COLUMNS: dict[str, str] = {
    "id_contrato": "VARCHAR",
    "nit_entidad_norm": "VARCHAR",
    "nombre_entidad": "VARCHAR",
    "doc_proveedor_norm": "VARCHAR",
    "nombre_proveedor": "VARCHAR",
    "cod_dpto": "VARCHAR",
    "cod_mpio": "VARCHAR",
    "valor_contrato": "DOUBLE",
    "fecha_firma": "DATE",
    "anio": "INTEGER",
    "urlproceso": "VARCHAR",
    "source": "VARCHAR",
    "n_flags_aplicables": "INTEGER",
    "n_flags_disparados": "INTEGER",
    "score": "DOUBLE",
    "tier": "VARCHAR",
    "flags_disparados": "VARCHAR",
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


def make_flag_contrato(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "flag_contrato", FLAG_CONTRATO_COLUMNS, rows)


def make_flag_entidad(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "flag_entidad", FLAG_ENTIDAD_COLUMNS, rows)


def make_dim_entidad(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "dim_entidad", DIM_ENTIDAD_COLUMNS, rows)


def make_divipola(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "divipola", DIVIPOLA_COLUMNS, rows)


def make_sanciones(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "sanciones", SANCIONES_COLUMNS, rows)


def make_monitor_ciudadano(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "monitor_ciudadano_hechos", MONITOR_CIUDADANO_COLUMNS, rows)


def make_contrato_score(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    make_table(con, "contrato_score", CONTRATO_SCORE_COLUMNS, rows)
