"""Unit tests for F09 -- Afán de diciembre."""

from __future__ import annotations

from conftest import make_fct_contrato

from pipeline.flags import f09_afan_diciembre as f09


class TestF09:
    def test_positive_december_20(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "fecha_firma": "2023-12-20"}])
        rows = f09.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_negative_early_december(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "fecha_firma": "2023-12-10"}])
        rows = f09.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_negative_other_month(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "fecha_firma": "2023-06-20"}])
        rows = f09.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_boundary_december_15_fires(self, mem_con):
        """Dec 15 is the inclusive start of the window."""
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "fecha_firma": "2023-12-15"}])
        rows = f09.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_edge_boundary_december_31_fires(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "fecha_firma": "2023-12-31"}])
        rows = f09.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_edge_null_fecha_firma_excluded(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "fecha_firma": None}])
        rows = f09.compute(mem_con)
        assert rows == []
