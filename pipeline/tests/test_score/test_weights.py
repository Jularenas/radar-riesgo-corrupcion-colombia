"""Unit tests for pipeline.score.weights: tier boundaries + basic loader sanity."""

from __future__ import annotations

from pipeline.score.weights import FLAG_WEIGHTS, TIERS, tier_case_sql, tier_for, tier_nombre, total_weight


class TestTierBoundaries:
    """PLAN.md: Bajo <20, Medio 20-40, Alto 40-60, Critico >=60 -- exact boundary behavior."""

    def test_bajo_below_20(self):
        assert tier_for(0) == "bajo"
        assert tier_for(19.999) == "bajo"

    def test_exactly_20_is_medio_not_bajo(self):
        assert tier_for(20) == "medio"

    def test_medio_below_40(self):
        assert tier_for(39.999) == "medio"

    def test_exactly_40_is_alto_not_medio(self):
        assert tier_for(40) == "alto"

    def test_alto_below_60(self):
        assert tier_for(59.999) == "alto"

    def test_exactly_60_is_critico_not_alto(self):
        assert tier_for(60) == "critico"

    def test_critico_has_no_ceiling(self):
        assert tier_for(60.0001) == "critico"
        assert tier_for(100) == "critico"
        assert tier_for(1000) == "critico"

    def test_none_score_gives_none_tier(self):
        assert tier_for(None) is None

    def test_tier_nombre_roundtrip(self):
        for t in TIERS:
            assert tier_nombre(t.id) == t.nombre
        assert tier_nombre(None) is None


class TestWeightsLoader:
    def test_all_14_flags_present(self):
        assert set(FLAG_WEIGHTS) == {f"F{i:02d}" for i in range(1, 15)}

    def test_weights_are_positive(self):
        assert all(m["peso"] > 0 for m in FLAG_WEIGHTS.values())

    def test_nivel_is_contract_or_entity(self):
        assert all(m["nivel"] in ("contract", "entity") for m in FLAG_WEIGHTS.values())

    def test_total_weight_splits_by_nivel(self):
        contract_total = total_weight("contract")
        entity_total = total_weight("entity")
        assert contract_total + entity_total == total_weight()
        assert contract_total == sum(m["peso"] for m in FLAG_WEIGHTS.values() if m["nivel"] == "contract")
        assert entity_total == sum(m["peso"] for m in FLAG_WEIGHTS.values() if m["nivel"] == "entity")


class TestTierCaseSql:
    def test_generated_case_matches_tier_for(self):
        # Exercise the generated SQL against a tiny in-memory table via duckdb
        # to prove it agrees with tier_for's pure-Python boundaries.
        import duckdb

        con = duckdb.connect(":memory:")
        try:
            con.execute("CREATE TABLE t (score DOUBLE)")
            values = [0, 19.999, 20, 39.999, 40, 59.999, 60, 100]
            con.executemany("INSERT INTO t VALUES (?)", [(v,) for v in values])
            case_sql = tier_case_sql("score")
            rows = con.execute(f"SELECT score, {case_sql} FROM t ORDER BY score").fetchall()
        finally:
            con.close()
        for score, tier in rows:
            assert tier == tier_for(score), f"SQL tier {tier!r} != tier_for {tier_for(score)!r} for score={score}"
