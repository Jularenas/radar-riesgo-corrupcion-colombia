"""
Unit tests for pipeline.score.scorer.

Score-formula tests monkeypatch `scorer.FLAG_META` to a small, fully
controlled weight set (independent of whatever pipeline/src/pipeline/score/
weights.yaml currently says -- including after the M5 backtest's one
documented weight iteration) so expected scores can be hand-computed and
hardcoded rather than re-derived via the same formula the code implements.
"""

from __future__ import annotations

import json

import duckdb
import pytest
from score_fixtures import (
    make_dim_entidad,
    make_divipola,
    make_fct_contrato,
    make_flag_contrato,
    make_flag_entidad,
)

from pipeline.score import scorer


@pytest.fixture
def mem_con():
    con = duckdb.connect(":memory:")
    yield con
    con.close()

_SMALL_WEIGHTS = {
    "FX1": {"nombre": "Flag Uno", "nivel": "contract", "peso": 10},
    "FX2": {"nombre": "Flag Dos", "nivel": "contract", "peso": 30},
    "FX3": {"nombre": "Flag Tres", "nivel": "contract", "peso": 60},
    "EX1": {"nombre": "Entidad Uno", "nivel": "entity", "peso": 5},
    "EX2": {"nombre": "Entidad Dos", "nivel": "entity", "peso": 15},
}


@pytest.fixture
def small_weights(monkeypatch):
    monkeypatch.setattr(scorer, "FLAG_META", _SMALL_WEIGHTS)
    return _SMALL_WEIGHTS


def _one_contrato_row(id_contrato: str, **overrides) -> dict:
    row = {
        "id_contrato": id_contrato,
        "row_id": f"r-{id_contrato}",
        "fecha_firma": "2023-01-01",
        "valor_contrato": 1000.0,
        "anio": 2023,
    }
    row.update(overrides)
    return row


class TestContractScoreFormula:
    """score = 100 x sum(weights fired) / sum(weights applicable); NULL if 0 applicable."""

    def test_known_fired_flags_produce_known_score(self, mem_con, small_weights):
        make_fct_contrato(mem_con, [_one_contrato_row("C1")])
        make_flag_contrato(
            mem_con,
            [
                {"id_contrato": "C1", "flag_id": "FX1", "fired": True, "evidence_json": '{"a":1}'},
                {"id_contrato": "C1", "flag_id": "FX2", "fired": False, "evidence_json": "{}"},
                {"id_contrato": "C1", "flag_id": "FX3", "fired": True, "evidence_json": "{}"},
            ],
        )
        scorer.compute_contract_scores(mem_con)

        score, tier, n_ap, n_di, flags_json = mem_con.execute(
            "SELECT score, tier, n_flags_aplicables, n_flags_disparados, flags_disparados "
            "FROM contrato_score WHERE id_contrato='C1'"
        ).fetchone()

        # applicable = 10+30+60 = 100; fired = 10+60 = 70 -> 100*70/100 = 70.0
        assert score == pytest.approx(70.0)
        assert tier == "critico"  # >=60
        assert n_ap == 3
        assert n_di == 2
        fired = {f["flag_id"]: f for f in json.loads(flags_json)}
        assert set(fired) == {"FX1", "FX3"}
        assert fired["FX1"]["peso"] == 10
        assert fired["FX1"]["evidence"] == {"a": 1}

    def test_zero_applicable_flags_gives_null_score(self, mem_con, small_weights):
        make_fct_contrato(mem_con, [_one_contrato_row("C1")])
        make_flag_contrato(mem_con, [])  # C1 has no row at all -> not applicable, not zero
        scorer.compute_contract_scores(mem_con)

        score, tier, n_ap, flags_json = mem_con.execute(
            "SELECT score, tier, n_flags_aplicables, flags_disparados FROM contrato_score WHERE id_contrato='C1'"
        ).fetchone()
        assert score is None
        assert tier is None
        assert n_ap == 0
        assert json.loads(flags_json) == []

    def test_all_applicable_flags_checked_but_none_fired_gives_zero_not_null(self, mem_con, small_weights):
        make_fct_contrato(mem_con, [_one_contrato_row("C1")])
        make_flag_contrato(mem_con, [{"id_contrato": "C1", "flag_id": "FX1", "fired": False, "evidence_json": "{}"}])
        scorer.compute_contract_scores(mem_con)

        score, n_ap = mem_con.execute("SELECT score, n_flags_aplicables FROM contrato_score WHERE id_contrato='C1'").fetchone()
        assert score == 0.0  # not NULL: the flag WAS applicable, it just didn't fire
        assert n_ap == 1

    def test_all_fired_gives_100(self, mem_con, small_weights):
        make_fct_contrato(mem_con, [_one_contrato_row("C1")])
        make_flag_contrato(
            mem_con,
            [{"id_contrato": "C1", "flag_id": fid, "fired": True, "evidence_json": "{}"} for fid in ("FX1", "FX2", "FX3")],
        )
        scorer.compute_contract_scores(mem_con)
        score = mem_con.execute("SELECT score FROM contrato_score WHERE id_contrato='C1'").fetchone()[0]
        assert score == pytest.approx(100.0)

    def test_duplicate_key_flag_rows_are_deduped_via_bool_or(self, mem_con, small_weights):
        """
        A key can have >1 physical row for the same flag_id (pre-existing
        upstream artifact -- see scorer.py module docstring). Must count the
        flag once, firing if ANY row fired.
        """
        make_fct_contrato(mem_con, [_one_contrato_row("C1")])
        make_flag_contrato(
            mem_con,
            [
                {"id_contrato": "C1", "flag_id": "FX1", "fired": False, "evidence_json": "{}"},
                {"id_contrato": "C1", "flag_id": "FX1", "fired": True, "evidence_json": '{"why": "second row fired"}'},
            ],
        )
        scorer.compute_contract_scores(mem_con)
        score, n_ap, n_di = mem_con.execute(
            "SELECT score, n_flags_aplicables, n_flags_disparados FROM contrato_score WHERE id_contrato='C1'"
        ).fetchone()
        assert n_ap == 1  # not 2 -- deduped to one applicable flag
        assert n_di == 1
        assert score == pytest.approx(100.0)

    def test_multiple_contracts_scored_independently(self, mem_con, small_weights):
        make_fct_contrato(mem_con, [_one_contrato_row("C1"), _one_contrato_row("C2"), _one_contrato_row("C3")])
        make_flag_contrato(
            mem_con,
            [
                {"id_contrato": "C1", "flag_id": "FX1", "fired": True, "evidence_json": "{}"},
                {"id_contrato": "C2", "flag_id": "FX2", "fired": False, "evidence_json": "{}"},
                # C3: no rows at all -> NULL score
            ],
        )
        scorer.compute_contract_scores(mem_con)
        rows = dict(mem_con.execute("SELECT id_contrato, score FROM contrato_score").fetchall())
        assert rows["C1"] == pytest.approx(100.0)
        assert rows["C2"] == pytest.approx(0.0)
        assert rows["C3"] is None


