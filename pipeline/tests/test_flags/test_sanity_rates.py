"""
Sanity tests: run run_all against a read-only copy of whatever mart
currently exists at MARTS_DIR (the 2023 sample during early development,
the full multi-year rebuild from M8 onward) and assert fire rates land in
sane bounds.

Complements the per-flag synthetic-fixture tests (which prove correctness
on hand-crafted, unambiguous data) with a check against real, messy SECOP
data: every flag should have a non-trivial applicable population and a
fire rate that isn't degenerate (0% from a broken join/filter, or ~100%
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

Bounds below are deliberately wide: meant to catch a broken query (an
accidental cross join firing ~100%, a typo'd condition firing 0%), not to
pin exact values from one specific run. They were widened once already
(M8, full-data rebuild): the 2023-only sample had ~20-28% contract<->process
join coverage, capping how often join-dependent flags (F01, F08) could even
be evaluated; the full multi-year rebuild has 100% join coverage, so their
TRUE rates (previously invisible) are now measured directly and are
legitimately higher -- see docs/METHODOLOGY.md for the before/after.
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
    "F01": (1.0, 45.0),  # sample (~20% join coverage): ~14.3%; full data (100% join coverage): ~31.7%
    "F02": (0.0, 50.0),  # RUES coverage is partial by nature (registry gaps); wide open, see population check
    "F03": (0.1, 10.0),  # sample ~1.0%, full ~2.5%
    "F04": (0.0, 15.0),  # sample ~1.6%, full ~2.6%
    "F05": (0.0, 5.0),  # sample ~0.24%, full ~0.56%
    "F06": (0.0, 5.0),  # sample: 0% (insufficient volume per group); full: ~0.10% -- see test below
    "F07": (1.0, 30.0),  # sample ~14.9%, full ~27.6%
    "F08": (1.0, 40.0),  # sample ~27.6%, full ~34.1%
    "F09": (0.1, 10.0),  # sample ~1.7%, full ~2.2%
    "F10": (1.0, 40.0),  # sample ~18.9% (single-year, inflated), full ~9.1% (multi-year, more representative)
    "F11": (0.0, 5.0),  # sample ~0.1%, full ~0.11%
    "F12": (0.0, 40.0),  # sample ~22.9%, full ~19.4%
    "F13": (2.0, 25.0),  # sample ~10.5%, full ~10.4%
    "F14": (0.0, 5.0),  # sample ~0.09%, full ~0.11%
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

    def test_f01_lands_in_a_sane_range(self, summary):
        """F01 (unico oferente) is used as a correctness signal for the whole contract<->process
        join, not just F01 itself: population>0 and a non-degenerate rate. The upper bound is
        wide on purpose -- on the 2023-only sample (~20% join coverage) this measured ~14.3%; on
        the full multi-year rebuild (100% join coverage, M8) it measures ~31.7%. Both are
        plausible for Colombian public procurement; a bug would look like ~0% (broken join) or
        ~100% (inverted condition), which this still catches."""
        f01 = summary["F01"]
        assert f01["population"] > 0
        assert 1.0 <= f01["rate_pct"] <= 45.0

    def test_f06_fire_rate_is_sane(self, summary):
        """F06 (carrusel) needs real volume per (entity, UNSPSC, 24-month bucket) group to ever
        fire: on the 2023-only sample every qualifying group had 10-49 distinct winners (a
        diverse market, not a 2-4-supplier rotation) so it fired 0 times -- a documented finding,
        not a bug, since F06's ability to fire at all is proven separately by
        test_f06_carrusel.py's synthetic fixtures. The full multi-year rebuild (M8) has enough
        volume to surface real candidates (~98 fires / ~0.1%), which is the flag doing its job at
        adequate scale. Assert non-trivial population and a non-degenerate rate rather than
        pinning either sample-era zero or full-data-era ~98 as the only valid outcome."""
        f06 = summary["F06"]
        assert f06["population"] > 100
        assert 0 <= f06["rate_pct"] <= 5.0
