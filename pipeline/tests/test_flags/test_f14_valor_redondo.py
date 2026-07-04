"""Unit tests for F14 -- Valor redondo."""

from __future__ import annotations

from conftest import make_fct_contrato

from pipeline.flags import f14_valor_redondo as f14


class TestF14:
    def test_positive_round_billion_plus(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "valor_contrato": 1_200_000_000}])
        rows = f14.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_negative_not_a_round_number(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "valor_contrato": 1_234_567_890}])
        rows = f14.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_round_but_below_minimum_value(self, mem_con):
        """900M is a round multiple of 100M but under the 1,000M floor -- must not fire."""
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "valor_contrato": 900_000_000}])
        rows = f14.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_exactly_at_minimum(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "valor_contrato": 1_000_000_000}])
        rows = f14.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_edge_null_value_excluded(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "valor_contrato": None}])
        rows = f14.compute(mem_con)
        assert rows == []
