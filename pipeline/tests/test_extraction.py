"""
Tests for the M1 extraction layer.

All tests are network-free: a fake httpx transport injects synthetic responses.
"""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import patch

import httpx
import pyarrow.parquet as pq
import pytest

from pipeline.extract.socrata import (
    SocrataClient,
    _atomic_write_json,
    _load_manifest,
    _parse_csv_all_strings,
    _save_manifest,
    _update_manifest_entry,
)

# ---------------------------------------------------------------------------
# Helpers — fake CSV generation
# ---------------------------------------------------------------------------


def _make_csv(rows: list[dict[str, str]]) -> bytes:
    """Build CSV bytes from a list of dicts."""
    if not rows:
        return b":id,col_a\n"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def _make_rows(start: int, count: int) -> list[dict[str, str]]:
    """Generate `count` synthetic rows starting at :id=start."""
    return [
        {
            ":id": str(start + i),
            "nombre": f"entidad_{start + i}",
            "valor": str((start + i) * 1000),
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Fake transport
# ---------------------------------------------------------------------------


class FakeTransport(httpx.BaseTransport):
    """
    Minimal fake transport that serves paginated CSV and count JSON responses.

    Pagination model:
      - Total rows = total_rows
      - Pages of page_size rows each
      - Uses :id > last_id keyset
    """

    def __init__(
        self,
        dataset_id: str,
        total_rows: int = 150_000,
        page_size: int = 50_000,
        count_response: int | None = None,
    ) -> None:
        self.dataset_id = dataset_id
        self.total_rows = total_rows
        self.page_size = page_size
        self.count_response = count_response if count_response is not None else total_rows
        self.call_log: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        params = dict(request.url.params)
        self.call_log.append({"url": url, "params": params})

        # Count endpoint
        if f"/resource/{self.dataset_id}.json" in url:
            select = params.get("$select", "")
            if "count(1)" in select:
                return httpx.Response(
                    200,
                    json=[{"count_1": str(self.count_response)}],
                )
            if "max(:updated_at)" in select:
                return httpx.Response(
                    200,
                    json=[{"max_ts": "2024-01-15T10:00:00.000"}],
                )

        # Metadata endpoint
        if f"/api/views/{self.dataset_id}.json" in url:
            return httpx.Response(
                200,
                json={
                    "id": self.dataset_id,
                    "name": "Test Dataset",
                    "columns": [
                        {"fieldName": ":id", "dataTypeName": "meta_data"},
                        {"fieldName": "nombre", "dataTypeName": "text"},
                        {"fieldName": "valor", "dataTypeName": "number"},
                    ],
                },
            )

        # CSV data endpoint
        if f"/resource/{self.dataset_id}.csv" in url:
            where = params.get("$where", "")
            limit = int(params.get("$limit", self.page_size))

            # Parse last_id from where clause (:id > 'X')
            # The keyset uses strict >, so next page starts at last_id + 1
            last_id = -1
            if ":id > '" in where:
                try:
                    last_id = int(where.split(":id > '")[1].split("'")[0])
                except (IndexError, ValueError):
                    last_id = -1

            start = last_id + 1
            available = self.total_rows - start
            count = min(limit, max(0, available))

            rows = _make_rows(start, count)
            csv_bytes = _make_csv(rows)
            return httpx.Response(200, content=csv_bytes, headers={"Content-Type": "text/csv"})

        return httpx.Response(404, text="Not found")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_raw(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    return raw


@pytest.fixture()
def fake_client(tmp_raw: Path) -> Iterator[tuple[SocrataClient, FakeTransport]]:
    transport = FakeTransport("test-1234", total_rows=130_000, page_size=50_000)
    with patch.dict(os.environ, {}, clear=False):
        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=transport,
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        yield client, transport
    client.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestManifest:
    def test_atomic_write_and_read(self, tmp_path: Path) -> None:
        """Atomic write produces readable JSON."""
        path = tmp_path / "manifest.json"
        data = {"dataset": {"status": "complete", "rows_pulled": 42}}
        _atomic_write_json(path, data)
        assert path.exists()
        loaded = _load_manifest(path)
        assert loaded["dataset"]["rows_pulled"] == 42

    def test_atomic_write_overwrite(self, tmp_path: Path) -> None:
        """Atomic write correctly overwrites existing file."""
        path = tmp_path / "manifest.json"
        _atomic_write_json(path, {"v": 1})
        _atomic_write_json(path, {"v": 2})
        assert _load_manifest(path)["v"] == 2

    def test_load_missing_manifest(self, tmp_path: Path) -> None:
        """Loading a missing manifest returns empty dict."""
        result = _load_manifest(tmp_path / "nonexistent.json")
        assert result == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """save_manifest + _load_manifest roundtrip preserves structure."""
        path = tmp_path / "manifest.json"
        original = {
            "ds1": {
                "dataset_id": "abcd-1234",
                "rows_pulled": 100,
                "status": "complete",
                "parts": [{"file": "p1.parquet", "rows": 100, "last_id": "99"}],
            }
        }
        _save_manifest(path, original)
        loaded = _load_manifest(path)
        assert loaded["ds1"]["rows_pulled"] == 100
        assert loaded["ds1"]["parts"][0]["last_id"] == "99"

    def test_update_manifest_entry_preserves_other_keys(self, tmp_path: Path) -> None:
        """Merging in one dataset's entry must not disturb a sibling's."""
        path = tmp_path / "manifest.json"
        _save_manifest(path, {"s1_secop2_contratos": {"status": "complete", "rows_pulled": 5657593}})
        _update_manifest_entry(path, "s2_secop2_procesos", {"status": "in_progress", "rows_pulled": 50000})
        loaded = _load_manifest(path)
        assert loaded["s1_secop2_contratos"]["rows_pulled"] == 5657593
        assert loaded["s2_secop2_procesos"]["rows_pulled"] == 50000

    def test_update_manifest_entry_survives_concurrent_writers(self, tmp_path: Path) -> None:
        """
        Regression test for the real bug this function fixes: `make pull-full`
        runs S1 and S2 as separate OS processes writing the same
        manifest.json. The old code (`manifest = _load_manifest(...)` held
        for the whole pull, mutated, then `_save_manifest` on every page)
        held a stale in-memory copy per process -- whichever process saved
        last would silently erase the other's entry. Simulate many
        concurrent writers (threads, real OS-level file locking via fcntl
        doesn't care whether the caller is a thread or a process) hammering
        distinct keys and assert every single one survives.
        """
        import threading

        path = tmp_path / "manifest.json"
        n_writers = 20

        def write_one(i: int) -> None:
            for round_ in range(3):  # multiple rounds per writer, like real pagination
                _update_manifest_entry(path, f"dataset_{i}", {"rows_pulled": round_ * 100 + i})

        threads = [threading.Thread(target=write_one, args=(i,)) for i in range(n_writers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        loaded = _load_manifest(path)
        assert len(loaded) == n_writers
        for i in range(n_writers):
            assert loaded[f"dataset_{i}"]["rows_pulled"] == 2 * 100 + i  # last round each writer completed


class TestCsvParsing:
    def test_all_columns_are_strings(self) -> None:
        """_parse_csv_all_strings returns all columns as string type."""
        import pyarrow as pa

        rows = _make_rows(0, 5)
        csv_bytes = _make_csv(rows)
        table = _parse_csv_all_strings(csv_bytes)
        for col in table.schema:
            assert table.schema.field(col.name).type == pa.string(), (
                f"Column {col.name} should be string, got {table.schema.field(col.name).type}"
            )

    def test_row_count(self) -> None:
        """Parsed CSV has the expected number of rows."""
        rows = _make_rows(0, 100)
        csv_bytes = _make_csv(rows)
        table = _parse_csv_all_strings(csv_bytes)
        assert len(table) == 100


class TestKeysetPagination:
    def test_pages_assembled_correctly(self, fake_client: tuple, tmp_raw: Path) -> None:
        """Keyset pagination assembles all pages and stops at the right row count."""
        client, transport = fake_client
        # 130,000 rows → 3 pages (50k + 50k + 30k)
        manifest_path = tmp_raw / "manifest.json"

        entry = client.pull_dataset(
            dataset_id="test-1234",
            name="test_ds",
            manifest_path=manifest_path,
        )

        assert entry["rows_pulled"] == 130_000
        assert entry["status"] == "complete"
        assert len(entry["parts"]) == 3

        # Verify part files exist and have correct row counts
        parts = entry["parts"]
        assert parts[0]["rows"] == 50_000
        assert parts[1]["rows"] == 50_000
        assert parts[2]["rows"] == 30_000

    def test_parquet_files_written(self, fake_client: tuple, tmp_raw: Path) -> None:
        """Parquet part files are written for each page."""
        client, transport = fake_client
        manifest_path = tmp_raw / "manifest.json"

        client.pull_dataset(
            dataset_id="test-1234",
            name="test_ds",
            manifest_path=manifest_path,
        )

        ds_dir = tmp_raw / "test_ds"
        part_files = sorted(ds_dir.glob("part-*.parquet"))
        assert len(part_files) == 3

        # Verify first part is readable
        table = pq.read_table(part_files[0])
        assert len(table) == 50_000

    def test_last_id_advances_per_page(self, fake_client: tuple, tmp_raw: Path) -> None:
        """Each page's last_id is strictly greater than the previous."""
        client, transport = fake_client
        manifest_path = tmp_raw / "manifest.json"

        entry = client.pull_dataset(
            dataset_id="test-1234",
            name="test_ds",
            manifest_path=manifest_path,
        )

        parts = entry["parts"]
        last_ids = [int(p["last_id"]) for p in parts]
        assert last_ids == sorted(last_ids), "last_ids should be strictly increasing"
        assert last_ids[-1] == 129_999, f"Expected last_id=129999, got {last_ids[-1]}"

    def test_stops_at_empty_page(self, tmp_raw: Path) -> None:
        """Pull stops when API returns 0 rows (exact multiple of page size)."""
        transport = FakeTransport("test-1234", total_rows=100_000, page_size=50_000)
        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=transport,
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            entry = client.pull_dataset(
                dataset_id="test-1234",
                name="test_ds",
                manifest_path=tmp_raw / "manifest.json",
            )
            assert entry["rows_pulled"] == 100_000
            assert len(entry["parts"]) == 2  # 50k + 50k, then empty page stops
        finally:
            client.close()


class TestResume:
    def test_resume_from_last_id(self, tmp_raw: Path) -> None:
        """Resume continues from the last recorded :id without duplicating rows."""
        transport = FakeTransport("abcd-5678", total_rows=120_000, page_size=50_000)
        manifest_path = tmp_raw / "manifest.json"
        ds_dir = tmp_raw / "resume_ds"
        ds_dir.mkdir()

        # Simulate a partial pull: 1 page already done (rows 0–49999)
        existing_part = ds_dir / "part-00000.parquet"
        rows = _make_rows(0, 50_000)
        csv_bytes = _make_csv(rows)
        first_table = _parse_csv_all_strings(csv_bytes)
        pq.write_table(first_table, existing_part)

        pre_manifest = {
            "resume_ds": {
                "dataset_id": "abcd-5678",
                "params": {"where": None, "select": None},
                "live_count_at_start": 120_000,
                "rows_pulled": 50_000,
                "status": "in_progress",
                "parts": [
                    {
                        "file": "data/raw/resume_ds/part-00000.parquet",
                        "rows": 50_000,
                        "last_id": "49999",
                    }
                ],
                "started_at": "2024-01-01T00:00:00+00:00",
            }
        }
        _save_manifest(manifest_path, pre_manifest)

        # Now resume
        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=transport,
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            entry = client.pull_dataset(
                dataset_id="abcd-5678",
                name="resume_ds",
                out_dir=ds_dir,
                manifest_path=manifest_path,
            )
        finally:
            client.close()

        # Should have 3 parts total: the original + 2 more (50k+20k)
        assert len(entry["parts"]) == 3
        # Total rows: 50k already + 70k new
        assert entry["rows_pulled"] == 120_000
        # The first part's last_id is still 49999
        assert entry["parts"][0]["last_id"] == "49999"
        # The second page starts from 50000 (last_id=99999)
        assert int(entry["parts"][1]["last_id"]) == 99_999
        assert entry["status"] == "complete"

    def test_complete_dataset_is_noop(self, fake_client: tuple, tmp_raw: Path) -> None:
        """Re-running a complete pull without --refresh is a no-op."""
        client, transport = fake_client
        manifest_path = tmp_raw / "manifest.json"

        # First pull
        entry1 = client.pull_dataset(
            dataset_id="test-1234",
            name="test_ds",
            manifest_path=manifest_path,
        )
        calls_after_first = len(transport.call_log)

        # Second pull (no --refresh) — should be a no-op
        entry2 = client.pull_dataset(  # noqa: F841
            dataset_id="test-1234",
            name="test_ds",
            manifest_path=manifest_path,
        )

        assert len(transport.call_log) == calls_after_first, (
            "No new HTTP calls should be made for a complete dataset"
        )
        assert entry2["rows_pulled"] == entry1["rows_pulled"]
        assert entry2["status"] == "complete"


class TestIncremental:
    def test_refresh_uses_updated_at_where(self, tmp_raw: Path) -> None:
        """--refresh pull uses :updated_at > watermark in WHERE clause."""
        transport = FakeTransport("ref-5678", total_rows=5, page_size=50_000)
        manifest_path = tmp_raw / "manifest.json"

        # Seed manifest with a completed pull and watermark
        pre_manifest = {
            "ref_ds": {
                "dataset_id": "ref-5678",
                "rows_pulled": 130_000,
                "status": "complete",
                "max_updated_at": "2024-01-15T10:00:00.000",
                "parts": [{"file": "p0.parquet", "rows": 130_000, "last_id": "129999"}],
            }
        }
        _save_manifest(manifest_path, pre_manifest)

        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=transport,
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            client.pull_dataset(
                dataset_id="ref-5678",
                name="ref_ds",
                manifest_path=manifest_path,
                refresh=True,
            )
        finally:
            client.close()

        # Check that a CSV request was made with :updated_at in WHERE
        csv_calls = [
            c for c in transport.call_log if "/resource/ref-5678.csv" in c["url"]
        ]
        assert csv_calls, "Should have made at least one CSV request for refresh"
        where_val = csv_calls[0]["params"].get("$where", "")
        assert ":updated_at" in where_val, (
            f":updated_at should appear in WHERE clause, got: {where_val}"
        )
        assert "2024-01-15T10:00:00.000" in where_val, (
            "Watermark timestamp should appear in WHERE clause"
        )

    def test_refresh_produces_refresh_parts(self, tmp_raw: Path) -> None:
        """Refresh parts use 'part-refresh-' prefix."""
        transport = FakeTransport("ref-5678", total_rows=100, page_size=50_000)
        manifest_path = tmp_raw / "manifest.json"

        pre_manifest = {
            "ref_ds": {
                "dataset_id": "ref-5678",
                "rows_pulled": 1000,
                "status": "complete",
                "max_updated_at": "2024-01-10T00:00:00.000",
                "parts": [{"file": "p0.parquet", "rows": 1000, "last_id": "999"}],
            }
        }
        _save_manifest(manifest_path, pre_manifest)

        ds_dir = tmp_raw / "ref_ds"
        ds_dir.mkdir()

        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=transport,
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            entry = client.pull_dataset(
                dataset_id="ref-5678",
                name="ref_ds",
                out_dir=ds_dir,
                manifest_path=manifest_path,
                refresh=True,
            )
        finally:
            client.close()

        refresh_files = list(ds_dir.glob("part-refresh-*.parquet"))
        assert len(refresh_files) >= 1, "Should have written at least one refresh part"
        # Check manifest entry has refresh parts
        new_parts = [p for p in entry.get("parts", []) if "refresh" in p["file"]]
        assert new_parts, "Manifest should record refresh parts"
        # rows_pulled_this_run must be the 100 rows fetched THIS call, not
        # entry["rows_pulled"] (1000, the pre-seeded lifetime total + this
        # run's 100 = 1100) -- a caller logging "N rows this refresh" needs
        # the former, or every log line reports the dataset's lifetime size
        # regardless of what actually changed (see socrata.py's pull_dataset
        # docstring note added alongside this test).
        assert entry["rows_pulled_this_run"] == 100
        assert entry["rows_pulled"] == 1100

    def test_refresh_with_zero_new_rows_reports_zero_not_lifetime_total(
        self, tmp_raw: Path
    ) -> None:
        """A refresh that finds nothing new must report 0 rows_pulled_this_run,
        not silently echo the dataset's lifetime rows_pulled (a real bug caught
        live: datos.gov.co's jbjy-vk9h had 0 rows changed since the watermark,
        and the pre-fix log line printed "5657593 rows pulled" -- the dataset's
        total size -- which would make every quiet week's cron log look
        identical to a full re-pull instead of clearly saying nothing changed)."""
        transport = FakeTransport("ref-5678", total_rows=0, page_size=50_000)
        manifest_path = tmp_raw / "manifest.json"

        pre_manifest = {
            "ref_ds": {
                "dataset_id": "ref-5678",
                "rows_pulled": 5_657_593,
                "status": "complete",
                "max_updated_at": "2026-07-02T07:52:43.863Z",
                "parts": [{"file": "p0.parquet", "rows": 5_657_593, "last_id": "999"}],
            }
        }
        _save_manifest(manifest_path, pre_manifest)

        ds_dir = tmp_raw / "ref_ds"
        ds_dir.mkdir()

        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=transport,
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            entry = client.pull_dataset(
                dataset_id="ref-5678",
                name="ref_ds",
                out_dir=ds_dir,
                manifest_path=manifest_path,
                refresh=True,
            )
        finally:
            client.close()

        assert entry["rows_pulled_this_run"] == 0
        assert entry["rows_pulled"] == 5_657_593, "Lifetime total must stay unchanged when nothing new was pulled"
        assert not list(ds_dir.glob("part-refresh-*.parquet")), "No refresh part file should be written when 0 rows come back"


class TestWhereClause:
    def test_sample_where_limits_to_year(self, tmp_raw: Path) -> None:
        """Sample pull WHERE clause contains the 2023 year filter."""
        captured_params: list[dict] = []

        class CapturingTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                params = dict(request.url.params)
                captured_params.append(params)
                if "/resource/samp-0001.csv" in str(request.url):
                    return httpx.Response(
                        200,
                        content=b":id,col_a\n",
                        headers={"Content-Type": "text/csv"},
                    )
                if "/resource/samp-0001.json" in str(request.url):
                    select = params.get("$select", "")
                    if "count(1)" in select:
                        return httpx.Response(200, json=[{"count_1": "0"}])
                    if "max(:updated_at)" in select:
                        return httpx.Response(200, json=[{"max_ts": "2024-01-01T00:00:00.000"}])
                return httpx.Response(200, json={})

        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=CapturingTransport(),
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            client.pull_dataset(
                dataset_id="samp-0001",
                name="sample_ds",
                where=(
                    "fecha_de_firma >= '2023-01-01T00:00:00.000'"
                    " AND fecha_de_firma <= '2023-12-31T23:59:59.999'"
                ),
                manifest_path=tmp_raw / "manifest.json",
                sample_cap_pages=6,
            )
        finally:
            client.close()

        csv_calls = [p for p in captured_params if p.get("$where")]
        assert csv_calls, "Should have made calls with WHERE clause"
        where_val = csv_calls[0]["$where"]
        assert "2023" in where_val, "WHERE should contain year 2023"

    def test_secop1_slice_where_builder(self) -> None:
        """_find_col finds entity column in SECOP I metadata."""
        from pipeline.extract.pull import _find_col

        secop1_cols = [
            "nro_proceso",
            "entidad",
            "objeto_a_contratar",
            "fecha_de_publicacion_del",
            "modalidad_de_contratacion",
        ]
        result = _find_col(secop1_cols, ["entidad", "nombre_entidad", "entidad_estatal"])
        assert result == "entidad"

    def test_find_col_partial_match(self) -> None:
        """_find_col falls back to partial match when exact match fails."""
        from pipeline.extract.pull import _find_col

        cols = ["nombre_del_proveedor_adjudicatario", "valor_total", "fecha_inicio"]
        result = _find_col(cols, ["nombre_proveedor", "nombre_del_proveedor"])
        assert result == "nombre_del_proveedor_adjudicatario"

    def test_find_col_returns_none_when_no_match(self) -> None:
        """_find_col returns None when no candidate matches."""
        from pipeline.extract.pull import _find_col

        cols = ["col_a", "col_b", "col_c"]
        result = _find_col(cols, ["xyz_nonexistent"])
        assert result is None


class TestCount:
    def test_count_parses_response(self, fake_client: tuple) -> None:
        """count() correctly parses the SoQL count response."""
        client, transport = fake_client
        result = client.count("test-1234")
        assert result == 130_000

    def test_count_with_where(self, tmp_raw: Path) -> None:
        """count() passes WHERE clause through to the API."""
        captured: list[dict] = []

        class WhereCapture(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                params = dict(request.url.params)
                captured.append(params)
                return httpx.Response(200, json=[{"count_1": "42"}])

        client = SocrataClient(tmp_raw)
        client._client = httpx.Client(
            transport=WhereCapture(),
            base_url="https://www.datos.gov.co",
            timeout=30,
        )
        try:
            result = client.count("abcd-1234", where="departamento = 'BOGOTA'")
        finally:
            client.close()

        assert result == 42
        assert any("departamento" in str(c.get("$where", "")) for c in captured)


class TestKnownCases:
    def test_known_cases_yaml_loads(self) -> None:
        """known_cases.yaml loads and has ≥8 cases."""
        from pipeline.extract.pull import load_known_cases

        cases = load_known_cases()
        assert len(cases) >= 8, f"Expected ≥8 cases, got {len(cases)}"

    def test_each_case_has_required_fields(self) -> None:
        """Each known case has slug, nombre, periodo, secop1, fuentes."""
        from pipeline.extract.pull import load_known_cases

        cases = load_known_cases()
        for case in cases:
            assert "slug" in case, f"Case missing 'slug': {case}"
            assert "nombre" in case, f"Case {case.get('slug')} missing 'nombre'"
            assert "periodo" in case, f"Case {case.get('slug')} missing 'periodo'"
            assert "secop1" in case, f"Case {case.get('slug')} missing 'secop1'"
            assert "fuentes" in case, f"Case {case.get('slug')} missing 'fuentes'"
            assert len(case["fuentes"]) >= 1, (
                f"Case {case.get('slug')} has no fuentes"
            )

    def test_secop1_cases_have_hint(self) -> None:
        """All secop1=True cases have hint_entidad_like."""
        from pipeline.extract.pull import load_known_cases

        cases = load_known_cases()
        for case in cases:
            if case.get("secop1"):
                assert case.get("hint_entidad_like"), (
                    f"SECOP I case {case['slug']} has no hint_entidad_like"
                )


class TestFullDatasetDispatch:
    """
    `make pull-full` runs S1 and S2 as two separate `--full --dataset X`
    processes (see Makefile) instead of pull_big_full's sequential default,
    so this routing is load-bearing: if `--full --dataset s1_secop2_contratos`
    ever accidentally called pull_big_full (both datasets) instead of just
    pull_s1_full, `make pull-full`'s two background processes would each
    pull BOTH datasets, doubling the work instead of parallelizing it.
    """

    def _run_main(self, monkeypatch: pytest.MonkeyPatch, argv: list[str], tmp_path: Path) -> None:
        import pipeline.extract.pull as pull_mod

        monkeypatch.setattr("sys.argv", ["pull.py", *argv])
        monkeypatch.setattr(pull_mod, "RAW_DIR", tmp_path)
        monkeypatch.setenv("SOCRATA_APP_TOKEN", "fake-token-for-test")
        pull_mod.main()

    def test_full_with_s1_dataset_calls_only_pull_s1_full(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import pipeline.extract.pull as pull_mod

        with (
            patch.object(pull_mod, "pull_s1_full") as mock_s1,
            patch.object(pull_mod, "pull_s2_full") as mock_s2,
            patch.object(pull_mod, "pull_big_full") as mock_big,
        ):
            self._run_main(monkeypatch, ["--full", "--dataset", "s1_secop2_contratos"], tmp_path)
        mock_s1.assert_called_once()
        mock_s2.assert_not_called()
        mock_big.assert_not_called()

    def test_full_with_s2_dataset_calls_only_pull_s2_full(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import pipeline.extract.pull as pull_mod

        with (
            patch.object(pull_mod, "pull_s1_full") as mock_s1,
            patch.object(pull_mod, "pull_s2_full") as mock_s2,
            patch.object(pull_mod, "pull_big_full") as mock_big,
        ):
            self._run_main(monkeypatch, ["--full", "--dataset", "s2_secop2_procesos"], tmp_path)
        mock_s2.assert_called_once()
        mock_s1.assert_not_called()
        mock_big.assert_not_called()

    def test_full_without_dataset_calls_pull_big_full(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import pipeline.extract.pull as pull_mod

        with patch.object(pull_mod, "pull_big_full") as mock_big:
            self._run_main(monkeypatch, ["--full"], tmp_path)
        mock_big.assert_called_once()

    def test_full_with_dataset_requires_app_token(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Without SOCRATA_APP_TOKEN, --full --dataset X must refuse to run rather than silently throttle."""
        import pipeline.extract.pull as pull_mod

        monkeypatch.setattr("sys.argv", ["pull.py", "--full", "--dataset", "s1_secop2_contratos"])
        monkeypatch.setattr(pull_mod, "RAW_DIR", tmp_path)
        monkeypatch.delenv("SOCRATA_APP_TOKEN", raising=False)
        with (
            patch.object(pull_mod, "pull_s1_full") as mock_s1,
            pytest.raises(SystemExit) as exc_info,
        ):
            pull_mod.main()
        assert exc_info.value.code == 1
        mock_s1.assert_not_called()

    def test_full_with_unsupported_dataset_name_exits(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """--full --dataset only makes sense for the two big datasets, not the small ones."""
        with pytest.raises(SystemExit) as exc_info:
            self._run_main(monkeypatch, ["--full", "--dataset", "e1_rues_santarosa"], tmp_path)
        assert exc_info.value.code == 1


class TestPullSmallFailureAggregation:
    """
    Regression coverage for a real bug caught live: l4_siri failed with a
    transient network error (since fixed separately by widening
    _is_retryable to cover httpx.TransportError), pull_small logged and
    swallowed it, `make pull` exited 0 with l4_siri's directory empty, and
    the real failure only surfaced ~20+ minutes later as a confusing
    `_duckdb.IOException` deep inside `marts`. pull_small/pull_secop1_slices
    must still attempt every dataset (one flaky dataset shouldn't block the
    rest) but report the failure back so the CLI can exit non-zero.
    """

    def test_pull_small_tries_all_datasets_and_reports_failure(self, fake_client: tuple) -> None:
        from pipeline.extract.pull import SMALL_DATASETS, pull_small

        client, _ = fake_client
        attempted: list[str] = []

        def fake_pull_dataset(*, dataset_id, name, manifest_path=None, **kwargs):  # noqa: ANN001
            attempted.append(name)
            if name == "l4_siri":
                raise RuntimeError("peer closed connection without sending complete message body")
            return {"status": "complete", "rows_pulled": 1, "live_count_at_start": 1}

        with patch.object(client, "pull_dataset", side_effect=fake_pull_dataset):
            result = pull_small(client)

        assert result is False
        assert attempted == SMALL_DATASETS  # every dataset attempted, none skipped after the failure

    def test_pull_small_returns_true_when_all_succeed(self, fake_client: tuple) -> None:
        from pipeline.extract.pull import pull_small

        client, _ = fake_client
        with patch.object(
            client, "pull_dataset", return_value={"status": "complete", "rows_pulled": 1, "live_count_at_start": 1}
        ):
            result = pull_small(client)

        assert result is True
