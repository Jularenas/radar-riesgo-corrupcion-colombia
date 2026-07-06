"""Tests for M6: JSON-schema validation, chunking math, size-budget enforcement, and the fixture generator."""

from __future__ import annotations

import json

import pytest

from pipeline.export.build_artifacts import (
    MAX_FILE_BYTES,
    MAX_TOTAL_BYTES,
    SizeBudgetExceeded,
    check_size_budget,
)
from pipeline.export.build_fixtures import build_fixture_con
from pipeline.export.common import chunk_list, write_json
from pipeline.export.validate import SchemaValidationError, validate_artifact, validate_many

VALID_META = {
    "generado_en": "2026-07-04T12:00:00Z",
    "version": {"git_commit": "abc1234"},
    "banderas": [{"id": "F01", "nombre": "Único oferente", "nivel": "contract", "peso": 15, "descripcion": "texto"}],
    "niveles_riesgo": [{"id": "bajo", "nombre": "Bajo", "min_score": 0, "max_score": 20}],
    "formula_score": "100 x ...",
    "shrinkage": {"k": 10, "min_contratos_rank": 10},
    "backtest": {
        "auc_roc": 0.42, "objetivo_auc_roc": 0.6, "lift_top_decil": 0.9, "objetivo_lift_top_decil": 1.5,
        "cumple_objetivos": False, "n_contratos_evaluados": 100, "n_positivos_l1_l4": 1,
        "precision_top_1pct": None, "precision_top_5pct": None, "precision_top_10pct": None,
        "casos_emblematicos": [], "n_casos_emblematicos_total": 0,
        "n_casos_emblematicos_con_coincidencias_genuinas": 0, "n_casos_emblematicos_en_percentil_superior": 0,
        "monitor_ciudadano": {"n_total": 0, "n_matched": 0, "match_rate_pct": None, "nota": "x"},
        "resumen": "texto",
    },
    "artefactos": {
        "casos_prioritarios": {"top_n": 2500, "chunk_size": 500, "n_chunks": 1, "patron_archivo": "x"},
        "contratos_recientes": {"top_n": 1000, "chunk_size": 500, "n_chunks": 1, "patron_archivo": "x"},
        "entidades_top": {"top_n": 300, "criterio": "x"},
        "proveedores_top": {"top_n": 300, "criterio": "x"},
        "departamentos": {"patron_archivo": "x", "top_n_entidades_por_departamento": 50},
    },
}


class TestSchemaValidation:
    def test_valid_meta_passes(self):
        validate_artifact("meta", VALID_META, source="test")

    def test_broken_meta_fails(self):
        broken = {k: v for k, v in VALID_META.items() if k != "banderas"}  # required field missing
        with pytest.raises(SchemaValidationError):
            validate_artifact("meta", broken, source="test")

    def test_validate_many_collects_all_failures(self):
        good = ({"cod_dpto": "05", "dpto": "ANTIOQUIA", "n_contratos": 0, "valor_total": 0,
                 "score_promedio": None, "n_bajo": 0, "n_medio": 0, "n_alto": 0, "n_criticos": 0,
                 "municipios": [], "top_entidades": [], "serie_anio": []}, "good.json")
        bad = ({"cod_dpto": "05"}, "bad.json")  # missing required fields
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_many("departamento", [good, bad])
        assert "bad.json" in str(exc_info.value)
        assert "good.json" not in str(exc_info.value)

    def test_unknown_schema_name_raises(self):
        with pytest.raises(KeyError):
            validate_artifact("no_existe", {}, source="test")


class TestChunking:
    def test_exact_multiple(self):
        chunks = chunk_list(list(range(1000)), 500)
        assert len(chunks) == 2
        assert [len(c) for c in chunks] == [500, 500]

    def test_partial_last_chunk(self):
        chunks = chunk_list(list(range(2500)), 500)
        assert len(chunks) == 5
        assert [len(c) for c in chunks] == [500, 500, 500, 500, 500]

        chunks = chunk_list(list(range(2237)), 500)
        assert len(chunks) == 5
        assert [len(c) for c in chunks] == [500, 500, 500, 500, 237]

    def test_empty_input(self):
        assert chunk_list([], 500) == []

    def test_invalid_chunk_size_raises(self):
        with pytest.raises(ValueError):
            chunk_list([1, 2, 3], 0)


