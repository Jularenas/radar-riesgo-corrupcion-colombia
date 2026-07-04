"""Unit tests for F07 -- Ventana de licitación corta."""

from __future__ import annotations

from conftest import make_fct_contrato, make_fct_proceso

from pipeline.flags import f07_ventana_licitacion_corta as f07


def _setup(con, *, modalidad_norm, fecha_publicacion, fecha_recepcion_respuestas):
    make_fct_contrato(
        con,
        [{"id_contrato": "C1", "proceso_de_compra": "P1", "modalidad_norm": modalidad_norm, "es_competitiva": True}],
    )
    make_fct_proceso(
        con,
        [
            {
                "referencia": "P1", "row_id": "r1",
                "fecha_publicacion": fecha_publicacion,
                "fecha_recepcion_respuestas": fecha_recepcion_respuestas,
            }
        ],
    )


class TestF07:
    def test_positive_licitacion_below_floor(self, mem_con):
        """Licitación pública: only 5 days between publication and bid deadline (floor is 10)."""
        _setup(mem_con, modalidad_norm="LICITACION_PUBLICA", fecha_publicacion="2023-01-01", fecha_recepcion_respuestas="2023-01-06")
        rows = f07.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["dias_ventana"] == 5

    def test_negative_licitacion_above_floor(self, mem_con):
        """Licitación pública with a normal 20-day window -- does not fire."""
        _setup(mem_con, modalidad_norm="LICITACION_PUBLICA", fecha_publicacion="2023-01-01", fecha_recepcion_respuestas="2023-01-21")
        rows = f07.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_selection_abreviada_uses_its_own_lower_floor(self, mem_con):
        """4 days is short for selección abreviada (floor 5) even though it'd also be short
        for licitación -- confirms the per-modality floor is actually applied, not a single
        global constant."""
        _setup(mem_con, modalidad_norm="SELECCION_ABREVIADA", fecha_publicacion="2023-01-01", fecha_recepcion_respuestas="2023-01-05")
        rows = f07.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True

    def test_edge_negative_day_count_excluded(self, mem_con):
        """Bid deadline recorded before the publication date is a data error, not a genuinely
        short window -- must be excluded from the population entirely."""
        _setup(mem_con, modalidad_norm="LICITACION_PUBLICA", fecha_publicacion="2023-05-01", fecha_recepcion_respuestas="2023-04-20")
        rows = f07.compute(mem_con)
        assert rows == []

    def test_edge_modality_without_defined_floor_not_applicable(self, mem_con):
        """Concurso de méritos has no floor defined in PLAN.md -- out of scope, not flagged."""
        _setup(mem_con, modalidad_norm="CONCURSO_MERITOS", fecha_publicacion="2023-01-01", fecha_recepcion_respuestas="2023-01-02")
        rows = f07.compute(mem_con)
        assert rows == []
