"""Unit tests for F13 -- Objeto vago (short text OR top-decile repeated/boilerplate text)."""

from __future__ import annotations

from conftest import make_fct_contrato

from pipeline.flags import f13_objeto_vago as f13

_LONG_UNIQUE = "PRESTACION DE SERVICIOS PROFESIONALES ESPECIALIZADOS PARA EL PROYECTO NUMERO "


class TestF13:
    def test_positive_short_object(self, mem_con):
        """A contract object under 40 chars fires regardless of repetition."""
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "objeto_del_contrato": "Compra de insumos"}])
        rows = f13.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].evidence["objeto_muy_corto"] is True

    def test_negative_long_unique_object(self, mem_con):
        """A single-row population makes 'top decile' degenerate (everything is the 100th
        percentile of itself). Give the target row a realistic comparison population -- a
        common boilerplate text repeated 8x -- so the P90 threshold is meaningfully above 1,
        and confirm the long, one-off text sits below it."""
        target_text = _LONG_UNIQUE + "0001 CON ALCANCE DETALLADO Y ESPECIFICO"
        filler_text = _LONG_UNIQUE + "COMUN REPETIDO EN VARIOS CONTRATOS"
        rows = [{"id_contrato": "TARGET", "objeto_del_contrato": target_text}]
        rows += [{"id_contrato": f"FILLER{i}", "objeto_del_contrato": filler_text} for i in range(8)]
        make_fct_contrato(mem_con, rows)
        out = {r.key: r for r in f13.compute(mem_con)}
        assert out["TARGET"].fired is False
        assert out["TARGET"].evidence["objeto_repetitivo"] is False

    def test_positive_top_decile_boilerplate_repetition(self, mem_con):
        """10 contracts: one long text repeated 5x (freq=5, lands at the P90 cutoff of this
        tiny population) and 5 other contracts each with a distinct long text (freq=1). The
        5 repeated ones must fire on repetition; the 5 unique ones must not fire at all."""
        boilerplate = _LONG_UNIQUE + "GENERICO SIN DETALLE ADICIONAL DE ALCANCE"
        rows = [{"id_contrato": f"REP{i}", "objeto_del_contrato": boilerplate} for i in range(5)]
        rows += [
            {"id_contrato": f"UNIQ{i}", "objeto_del_contrato": f"{_LONG_UNIQUE}{i:04d} CON ALCANCE DETALLADO Y ESPECIFICO"}
            for i in range(5)
        ]
        make_fct_contrato(mem_con, rows)

        out = {r.key: r for r in f13.compute(mem_con)}
        assert len(out) == 10
        for i in range(5):
            assert out[f"REP{i}"].fired is True
            assert out[f"REP{i}"].evidence["objeto_repetitivo"] is True
        for i in range(5):
            assert out[f"UNIQ{i}"].fired is False

    def test_edge_null_object_excluded(self, mem_con):
        make_fct_contrato(mem_con, [{"id_contrato": "C1", "objeto_del_contrato": None}])
        rows = f13.compute(mem_con)
        assert rows == []
