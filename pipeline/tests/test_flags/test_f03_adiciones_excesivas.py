"""Unit tests for F03 -- Adiciones excesivas (time and money sub-flags, both sources)."""

from __future__ import annotations

from conftest import make_fct_contrato, make_fct_proceso, make_stg_secop1

from pipeline.flags import f03_adiciones_excesivas as f03


class TestF03Tiempo:
    def test_positive_time_addition_over_half(self, mem_con):
        """dias_adicionados >= 50% of the initial duration -> fires on the time sub-flag."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "C1", "source": "SECOP2", "row_id": "r1",
                    "duracion_dias_inicial": 100, "dias_adicionados": 60, "valor_contrato": 1000,
                }
            ],
        )
        make_fct_proceso(mem_con, [])
        make_stg_secop1(mem_con, [])
        rows = f03.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["f03_tiempo"] is True

    def test_negative_small_time_addition(self, mem_con):
        """dias_adicionados well under 50% -> does not fire."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "C1", "source": "SECOP2", "row_id": "r1",
                    "duracion_dias_inicial": 100, "dias_adicionados": 5, "valor_contrato": 1000,
                }
            ],
        )
        make_fct_proceso(mem_con, [])
        make_stg_secop1(mem_con, [])
        rows = f03.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_zero_initial_duration_not_applicable(self, mem_con):
        """duracion_dias_inicial = 0 makes the time ratio meaningless (0.5*0=0, any
        dias_adicionados>=0 would trivially 'fire') -- must be excluded, not flagged."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "C1", "source": "SECOP2", "row_id": "r1",
                    "duracion_dias_inicial": 0, "dias_adicionados": 3, "valor_contrato": 1000,
                }
            ],
        )
        make_fct_proceso(mem_con, [])
        make_stg_secop1(mem_con, [])
        rows = f03.compute(mem_con)
        assert len(rows) == 0


class TestF03DineroSecop2:
    def test_positive_money_addition_via_join(self, mem_con):
        """valor_contrato is 50% over the process's awarded value -> fires the money sub-flag."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "C1", "source": "SECOP2", "row_id": "r1",
                    "proceso_de_compra": "P1", "duracion_dias_inicial": None, "dias_adicionados": 0,
                    "valor_contrato": 150,
                }
            ],
        )
        make_fct_proceso(mem_con, [{"referencia": "P1", "row_id": "pr1", "valor_adjudicacion": 100}])
        make_stg_secop1(mem_con, [])
        rows = f03.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["fuente_dinero"] == "secop2_join"

    def test_negative_no_money_addition(self, mem_con):
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "C1", "source": "SECOP2", "row_id": "r1",
                    "proceso_de_compra": "P1", "duracion_dias_inicial": None, "dias_adicionados": 0,
                    "valor_contrato": 101,
                }
            ],
        )
        make_fct_proceso(mem_con, [{"referencia": "P1", "row_id": "pr1", "valor_adjudicacion": 100}])
        make_stg_secop1(mem_con, [])
        rows = f03.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False


class TestF03DineroSecop1:
    def test_positive_money_addition_direct_columns(self, mem_con):
        """SECOP1 row: valor_total_de_adiciones / valor_contrato >= 40% -> fires."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "AT-1-2018", "source": "SECOP1", "row_id": "s1row",
                    "duracion_dias_inicial": None, "dias_adicionados": 0, "valor_contrato": 1000,
                }
            ],
        )
        make_fct_proceso(mem_con, [])
        make_stg_secop1(mem_con, [{":id": "s1row", "valor_total_de_adiciones": "500"}])
        rows = f03.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["fuente_dinero"] == "secop1_directo"

    def test_no_addition_row_still_applicable_via_time_or_excluded(self, mem_con):
        """If stg_secop1 has no matching row and duracion is also missing, the contract has
        no computable sub-flag at all and must be excluded from the population."""
        make_fct_contrato(
            mem_con,
            [
                {
                    "id_contrato": "AT-2-2018", "source": "SECOP1", "row_id": "no-match",
                    "duracion_dias_inicial": None, "dias_adicionados": None, "valor_contrato": 1000,
                }
            ],
        )
        make_fct_proceso(mem_con, [])
        make_stg_secop1(mem_con, [{":id": "other-row", "valor_total_de_adiciones": "500"}])
        rows = f03.compute(mem_con)
        assert len(rows) == 0