class TestSizeBudget:
    def test_within_budget_passes(self, tmp_path):
        write_json(tmp_path / "small.json", {"a": 1})
        result = check_size_budget(tmp_path)
        assert result["n_files"] == 1
        assert result["total_bytes"] < MAX_TOTAL_BYTES

    def test_oversized_single_file_raises(self, tmp_path):
        big_path = tmp_path / "huge.json"
        big_path.write_text(json.dumps({"data": "x" * (MAX_FILE_BYTES + 1000)}), encoding="utf-8")
        with pytest.raises(SizeBudgetExceeded, match="huge.json"):
            check_size_budget(tmp_path)

    def test_oversized_total_raises_even_if_each_file_ok(self, tmp_path, monkeypatch):
        # Simulate exceeding the *total* budget with many small (individually OK) files.
        monkeypatch.setattr("pipeline.export.build_artifacts.MAX_TOTAL_BYTES", 100)
        write_json(tmp_path / "a.json", {"a": "x" * 60})
        write_json(tmp_path / "b.json", {"b": "x" * 60})
        with pytest.raises(SizeBudgetExceeded, match="Tamano total"):
            check_size_budget(tmp_path)


class TestFixtures:
    def test_fixture_con_has_all_required_tables(self):
        con = build_fixture_con()
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            assert tables >= {
                "fct_contrato", "contrato_score", "entidad_score", "municipio_score",
                "dim_proveedor", "sanciones", "monitor_ciudadano_hechos", "divipola",
            }
            assert con.execute("SELECT COUNT(*) FROM contrato_score").fetchone()[0] == 50
            assert con.execute("SELECT COUNT(*) FROM divipola").fetchone()[0] >= 33  # all real departments present
        finally:
            con.close()

    def test_fixture_covers_all_four_tiers(self):
        con = build_fixture_con()
        try:
            tiers = {r[0] for r in con.execute("SELECT DISTINCT tier FROM contrato_score").fetchall()}
        finally:
            con.close()
        assert tiers == {"bajo", "medio", "alto", "critico"}

    def test_fixture_has_at_least_one_datos_insuficientes_entity(self):
        con = build_fixture_con()
        try:
            n = con.execute("SELECT COUNT(*) FROM entidad_score WHERE datos_insuficientes").fetchone()[0]
        finally:
            con.close()
        assert n >= 1

    def test_build_fixtures_run_produces_schema_valid_artifacts(self, tmp_path):
        """End-to-end: fixture mart -> build_artifacts.run() -> real schema validation, into a tmp dir (not the committed fixtures path)."""
        from pipeline.export.build_artifacts import run

        con = build_fixture_con()
        try:
            summary = run(con, tmp_path, validate=True)  # raises on any schema failure
        finally:
            con.close()

        assert summary["n_casos_prioritarios"] == 50
        assert summary["n_contratos_recientes"] == 50
        assert summary["n_departamentos"] == 33
        assert (tmp_path / "meta.json").exists()
        assert (tmp_path / "resumen_nacional.json").exists()
        assert (tmp_path / "casos_prioritarios" / "000.json").exists()
        assert (tmp_path / "contratos_recientes" / "000.json").exists()


class TestContratosRecientes:
    """
    Regression coverage for a real bug caught manually: 5 legacy SECOP I rows
    in the production mart (all pre-2000 ANI contracts) have a corrupted
    century in fecha_firma (e.g. 1994 stored as 2094), invisible everywhere
    else because they score ~0, but a fecha_firma-desc sort put "signed in
    2096" at the top of the page. build_contratos_recientes must exclude any
    fecha_firma after today, however the fixture/mart happens to be seeded.
    """

    def test_excludes_contract_with_corrupted_future_fecha_firma(self):
        import datetime as dt

        from pipeline.export.build_artifacts import build_contratos_recientes

        con = build_fixture_con()
        try:
            con.execute("UPDATE contrato_score SET fecha_firma = DATE '2096-05-23' WHERE id_contrato = 'FIXTURE-0000'")
            con.execute("UPDATE fct_contrato SET fecha_firma = DATE '2096-05-23' WHERE id_contrato = 'FIXTURE-0000'")
            items = build_contratos_recientes(con)
        finally:
            con.close()

        today_iso = dt.date.today().isoformat()
        ids = {i["id_contrato"] for i in items}
        assert "FIXTURE-0000" not in ids
        assert all(i["fecha_firma"] <= today_iso for i in items)  # ISO dates compare lexicographically
        assert len(items) == 49  # 50 fixture contracts minus the one excluded for a future date
