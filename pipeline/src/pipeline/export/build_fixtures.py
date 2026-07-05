"""
M6 dev fixtures: a small synthetic mart, in the exact schema of the real
`corruption.duckdb`, so the M7 dashboard can be built/tested without needing
the full pipeline to have run.

Deliberately reuses `build_artifacts.run()` against an in-memory DuckDB
connection instead of hand-writing JSON: the fixtures are guaranteed to match
the real artifact shape exactly (same code, same JSON-schema validation,
different data) -- see build_artifacts.py's module docstring.

Uses the real 33 DIVIPOLA departments (so a choropleth map built against
fixtures renders actual Colombian department outlines), with sample
contracts concentrated in 4 of them and the rest correctly empty.

Usage:
    uv run python -m pipeline.export.build_fixtures
"""

from __future__ import annotations

import datetime as dt
import json
import logging

import duckdb

from pipeline.config import WEB_FIXTURES_DIR
from pipeline.export.build_artifacts import print_report, run
from pipeline.flags.params import FLAG_META
from pipeline.score.weights import MIN_CONTRATOS_RANK, tier_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Real DIVIPOLA department list (extracted from the production mart's
# `divipola` table, 2026-07) -- all 33 are present so `build_departamentos`
# emits a file per real department, most with zero contracts, matching how
# the real mart behaves for sparsely-represented departments.
# ---------------------------------------------------------------------------
_DEPARTAMENTOS: list[tuple[str, str, str]] = [
    ("11", "BOGOTÁ, D.C.", "BOGOTA, D.C."), ("13", "BOLÍVAR", "BOLIVAR"),
    ("15", "BOYACÁ", "BOYACA"), ("17", "CALDAS", "CALDAS"),
    ("18", "CAQUETÁ", "CAQUETA"), ("19", "CAUCA", "CAUCA"),
    ("20", "CESAR", "CESAR"), ("23", "CÓRDOBA", "CORDOBA"),
    ("25", "CUNDINAMARCA", "CUNDINAMARCA"), ("27", "CHOCÓ", "CHOCO"),
    ("41", "HUILA", "HUILA"), ("44", "LA GUAJIRA", "LA GUAJIRA"),
    ("47", "MAGDALENA", "MAGDALENA"), ("5", "ANTIOQUIA", "ANTIOQUIA"),
    ("50", "META", "META"), ("52", "NARIÑO", "NARINO"),
    ("54", "NORTE DE SANTANDER", "NORTE DE SANTANDER"), ("63", "QUINDÍO", "QUINDIO"),
    ("66", "RISARALDA", "RISARALDA"), ("68", "SANTANDER", "SANTANDER"),
    ("70", "SUCRE", "SUCRE"), ("73", "TOLIMA", "TOLIMA"),
    ("76", "VALLE DEL CAUCA", "VALLE DEL CAUCA"), ("8", "ATLÁNTICO", "ATLANTICO"),
    ("81", "ARAUCA", "ARAUCA"), ("85", "CASANARE", "CASANARE"),
    ("86", "PUTUMAYO", "PUTUMAYO"),
    ("88", "ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA",
     "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA"),
    ("91", "AMAZONAS", "AMAZONAS"), ("94", "GUAINÍA", "GUAINIA"),
    ("95", "GUAVIARE", "GUAVIARE"), ("97", "VAUPÉS", "VAUPES"),
    ("99", "VICHADA", "VICHADA"),
]

# Municipios that actually get contracts (cod_dpto, cod_mpio, nombre)
_MUNICIPIOS_ACTIVOS = [
    ("5", "5001", "MEDELLÍN"), ("5", "5266", "ENVIGADO"),
    ("11", "11001", "BOGOTÁ, D.C."),
    ("76", "76001", "CALI"), ("76", "76109", "BUENAVENTURA"),
    ("25", "25754", "SOACHA"),
]

_MODALIDADES = ["LICITACION_PUBLICA", "CONTRATACION_DIRECTA", "SELECCION_ABREVIADA", "MINIMA_CUANTIA"]

# Target scores chosen to land deterministically in each of the 4 tiers
# (bajo/medio/alto/critico), per weights.yaml's thresholds via tier_for().
_TARGET_SCORES = [5.0, 15.0, 28.0, 35.0, 45.0, 55.0, 65.0, 78.0, 90.0, 12.0] * 5  # 50 contracts


def _flags_for_score(score: float, contract_idx: int) -> list[dict]:
    """Pick a plausible subset of real flags (name/weight from FLAG_META) whose
    presence roughly tracks the target score, with real evidence-shaped payloads."""
    all_ids = sorted(FLAG_META)
    n_fire = max(0, min(len(all_ids), round(score / 100 * 5) + (contract_idx % 2)))
    chosen = [all_ids[(contract_idx + i) % len(all_ids)] for i in range(n_fire)]
    out = []
    for fid in dict.fromkeys(chosen):  # dedup, preserve order
        meta = FLAG_META[fid]
        evidence = {
            "F01": {"num_oferentes_unicos": 1, "modalidad_norm": "LICITACION_PUBLICA"},
            "F02": {"fecha_matricula": "2023-01-15", "dias_antes_publicacion": 45},
            "F03": {"dias_adicionados": 200, "duracion_dias_inicial": 300, "f03_tiempo": True},
            "F09": {"fecha_firma": "2022-12-22"},
            "F11": {"n_sanciones_antes_firma": 1, "fuentes_antes_firma": ["CGR"]},
            "F13": {"objeto_len": 18},
            "F14": {"valor_contrato": 1200000000},
        }.get(fid, {"nota": "evidencia sintetica de fixture"})
        out.append({"flag_id": fid, "nombre": meta["nombre"], "peso": meta["peso"], "evidence": evidence})
    return out


def build_fixture_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")

    con.execute("""
        CREATE TABLE divipola (
            cod_dpto VARCHAR, dpto VARCHAR, cod_mpio VARCHAR, municipio VARCHAR,
            dpto_norm VARCHAR, mpio_norm VARCHAR
        )
    """)
    for cod_dpto, dpto, dpto_norm in _DEPARTAMENTOS:
        munis = [m for m in _MUNICIPIOS_ACTIVOS if m[0] == cod_dpto] or [(cod_dpto, cod_dpto + "001", dpto)]
        for _, cod_mpio, municipio in munis:
            con.execute(
                "INSERT INTO divipola VALUES (?,?,?,?,?,?)",
                [cod_dpto, dpto, cod_mpio, municipio, dpto_norm, municipio.upper()],
            )

    con.execute("""
        CREATE TABLE fct_contrato (
            source VARCHAR, row_id VARCHAR, id_contrato VARCHAR, proceso_de_compra VARCHAR,
            nit_entidad_norm VARCHAR, nombre_entidad VARCHAR, doc_proveedor_norm VARCHAR, nombre_proveedor VARCHAR,
            cod_dpto VARCHAR, cod_mpio VARCHAR, modalidad_norm VARCHAR, es_competitiva BOOLEAN, es_abierta BOOLEAN,
            tipo_de_contrato VARCHAR, objeto_del_contrato VARCHAR, unspsc_segmento INTEGER,
            fecha_firma DATE, fecha_inicio DATE, fecha_fin DATE, duracion_dias_inicial INTEGER,
            dias_adicionados INTEGER, valor_contrato DOUBLE, valor_pagado DOUBLE, anio INTEGER,
            urlproceso VARCHAR, estado VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE contrato_score (
            id_contrato VARCHAR, nit_entidad_norm VARCHAR, nombre_entidad VARCHAR,
            doc_proveedor_norm VARCHAR, nombre_proveedor VARCHAR, cod_dpto VARCHAR, cod_mpio VARCHAR,
            valor_contrato DOUBLE, fecha_firma DATE, anio INTEGER, urlproceso VARCHAR, source VARCHAR,
            n_flags_aplicables INTEGER, n_flags_disparados INTEGER, score DOUBLE, tier VARCHAR, flags_disparados VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE entidad_score (
            nit_entidad_norm VARCHAR, nombre_entidad VARCHAR, cod_dpto VARCHAR, cod_mpio VARCHAR,
            n_contratos BIGINT, valor_total DOUBLE, contract_component DOUBLE, entity_component DOUBLE,
            combined_raw_score DOUBLE, dept_mean_score DOUBLE, k_shrinkage DOUBLE, score DOUBLE, tier VARCHAR,
            datos_insuficientes BOOLEAN, n_flags_aplicables INTEGER, n_flags_disparados INTEGER, flags_disparados VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE municipio_score (
            cod_dpto VARCHAR, cod_mpio VARCHAR, dpto VARCHAR, municipio VARCHAR, n_contratos BIGINT,
            valor_total DOUBLE, raw_score DOUBLE, dept_mean_score DOUBLE, k_shrinkage DOUBLE, score DOUBLE,
            tier VARCHAR, datos_insuficientes BOOLEAN
        )
    """)
    con.execute("""
        CREATE TABLE dim_proveedor (
            doc_proveedor_norm VARCHAR, nombre_proveedor VARCHAR, es_persona_natural BOOLEAN,
            n_contratos BIGINT, valor_total DOUBLE, fecha_matricula DATE
        )
    """)
    con.execute("""
        CREATE TABLE sanciones (doc_norm VARCHAR, nombre VARCHAR, fuente VARCHAR, fecha_sancion DATE, detalle VARCHAR)
    """)
    con.execute("""
        CREATE TABLE monitor_ciudadano_hechos (
            departamento VARCHAR, municipio VARCHAR, anio INTEGER,
            tipo_corrupcion VARCHAR, sector VARCHAR, descripcion VARCHAR
        )
    """)

    # -- Entities: 8 total, one deliberately under MIN_CONTRATOS_RANK ------
    entidades = [
        ("900111001", "ALCALDÍA DE MEDELLÍN", "5", "5001", 12),
        ("900111002", "GOBERNACIÓN DE ANTIOQUIA", "5", "5001", 9),
        ("900111003", "ALCALDÍA DE BOGOTÁ", "11", "11001", 15),
        ("900111004", "ALCALDÍA DE CALI", "76", "76001", 10),
        ("900111005", "ALCALDÍA DE BUENAVENTURA", "76", "76109", 3),  # datos_insuficientes
        ("900111006", "ALCALDÍA DE SOACHA", "25", "25754", 1),  # datos_insuficientes
    ]
    # -- Suppliers: 15, 3 with fecha_matricula (express-company scenario) ---
    proveedores = [(f"80099900{i}", f"PROVEEDOR EJEMPLO {i} SAS", i % 4 == 0) for i in range(1, 16)]
    fecha_matricula_by_doc = {
        proveedores[0][0]: dt.date(2023, 1, 15),  # express company
        proveedores[1][0]: dt.date(2010, 3, 1),
        proveedores[2][0]: dt.date(2005, 6, 20),
    }

    contratos = []
    for i in range(50):
        ent = entidades[i % len(entidades)]
        prov = proveedores[i % len(proveedores)]
        score = _TARGET_SCORES[i]
        tier = tier_for(score)
        anio = 2021 + (i % 3)
        fecha_firma = dt.date(anio, 12, 22) if i % 9 == 0 else dt.date(anio, 6, (i % 27) + 1)
        banderas = _flags_for_score(score, i)
        contratos.append({
            "id_contrato": f"FIXTURE-{i:04d}",
            "nit_entidad_norm": ent[0], "nombre_entidad": ent[1],
            "cod_dpto": ent[2], "cod_mpio": ent[3],
            "doc_proveedor_norm": prov[0], "nombre_proveedor": prov[1],
            "modalidad_norm": _MODALIDADES[i % len(_MODALIDADES)],
            "valor_contrato": 50_000_000.0 * ((i % 20) + 1),
            "fecha_firma": fecha_firma, "anio": anio,
            "urlproceso": f"https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=FIXTURE-{i:04d}",
            "source": "SECOP1" if i % 25 == 0 else "SECOP2",
            "score": score, "tier": tier,
            "n_flags_aplicables": max(len(banderas), 3),
            "n_flags_disparados": len(banderas),
            "flags_disparados": json.dumps(banderas, ensure_ascii=False),
        })

    for c in contratos:
        con.execute(
            """INSERT INTO contrato_score VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [c["id_contrato"], c["nit_entidad_norm"], c["nombre_entidad"], c["doc_proveedor_norm"], c["nombre_proveedor"],
             c["cod_dpto"], c["cod_mpio"], c["valor_contrato"], c["fecha_firma"], c["anio"], c["urlproceso"], c["source"],
             c["n_flags_aplicables"], c["n_flags_disparados"], c["score"], c["tier"], c["flags_disparados"]],
        )
        con.execute(
            """INSERT INTO fct_contrato VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [c["source"], c["id_contrato"], c["id_contrato"], f"PROC-{c['id_contrato']}",
             c["nit_entidad_norm"], c["nombre_entidad"], c["doc_proveedor_norm"], c["nombre_proveedor"],
             c["cod_dpto"], c["cod_mpio"], c["modalidad_norm"], c["modalidad_norm"] != "CONTRATACION_DIRECTA", True,
             "Prestación de servicios", "Objeto contractual de ejemplo para datos sinteticos de prueba", 80,
             c["fecha_firma"], c["fecha_firma"], dt.date(c["anio"] + 1, 6, 1), 300, 0,
             c["valor_contrato"], c["valor_contrato"] * 0.9, c["anio"], c["urlproceso"], "Ejecutado"],
        )

    for nit, nombre, cod_dpto, cod_mpio, n in entidades:
        ent_contratos = [c for c in contratos if c["nit_entidad_norm"] == nit]
        valor_total = sum(c["valor_contrato"] for c in ent_contratos) or 1.0
        avg_score = sum(c["score"] for c in ent_contratos) / len(ent_contratos) if ent_contratos else 10.0
        datos_insuf = n < MIN_CONTRATOS_RANK
        con.execute(
            "INSERT INTO entidad_score VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [nit, nombre, cod_dpto, cod_mpio, n, valor_total, avg_score, avg_score, avg_score, avg_score, 10.0,
             avg_score, tier_for(avg_score), datos_insuf, 5, 2 if avg_score > 20 else 0, "[]"],
        )

    for cod_dpto, cod_mpio, municipio in _MUNICIPIOS_ACTIVOS:
        muni_contratos = [c for c in contratos if c["cod_mpio"] == cod_mpio]
        n = len(muni_contratos) or 1
        valor_total = sum(c["valor_contrato"] for c in muni_contratos) or 0.0
        avg_score = (sum(c["score"] for c in muni_contratos) / n) if muni_contratos else None
        con.execute(
            "INSERT INTO municipio_score VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [cod_dpto, cod_mpio, next(d for c, d, _ in _DEPARTAMENTOS if c == cod_dpto), municipio, n, valor_total,
             avg_score, avg_score, 10.0, avg_score, tier_for(avg_score) if avg_score else None, n < MIN_CONTRATOS_RANK],
        )

    for doc, nombre, es_pn in proveedores:
        prov_contratos = [c for c in contratos if c["doc_proveedor_norm"] == doc]
        con.execute(
            "INSERT INTO dim_proveedor VALUES (?,?,?,?,?,?)",
            [doc, nombre, es_pn, len(prov_contratos), sum(c["valor_contrato"] for c in prov_contratos),
             fecha_matricula_by_doc.get(doc)],
        )

    # -- Sanciones: one AFTER a contract's signing (valid positive label), one BEFORE (leakage-guard demo) --
    con.execute(
        "INSERT INTO sanciones VALUES (?,?,?,?,?)",
        [proveedores[0][0], proveedores[0][1], "CGR", dt.date(2024, 1, 10), "Responsabilidad fiscal (dato sintetico de fixture)"],
    )
    con.execute(
        "INSERT INTO sanciones VALUES (?,?,?,?,?)",
        [proveedores[1][0], proveedores[1][1], "SIRI", dt.date(2015, 1, 1),
         "Sancion disciplinaria previa (dato sintetico, no debe contar como positivo)"],
    )

    # -- Monitor Ciudadano: 2 usable rows matching an active dept/muni/year, 1 with blank fields --
    con.execute("INSERT INTO monitor_ciudadano_hechos VALUES (?,?,?,?,?,?)",
                ["ANTIOQUIA", "MEDELLÍN", 2022, "Corrupción Administrativa", "Infraestructura", "Hecho sintetico de ejemplo (fixture)"])
    con.execute("INSERT INTO monitor_ciudadano_hechos VALUES (?,?,?,?,?,?)",
                ["VALLE DEL CAUCA", "CALI", 2021, "Corrupción Política", "Salud", "Hecho sintetico de ejemplo (fixture)"])
    con.execute("INSERT INTO monitor_ciudadano_hechos VALUES (?,?,?,?,?,?)", ["", "", None, "", "", ""])

    return con


def main() -> None:
    con = build_fixture_con()
    try:
        summary = run(con, WEB_FIXTURES_DIR, validate=True)
    finally:
        con.close()
    print_report(summary)


if __name__ == "__main__":
    main()
