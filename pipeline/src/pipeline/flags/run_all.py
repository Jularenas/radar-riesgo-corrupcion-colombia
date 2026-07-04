"""
M3 runner: executes all 14 red-flag modules and writes results into the
`flag_contrato` / `flag_entidad` mart tables.

Usage:
    uv run python -m pipeline.flags.run_all
"""

from __future__ import annotations

import json
import logging
import time

import duckdb
import pyarrow as pa

from pipeline.config import MARTS_DIR
from pipeline.flags import (
    f01_unico_oferente,
    f02_empresa_expres,
    f03_adiciones_excesivas,
    f04_abuso_contratacion_directa,
    f05_fraccionamiento,
    f06_carrusel,
    f07_ventana_licitacion_corta,
    f08_precio_calcado,
    f09_afan_diciembre,
    f10_ventana_electoral,
    f11_proveedor_sancionado,
    f12_concentracion_dependencia,
    f13_objeto_vago,
    f14_valor_redondo,
)
from pipeline.flags.common import FlagRow
from pipeline.flags.params import FLAG_META

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# Order matches the PLAN.md catalog (F01..F14).
_MODULES = {
    "F01": f01_unico_oferente,
    "F02": f02_empresa_expres,
    "F03": f03_adiciones_excesivas,
    "F04": f04_abuso_contratacion_directa,
    "F05": f05_fraccionamiento,
    "F06": f06_carrusel,
    "F07": f07_ventana_licitacion_corta,
    "F08": f08_precio_calcado,
    "F09": f09_afan_diciembre,
    "F10": f10_ventana_electoral,
    "F11": f11_proveedor_sancionado,
    "F12": f12_concentracion_dependencia,
    "F13": f13_objeto_vago,
    "F14": f14_valor_redondo,
}

assert set(_MODULES) == set(FLAG_META), "run_all's module registry and params.FLAG_META must list the same flags"


def _create_tables(con: duckdb.DuckDBPyConnection) -> None:
    """(Re)create the two output tables. Idempotent, mirrors clean/build.py's own style."""
    con.execute("DROP TABLE IF EXISTS flag_contrato")
    con.execute("""
        CREATE TABLE flag_contrato (
            id_contrato VARCHAR,
            flag_id VARCHAR,
            fired BOOLEAN,
            evidence_json VARCHAR
        )
    """)
    con.execute("DROP TABLE IF EXISTS flag_entidad")
    con.execute("""
        CREATE TABLE flag_entidad (
            nit_entidad_norm VARCHAR,
            flag_id VARCHAR,
            fired BOOLEAN,
            evidence_json VARCHAR
        )
    """)


def _write_rows(con: duckdb.DuckDBPyConnection, table: str, rows: list[FlagRow]) -> None:
    """
    Bulk-load `rows` into `table` via a registered pyarrow Table rather than
    `executemany`. Measured on the sample mart: `executemany` was still
    running after 3+ minutes for a single 300k-row flag (of ~2M rows total
    across all 14 flags); building a pyarrow Table and inserting via
    `INSERT INTO ... SELECT * FROM <registered arrow table>` does the same
    300k rows in ~0.1s. pyarrow is already a pipeline dependency.
    """
    if not rows:
        return
    key_col = "nit_entidad_norm" if table == "flag_entidad" else "id_contrato"
    arrow_tbl = pa.table(
        {
            key_col: [row.key for row in rows],
            "flag_id": [row.flag_id for row in rows],
            "fired": [row.fired for row in rows],
            "evidence_json": [json.dumps(row.evidence, ensure_ascii=False, default=str) for row in rows],
        }
    )
    con.register("_flag_rows_tmp", arrow_tbl)
    try:
        con.execute(f"INSERT INTO {table} SELECT * FROM _flag_rows_tmp")  # noqa: S608 (table is one of two fixed constants)
    finally:
        con.unregister("_flag_rows_tmp")


def run(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """
    Run all 14 flags against `con`, (re)creating flag_contrato/flag_entidad in
    it. Returns one summary dict per flag: flag_id, nombre, nivel,
    population, fired, rate_pct, seconds.

    `con` is taken as a parameter (rather than this module owning the
    connection/path) so tests can point it at an in-memory copy of the real
    mart instead of the live file -- see tests/test_flags/test_sanity_rates.py.
    """
    _create_tables(con)

    summary = []
    for flag_id, mod in _MODULES.items():
        meta = FLAG_META[flag_id]
        t0 = time.time()
        rows = mod.compute(con)
        elapsed = time.time() - t0

        table = "flag_entidad" if meta["nivel"] == "entity" else "flag_contrato"
        _write_rows(con, table, rows)

        population = len(rows)
        fired = sum(1 for r in rows if r.fired)
        rate = (100.0 * fired / population) if population else 0.0
        summary.append(
            {
                "flag_id": flag_id,
                "nombre": meta["nombre"],
                "nivel": meta["nivel"],
                "population": population,
                "fired": fired,
                "rate_pct": rate,
                "seconds": elapsed,
            }
        )
        log.info(
            "%s (%s): population=%d fired=%d rate=%.2f%% [%.2fs]",
            flag_id, meta["nombre"], population, fired, rate, elapsed,
        )

    return summary


def print_summary(summary: list[dict]) -> None:
    header = f"{'Flag':6s} {'Nombre':32s} {'Nivel':9s} {'Poblacion':>10s} {'Fired':>8s} {'Rate %':>8s}"
    print()
    print(header)
    print("-" * len(header))
    for row in summary:
        print(
            f"{row['flag_id']:6s} {row['nombre']:32s} {row['nivel']:9s} "
            f"{row['population']:10d} {row['fired']:8d} {row['rate_pct']:7.2f}%"
        )
    print()


def main() -> None:
    db_path = MARTS_DIR / "corruption.duckdb"
    log.info("Connecting to %s", db_path)
    con = duckdb.connect(str(db_path))
    try:
        summary = run(con)
    finally:
        con.close()
    print_summary(summary)


if __name__ == "__main__":
    main()
