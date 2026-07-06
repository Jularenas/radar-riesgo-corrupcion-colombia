"""
Socrata SODA v2 client for datos.gov.co.

Features:
- Optional X-App-Token from SOCRATA_APP_TOKEN env var.
- Tenacity retry on 429/5xx/timeouts with exponential backoff and Retry-After support.
- count(dataset_id) via SoQL $select=count(1).
- get_metadata(dataset_id) → dict; saves snapshot to data/raw/{name}/metadata.json.
- Keyset pagination via :id, returns pages as pyarrow Tables (all strings).
- Appends each page to data/raw/{name}/part-{seq:05d}.parquet.
- Atomic manifest.json writes (temp + rename).
- Resume: continues from last recorded :id if manifest shows in_progress.
- Incremental refresh: pulls rows where :updated_at > watermark.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pyarrow as pa
import pyarrow.csv as pa_csv
import pyarrow.parquet as pq
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

BASE_URL = "https://www.datos.gov.co"
PAGE_SIZE = 50_000


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


def _is_retryable(exc: BaseException) -> bool:
    """Return True for 429/5xx HTTP responses and any transport-level failure."""
    if isinstance(exc, httpx.TransportError):
        # Covers httpx.TimeoutException (a TransportError subclass) plus
        # ConnectError/ReadError/RemoteProtocolError -- e.g. "peer closed
        # connection without sending complete message body", observed live
        # pulling l4_siri and e1_rues_santarosa. These have no HTTP response
        # to read a status code from, unlike HTTPStatusError below. A real,
        # ordinary risk over a many-thousand-request pull spanning tens of
        # minutes against a government open-data API -- not specific to
        # running pulls concurrently, just more likely to show up somewhere
        # across a long pull than it is to show up in any one request.
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return False


def _retry_decorator(max_attempts: int = 5):
    return retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# SocrataClient
# ---------------------------------------------------------------------------


class SocrataClient:
    """HTTP client for the Socrata SODA v2 API on datos.gov.co."""

    def __init__(self, raw_dir: Path, timeout: float = 120.0) -> None:
        self.raw_dir = raw_dir
        self._headers: dict[str, str] = {"Accept": "application/json"}
        token = os.getenv("SOCRATA_APP_TOKEN")
        if token:
            self._headers["X-App-Token"] = token
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers=self._headers,
            timeout=timeout,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SocrataClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal HTTP
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with retry and Retry-After support."""

        @_retry_decorator()
        def _do() -> httpx.Response:
            r = self._client.get(path, params=params)
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", "5"))
                time.sleep(retry_after)
                r.raise_for_status()
            r.raise_for_status()
            return r

        return _do()

    def _get_csv(self, path: str, params: dict[str, Any] | None = None) -> bytes:
        """GET CSV bytes with retry."""
        headers = dict(self._headers)
        headers["Accept"] = "text/csv"

        @_retry_decorator()
        def _do() -> bytes:
            r = self._client.get(path, params=params, headers=headers)
            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", "5"))
                time.sleep(retry_after)
                r.raise_for_status()
            r.raise_for_status()
            return r.content

        return _do()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def count(self, dataset_id: str, where: str | None = None) -> int:
        """Return row count via SoQL SELECT count(1)."""
        params: dict[str, Any] = {"$select": "count(1)"}
        if where:
            params["$where"] = where
        resp = self._get(f"/resource/{dataset_id}.json", params=params)
        data = resp.json()
        return int(data[0]["count_1"])

    def get_metadata(
        self,
        dataset_id: str,
        name: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch dataset metadata from /api/views/{id}.json.
        If `name` is given, saves a snapshot to data/raw/{name}/metadata.json.
        Returns the metadata dict.
        """
        resp = self._get(f"/api/views/{dataset_id}.json")
        meta: dict[str, Any] = resp.json()

        if name:
            out_dir = self.raw_dir / name
            out_dir.mkdir(parents=True, exist_ok=True)
            _atomic_write_json(out_dir / "metadata.json", meta)

        return meta

    def max_updated_at(self, dataset_id: str, where: str | None = None) -> str | None:
        """Return the max :updated_at timestamp string for the dataset (or filtered subset)."""
        params: dict[str, Any] = {"$select": "max(:updated_at) as max_ts"}
        if where:
            params["$where"] = where
        resp = self._get(f"/resource/{dataset_id}.json", params=params)
        data = resp.json()
        if data and data[0].get("max_ts"):
            return data[0]["max_ts"]
        return None

    def pull_dataset(
        self,
        dataset_id: str,
        name: str,
        where: str | None = None,
        select: str | None = None,
        out_dir: Path | None = None,
        manifest_path: Path | None = None,
        refresh: bool = False,
        sample_cap_pages: int | None = None,
    ) -> dict[str, Any]:
        """
        Pull a dataset with keyset pagination, saving parts to Parquet.

        Parameters
        ----------
        dataset_id : Socrata 4x4 ID.
        name       : logical name (used for paths and manifest key).
        where      : optional base $where filter (user-supplied).
        select     : optional $select expression (default = all cols).
        out_dir    : directory for part-*.parquet files. Defaults to raw_dir/name.
        manifest_path : path to manifest.json. Defaults to raw_dir/manifest.json.
        refresh    : if True, pull only rows updated since last watermark.
        sample_cap_pages : if set, stop after this many pages.

        Returns the manifest entry for this dataset.
        """
        if out_dir is None:
            out_dir = self.raw_dir / name
        if manifest_path is None:
            manifest_path = self.raw_dir / "manifest.json"

        out_dir.mkdir(parents=True, exist_ok=True)

        manifest = _load_manifest(manifest_path)
        entry = manifest.get(name, {})

        # ------------------------------------------------------------------
        # Decide pull mode
        # ------------------------------------------------------------------
        if not refresh:
            # Normal pull / resume
            if entry.get("status") == "complete":
                # Already complete; idempotent no-op
                return entry

            # Resume from last recorded :id
            last_id: str | None = None
            if entry.get("status") == "in_progress":
                parts = entry.get("parts", [])
                if parts:
                    last_id = parts[-1].get("last_id")
            start_seq = len(entry.get("parts", []))

        else:
            # Incremental refresh: pull rows updated since watermark
            watermark = entry.get("max_updated_at")
            if not watermark:
                # No watermark means no previous pull — do a full pull instead
                refresh = False
                last_id = None
                start_seq = 0
            else:
                refresh_where = f":updated_at > '{watermark}'"
                if where:
                    refresh_where = f"({where}) AND ({refresh_where})"
                where = refresh_where
                last_id = None
                # Refresh parts get a different prefix
                existing_refresh = [
                    p for p in entry.get("parts", []) if "refresh" in p["file"]
                ]
                start_seq = len(existing_refresh)

        # ------------------------------------------------------------------
        # Fetch live count and max :updated_at at pull start
        # ------------------------------------------------------------------
        live_count = self.count(dataset_id, where=None if refresh else where)
        max_ts = self.max_updated_at(dataset_id, where=None if refresh else where)

        started_at = _now_iso()

        # Initialize / update manifest entry
        if "parts" not in entry:
            entry["parts"] = []
        entry.update(
            {
                "dataset_id": dataset_id,
                "params": {"where": where, "select": select},
                "live_count_at_start": live_count,
                "max_updated_at": max_ts,
                "started_at": started_at,
                "status": "in_progress",
            }
        )
        entry.setdefault("rows_pulled", 0)
        _update_manifest_entry(manifest_path, name, entry)

        # ------------------------------------------------------------------
        # Keyset pagination
        # ------------------------------------------------------------------
        seq = start_seq
        total_new_rows = 0

        while True:
            # Build $where clause
            page_where_parts: list[str] = []
            if last_id is not None:
                page_where_parts.append(f"(:id > '{last_id}')")
            if where:
                page_where_parts.append(f"({where})")
            page_where = " AND ".join(page_where_parts) if page_where_parts else None

            params: dict[str, Any] = {
                "$order": ":id",
                "$limit": PAGE_SIZE,
            }
            if page_where:
                params["$where"] = page_where
            if select:
                # Star selections must come before :id in select list
                params["$select"] = f"{select},:id"
            else:
                params["$select"] = "*,:id"

            csv_bytes = self._get_csv(f"/resource/{dataset_id}.csv", params=params)

            table = _parse_csv_all_strings(csv_bytes)
            n_rows = len(table)

            if n_rows == 0:
                break

            # Determine last :id in this page
            id_col = table.column(":id")
            page_last_id = id_col[-1].as_py()

            # Write part file
            if refresh:
                part_fname = f"part-refresh-{seq:05d}.parquet"
            else:
                part_fname = f"part-{seq:05d}.parquet"
            part_path = out_dir / part_fname
            pq.write_table(table, part_path, compression="snappy")

            # Update manifest entry
            entry["parts"].append(
                {
                    "file": str(part_path.relative_to(self.raw_dir.parent.parent)),
                    "rows": n_rows,
                    "last_id": page_last_id,
                }
            )
            entry["rows_pulled"] = entry.get("rows_pulled", 0) + n_rows
            _update_manifest_entry(manifest_path, name, entry)

            total_new_rows += n_rows
            last_id = page_last_id
            seq += 1

            if n_rows < PAGE_SIZE:
                break  # Last page

            if sample_cap_pages is not None and (seq - start_seq) >= sample_cap_pages:
                break

        # Mark complete (unless sample-capped)
        if sample_cap_pages is None or (seq - start_seq) < sample_cap_pages:
            entry["status"] = "complete"
        else:
            entry["status"] = "in_progress"  # will resume if needed

        entry["finished_at"] = _now_iso()
        _update_manifest_entry(manifest_path, name, entry)

        # `rows_pulled_this_run` is informational only (not persisted to the
        # manifest -- `entry["rows_pulled"]` there stays the dataset's lifetime
        # total). Callers logging a refresh result need "how many rows changed
        # since the watermark", not the lifetime total, or a Sunday cron log
        # showing e.g. "5657593 rows pulled" every week regardless of whether
        # 0 or 5000 rows actually changed would be actively misleading.
        return {**entry, "rows_pulled_this_run": total_new_rows}


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _load_manifest(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_manifest(path: Path, data: dict[str, Any]) -> None:
    _atomic_write_json(path, data)


def _update_manifest_entry(path: Path, name: str, entry: dict[str, Any]) -> None:
    """
    Merge `manifest[name] = entry` into the manifest on disk, safe for two
    OS processes pulling different datasets into the same manifest.json at
    the same time (e.g. `make pull-full` runs S1 and S2 as separate
    concurrent processes -- see Makefile). `pull_dataset` used to hold one
    manifest dict in memory for its whole run and overwrite the entire file
    on every page; a concurrent sibling process's dict wouldn't have this
    process's key yet (or vice versa), so whichever process saved last would
    silently erase the other's entry. This instead re-reads the latest
    on-disk state and merges in only this process's own key, the whole
    read-merge-write cycle serialized via an flock on a sibling `.lock` file
    (advisory, POSIX-only -- fine for the local dev machine and GitHub
    Actions' ubuntu runners, the only two environments this pipeline runs
    on).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with open(lock_path, "w") as lock_f:
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            manifest = _load_manifest(path)
            manifest[name] = entry
            _save_manifest(path, manifest)
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically using a temp file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CSV parsing helpers
# ---------------------------------------------------------------------------


def _parse_csv_all_strings(csv_bytes: bytes) -> pa.Table:
    """Parse CSV bytes into a PyArrow Table with all columns as strings."""
    # First read to discover columns
    # newlines_in_values=True handles multiline cell values common in SECOP datasets
    table = pa_csv.read_csv(
        BytesIO(csv_bytes),
        read_options=pa_csv.ReadOptions(),
        parse_options=pa_csv.ParseOptions(newlines_in_values=True),
        convert_options=pa_csv.ConvertOptions(
            auto_dict_encode=False,
        ),
    )
    # Cast all columns to string
    new_cols = []
    for col in table.schema:
        arr = table.column(col.name)
        new_cols.append(arr.cast(pa.string()))

    return pa.table(
        {col.name: new_cols[i] for i, col in enumerate(table.schema)},
    )


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
