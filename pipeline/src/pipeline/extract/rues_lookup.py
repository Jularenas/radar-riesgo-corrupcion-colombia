"""
M4: tiered per-NIT RUES fallback for suppliers the bulk chamber datasets (E1) don't match.

--------------------------------------------------------------------------------------------
DECISION — no real lookup is implemented, and this is deliberate, not an oversight.
--------------------------------------------------------------------------------------------
Before writing this module we spent time (WebSearch/WebFetch, ~10-15 minutes) checking whether
RUES (rues.org.co) or Confecámaras expose an official, documented, self-service API or open-data
bulk endpoint for per-NIT company lookup, beyond the per-chamber bulk datasets already ingested
as E1 (pipeline.extract.pull / e1_rues_ibague, e1_rues_santarosa). Findings:

  - rues.org.co's own public "Consulta de Registros Públicos" (and Confecámaras'
    confecamaras.org.co/consulta-por-nit/) are browser-facing web forms, not APIs.
  - There IS a JSON API behind the scenes (ruesapi.rues.org.co, pruebasruesapi.rues.org.co,
    endpoints like `GET api/EstablecimientoResumido?...nit=...`), reverse-engineered and
    documented informally by third parties (e.g. a public GitHub gist). But:
      * It is not documented by RUES/Confecámaras themselves — the official `/Help` page for it
        is effectively empty; what documentation exists lives on a "pruebas" (testing) subdomain.
      * It requires a bearer token from `ruesapi.rues.org.co/Token`, and per RUES's own published
        user guidance that token is only issued to public entities, private entities performing
        public functions, academics, or registered merchants renewing their own registration —
        after an application/validation step, not self-service signup for a general integrator.
      * Third parties report the token endpoint has broken/changed as RUES migrates its frontend
        to direct Elasticsearch calls — i.e. it's an undocumented implementation detail of their
        own web app, not a stable public contract.
      * Commercial resellers (e.g. apitude.co) sell wrapped access to this same data, which is
        itself evidence there's no free, open, bulk per-NIT API a project like this can rely on.
  - Conclusion: no real, authorized, documented API exists for this project to call. The
    legitimate open-data channel for this data IS what M1 already pulls (the per-chamber E1
    bulk datasets on datos.gov.co).

Given that, we explicitly chose NOT to scrape rues.org.co's consulta web form. RUES is a
government anti-fraud registry; its consulta form is not designed for automated bulk queries
(session/anti-automation friction is expected), and deciding to route around that is a
legal/authorization judgment call this project should not make unilaterally just to fill in a
few more dates. That decision belongs to whoever operates this project in production (e.g. by
procuring a paid data-provider contract, or getting Confecámaras to grant the gated API token
through their real application process) — not to code written under a deadline.

So `lookup_fecha_matricula()` below is a **stable, cached, rate-limited no-op**: it always
returns None today. The point of building it anyway is that callers (M5 scoring, M7 export) can
depend on the final signature now, and whoever wires in a real source later (paid provider drop-in,
manual CSV import, or a future *actual* documented API) only has to fill in `_fetch_from_api()` —
every caller, the cache, and the rate limiter keep working unchanged. The rate limiter and
tenacity retry/backoff scaffolding are real (not stubbed) specifically so that day is safe by
construction: nobody can wire in a real HTTP call here and accidentally hammer a government site.

Usage as a library (stable signature — this is the one thing M5/M7 should import):
    from pipeline.extract.rues_lookup import lookup_fecha_matricula
    fecha = lookup_fecha_matricula("900123456")   # -> date | None

CLI (identifies which unmatched suppliers currently qualify for this fallback tier per
PLAN.md M4 — contracts >= 200M COP, or already-flagged once M3's flag_contrato exists —
and demonstrates the lookup path against a small sample of them):
    uv run python -m pipeline.extract.rues_lookup [--mart PATH] [--limit N] [--rate-limit R]
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
from tenacity import retry, stop_after_attempt, wait_exponential

from pipeline.clean.normalize import normalize_doc
from pipeline.config import MARTS_DIR, STAGING_DIR
from pipeline.extract.socrata import _load_manifest as _load_cache_file
from pipeline.extract.socrata import _save_manifest as _save_cache_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = STAGING_DIR / "rues_lookup_cache.json"

# Conservative by design: this only matters once/if a real endpoint is wired into
# _fetch_from_api(); it costs nothing while that function is a no-op.
DEFAULT_RATE_LIMIT_PER_SEC = 1.0

# PLAN.md M4: fallback tier applies to suppliers on contracts >= 200M COP (or already
# otherwise-flagged, once M3's flag_contrato table exists — see find_fallback_candidates()).
MIN_CONTRACT_VALUE_COP = 200_000_000


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple leaky-bucket-of-one throttle: blocks so calls are spaced >= 1/rate_per_sec apart."""

    def __init__(self, rate_per_sec: float) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be > 0")
        self._min_interval = 1.0 / rate_per_sec
        self._last_call: float | None = None

    def wait(self) -> None:
        now = time.monotonic()
        if self._last_call is not None:
            elapsed = now - self._last_call
            remaining = self._min_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# The swap-in point for a real data source (paid provider, future documented API, ...)
# ---------------------------------------------------------------------------


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30), reraise=True)
def _fetch_from_api(nit_base: str) -> date | None:
    """
    Currently a documented no-op — see module docstring for why.

    Left as its own retry-wrapped function (rather than inlined) so that plugging in a real
    HTTP call here automatically inherits tenacity backoff on top of the caller's rate limiting.
    """
    return None


# ---------------------------------------------------------------------------
# Cached, rate-limited client
# ---------------------------------------------------------------------------


