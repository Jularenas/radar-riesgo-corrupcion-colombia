"""
Pull orchestration CLI.

Usage:
    uv run python -m pipeline.extract.pull --dataset <name>
    uv run python -m pipeline.extract.pull --all-small
    uv run python -m pipeline.extract.pull --full
    uv run python -m pipeline.extract.pull --sample
    uv run python -m pipeline.extract.pull --refresh --dataset <name>
    uv run python -m pipeline.extract.pull --divipola
    uv run python -m pipeline.extract.pull --secop1-slices
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from pipeline.config import DATASETS, RAW_DIR
from pipeline.extract.socrata import SocrataClient, _load_manifest, _save_manifest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dataset groups
# ---------------------------------------------------------------------------

SMALL_DATASETS = [
    "l1_responsabilidad_fiscal",
    "l2_multas_secop1",
    "l3_multas_secop2",
    "l4_siri",
    "e1_rues_ibague",
]

# e1_rues_santarosa (9.36M rows) is NOT small -- comparable in scale to S1/S2,
# not the ~tens-of-thousands-of-rows datasets above (e1_rues_ibague is only
# 90,937 rows, an actual small dataset despite the shared "e1_rues_" prefix).
# Pulling it inside pull_small's sequential loop bottlenecked that whole
# "small" bucket on one 9M-row pull. Treated here as a peer of S1/S2 for
# full pulls (see Makefile's pull-full); its --refresh path already ran
# concurrently with s1/s2 (see pull-refresh) since that predates this split.
BIG_DATASETS = ["s1_secop2_contratos", "s2_secop2_procesos", "e1_rues_santarosa"]

# Columns to pull for s2_secop2_procesos (verified against live metadata 2026-07-03)
# Actual column names from API: entidad, nit_entidad, departamento_entidad,
# ciudad_entidad, referencia_del_proceso, id_del_portafolio, fase,
# fecha_de_publicacion_del, precio_base, modalidad_de_contratacion, duracion,
# unidad_de_duracion, proveedores_invitados, proveedores_con_invitacion,
# visualizaciones_del, respuestas_al_procedimiento, respuestas_externas,
# conteo_de_respuestas_a_ofertas, proveedores_unicos_con, adjudicado,
# valor_total_adjudicacion, nombre_del_adjudicador, nombre_del_proveedor,
# nit_del_proveedor_adjudicado, urlproceso, estado_del_procedimiento
S2_DESIRED_COLS = [
    # Process / reference IDs
    "referencia_del_proceso",
    "id_del_portafolio",
    "id_del_proceso",
    # Entity
    "entidad",
    "nit_entidad",
    # Geography
    "departamento_entidad",
    "ciudad_entidad",
    # Modality / status
    "modalidad_de_contratacion",
    "fase",
    "estado_del_procedimiento",
    # Dates
    "fecha_de_publicacion_del",
    "fecha_de_recepcion_de",
    # Pricing / duration
    "precio_base",
    "duracion",
    "unidad_de_duracion",
    # Bidder metrics
    "proveedores_invitados",
    "proveedores_con_invitacion",
    "respuestas_al_procedimiento",
    "respuestas_externas",
    "conteo_de_respuestas_a_ofertas",
    "proveedores_unicos_con",
    "visualizaciones_del",
    # Award
    "adjudicado",
    "valor_total_adjudicacion",
    "nombre_del_adjudicador",
    "nit_del_proveedor_adjudicado",
    # Supplier / provider
    "nombre_del_proveedor",
    # URL
    "urlproceso",
]

# ---------------------------------------------------------------------------
# DIVIPOLA discovery
# ---------------------------------------------------------------------------

DIVIPOLA_SEARCH_URL = (
    "https://api.us.socrata.com/api/catalog/v1"
    "?domains=www.datos.gov.co&q=DIVIPOLA&limit=20"
)
DIVIPOLA_KEY = "e2_divipola"


def discover_divipola(client: SocrataClient) -> str:
    """
    Discover the DIVIPOLA dataset ID via Socrata discovery API.
    Returns the best-matching 4x4 ID and saves it to config context.
    """
    import httpx

    log.info("Discovering DIVIPOLA dataset via Socrata catalog API...")
    resp = httpx.get(DIVIPOLA_SEARCH_URL, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    results = resp.json().get("results", [])

    # Pick DANE-official dataset with dept + muni codes and names
    keywords = ["divipola", "dane", "municipio", "departamento", "codigo"]
    best: tuple[int, str, str] | None = None
    for r in results:
        resource = r.get("resource", {})
        name = (resource.get("name") or "").lower()
        description = (resource.get("description") or "").lower()
        combined = name + " " + description
        score = sum(1 for kw in keywords if kw in combined)
        dataset_id = resource.get("id", "")
        if dataset_id and score > 0:
            if best is None or score > best[0]:
                best = (score, dataset_id, resource.get("name", ""))

    if best is None:
        raise RuntimeError(
            "Could not find DIVIPOLA dataset via Socrata catalog. "
            "Check DIVIPOLA_SEARCH_URL or add e2_divipola manually to DATASETS."
        )

    score, dataset_id, found_name = best
    log.info(
        "DIVIPOLA dataset found: id=%s name=%r (score=%d)", dataset_id, found_name, score
    )
    return dataset_id


def ensure_divipola_in_config(dataset_id: str) -> None:
    """Patch DATASETS dict at runtime (for this process) and update config.py."""
    config_path = Path(__file__).resolve().parents[1] / "config.py"
    text = config_path.read_text()
    if "e2_divipola" in text:
        # Already present; just update runtime dict
        DATASETS[DIVIPOLA_KEY] = dataset_id
        return

    # Insert the new entry before the closing brace of DATASETS
    insert = f'    # Geography\n    "{DIVIPOLA_KEY}": "{dataset_id}",\n'
    # Find the line just before "# Data directories" comment
    marker = "    # Entity registries (RUES)"
    text = text.replace(marker, insert + "    " + marker[4:])
    config_path.write_text(text)
    DATASETS[DIVIPOLA_KEY] = dataset_id
    log.info("Saved e2_divipola=%s to config.py", dataset_id)


# ---------------------------------------------------------------------------
# SECOP I known-case slices
# ---------------------------------------------------------------------------


def load_known_cases() -> list[dict[str, Any]]:
    # __file__ = src/pipeline/extract/pull.py
    # parents[1] = src/pipeline/ → refs/ lives there
    cases_path = (
        Path(__file__).resolve().parents[1] / "refs" / "known_cases.yaml"
    )
    if not cases_path.exists():
        log.warning("known_cases.yaml not found at %s", cases_path)
        return []
    with open(cases_path) as f:
        return yaml.safe_load(f) or []


def pull_secop1_slices(client: SocrataClient, cases: list[dict[str, Any]]) -> bool:
    """
    For each known case with secop1=True, pull targeted slices from
    s3_secop1_procesos (and s4_secop1_contratos as fallback). Tries every
    case/dataset combination even if an earlier one fails, but returns False
    if any did (see pull_small's docstring for why callers must check this).
    """
    slices_dir = RAW_DIR / "secop1_slices"
    slices_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = slices_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)
    ok = True

    secop1_datasets = {
        "s3": ("s3_secop1_procesos", DATASETS.get("s3_secop1_procesos", "f789-7hwg")),
        "s4": ("s4_secop1_contratos", DATASETS.get("s4_secop1_contratos", "79ga-5jck")),
    }

    for case in cases:
        if not case.get("secop1", False):
            continue

        slug = case["slug"]
        hint_patterns = case.get("hint_entidad_like", [])
        periodo = case.get("periodo", [])

        if not hint_patterns:
            log.warning("Case %s has secop1=True but no hint_entidad_like, skipping", slug)
            continue

        for ds_short, (ds_name, ds_id) in secop1_datasets.items():
            # Get metadata to discover real column names
            try:
                meta = client.get_metadata(ds_id)
                columns = [c["fieldName"] for c in meta.get("columns", [])]
            except Exception as e:
                log.warning("Could not get metadata for %s: %s", ds_name, e)
                columns = []

            # Find entity name column (SECOP I uses different names)
            # Also check metadata for column data types
            col_types = {
                c["fieldName"]: c.get("dataTypeName", "text")
                for c in meta.get("columns", [])
            }

            entity_col = _find_col(
                columns,
                ["entidad", "nombre_entidad", "entidad_estatal", "descripcion_entidad"],
            )
            # Prefer timestamp columns for date filtering; anno_cargue_secop is a year string
            date_col = _find_col(
                columns,
                [
                    "fecha_de_publicacion_del",
                    "fecha_publicacion",
                    "fecha_inicio",
                    "fecha_de_firma",
                    "anno_cargue_secop",
                ],
            )

            # Build WHERE clause
            where_parts: list[str] = []
            if entity_col and hint_patterns:
                entity_filters = " OR ".join(
                    f"upper({entity_col}) LIKE '{p.upper()}'" for p in hint_patterns
                )
                where_parts.append(f"({entity_filters})")
            if date_col and periodo and len(periodo) >= 2:
                yr_start, yr_end = periodo[0], periodo[-1]
                col_type = col_types.get(date_col, "text")
                # anno_cargue_secop and similar year fields are stored as text/number
                if date_col in ("anno_cargue_secop", "anno_firma_contrato") or col_type in (
                    "number",
                    "text",
                ):
                    # Year-only comparison
                    where_parts.append(
                        f"({date_col} >= '{yr_start}' AND {date_col} <= '{yr_end}')"
                    )
                else:
                    where_parts.append(
                        f"({date_col} >= '{yr_start}-01-01T00:00:00.000' "
                        f"AND {date_col} <= '{yr_end}-12-31T23:59:59.999')"
                    )

            where = " AND ".join(where_parts) if where_parts else None

            out_dir = slices_dir / slug / ds_short
            entry_key = f"{slug}__{ds_short}"

            # Check existing
            if manifest.get(entry_key, {}).get("status") == "complete":
                log.info("Slice %s already complete, skipping", entry_key)
                continue

            log.info("Pulling SECOP I slice: case=%s dataset=%s", slug, ds_name)
            log.info("  WHERE: %s", where)

            try:
                # Check live count first
                live = client.count(ds_id, where=where)
                log.info("  Live count: %d rows", live)
                if live == 0:
                    log.info("  Slice returned 0 rows, recording in manifest")
                    manifest[entry_key] = {
                        "dataset_id": ds_id,
                        "case_slug": slug,
                        "where": where,
                        "rows_pulled": 0,
                        "status": "complete",
                        "note": "0 rows from API",
                    }
                    _save_manifest(manifest_path, manifest)
                    continue

                entry = client.pull_dataset(
                    dataset_id=ds_id,
                    name=entry_key,
                    where=where,
                    out_dir=out_dir,
                    manifest_path=manifest_path,
                )
                log.info(
                    "  Slice complete: %d rows in %d parts",
                    entry.get("rows_pulled", 0),
                    len(entry.get("parts", [])),
                )
            except Exception as e:
                log.error("Slice pull failed for %s/%s: %s", slug, ds_name, e)
                manifest[entry_key] = {
                    "dataset_id": ds_id,
                    "case_slug": slug,
                    "where": where,
                    "status": "error",
                    "error": str(e),
                }
                _save_manifest(manifest_path, manifest)
                ok = False

    return ok


def _find_col(columns: list[str], candidates: list[str]) -> str | None:
    """Find the first candidate that appears in columns (case-insensitive)."""
    cols_lower = {c.lower(): c for c in columns}
    for c in candidates:
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]
    # Partial match fallback
    for candidate in candidates:
        for col in columns:
            if candidate.lower() in col.lower():
                return col
    return None


# ---------------------------------------------------------------------------
# S2 column selection helper
# ---------------------------------------------------------------------------


def build_s2_select(meta: dict[str, Any]) -> str:
    """
    Build the $select string for s2_secop2_procesos based on actual metadata columns.
    Falls back to '*' if column list cannot be determined.
    """
    available = {c["fieldName"].lower() for c in meta.get("columns", [])}
    actual_name_map = {c["fieldName"].lower(): c["fieldName"] for c in meta.get("columns", [])}

    chosen: list[str] = []
    for col in S2_DESIRED_COLS:
        # Try exact match
        if col.lower() in available:
            chosen.append(actual_name_map[col.lower()])
            continue
        # Try prefix match (truncated column names)
        candidates = [c for c in available if c.startswith(col[:12].lower())]
        if candidates:
            chosen.append(actual_name_map[candidates[0]])

    if not chosen:
        log.warning("Could not match any S2 columns; falling back to SELECT *")
        return "*"

    log.info("S2 select: %d columns chosen", len(chosen))
    return ",".join(chosen)


# ---------------------------------------------------------------------------
# Main pull functions
# ---------------------------------------------------------------------------


def pull_small(client: SocrataClient) -> bool:
    """
    Pull all small datasets fully. Tries every dataset even if an earlier one
    fails (one flaky dataset shouldn't block the rest), but returns False if
    ANY failed -- after retries are exhausted in SocrataClient (see
    _is_retryable), a persistent failure here used to be logged and
    swallowed, so `make pull` exited 0 with e.g. l4_siri's directory empty,
    and the real failure only surfaced much later as a confusing
    `_duckdb.IOException` deep inside `marts`. Callers must check this and
    exit non-zero so the failure is loud and immediate instead.
    """
    manifest_path = RAW_DIR / "manifest.json"
    ok = True
    for name in SMALL_DATASETS:
        dataset_id = DATASETS.get(name)
        if not dataset_id:
            log.warning("Dataset %s not in DATASETS, skipping", name)
            continue
        log.info("Pulling small dataset: %s (%s)", name, dataset_id)
        try:
            entry = client.pull_dataset(
                dataset_id=dataset_id,
                name=name,
                manifest_path=manifest_path,
            )
            log.info(
                "  Done: %d rows pulled (live count: %d)",
                entry.get("rows_pulled", 0),
                entry.get("live_count_at_start", 0),
            )
        except Exception as e:
            log.error("Failed to pull %s: %s", name, e)
            ok = False
    return ok


def pull_s1_full(client: SocrataClient) -> None:
    """Pull S1 (SECOP II Contratos) fully, all columns — long-running, resumable."""
    log.info("Pulling S1 (SECOP II Contratos) — all columns")
    try:
        entry = client.pull_dataset(
            dataset_id=DATASETS["s1_secop2_contratos"],
            name="s1_secop2_contratos",
            manifest_path=RAW_DIR / "manifest.json",
        )
        log.info("S1 status: %s, rows: %d", entry.get("status"), entry.get("rows_pulled", 0))
    except Exception as e:
        log.error("S1 pull error: %s", e)
        raise


def pull_s2_full(client: SocrataClient) -> None:
    """Pull S2 (SECOP II Procesos) fully, column-projected — long-running, resumable."""
    log.info("Pulling S2 (SECOP II Procesos) — selected columns")
    try:
        meta = client.get_metadata(DATASETS["s2_secop2_procesos"], name="s2_secop2_procesos")
        s2_select = build_s2_select(meta)
        entry = client.pull_dataset(
            dataset_id=DATASETS["s2_secop2_procesos"],
            name="s2_secop2_procesos",
            select=s2_select,
            manifest_path=RAW_DIR / "manifest.json",
        )
        log.info("S2 status: %s, rows: %d", entry.get("status"), entry.get("rows_pulled", 0))
    except Exception as e:
        log.error("S2 pull error: %s", e)
        raise


def pull_rues_full(client: SocrataClient) -> None:
    """Pull e1_rues_santarosa fully (~9.36M rows) -- see BIG_DATASETS' comment for why this isn't in SMALL_DATASETS."""
    log.info("Pulling e1_rues_santarosa (RUES Santa Rosa de Cabal)")
    try:
        entry = client.pull_dataset(
            dataset_id=DATASETS["e1_rues_santarosa"],
            name="e1_rues_santarosa",
            manifest_path=RAW_DIR / "manifest.json",
        )
        log.info("RUES status: %s, rows: %d", entry.get("status"), entry.get("rows_pulled", 0))
    except Exception as e:
        log.error("RUES pull error: %s", e)
        raise


def pull_big_full(client: SocrataClient) -> None:
    """
    Pull S1 + S2 + e1_rues_santarosa fully, sequentially in this one process.
    Used when `--full` is invoked without `--dataset` (e.g. a manual one-off
    pull). `make pull-full` instead runs each as a separate concurrent
    process (see Makefile) -- all three write to the same manifest.json
    either way, which is safe because `pull_dataset`'s writes go through
    `_update_manifest_entry`'s lock-protected merge, not a stale in-memory
    copy.
    """
    print(
        "\nWARNING: Full pull of S1 (~5.6M rows), S2 (~8.7M rows), and RUES (~9.4M rows) "
        "may take several hours.\nThe pull is resumable: kill it at any time and re-run to continue.\n"
    )
    pull_s1_full(client)
    pull_s2_full(client)
    pull_rues_full(client)


def pull_sample(client: SocrataClient) -> None:
    """
    Pull a sample of S1 and S2 (2023 data, max 6 pages = 300k rows each).
    Writes to data/raw/sample/{name}/ with its own manifest.json.
    """
    sample_dir = RAW_DIR / "sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = sample_dir / "manifest.json"

    YEAR_WHERE = (
        "fecha_de_firma >= '2023-01-01T00:00:00.000'"
        " AND fecha_de_firma <= '2023-12-31T23:59:59.999'"
    )
    S2_YEAR_WHERE = (
        "fecha_de_publicacion_del >= '2023-01-01T00:00:00.000'"
        " AND fecha_de_publicacion_del <= '2023-12-31T23:59:59.999'"
    )

    # S1 sample
    log.info("Pulling S1 sample (2023, max 300k rows)")
    try:
        entry = client.pull_dataset(
            dataset_id=DATASETS["s1_secop2_contratos"],
            name="s1_secop2_contratos",
            where=YEAR_WHERE,
            out_dir=sample_dir / "s1_secop2_contratos",
            manifest_path=manifest_path,
            sample_cap_pages=6,
        )
        log.info("S1 sample: %d rows", entry.get("rows_pulled", 0))
    except Exception as e:
        log.error("S1 sample error: %s", e)

    # S2 sample (column-projected)
    log.info("Pulling S2 sample (2023, max 300k rows)")
    try:
        meta = client.get_metadata(
            DATASETS["s2_secop2_procesos"], name="s2_secop2_procesos"
        )
        s2_select = build_s2_select(meta)
        entry = client.pull_dataset(
            dataset_id=DATASETS["s2_secop2_procesos"],
            name="s2_secop2_procesos",
            where=S2_YEAR_WHERE,
            select=s2_select,
            out_dir=sample_dir / "s2_secop2_procesos",
            manifest_path=manifest_path,
            sample_cap_pages=6,
        )
        log.info("S2 sample: %d rows", entry.get("rows_pulled", 0))
    except Exception as e:
        log.error("S2 sample error: %s", e)


def pull_refresh(client: SocrataClient, name: str) -> None:
    """Pull incremental refresh for a dataset using :updated_at watermark."""
    manifest_path = RAW_DIR / "manifest.json"
    dataset_id = DATASETS.get(name)
    if not dataset_id:
        log.error("Unknown dataset: %s", name)
        sys.exit(1)

    log.info("Refreshing dataset: %s (%s)", name, dataset_id)
    entry = client.pull_dataset(
        dataset_id=dataset_id,
        name=name,
        manifest_path=manifest_path,
        refresh=True,
    )
    log.info(
        "Refresh done: %d new/changed rows since last watermark (dataset total: %d, new watermark: %s)",
        entry.get("rows_pulled_this_run", 0),
        entry.get("rows_pulled", 0),
        entry.get("max_updated_at"),
    )


def pull_divipola(client: SocrataClient) -> None:
    """Discover and pull the DIVIPOLA dataset."""
    manifest_path = RAW_DIR / "manifest.json"

    # Check if we already have the ID
    if DIVIPOLA_KEY not in DATASETS:
        dataset_id = discover_divipola(client)
        ensure_divipola_in_config(dataset_id)
    else:
        dataset_id = DATASETS[DIVIPOLA_KEY]

    log.info("Pulling DIVIPOLA: %s", dataset_id)
    entry = client.pull_dataset(
        dataset_id=dataset_id,
        name=DIVIPOLA_KEY,
        manifest_path=manifest_path,
    )
    log.info(
        "DIVIPOLA done: %d rows", entry.get("rows_pulled", 0)
    )


# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------


def print_summary(raw_dir: Path, sample: bool = False) -> None:
    """Print per-dataset row count summary from manifest."""
    if sample:
        manifest_path = raw_dir / "sample" / "manifest.json"
    else:
        manifest_path = raw_dir / "manifest.json"

    if not manifest_path.exists():
        log.info("No manifest found at %s", manifest_path)
        return

    manifest = json.loads(manifest_path.read_text())
    print("\n=== Dataset Pull Summary ===")
    print(f"{'Name':<35} {'Live':>10} {'Pulled':>10} {'Status':<12}")
    print("-" * 70)
    for name, entry in manifest.items():
        live = entry.get("live_count_at_start", "?")
        pulled = entry.get("rows_pulled", 0)
        status = entry.get("status", "?")
        print(f"{name:<35} {str(live):>10} {str(pulled):>10} {status:<12}")
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull Socrata datasets")
    parser.add_argument("--dataset", help="Pull a single dataset by logical name")
    parser.add_argument("--all-small", action="store_true", help="Pull all small datasets")
    parser.add_argument("--full", action="store_true", help="Pull S1+S2 fully (hours)")
    parser.add_argument("--sample", action="store_true", help="Pull S1+S2 sample (2023)")
    parser.add_argument(
        "--refresh", action="store_true", help="Incremental refresh (use with --dataset)"
    )
    parser.add_argument("--divipola", action="store_true", help="Discover and pull DIVIPOLA")
    parser.add_argument(
        "--secop1-slices", action="store_true", help="Pull SECOP I slices for known cases"
    )
    parser.add_argument(
        "--monitor", action="store_true", help="Download Monitor Ciudadano database"
    )
    parser.add_argument("--summary", action="store_true", help="Print pull summary")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    ok = True

    with SocrataClient(RAW_DIR) as client:
        if args.summary:
            print_summary(RAW_DIR, sample=args.sample)
            return

        if args.all_small:
            ok = pull_small(client) and ok
            pull_divipola(client)

        if args.divipola:
            pull_divipola(client)

        if args.full and args.dataset:
            # Pulling one of the BIG_DATASETS by name under --full is how
            # `make pull-full` runs them as concurrent sibling processes (see
            # Makefile) instead of pull_big_full's sequential default. All
            # share manifest.json, so this only goes fast (rather than just
            # contending for one small tokenless rate-limit budget --
            # verified against Socrata's own docs) with an app token
            # configured.
            if not os.getenv("SOCRATA_APP_TOKEN"):
                log.error(
                    "SOCRATA_APP_TOKEN is not set. `--full --dataset X` is meant to run "
                    "concurrently with its sibling datasets (see `make pull-full`), and "
                    "tokenless requests share one small per-IP rate-limit budget -- "
                    "concurrent full pulls would fight over it instead of going faster. "
                    "Get a free token at https://www.datos.gov.co (account -> developer "
                    "settings) and set it via `export SOCRATA_APP_TOKEN=...` or in "
                    "pipeline/.env -- see pipeline/.env.example."
                )
                sys.exit(1)
            if args.dataset == "s1_secop2_contratos":
                pull_s1_full(client)
            elif args.dataset == "s2_secop2_procesos":
                pull_s2_full(client)
            elif args.dataset == "e1_rues_santarosa":
                pull_rues_full(client)
            else:
                log.error(
                    "--full --dataset only supports %s (got: %s) -- other datasets are "
                    "small enough that --full has no separate per-dataset pull for them",
                    ", ".join(BIG_DATASETS),
                    args.dataset,
                )
                sys.exit(1)
        elif args.full:
            pull_big_full(client)

        if args.sample:
            pull_sample(client)

        if args.refresh and args.dataset:
            pull_refresh(client, args.dataset)
        elif args.dataset and not args.refresh and not args.full:
            manifest_path = RAW_DIR / "manifest.json"
            dataset_id = DATASETS.get(args.dataset)
            if not dataset_id:
                log.error("Unknown dataset: %s", args.dataset)
                sys.exit(1)
            log.info("Pulling dataset: %s (%s)", args.dataset, dataset_id)
            entry = client.pull_dataset(
                dataset_id=dataset_id,
                name=args.dataset,
                manifest_path=manifest_path,
            )
            log.info(
                "Done: %d rows (live: %d, status: %s)",
                entry.get("rows_pulled", 0),
                entry.get("live_count_at_start", 0),
                entry.get("status"),
            )

        if args.secop1_slices:
            cases = load_known_cases()
            ok = pull_secop1_slices(client, cases) and ok

        if args.monitor:
            from pipeline.extract.monitor_ciudadano import download as mc_download

            mc_download(RAW_DIR)

    if not ok:
        log.error(
            "One or more datasets failed to pull after retries (see errors above) -- "
            "exiting non-zero so this fails loudly here instead of surfacing later as a "
            "confusing crash in `marts` (missing part-*.parquet files)."
        )
        sys.exit(1)

    if not any(
        [
            args.dataset,
            args.all_small,
            args.full,
            args.sample,
            args.divipola,
            args.secop1_slices,
            args.monitor,
            args.summary,
        ]
    ):
        parser.print_help()


if __name__ == "__main__":
    main()
