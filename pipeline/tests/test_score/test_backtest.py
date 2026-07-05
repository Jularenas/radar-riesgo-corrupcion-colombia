"""
Unit tests for pipeline.score.backtest: label-leakage guard (mandatory per
the M5 brief), AUC correctness, and the V1 Monitor Ciudadano matching path
(exercised here with synthetic clean data since the real mart's source data
is currently unusable -- see match_monitor_ciudadano's docstring).
"""

from __future__ import annotations

import duckdb
import pytest
from score_fixtures import make_contrato_score, make_divipola, make_monitor_ciudadano, make_sanciones

from pipeline.score import backtest


@pytest.fixture
def mem_con():
    con = duckdb.connect(":memory:")
    yield con
    con.close()


def _base_contrato_score(id_contrato: str, doc_proveedor_norm: str, fecha_firma: str, score: float = 10.0) -> dict:
    """A minimal contrato_score row -- fetch_contract_labels reads FROM contrato_score, not fct_contrato."""
    return {
        "id_contrato": id_contrato,
        "doc_proveedor_norm": doc_proveedor_norm,
        "nit_entidad_norm": "800000000",
        "fecha_firma": fecha_firma,
        "score": score,
    }


class TestLeakageGuard:
    """A sanction dated before (or on) signing must NEVER count as a positive-after label."""

    def test_sanction_before_signing_is_not_positive(self, mem_con):
        make_contrato_score(mem_con, [_base_contrato_score("C1", "900111222", "2023-06-01")])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2022-01-01"}])

        rows = backtest.fetch_contract_labels(mem_con)
        assert rows == [("C1", 10.0, False)]

    def test_sanction_same_day_as_signing_is_not_positive(self, mem_con):
        """Same-day is deliberately treated as NOT "after" (strict `>` only) -- ambiguous, not a clean outcome signal."""
        make_contrato_score(mem_con, [_base_contrato_score("C1", "900111222", "2023-06-01")])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2023-06-01"}])

        rows = backtest.fetch_contract_labels(mem_con)
        assert rows == [("C1", 10.0, False)]

    def test_sanction_after_signing_is_positive(self, mem_con):
        make_contrato_score(mem_con, [_base_contrato_score("C1", "900111222", "2023-06-01")])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2023-06-02"}])

        rows = backtest.fetch_contract_labels(mem_con)
        assert rows == [("C1", 10.0, True)]

    def test_one_sanction_before_and_one_after_is_still_positive(self, mem_con):
        """A supplier can have several sanciones rows; even one strictly-after occurrence is enough to flag positive."""
        make_contrato_score(mem_con, [_base_contrato_score("C1", "900111222", "2023-06-01")])
        make_sanciones(
            mem_con,
            [
                {"doc_norm": "900111222", "fuente": "CGR", "fecha_sancion": "2021-01-01"},  # before -> not this alone
                {"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2023-06-02"},  # after -> positive
            ],
        )
        rows = backtest.fetch_contract_labels(mem_con)
        assert rows == [("C1", 10.0, True)]

    def test_no_sanction_at_all_is_not_positive(self, mem_con):
        make_contrato_score(mem_con, [_base_contrato_score("C1", "900999888", "2023-06-01")])
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2023-06-02"}])
        rows = backtest.fetch_contract_labels(mem_con)
        assert rows == [("C1", 10.0, False)]

    def test_entity_side_sanction_after_signing_is_also_positive(self, mem_con):
        """Positive label can come from either the supplier's OR the entity's own document."""
        row = _base_contrato_score("C1", "900111222", "2023-06-01")
        row["nit_entidad_norm"] = "800555666"
        make_contrato_score(mem_con, [row])
        make_sanciones(mem_con, [{"doc_norm": "800555666", "fuente": "CGR", "fecha_sancion": "2023-06-02"}])
        rows = backtest.fetch_contract_labels(mem_con)
        assert rows == [("C1", 10.0, True)]

    def test_null_score_contracts_are_excluded(self, mem_con):
        make_contrato_score(
            mem_con,
            [
                _base_contrato_score("C1", "900111222", "2023-06-01", score=10.0),
                _base_contrato_score("C2", "900111222", "2023-06-01", score=None),
            ],
        )
        make_sanciones(mem_con, [{"doc_norm": "900111222", "fuente": "SIRI", "fecha_sancion": "2023-06-02"}])
        rows = backtest.fetch_contract_labels(mem_con)
        assert {r[0] for r in rows} == {"C1"}  # C2 has NULL score -> excluded, not scored as a negative