class RuesLookupClient:
    def __init__(
        self,
        cache_path: Path | None = None,
        rate_limit_per_sec: float = DEFAULT_RATE_LIMIT_PER_SEC,
    ) -> None:
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self._rate_limiter = _RateLimiter(rate_limit_per_sec)
        self._cache: dict[str, Any] = _load_cache_file(self.cache_path)

    def lookup(self, nit: str) -> date | None:
        """Look up fecha_matricula for `nit`, using (and populating) the on-disk cache."""
        nit_base = normalize_doc(nit)["nit_base"]
        if not nit_base:
            return None

        if nit_base in self._cache:
            cached = self._cache[nit_base]
            raw = cached.get("fecha_matricula")
            return date.fromisoformat(raw) if raw else None

        self._rate_limiter.wait()
        result = _fetch_from_api(nit_base)

        self._cache[nit_base] = {
            "fecha_matricula": result.isoformat() if result else None,
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            # "noop" today; a real integration should write "api" / "manual_csv" / etc. so a
            # future re-check pass can tell "we checked with a real source" apart from
            # "we checked back when this was still a no-op."
            "source": "noop",
        }
        self._save()
        return result

    def _save(self) -> None:
        _save_cache_file(self.cache_path, self._cache)


_default_client: RuesLookupClient | None = None


def _get_default_client() -> RuesLookupClient:
    global _default_client
    if _default_client is None:
        _default_client = RuesLookupClient()
    return _default_client


def lookup_fecha_matricula(nit: str) -> date | None:
    """
    Stable entry point for M5/M7: look up a supplier's RUES fecha_matricula by NIT/cedula.

    Cached and rate-limited. Returns None for every input today (see module docstring) —
    callers must already treat None as "unknown," not "not express," exactly as they must
    for dim_proveedor.fecha_matricula itself.
    """
    return _get_default_client().lookup(nit)


# ---------------------------------------------------------------------------
# Candidate identification (PLAN.md M4 fallback-tier criteria) + CLI demo
# ---------------------------------------------------------------------------


def find_fallback_candidates(
    con: duckdb.DuckDBPyConnection,
    min_value: int = MIN_CONTRACT_VALUE_COP,
) -> list[tuple[str, str, float]]:
    """
    Suppliers with fecha_matricula still NULL after chamber-data enrichment (step 2) that
    qualify for the fallback tier: at least one contract >= min_value, OR (if M3's
    flag_contrato table exists yet) at least one fired flag. Returns (doc_proveedor_norm,
    nombre_proveedor, max_valor_contrato), highest value first.
    """
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    has_flags = "flag_contrato" in tables

    if has_flags:
        log.info("flag_contrato table found — using value OR flagged criterion")
        flagged_clause = """
            OR dp.doc_proveedor_norm IN (
                SELECT DISTINCT fc.doc_proveedor_norm
                FROM fct_contrato fc
                JOIN flag_contrato fl ON fl.row_id = fc.row_id
            )
        """
    else:
        log.info("flag_contrato table not present yet (M3 hasn't landed) — using value-only criterion")
        flagged_clause = ""

    query = f"""
        SELECT dp.doc_proveedor_norm, dp.nombre_proveedor, MAX(fc.valor_contrato) AS max_valor
        FROM dim_proveedor dp
        JOIN fct_contrato fc ON fc.doc_proveedor_norm = dp.doc_proveedor_norm
        WHERE dp.fecha_matricula IS NULL
        GROUP BY dp.doc_proveedor_norm, dp.nombre_proveedor
        HAVING MAX(fc.valor_contrato) >= {min_value} {flagged_clause}
        ORDER BY max_valor DESC
    """
    return con.execute(query).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser(description="M4: identify + demo the tiered per-NIT RUES fallback")
    parser.add_argument("--mart", type=Path, default=None, help="Path to corruption.duckdb")
    parser.add_argument("--limit", type=int, default=25, help="How many candidates to actually run lookup_fecha_matricula() on")
    parser.add_argument("--rate-limit", type=float, default=DEFAULT_RATE_LIMIT_PER_SEC, help="Requests/sec for the demo run")
    args = parser.parse_args()

    mart_path = args.mart or (MARTS_DIR / "corruption.duckdb")
    con = duckdb.connect(str(mart_path), read_only=True)
    try:
        candidates = find_fallback_candidates(con)
    finally:
        con.close()

    print(f"\n{len(candidates):,} suppliers qualify for the per-NIT fallback tier "
          f"(unmatched, contract >= {MIN_CONTRACT_VALUE_COP:,} COP or flagged).")

    demo = candidates[: args.limit]
    if not demo:
        print("Nothing to demo.")
        return

    client = RuesLookupClient(rate_limit_per_sec=args.rate_limit)
    print(f"Running lookup_fecha_matricula() on the top {len(demo)} by contract value "
          f"(no real network calls are made — see module docstring):")
    for doc, nombre, valor in demo:
        result = client.lookup(doc)
        print(f"  {doc:<15} {str(nombre)[:40]:<40} valor={valor:>18,.0f}  -> {result}")

    if len(candidates) > len(demo):
        remaining = len(candidates) - len(demo)
        est_minutes = remaining / max(args.rate_limit, 1e-9) / 60
        print(
            f"\n{remaining:,} more candidates not run in this demo. At the configured "
            f"{args.rate_limit:g} req/sec this would take ~{est_minutes:,.1f} more minutes — "
            "harmless to run in full since this path is a no-op today, but skipped here since "
            "it cannot produce a non-NULL result until a real source is wired into _fetch_from_api()."
        )


if __name__ == "__main__":
    main()