class TestShrinkage:
    """shrunk = (n/(n+k)) * own_mean + (k/(n+k)) * group_mean."""

    def test_small_n_pulled_toward_group_mean(self):
        result = scorer.shrink(own_mean=90.0, group_mean=10.0, n=1, k=10)
        expected = 90.0 * (1 / 11) + 10.0 * (10 / 11)
        assert result == pytest.approx(expected)
        # n=1 with k=10 should land much closer to the group mean than to its own
        assert abs(result - 10.0) < abs(result - 90.0)

    def test_large_n_stays_close_to_own_mean(self):
        result = scorer.shrink(own_mean=90.0, group_mean=10.0, n=10_000, k=10)
        expected = 90.0 * (10_000 / 10_010) + 10.0 * (10 / 10_010)
        assert result == pytest.approx(expected)
        assert result == pytest.approx(90.0, abs=0.1)

    def test_n_equals_k_is_exactly_halfway(self):
        assert scorer.shrink(own_mean=80.0, group_mean=20.0, n=10, k=10) == pytest.approx(50.0)

    def test_n_zero_is_entirely_group_mean(self):
        assert scorer.shrink(own_mean=100.0, group_mean=7.0, n=0, k=10) == pytest.approx(7.0)

    def test_missing_own_mean_falls_back_to_group_mean(self):
        assert scorer.shrink(None, 42.0, n=5, k=10) == 42.0

    def test_missing_group_mean_falls_back_to_own_mean(self):
        assert scorer.shrink(77.0, None, n=5, k=10) == 77.0

    def test_both_missing_is_none(self):
        assert scorer.shrink(None, None, n=5, k=10) is None


class TestCombineComponents:
    def test_blends_by_catalog_weight_mass(self):
        # contract flags total 100 (cw), entity flags total 20 (ew) -> 100/120, 20/120
        result = scorer.combine_components(contract_component=50.0, entity_component=0.0, cw=100.0, ew=20.0)
        assert result == pytest.approx((100 * 50.0 + 20 * 0.0) / 120)

    def test_missing_entity_component_falls_back_to_contract_component(self):
        assert scorer.combine_components(50.0, None, cw=100.0, ew=20.0) == 50.0

    def test_missing_contract_component_falls_back_to_entity_component(self):
        assert scorer.combine_components(None, 33.0, cw=100.0, ew=20.0) == 33.0

    def test_both_missing_is_none(self):
        assert scorer.combine_components(None, None, cw=100.0, ew=20.0) is None


