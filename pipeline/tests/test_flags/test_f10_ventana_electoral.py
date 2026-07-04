"""Unit tests for F10 -- Ventana electoral."""

from __future__ import annotations

from conftest import make_fct_contrato, make_ref_ventanas

from pipeline.flags import f10_ventana_electoral as f10


class TestF10:
    def test_positive_direct_contract_inside_window(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "modalidad_norm": "CONTRATACION_DIRECTA", "fecha_firma": "2023-08-15"}])
        make_ref_ventanas(mem_con)  # default window: VE2023T 2023-06-29..2023-10-29
        rows = f10.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["window_id"] == "VE2023T"

    def test_negative_direct_contract_outside_window(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "modalidad_norm": "CONTRATACION_DIRECTA", "fecha_firma": "2023-01-15"}])
        make_ref_ventanas(mem_con)
        rows = f10.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_competitive_modality_not_applicable(self, mem_con):
        """A competitive-modality contract signed during the same window is out of scope --
        F10 only targets direct contracting."""
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "modalidad_norm": "LICITACION_PUBLICA", "fecha_firma": "2023-08-15"}])
        make_ref_ventanas(mem_con)
        rows = f10.compute(mem_con)
        assert rows == []

    def test_edge_boundary_dates_inclusive(self, mem_con):
        make_fct_contrato(
            mem_con,
            [
                {"id_contrato": "START", "modalidad_norm": "CONTRATACION_DIRECTA", "fecha_firma": "2023-06-29"},
                {"id_contrato": "END", "modalidad_norm": "CONTRATACION_DIRECTA", "fecha_firma": "2023-10-29"},
            ],
        )
        make_ref_ventanas(mem_con)
        rows = {r.key: r for r in f10.compute(mem_con)}
        assert rows["START"].fired is True
        assert rows["END"].fired is True
