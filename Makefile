# Radar de Riesgo de Corrupcion -- Colombia
# Compatible with GNU Make 3.81 (POSIX, no GNU-4-only features)

.PHONY: check web web-gh-pages serve publish pull pull-sample pull-full pull-full-parallel pull-refresh marts profile rues-coverage flags score export export-fixtures all all-serve weekly

check:
	cd pipeline && uv run ruff check . && uv run pytest -q

web:
	cd web && npm run build

# Production build for GitHub Pages (project-site base path: served at
# <user>.github.io/radar-riesgo-corrupcion-colombia/, not the domain root).
# Used by `publish`. Plain `make web` (no base override) is for `make
# serve`/local preview at the site root instead -- building WITH the
# subpath base would make `npm run preview` require visiting that same
# subpath locally too.
web-gh-pages:
	cd web && npm run build -- --base=/radar-riesgo-corrupcion-colombia/

# Serve the already-built web/dist/ locally (vite preview, default http://localhost:4173)
serve:
	cd web && npm run preview

# Publishes web/dist/ (built via web-gh-pages) to the gh-pages branch via a
# git worktree -- see scripts/publish_gh_pages.sh. GitHub Pages is
# configured to serve directly from that branch (Settings -> Pages ->
# Source: Deploy from a branch), so this is the entire deploy step; no CI
# involved.
publish:
	./scripts/publish_gh_pages.sh

# M1: pull all small datasets + DIVIPOLA + SECOP I slices + Monitor Ciudadano.
# Three fully independent pulls (disjoint datasets; pipeline.extract.socrata's
# manifest writes are lock-protected against the shared data/raw/manifest.json
# -- see _update_manifest_entry), run concurrently. Each backgrounded job's
# PID is tracked and waited on individually so a failure in any one of them
# fails the whole target (plain `wait` alone would only report the last PID).
pull:
	cd pipeline && uv run python -m pipeline.extract.pull --all-small & p1=$$!; \
	cd pipeline && uv run python -m pipeline.extract.pull --secop1-slices & p2=$$!; \
	cd pipeline && uv run python -m pipeline.extract.pull --monitor & p3=$$!; \
	status=0; \
	for pid in $$p1 $$p2 $$p3; do wait $$pid || status=1; done; \
	exit $$status

# M1: sample pull of S1 + S2 (2023 data, max 300k rows each)
pull-sample:
	cd pipeline && uv run python -m pipeline.extract.pull --sample

# M1: full pull of S1 (~5.6M rows) + S2 (~8.7M rows) + e1_rues_santarosa
# (~9.4M rows), resumable. Runs all three as concurrent processes --
# independent API pulls that only share data/raw/manifest.json, which is
# safe to write from all three at once (see `pull` above). This is fast
# specifically BECAUSE it requires SOCRATA_APP_TOKEN: tokenless requests are
# throttled per source IP as one shared pool (verified against
# dev.socrata.com/docs/app-tokens.html), so concurrent full pulls without a
# token would fight over that single small budget instead of actually going
# faster -- pipeline.extract.pull refuses to run in that configuration
# rather than silently degrading. Get a free token at
# https://www.datos.gov.co (account -> developer settings) and
# `gh secret set SOCRATA_APP_TOKEN` (CI) or add it to pipeline/.env (local).
pull-full:
	@echo "Full pull of S1 (~5.6M rows), S2 (~8.7M rows), and RUES (~9.4M rows), running concurrently."
	@echo "The pull is fully resumable: kill at any time and re-run to continue."
	cd pipeline && uv run python -m pipeline.extract.pull --full --dataset s1_secop2_contratos & p1=$$!; \
	cd pipeline && uv run python -m pipeline.extract.pull --full --dataset s2_secop2_procesos & p2=$$!; \
	cd pipeline && uv run python -m pipeline.extract.pull --full --dataset e1_rues_santarosa & p3=$$!; \
	status=0; \
	for pid in $$p1 $$p2 $$p3; do wait $$pid || status=1; done; \
	exit $$status

# Runs `pull` (small datasets, 3-way concurrent internally) and `pull-full`
# (S1+S2+RUES, 3-way concurrent internally) concurrently with EACH OTHER too
# -- all six pulls are independent datasets sharing one lock-protected
# manifest, so none of them needs to wait on any other. Used by `all
# MODE=full` and the weekly local routine (see README's runbook) -- intended
# for a real dev machine (originally scaled back from automated use on
# GitHub Actions' standard 4-core/16GB runners after a live run at this
# concurrency peak coincided with the runner reporting "lost communication
# with the server"; never conclusively root-caused since GH captured zero
# logs for it either way, but not worth re-risking on a resource-constrained
# CI runner when a personal machine with real headroom is now the primary
# execution environment instead).
pull-full-parallel:
	$(MAKE) pull & p1=$$!; \
	$(MAKE) pull-full & p2=$$!; \
	status=0; \
	for pid in $$p1 $$p2; do wait $$pid || status=1; done; \
	exit $$status

