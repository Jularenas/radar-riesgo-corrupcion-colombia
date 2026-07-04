"""Unit tests for F08 -- Precio calcado."""

from __future__ import annotations

from conftest import make_fct_contrato, make_fct_proceso

from pipeline.flags import f08_precio_calcado as f08


def _setup(con, *, es_competitiva, valor_contrato, precio_base):
    make_fct_contrato(
        con,
        [{"id_contrato": "C1", "proceso_de_compra": "P1", "es_competitiva": es_competitiva, "valor_contrato": valor_contrato}],
    )
    make_fct_proceso(con, [{"referencia": "P1", "row_id": "r1", "precio_base": precio_base}])


class TestF08:
    def test_positive_within_tolerance(self, mem_con):
        """0.2% above precio_base -- within the +-0.5% tolerance."""
        _setup(mem_con, es_competitiva=True, valor_contrato=100_200_000, precio_base=100_000_000)
        rows = f08.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_negative_far_from_precio_base(self, mem_con):
        _setup(mem_con, es_competitiva=True, valor_contrato=80_000_000, precio_base=100_000_000)
        rows = f08.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_exactly_at_tolerance_boundary(self, mem_con):
        """Exactly 0.5% over precio_base -- boundary is inclusive (<=)."""
        _setup(mem_con, es_competitiva=True, valor_contrato=100_500_000, precio_base=100_000_000)
        rows = f08.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_edge_zero_precio_base_excluded(self, mem_con):
        """precio_base = 0 would make the ratio undefined -- must be excluded, not fired."""
        _setup(mem_con, es_competitiva=True, valor_contrato=100_000_000, precio_base=0)
        rows = f08.compute(mem_con)
        assert rows == []

    def test_edge_non_competitive_excluded(self, mem_con):
        _setup(mem_con, es_competitiva=False, valor_contrato=100_000_000, precio_base=100_000_000)
        rows = f08.compute(mem_con)
        assert rows == []
