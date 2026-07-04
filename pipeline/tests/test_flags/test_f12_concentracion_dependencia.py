"""Unit tests for F12 -- Concentración/dependencia (entity level, grain = entity x year)."""

from __future__ import annotations

from conftest import make_fct_contrato

from pipeline.flags import f12_concentracion_dependencia as f12


def _row(cid, entity, supplier, valor, anio=2023):
    return {"id_contrato": cid, "nit_entidad_norm": entity, "doc_proveedor_norm": supplier, "valor_contrato": valor, "anio": anio}


class TestF12:
    def test_positive_condition_a_entity_captured_by_one_supplier(self, mem_con):
        """Entity E1 (>=5 contracts that year): supplier S1 takes 87.5% of its annual value."""
        rows = []
        for i in range(3):
            rows.append(_row(f"C-S1-{i}", "E1", "S1", 700))
        for i in range(2):
            rows.append(_row(f"C-S2-{i}", "E1", "S2", 150))
        make_fct_contrato(mem_con, rows)

        out = {r.key: r for r in f12.compute(mem_con)}
        assert "E1" in out
        assert out["E1"].fired is True
        assert out["E1"].evidence["condicion_a_captura_entidad"] is True
        assert out["E1"].evidence["doc_proveedor_dominante"] == "S1"

    def test_positive_condition_b_supplier_dependent_on_entity(self, mem_con):
        """Entity E2's top supplier by value (S3) holds only ~29% of E2's annual value (so
        condition A does NOT fire), but S3 does all 5 of its contracts with E2 alone -- 100%
        of S3's own annual revenue depends on this one entity -> condition B fires."""
        rows = []
        for i in range(5):
            rows.append(_row(f"C-S3-{i}", "E2", "S3", 100))
        for supplier in ("SA", "SB", "SC"):
            for i in range(2):
                rows.append(_row(f"C-{supplier}-{i}", "E2", supplier, 200))
        make_fct_contrato(mem_con, rows)

        out = {r.key: r for r in f12.compute(mem_con)}
        assert "E2" in out
        assert out["E2"].evidence["doc_proveedor_dominante"] == "S3"
        assert out["E2"].evidence["condicion_a_captura_entidad"] is False
        assert out["E2"].evidence["condicion_b_dependencia_proveedor"] is True
        assert out["E2"].fired is True

    def test_negative_diversified_entity_and_suppliers(self, mem_con):
        """5 suppliers, 2 contracts each, no supplier dominates and none has enough contracts
        (only 2 < the 5-contract floor) to demonstrate a dependency pattern either."""
        rows = []
        for supplier in ("SA", "SB", "SC", "SD", "SE"):
            for i in range(2):
                rows.append(_row(f"C-{supplier}-{i}", "E3", supplier, 200))
        make_fct_contrato(mem_con, rows)

        out = {r.key: r for r in f12.compute(mem_con)}
        assert "E3" in out
        assert out["E3"].fired is False

    def test_edge_entity_below_minimum_contracts_excluded(self, mem_con):
        """Entity with only 3 contracts that year -- below the >=5 floor -- is excluded from
        the applicable population entirely, even though one supplier has 100% share."""
        rows = [_row(f"C{i}", "E4", "S1", 500) for i in range(3)]
        make_fct_contrato(mem_con, rows)

        out = f12.compute(mem_con)
        assert out == []
