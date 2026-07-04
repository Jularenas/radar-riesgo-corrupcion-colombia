"""
M4 unit tests: RUES NIT matching/normalization, conflict resolution, NULL semantics,
and the per-NIT lookup fallback's cache + rate limiter.
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline.clean.enrich_rues import (
    NIT_BASE_MACRO_SQL,
    _assert_nit_base_parity_on_sample,
    build_rues_resolved,
    enrich,
    install_macros,
)
from pipeline.clean.normalize import normalize_doc
from pipeline.extract.rues_lookup import (
    DEFAULT_RATE_LIMIT_PER_SEC,
    MIN_CONTRACT_VALUE_COP,
    RuesLookupClient,
    _RateLimiter,
    find_fallback_candidates,
)

# ---------------------------------------------------------------------------
# Synthetic fixture builders — mirror the REAL schemas discovered via DESCRIBE
# (see enrich_rues.py module docstring), not the "likely FECHA_MATRICULA" guess
# from the milestone brief.
# ---------------------------------------------------------------------------


def _write_ibague_fixture(path: Path, rows: list[dict]) -> None:
    """rows: list of {nit, fecha_de_matricula} dicts (both VARCHAR, like the real source)."""
    table = pa.table({
        "nit": pa.array([r["nit"] for r in rows], type=pa.string()),
        "fecha_de_matricula": pa.array([r["fecha_de_matricula"] for r in rows], type=pa.string()),
    })
    path.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path / "part-00000.parquet")


def _write_santarosa_fixture(path: Path, rows: list[dict]) -> None:
    """rows: list of {nit, digito_verificacion, numero_identificacion, fecha_matricula} dicts."""
    table = pa.table({
        "nit": pa.array([r.get("nit") for r in rows], type=pa.string()),
        "digito_verificacion": pa.array([r.get("digito_verificacion") for r in rows], type=pa.string()),
        "numero_identificacion": pa.array([r.get("numero_identificacion") for r in rows], type=pa.string()),
        "fecha_matricula": pa.array([r["fecha_matricula"] for r in rows], type=pa.string()),
    })
    path.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path / "part-00000.parquet")


@pytest.fixture
def rues_fixtures(tmp_path):
    """
    A small synthetic universe exercising:
      - entity matched via NIT-with-check-digit in ibague, NIT-without-check-digit's
        sibling representation in santarosa with a DIFFERENT (later) date -> cross-source conflict,
        earliest wins.
      - a second, distinct row within ibague for the SAME nit_base but an even earlier date,
        to test intra-source earliest-wins / multi-registro collapsing.
      - a persona natural matched only via santarosa's numero_identificacion (nit column NULL).
      - an entity matched only via santarosa (no ibague counterpart).
      - an ibague 'NO APLICA' (establecimiento) row that must never match anything.
      - a malformed-date row that must be dropped rather than crash the pipeline.
    """
    ibague_dir = tmp_path / "e1_rues_ibague"
    santarosa_dir = tmp_path / "e1_rues_santarosa"

    _write_ibague_fixture(ibague_dir, [
        {"nit": "8090031820", "fecha_de_matricula": "19970507"},  # nit_base=809003182
        {"nit": "809003182", "fecha_de_matricula": "19970101"},   # same nit_base, earlier, no check digit
        {"nit": "NO APLICA", "fecha_de_matricula": "19970429"},   # establecimiento — must not match
        {"nit": "900000001", "fecha_de_matricula": "NO APLICA"},  # malformed date — must be dropped
    ])
    _write_santarosa_fixture(santarosa_dir, [
        # Same entity as ibague rows above, but a LATER date -> cross-source conflict
        {"nit": "809003182", "digito_verificacion": "0", "numero_identificacion": "809003182", "fecha_matricula": "19970601"},
        # Persona natural, santarosa-only, via numero_identificacion (nit is NULL)
        {"nit": None, "digito_verificacion": None, "numero_identificacion": "12345678", "fecha_matricula": "20050615"},
        # Entity, santarosa-only
        {"nit": "900999999", "digito_verificacion": "9", "numero_identificacion": "900999999", "fecha_matricula": "20200101"},
        # Malformed/blank date — must be dropped, not crash
        {"nit": "111111111", "digito_verificacion": "1", "numero_identificacion": "111111111", "fecha_matricula": ""},
    ])

    return {
        "ibague_glob": str(ibague_dir / "part-*.parquet"),
        "santarosa_glob": str(santarosa_dir / "part-*.parquet"),
    }


# ---------------------------------------------------------------------------
# nit_base SQL macro <-> normalize_doc() parity (the "reuse the existing
# normalizer" guarantee — see enrich_rues.py module docstring for why the SQL
# isn't a literal call into normalize.py)
# ---------------------------------------------------------------------------


class TestNitBaseMacroParity:
    CASES = [
        "8090031820", "900123456", "1020304050", "12345678", "809003182",
        "9001234567", "8001234567", "900000001", "1", "", "123456789012", None,
    ]

    def test_macro_matches_python_normalizer(self):
        con = duckdb.connect()
        install_macros(con)
        for raw in self.CASES:
            sql_result = con.execute("SELECT nit_base(?)", [raw]).fetchone()[0]
            py_result = normalize_doc(raw)["nit_base"]
            assert sql_result == py_result, f"mismatch for {raw!r}: sql={sql_result!r} py={py_result!r}"

    def test_macro_sql_is_a_single_statement(self):
        # Sanity: the constant used by install_macros() is what we think it is. Must be a
        # TEMP macro so coverage measurement can install it on a read_only mart connection.
        assert "CREATE OR REPLACE TEMP MACRO nit_base" in NIT_BASE_MACRO_SQL


# ---------------------------------------------------------------------------
# NIT matching against synthetic fixtures for both chamber schemas
# ---------------------------------------------------------------------------


class TestBuildRuesResolved:
    def test_matches_both_schemas_and_collapses_by_nit_base(self, rues_fixtures):
        con = duckdb.connect()
        stats = build_rues_resolved(con, rues_fixtures["ibague_glob"], rues_fixtures["santarosa_glob"])

        rows = {
            r[0]: r for r in con.execute(
                "SELECT nit_base, fecha_ibague, fecha_santarosa, fecha_matricula, is_conflict, n_sources_matched "
                "FROM rues_resolved ORDER BY nit_base"
            ).fetchall()
        }

        # Entity present in both sources, cross-source conflict -> earliest of the two.
        assert rows["809003182"][1] == date(1997, 1, 1)   # ibague side already collapsed to its own earliest
        assert rows["809003182"][2] == date(1997, 6, 1)
        assert rows["809003182"][3] == date(1997, 1, 1)   # resolved = earliest overall
        assert rows["809003182"][4] is True                # is_conflict
        assert rows["809003182"][5] == 2                   # matched in both sources

        # Persona natural matched only via santarosa numero_identificacion.
        assert rows["12345678"][3] == date(2005, 6, 15)
        assert rows["12345678"][4] is False
        assert rows["12345678"][5] == 1

        # Entity matched only via santarosa.
        assert rows["900999999"][3] == date(2020, 1, 1)
        assert rows["900999999"][4] is False

        # Rows that must NEVER appear: the ibague 'NO APLICA' establecimiento row, the
        # malformed-date ibague row (900000001), and the blank-date santarosa row (111111111).
        assert "900000001" not in rows
        assert "111111111" not in rows

        # Multi-registro bookkeeping: 809003182 had 2 raw rows within ibague.
        assert stats["n_conflicts"] == 1
        assert stats["n_multi_registro_ibague"] == 1

    def test_no_crash_on_empty_sources(self, tmp_path):
        empty_ibague = tmp_path / "empty_ibague"
        empty_santarosa = tmp_path / "empty_santarosa"
        _write_ibague_fixture(empty_ibague, [])
        _write_santarosa_fixture(empty_santarosa, [])

        con = duckdb.connect()
        stats = build_rues_resolved(con, str(empty_ibague / "part-*.parquet"), str(empty_santarosa / "part-*.parquet"))
        assert stats["n_nit_base"] == 0
        assert stats["n_conflicts"] == 0


# ---------------------------------------------------------------------------
# Runtime parity self-check against "live" (fixture) data
# ---------------------------------------------------------------------------


class TestRuntimeParityCheck:
    def test_passes_on_synthetic_fixtures(self, rues_fixtures):
        con = duckdb.connect()
        # Should not raise.
        _assert_nit_base_parity_on_sample(
            con, rues_fixtures["ibague_glob"], rues_fixtures["santarosa_glob"], sample_n=50,
        )


# ---------------------------------------------------------------------------
# End-to-end enrichment: unmatched suppliers get NULL, never a sentinel
# ---------------------------------------------------------------------------


class TestEnrich:
    def _make_mart(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute("""
            CREATE TABLE dim_proveedor (
                doc_proveedor_norm VARCHAR,
                nombre_proveedor VARCHAR,
                es_persona_natural BOOLEAN,
                n_contratos BIGINT,
                valor_total DOUBLE
            )
        """)
        con.execute("""
            INSERT INTO dim_proveedor VALUES
                ('8090031820', 'INSETEL SAS', false, 3, 500000000.0),
                ('12345678', 'PERSONA X', true, 1, 10000000.0),
                ('9009999999', 'ENTIDAD SANTAROSA ONLY', false, 2, 300000000.0),
                ('999999999', 'NUNCA REGISTRADA', false, 1, 200000000.0)
        """)
        con.close()

    def test_matched_get_dates_unmatched_get_null(self, tmp_path, rues_fixtures):
        mart_path = tmp_path / "test_mart.duckdb"
        self._make_mart(mart_path)

        stats = enrich(
            mart_path=mart_path,
            ibague_glob=rues_fixtures["ibague_glob"],
            santarosa_glob=rues_fixtures["santarosa_glob"],
        )

        con = duckdb.connect(str(mart_path), read_only=True)
        rows = dict(con.execute("SELECT doc_proveedor_norm, fecha_matricula FROM dim_proveedor").fetchall())
        con.close()

        assert rows["8090031820"] == date(1997, 1, 1)
        assert rows["12345678"] == date(2005, 6, 15)
        assert rows["9009999999"] == date(2020, 1, 1)

        # The crux of the milestone: unmatched suppliers get NULL, not a default/sentinel
        # (not 1900-01-01, not epoch, not the earliest date seen anywhere else).
        assert rows["999999999"] is None

        assert stats["n_matched_after"] == 3
        assert stats["n_suppliers"] == 4
        assert stats["n_conflicts"] == 1

    def test_rerun_is_idempotent(self, tmp_path, rues_fixtures):
        mart_path = tmp_path / "test_mart2.duckdb"
        self._make_mart(mart_path)

        stats1 = enrich(mart_path=mart_path, ibague_glob=rues_fixtures["ibague_glob"], santarosa_glob=rues_fixtures["santarosa_glob"])
        stats2 = enrich(mart_path=mart_path, ibague_glob=rues_fixtures["ibague_glob"], santarosa_glob=rues_fixtures["santarosa_glob"])

        assert stats1["n_matched_after"] == stats2["n_matched_after"]
        assert stats2["n_matched_before"] == stats1["n_matched_after"]


# ---------------------------------------------------------------------------
# Per-NIT lookup fallback: cache read/write roundtrip
# ---------------------------------------------------------------------------


class TestRuesLookupClientCache:
    def test_lookup_returns_none_and_writes_cache(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        client = RuesLookupClient(cache_path=cache_path, rate_limit_per_sec=1000)

        result = client.lookup("900123456")

        assert result is None
        assert cache_path.exists()

        import json
        data = json.loads(cache_path.read_text())
        assert "900123456" in data
        assert data["900123456"]["fecha_matricula"] is None
        assert data["900123456"]["source"] == "noop"
        assert "checked_at" in data["900123456"]

    def test_second_client_reads_cache_without_refetching(self, tmp_path, monkeypatch):
        cache_path = tmp_path / "cache.json"
        client1 = RuesLookupClient(cache_path=cache_path, rate_limit_per_sec=1000)
        client1.lookup("800111222")

        def _boom(nit_base):
            raise AssertionError("should not re-fetch a cached NIT")

        monkeypatch.setattr("pipeline.extract.rues_lookup._fetch_from_api", _boom)

        client2 = RuesLookupClient(cache_path=cache_path, rate_limit_per_sec=1000)
        result = client2.lookup("800111222")
        assert result is None  # served from cache, no exception raised

    def test_invalid_nit_returns_none_without_caching(self, tmp_path):
        cache_path = tmp_path / "cache.json"
        client = RuesLookupClient(cache_path=cache_path, rate_limit_per_sec=1000)
        assert client.lookup("") is None
        assert client.lookup(None) is None
        assert not cache_path.exists()

    def test_roundtrip_preserves_a_real_date_if_present(self, tmp_path, monkeypatch):
        """Cache roundtrip must also work for a non-null date (once a real source is wired in)."""
        cache_path = tmp_path / "cache.json"
        monkeypatch.setattr(
            "pipeline.extract.rues_lookup._fetch_from_api",
            lambda nit_base: date(2019, 3, 4),
        )
        client1 = RuesLookupClient(cache_path=cache_path, rate_limit_per_sec=1000)
        assert client1.lookup("900555666") == date(2019, 3, 4)

        client2 = RuesLookupClient(cache_path=cache_path, rate_limit_per_sec=1000)
        assert client2.lookup("900555666") == date(2019, 3, 4)


class TestRateLimiter:
    def test_spaces_calls_apart(self, monkeypatch):
        clock = {"t": 0.0}
        sleeps: list[float] = []

        monkeypatch.setattr(time, "monotonic", lambda: clock["t"])

        def _fake_sleep(seconds):
            sleeps.append(seconds)
            clock["t"] += seconds

        monkeypatch.setattr(time, "sleep", _fake_sleep)

        limiter = _RateLimiter(rate_per_sec=2.0)  # min interval 0.5s
        limiter.wait()  # first call: no prior call, no sleep
        clock["t"] += 0.1  # simulate 0.1s of "work" between calls
        limiter.wait()  # should sleep ~0.4s to reach the 0.5s minimum spacing

        assert sleeps == [pytest.approx(0.4)]

    def test_rejects_nonpositive_rate(self):
        with pytest.raises(ValueError):
            _RateLimiter(rate_per_sec=0)


# ---------------------------------------------------------------------------
# Fallback candidate identification (PLAN.md M4 threshold)
# ---------------------------------------------------------------------------


class TestFindFallbackCandidates:
    def _make_mart_with_contracts(self, path: Path) -> None:
        con = duckdb.connect(str(path))
        con.execute("""
            CREATE TABLE dim_proveedor (
                doc_proveedor_norm VARCHAR, nombre_proveedor VARCHAR,
                es_persona_natural BOOLEAN, n_contratos BIGINT, valor_total DOUBLE,
                fecha_matricula DATE
            )
        """)
        con.execute("""
            CREATE TABLE fct_contrato (
                row_id VARCHAR, doc_proveedor_norm VARCHAR, valor_contrato DOUBLE
            )
        """)
        con.execute("""
            INSERT INTO dim_proveedor VALUES
                ('111', 'BIG UNMATCHED', false, 1, 300000000.0, NULL),
                ('222', 'SMALL UNMATCHED', false, 1, 1000000.0, NULL),
                ('333', 'BIG MATCHED', false, 1, 500000000.0, DATE '2010-01-01')
        """)
        con.execute("""
            INSERT INTO fct_contrato VALUES
                ('c1', '111', 300000000.0),
                ('c2', '222', 1000000.0),
                ('c3', '333', 500000000.0)
        """)
        con.close()

    def test_value_only_criterion_when_no_flag_table(self, tmp_path):
        mart_path = tmp_path / "mart.duckdb"
        self._make_mart_with_contracts(mart_path)

        con = duckdb.connect(str(mart_path), read_only=True)
        candidates = find_fallback_candidates(con, min_value=MIN_CONTRACT_VALUE_COP)
        con.close()

        docs = {c[0] for c in candidates}
        assert docs == {"111"}  # only the unmatched supplier above the value threshold

    def test_default_rate_limit_is_conservative(self):
        assert DEFAULT_RATE_LIMIT_PER_SEC <= 1.0
