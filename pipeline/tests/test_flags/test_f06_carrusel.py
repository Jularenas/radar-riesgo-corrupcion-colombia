"""Unit tests for F06 -- Carrusel."""

from __future__ import annotations

from conftest import make_fct_contrato

from pipeline.flags import f06_carrusel as f06


def _rows(entity, unspsc, winners, dates):
    return [
        {
            "id_contrato": f"C{i}",
            "nit_entidad_norm": entity,
            "unspsc_segmento": unspsc,
            "doc_proveedor_norm": w,
            "es_competitiva": True,
            "fecha_firma": d,
            "valor_contrato": 1000.0,
        }
        for i, (w, d) in enumerate(zip(winners, dates, strict=True))
    ]


def _monthly_dates(n, start="2023-01-01"):
    import datetime

    d0 = datetime.date.fromisoformat(start)
    return [(d0 + datetime.timedelta(days=20 * i)).isoformat() for i in range(n)]


class TestF06:
    def test_positive_tight_rotation_of_three_winners(self, mem_con):
        """9 competitive processes, 3 winners strictly alternating -> textbook carousel."""
        winners = ["W1", "W2", "W3"] * 3
        make_fct_contrato(mem_con, _rows("E1", 80, winners, _monthly_dates(9)))
        rows = f06.compute(mem_con)
        assert len(rows) == 9
        assert all(r.fired for r in rows)
        assert rows[0].evidence["indice_alternancia"] == 1.0
        assert rows[0].evidence["n_ganadores_distintos"] == 3

    def test_negative_too_many_distinct_winners(self, mem_con):
        """9 processes, 9 different winners -- a genuinely competitive/diverse market, not a
        tight rotation -- must not fire."""
        winners = [f"W{i}" for i in range(9)]
        make_fct_contrato(mem_con, _rows("E2", 81, winners, _monthly_dates(9)))
        rows = f06.compute(mem_con)
        assert len(rows) == 9
        assert not any(r.fired for r in rows)

    def test_negative_one_dominant_winner_below_share_floor(self, mem_con):
        """9 processes, 2 winners, but the second only won once (11% share, below the 15%
        floor) -- that's a near-monopoly with an outlier, not an alternating carousel."""
        winners = ["W1"] * 8 + ["W2"]
        make_fct_contrato(mem_con, _rows("E3", 82, winners, _monthly_dates(9)))
        rows = f06.compute(mem_con)
        assert len(rows) == 9
        assert not any(r.fired for r in rows)

    def test_negative_low_alternation_two_consecutive_blocks(self, mem_con):
        """8 processes, exactly 2 winners with an even 50/50 split (share condition satisfied),
        but as two consecutive blocks (W1 x4 then W2 x4) rather than alternating -- only 1 of 7
        transitions switches (index ~0.14), well under the 0.6 floor."""
        winners = ["W1"] * 4 + ["W2"] * 4
        make_fct_contrato(mem_con, _rows("E4", 83, winners, _monthly_dates(8)))
        rows = f06.compute(mem_con)
        assert len(rows) == 8
        assert not any(r.fired for r in rows)

    def test_edge_too_few_processes(self, mem_con):
        """Only 6 processes -- below the >=8 floor, even with perfect alternation."""
        winners = ["W1", "W2"] * 3
        make_fct_contrato(mem_con, _rows("E5", 84, winners, _monthly_dates(6)))
        rows = f06.compute(mem_con)
        assert len(rows) == 6
        assert not any(r.fired for r in rows)
