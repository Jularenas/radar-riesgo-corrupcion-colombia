"""Unit tests for F01 -- Único oferente."""

from __future__ import annotations

from conftest import make_fct_contrato, make_fct_proceso

from pipeline.flags import f01_unico_oferente as f01


def _setup(con, *, modalidad_norm, es_competitiva, num_oferentes_unicos):
    make_fct_contrato(
        con,
        [
            {
                "id_contrato": "C1",
                "proceso_de_compra": "P1",
                "modalidad_norm": modalidad_norm,
                "es_competitiva": es_competitiva,
            }
        ],
    )
    make_fct_proceso(
        con,
        [
            {
                "id_del_proceso": "REQ1",
                "referencia": "P1",
                "row_id": "r1",
                "num_oferentes_unicos": num_oferentes_unicos,
                "num_invitados": 5,
                "num_respuestas": num_oferentes_unicos,
                "fecha_publicacion": "2023-01-01",
            }
        ],
    )


class TestF01:
    def test_positive_single_bidder_competitive(self, mem_con):
        """Competitive modality + exactly 1 bidder -> fires."""
        _setup(mem_con, modalidad_norm="LICITACION_PUBLICA", es_competitiva=True, num_oferentes_unicos=1)
        rows = f01.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is True
        assert rows[0].key == "C1"
        assert rows[0].evidence["num_oferentes_unicos"] == 1

    def test_negative_multiple_bidders(self, mem_con):
        """Competitive modality + several bidders -> does not fire, but is in population."""
        _setup(mem_con, modalidad_norm="LICITACION_PUBLICA", es_competitiva=True, num_oferentes_unicos=4)
        rows = f01.compute(mem_con)
        assert len(rows) == 1
        assert rows[0].fired is False

    def test_edge_non_competitive_single_bidder_not_applicable(self, mem_con):
        """Non-competitive modality (e.g. contratación directa) with 1 bidder must NOT fire --
        it isn't even part of F01's applicable population (only competitive processes are)."""
        _setup(mem_con, modalidad_norm="CONTRATACION_DIRECTA", es_competitiva=False, num_oferentes_unicos=1)
        rows = f01.compute(mem_con)
        assert len(rows) == 0

    def test_unjoined_contract_excluded(self, mem_con):
        """A competitive contract with no matching process (join miss) is excluded, not a false fire."""
        make_fct_contrato(
            mem_con,
            [{"id_contrato": "C2", "proceso_de_compra": "NO-MATCH", "modalidad_norm": "LICITACION_PUBLICA", "es_competitiva": True}],
        )
        make_fct_proceso(mem_con, [])
        rows = f01.compute(mem_con)
        assert len(rows) == 0