class TestEntityScoringIntegration:
    """End-to-end wiring check: compute_contract_scores -> compute_entity_scores, real shrinkage."""

    def test_low_n_entity_shrunk_toward_department_mean(self, mem_con, small_weights, monkeypatch):
        monkeypatch.setattr(scorer, "SHRINKAGE_K", 10.0)
        monkeypatch.setattr(scorer, "MIN_CONTRATOS_RANK", 10)

        # "Entidad Grande": 20 contracts, nothing ever fires -> its own mean is 0.
        big_contratos = [
            _one_contrato_row(f"B{i}", nit_entidad_norm="900000001", cod_dpto="05", cod_mpio="05001")
            for i in range(20)
        ]
        # "Entidad Chica": 1 contract, everything fires -> its own mean is 100.
        small_contrato = [_one_contrato_row("S1", nit_entidad_norm="900000002", cod_dpto="05", cod_mpio="05002")]

        make_fct_contrato(mem_con, big_contratos + small_contrato)
        make_flag_contrato(
            mem_con,
            [{"id_contrato": f"B{i}", "flag_id": "FX1", "fired": False, "evidence_json": "{}"} for i in range(20)]
            + [{"id_contrato": "S1", "flag_id": fid, "fired": True, "evidence_json": "{}"} for fid in ("FX1", "FX2", "FX3")],
        )
        make_flag_entidad(mem_con, [])
        make_dim_entidad(
            mem_con,
            [
                {
                    "nit_entidad_norm": "900000001", "nombre_entidad": "Entidad Grande",
                    "cod_dpto": "05", "cod_mpio": "05001", "n_contratos": 20, "valor_total": 20_000.0,
                },
                {
                    "nit_entidad_norm": "900000002", "nombre_entidad": "Entidad Chica",
                    "cod_dpto": "05", "cod_mpio": "05002", "n_contratos": 1, "valor_total": 1_000.0,
                },
            ],
        )

        scorer.compute_contract_scores(mem_con)
        scorer.compute_entity_scores(mem_con)

        big_raw, big_score, big_insuf = mem_con.execute(
            "SELECT combined_raw_score, score, datos_insuficientes FROM entidad_score WHERE nit_entidad_norm='900000001'"
        ).fetchone()
        small_raw, small_score, small_insuf = mem_con.execute(
            "SELECT combined_raw_score, score, datos_insuficientes FROM entidad_score WHERE nit_entidad_norm='900000002'"
        ).fetchone()

        assert big_raw == pytest.approx(0.0)
        assert small_raw == pytest.approx(100.0)
        assert big_insuf is False  # n_contratos=20 >= 10
        assert small_insuf is True  # n_contratos=1 < 10

        # Small entity (n=1) must be shrunk well below its own raw score of 100,
        # pulled toward the (low) department mean -- but not erased to 0 either.
        assert small_score < small_raw
        assert 5.0 < small_score < 50.0

        # Big entity (n=20 >> k=10) must stay close to its own near-zero raw score.
        assert big_score < 3.0
        # And the small entity's shrunk score should still clearly exceed the big
        # entity's -- shrinkage dampens the signal, it does not invert it.
        assert small_score > big_score


class TestMunicipioScoringUsesDivipolaNames:
    def test_municipio_and_department_names_attached(self, mem_con, small_weights, monkeypatch):
        monkeypatch.setattr(scorer, "SHRINKAGE_K", 10.0)
        monkeypatch.setattr(scorer, "MIN_CONTRATOS_RANK", 10)

        make_fct_contrato(mem_con, [_one_contrato_row("C1", cod_dpto="05", cod_mpio="05001")])
        make_flag_contrato(mem_con, [{"id_contrato": "C1", "flag_id": "FX1", "fired": True, "evidence_json": "{}"}])
        make_divipola(
            mem_con,
            [{"cod_dpto": "05", "dpto": "ANTIOQUIA", "cod_mpio": "05001", "municipio": "MEDELLIN",
              "dpto_norm": "ANTIOQUIA", "mpio_norm": "MEDELLIN"}],
        )

        scorer.compute_contract_scores(mem_con)
        scorer.compute_municipio_scores(mem_con)

        dpto, municipio, n, datos_insuf = mem_con.execute(
            "SELECT dpto, municipio, n_contratos, datos_insuficientes FROM municipio_score "
            "WHERE cod_dpto='05' AND cod_mpio='05001'"
        ).fetchone()
        assert dpto == "ANTIOQUIA"
        assert municipio == "MEDELLIN"
        assert n == 1
        assert datos_insuf is True  # only 1 contract, < 10
