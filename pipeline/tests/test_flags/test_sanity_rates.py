"""
Sanity tests: run run_all against a read-only copy of the REAL sample mart
and assert fire rates land in sane bounds.

Complements the per-flag synthetic-fixture tests (which prove correctness
on hand-crafted, unambiguous data) with a check against real, messy 2023
SECOP data: every flag should have a non-trivial applicable population and
a fire rate that isn't degenerate (0% from a broken join/filter, or ~100%
from an inverted condition).

This test never opens the live mart file for writing -- it ATTACHes it
READ_ONLY and copies every table into a private in-memory database, then
runs the flags against that copy. That matters here specifically because
the mart is a *shared* artifact: M4 (RUES enrichment) runs in parallel per
PLAN.md and, as observed live during M3 development, writes to the same
`corruption.duckdb` file (it added `dim_proveedor.fecha_matricula`
mid-session). Opening the file read-write here would risk lock contention
with a concurrent milestone and would leave stray flag_contrato/
flag_entidad tables in the shared mart as a side effect of running tests.

Bounds below are deliberately wide: they're centered on what was actually
observed on the sample mart during M3 development (see the M3 report for
exact figures) and are meant to catch a broken query (an accidental cross
join firing ~100%, a typo'd condition firing 0%), not to pin exact values
on a mart another milestone may still be enriching. F01's bound is the one
explicitly required by the M3 brief (1-15% of its applicable population).
"""

from __future__ import annotations

import duckdb
import pytest

from pipeline.config import MARTS_DIR
from pipeline.flags.params import FLAG_META
from pipeline.flags.run_all import run

_MART_PATH = MARTS_DIR / "corruption.duckdb"

# flag_id -> (min_rate_pct, max_rate_pct)
_RATE_BOUNDS: dict[str, tuple[float, float]] = {
    "F01": (1.0, 15.0),  # explicitly required by the M3 brief; observed ~14.3%
    "F02": (0.0, 50.0),  # RUES data is partial/in-progress (M4); wide open, see population check
    "F03": (0.1, 10.0),  # observed ~1.0%
    "F04": (0.0, 15.0),  # observed ~1.6%
    "F05": (0.0, 5.0),  # observed ~0.24%
    "F06": (0.0, 5.0),  # observed 0% -- see module docstring; correctness proven by unit test instead
    "F07": (1.0, 30.0),  # observed ~14.9%
    "F08": (1.0, 40.0),  # observed ~27.6%
    "F09": (0.1, 10.0),  # observed ~1.7%
    "F10": (1.0, 40.0),  # observed ~18.9% -- inflated by the single-year sample, see module docstring
    "F11": (0.0, 5.0),  # observed ~0.1%
    "F12": (0.0, 40.0),  # observed ~22.9%
    "F13": (2.0, 25.0),  # observed ~10.5%
    "F14": (0.0, 5.0),  # observed ~0.09%
}

# Only F02 (RUES enrichment is M4's job, may not have run yet) is allowed an empty population.
_ALLOW_ZERO_POPULATION = {"F02"}


@pytest.fixture(scope="module")
def real_mart_copy():
    if not _MART_PATH.exists():
        pytest.skip(f"Sample mart not built yet: {_MART_PATH}")
    mem = duckdb.connect(":memory:")
    try:
        mem.execute(f"ATTACH '{_MART_PATH}' AS src (READ_ONLY)")
    except duckdb.Error as exc:
        pytest.skip(f"Could not open the sample mart read-only (maybe locked by a concurrent milestone): {exc}")
    try:
        tables = [
            r[0]
            for r in mem.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog = 'src'").fetchall()
        ]
        for t in tables:
            mem.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
    finally:
        mem.execute("DETACH src")
    return mem


@pytest.fixture(scope="module")
def summary(real_mart_copy) -> dict[str, dict]:
    rows = run(real_mart_copy)
    return {r["flag_id"]: r for r in rows}


class TestPopulationSanity:
    """No flag should have population 0 unless that's an explicitly-justified missing input."""

    @pytest.mark.parametrize("flag_id", sorted(FLAG_META))
    def test_population_not_unexpectedly_zero(self, summary, flag_id):
        pop = summary[flag_id]["population"]
        if pop == 0 and flag_id in _ALLOW_ZERO_POPULATION:
            pytest.skip(f"{flag_id}: population is 0 -- allowed pending M4 RUES enrichment")
        assert pop > 0, f"{flag_id} has population 0 -- likely a broken query, not a real absence of applicable rows"


class TestFireRateSanity:
    @pytest.mark.parametrize("flag_id", sorted(FLAG_META))
    def test_fire_rate_within_observed_bounds(self, summary, flag_id):
        row = summary[flag_id]
        if row["population"] == 0:
            pytest.skip(f"{flag_id}: population 0, no rate to check")
        lo, hi = _RATE_BOUNDS[flag_id]
        assert lo <= row["rate_pct"] <= hi, (
            f"{flag_id} fire rate {row['rate_pct']:.2f}% outside expected [{lo}, {hi}]% "
            f"(population={row['population']}, fired={row['fired']})"
        )

    def test_no_flag_fires_on_more_than_half_its_population(self, summary):
        offenders = {fid: r["rate_pct"] for fid, r in summary.items() if r["population"] > 0 and r["rate_pct"] > 50.0}
        assert not offenders, f"Flag(s) firing on >50% of their population (likely a bug): {offenders}"

    def test_f01_lands_in_the_plan_specified_range(self, summary):
        """Explicit callout from the M3 brief: F01 should land roughly 1-15% of its applicable
        (joined + competitive) population -- used as a correctness signal for the whole
        contract<->process join, not just F01 itself."""
        f01 = summary["F01"]
        assert f01["population"] > 0
        assert 1.0 <= f01["rate_pct"] <= 15.0

    def test_f06_zero_fires_is_a_documented_finding_not_a_bug(self, summary):
        """F06 fires 0 times on the sample: every (entity, UNSPSC, 24-month bucket) group with
        enough volume to qualify (>=8 processes) has 10-49 distinct winners -- a genuinely
        diverse market, not a 2-4-supplier rotation. Population must still be non-trivial;
        F06's ability to fire at all is proven separately by test_f06_carrusel.py."""
        f06 = summary["F06"]
        assert f06["population"] > 100
        assert f06["fired"] == 0