class TestComputeAUC:
    def test_perfect_separation_gives_auc_1(self):
        scores = [1, 2, 3, 4, 5, 6]
        labels = [False, False, False, True, True, True]
        result = backtest.compute_auc(scores, labels)
        assert result["auc"] == pytest.approx(1.0)

    def test_inverted_separation_gives_auc_0(self):
        scores = [1, 2, 3, 4, 5, 6]
        labels = [True, True, True, False, False, False]
        result = backtest.compute_auc(scores, labels)
        assert result["auc"] == pytest.approx(0.0)

    def test_symmetric_arrangement_gives_auc_half(self):
        # positives at ranks 1 and 4 (avg 2.5), negatives at ranks 2 and 3 (avg 2.5) -> no separation
        scores = [1, 2, 3, 4]
        labels = [True, False, False, True]
        result = backtest.compute_auc(scores, labels)
        assert result["auc"] == pytest.approx(0.5)

    def test_all_tied_scores_gives_auc_half_regardless_of_labels(self):
        scores = [5, 5, 5, 5]
        labels = [True, True, False, False]
        result = backtest.compute_auc(scores, labels)
        assert result["auc"] == pytest.approx(0.5)

    def test_no_positives_returns_none_auc(self):
        result = backtest.compute_auc([1, 2, 3], [False, False, False])
        assert result["auc"] is None
        assert result["n_pos"] == 0

    def test_no_negatives_returns_none_auc(self):
        result = backtest.compute_auc([1, 2, 3], [True, True, True])
        assert result["auc"] is None
        assert result["n_neg"] == 0


class TestPrecisionAndLift:
    def test_precision_at_k(self):
        labels_sorted_desc = [True, True, False, False, False]
        assert backtest.precision_at_k(labels_sorted_desc, 2) == pytest.approx(1.0)
        assert backtest.precision_at_k(labels_sorted_desc, 5) == pytest.approx(0.4)

    def test_lift_above_one_when_top_decile_concentrates_positives(self):
        # 100 items, top 10 are all positive, remaining 90 have 5 more positives scattered
        labels_sorted_desc = [True] * 10 + [True] * 5 + [False] * 85
        result = backtest.lift_at_top_decile(labels_sorted_desc)
        overall_rate = 15 / 100
        assert result["overall_rate"] == pytest.approx(overall_rate)
        assert result["top_rate"] == pytest.approx(1.0)
        assert result["lift"] == pytest.approx(1.0 / overall_rate)
        assert result["lift"] > 1.5


class TestMonitorCiudadanoMatching:
    """
    The real mart's monitor_ciudadano_hechos currently has blank
    departamento/municipio/anio for 100% of rows (a documented upstream
    M1/M2 bug, out of M5's scope). These tests exercise the matching logic
    directly with clean synthetic data, since that is otherwise the only
    way to verify it -- it cannot be exercised against the live mart today.
    """

    def test_empty_source_reported_honestly(self, mem_con):
        make_monitor_ciudadano(mem_con, [])
        result = backtest.match_monitor_ciudadano(mem_con)
        assert result["n_total"] == 0
        assert result["n_matched"] == 0

    def test_all_blank_rows_reported_as_upstream_bug_not_as_zero_matches(self, mem_con):
        make_monitor_ciudadano(mem_con, [{"departamento": "", "municipio": "", "anio": None, "sector": ""}])
        result = backtest.match_monitor_ciudadano(mem_con)
        assert result["n_total"] == 1
        assert result["n_usable_join_keys"] == 0
        assert result["n_matched"] == 0
        assert "bug de extraccion" in result["note"]

    def test_real_match_when_data_is_usable(self, mem_con):
        make_monitor_ciudadano(mem_con, [{"departamento": "TOLIMA", "municipio": "IBAGUE", "anio": 2023, "sector": "Salud"}])
        make_divipola(
            mem_con,
            [{"cod_dpto": "73", "dpto": "TOLIMA", "cod_mpio": "73001", "municipio": "IBAGUE",
              "dpto_norm": "TOLIMA", "mpio_norm": "IBAGUE"}],
        )
        make_contrato_score(mem_con, [{"id_contrato": "C1", "cod_dpto": "73", "cod_mpio": "73001", "anio": 2023, "score": 10.0}])

        result = backtest.match_monitor_ciudadano(mem_con)
        assert result["n_usable_join_keys"] == 1
        assert result["n_geo_matched"] == 1
        assert result["n_matched"] == 1
        assert result["match_rate_pct"] == pytest.approx(100.0)

    def test_geo_match_but_no_contract_that_year_is_not_counted(self, mem_con):
        make_monitor_ciudadano(mem_con, [{"departamento": "TOLIMA", "municipio": "IBAGUE", "anio": 2019, "sector": "Salud"}])
        make_divipola(
            mem_con,
            [{"cod_dpto": "73", "dpto": "TOLIMA", "cod_mpio": "73001", "municipio": "IBAGUE",
              "dpto_norm": "TOLIMA", "mpio_norm": "IBAGUE"}],
        )
        # Only a 2023 contract exists -- no contract in 2019 for this municipio.
        make_contrato_score(mem_con, [{"id_contrato": "C1", "cod_dpto": "73", "cod_mpio": "73001", "anio": 2023, "score": 10.0}])

        result = backtest.match_monitor_ciudadano(mem_con)
        assert result["n_geo_matched"] == 1
        assert result["n_matched"] == 0