# M1: incremental refresh of the big datasets only, via each dataset's
# :updated_at watermark (see pipeline.extract.socrata.pull_refresh) -- pulls
# only what changed since the last full/refresh pull, not the whole dataset.
# Run concurrently for the same reason as `pull-full` above (independent
# pulls, lock-protected shared manifest) -- usually all three finish in
# seconds regardless since refreshes are small, but see the note below on
# why that isn't always true for s2.
#
# Observed live (2026-07-05): this is usually fast (s1_secop2_contratos
# found 0 changed rows over a 3-day window), but s2_secop2_procesos
# periodically bulk-republishes its ENTIRE table -- confirmed via the live
# API, min(:updated_at) == max(:updated_at) across all 8.77M rows at the
# same millisecond, i.e. Colombia Compra Eficiente's own republish
# mechanism touches every row, not 8.77M individual edits. On those weeks
# `--refresh` for s2 degrades to something close to a full pull (still
# correct, just not fast) -- unlike `pull-full`, this doesn't hard-require
# SOCRATA_APP_TOKEN since a degraded-to-full s2 refresh running tokenless
# alongside a normally-tiny s1 refresh is a rare, self-correcting slow week,
# not a routine parallel load.
pull-refresh:
	cd pipeline && uv run python -m pipeline.extract.pull --refresh --dataset s1_secop2_contratos & p1=$$!; \
	cd pipeline && uv run python -m pipeline.extract.pull --refresh --dataset s2_secop2_procesos & p2=$$!; \
	cd pipeline && uv run python -m pipeline.extract.pull --refresh --dataset e1_rues_santarosa & p3=$$!; \
	status=0; \
	for pid in $$p1 $$p2 $$p3; do wait $$pid || status=1; done; \
	exit $$status

marts:
	@echo "Building DuckDB marts (mode=$(MODE))"
	@if [ "$(MODE)" = "full" ]; then \
		cd pipeline && uv run python -m pipeline.clean.build --full; \
	else \
		cd pipeline && uv run python -m pipeline.clean.build --sample; \
	fi

# M2: regenerate docs/PROFILING.md, a one-time schema-exploration report
# (column types, null%, distinct examples) hardcoded to read data/raw/sample/
# -- by design, since column *structure* doesn't differ between sample and
# full pulls of the same dataset and profiling all 14M+ full-mode rows column
# by column (COUNT(DISTINCT ...) per column) would be slow for no benefit.
# NOT part of `marts`/`all`/`weekly` (requires `make pull-sample` to have run
# at least once; unlike DQ_REPORT.md, which build.py itself regenerates on
# every run and correctly reflects whichever mode was actually built).
profile:
	cd pipeline && uv run python -m pipeline.clean.profile

# M4: populate dim_proveedor.fecha_matricula from RUES chamber data, then report coverage
rues-coverage:
	cd pipeline && uv run python -m pipeline.clean.enrich_rues
	cd pipeline && uv run python -m pipeline.clean.rues_coverage

flags:
	cd pipeline && uv run python -m pipeline.flags.run_all

score:
	cd pipeline && uv run python -m pipeline.score.scorer
	cd pipeline && uv run python -m pipeline.score.backtest

# M6: build web/public/data/ artifacts from corruption.duckdb (schema-validated)
export:
	cd pipeline && uv run python -m pipeline.export.build_artifacts

# M6: regenerate the small synthetic dataset at web/src/fixtures/ (committed to
# git) so the M7 dashboard can be built/tested without running the real pipeline
export-fixtures:
	cd pipeline && uv run python -m pipeline.export.build_fixtures

# Full pipeline, fresh-clone-safe. Default (no MODE) pulls only the 2023
# sample of S1/S2 and builds marts from it -- completes in minutes, the
# CI-friendly smoke path from PLAN.md's Verification section. `make all
# MODE=full` pulls the complete multi-year S1/S2/RUES history instead (with
# SOCRATA_APP_TOKEN set, via pull-full-parallel -- see that target) and
# builds marts from that -- the real production run.
all:
	@if [ "$(MODE)" = "full" ]; then \
		$(MAKE) pull-full-parallel; \
	else \
		$(MAKE) pull; \
		$(MAKE) pull-sample; \
	fi
	$(MAKE) marts MODE=$(MODE)
	$(MAKE) rues-coverage
	$(MAKE) flags
	$(MAKE) score
	$(MAKE) export
	$(MAKE) web

# Same as `all`, then serves the result locally. `make all-serve MODE=full`
# for the real production data; plain `make all-serve` for the fast sample.
all-serve:
	$(MAKE) all MODE=$(MODE)
	$(MAKE) serve

# The recurring-refresh path, run weekly on this machine via a launchd
# LaunchAgent (see README's runbook and scripts/) rather than a hosted CI
# runner: small datasets pull in full (cheap, 3-way concurrent) while the
# big three refresh incrementally instead of re-pulling from scratch
# (3-way concurrent), running alongside the small pulls too -- see
# PLAN.md's Verification notes on `pull-refresh` for why the incremental
# path is safe (refresh parts never replace originals; the mart-build glob
# and :id dedup already pick them up). Ends by building the GitHub-Pages
# flavored site and pushing it straight to the gh-pages branch -- no CI
# involved anywhere in this target.
weekly:
	$(MAKE) pull & p1=$$!; \
	$(MAKE) pull-refresh & p2=$$!; \
	status=0; \
	for pid in $$p1 $$p2; do wait $$pid || status=1; done; \
	exit $$status
	$(MAKE) marts MODE=full
	$(MAKE) rues-coverage
	$(MAKE) flags
	$(MAKE) score
	$(MAKE) export
	$(MAKE) web-gh-pages
	$(MAKE) publish
