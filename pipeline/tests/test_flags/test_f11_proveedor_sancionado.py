"""Unit tests for F11 -- Proveedor sancionado."""

from __future__ import annotations

from conftest import make_fct_contrato, make_sanciones

from pipeline.flags import f11_proveedor_sancionado as f11


class TestF11:
    def test_positive_sanction_before_signing(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "doc_proveedor_norm": "900111222", "fecha_firma": "2023-06-01"}])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2022-01-01"}])
        rows = f11.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["n_sanciones_antes_firma"] == 1

    def test_negative_sanction_after_signing_does_not_fire(self, mem_con):
        """A sanction dated *after* the contract was signed must NOT count toward scoring --
        but should still show up in the any-date context evidence."""
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "doc_proveedor_norm": "900111222", "fecha_firma": "2023-06-01"}])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2024-01-01"}])
        rows = f11.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False
        assert rows[0].evidence["n_sanciones_antes_firma"] == 0
        assert rows[0].evidence["n_sanciones_total_contexto"] == 1

    def test_negative_no_sanction_at_all(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "doc_proveedor_norm": "900999888", "fecha_firma": "2023-06-01"}])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2022-01-01"}])
        rows = f11.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False
        assert rows[0].evidence["n_sanciones_total_contexto"] == 0

    def test_edge_missing_supplier_doc_excluded(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "doc_proveedor_norm": None, "fecha_firma": "2023-06-01"}])
        make_sanciones(mem_con, [])
        rows = f11.compute(mem_con)
        assert rows == []

    def test_multiple_sanctions_aggregated_into_one_row(self, mem_con):
        """A supplier with several matching sanciones rows must still yield exactly one
        flag_contrato row for that contract (not one per sanction)."""
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "doc_proveedor_norm": "900111222", "fecha_firma": "2023-06-01"}])
        make_sanciones(
            mem_con,
            [
                {"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2022-01-01"},
                {"doc_norm": "900111222", "fuente": "CGR", "fecha_sancion": "2021-06-01"},
            ],
        )
        rows = f11.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].evidence["n_sanciones_antes_firma"] == 2
