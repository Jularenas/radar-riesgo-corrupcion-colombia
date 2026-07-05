# Radar de Riesgo de Corrupcion -- Colombia
# Compatible with GNU Make 3.81 (POSIX, no GNU-4-only features)

.PHONY: check web serve pull pull-sample pull-full pull-refresh marts rues-coverage flags score export export-fixtures all all-serve weekly

check:
	cd pipeline && uv run ruff check . && uv run pytest -q

web:
	cd web && npm run build

# Serve the already-built web/dist/ locally (vite preview, default http://localhost:4173)
serve:
	cd web && npm run preview

# M1: pull all small datasets + DIVIPOLA + SECOP I slices + Monitor Ciudadano
pull:
	cd pipeline && uv run python -m pipeline.extract.pull --all-small
	cd pipeline && uv run python -m pipeline.extract.pull --secop1-slices
	cd pipeline && uv run python -m pipeline.extract.pull --monitor

# M1: sample pull of S1 + S2 (2023 data, max 300k rows each)
pull-sample:
	cd pipeline && uv run python -m pipeline.extract.pull --sample

# M1: full pull of S1 + S2 (hours — resumable, re-run to continue)
pull-full:
	@echo "WARNING: Full pull of S1 (~5.6M rows) and S2 (~8.7M rows) takes several hours."
	@echo "The pull is fully resumable: kill at any time and re-run to continue."
	cd pipeline && uv run python -m pipeline.extract.pull --full

# M1: incremental refresh of the big datasets only, via each dataset's
# :updated_at watermark (see pipeline.extract.socrata.pull_refresh) -- pulls
# only what changed since the last full/refresh pull, not the whole dataset.
# Sequential: shares one tokenless-by-default Socrata rate-limit budget.
#
# Observed live (2026-07-05): this is usually fast (s1_secop2_contratos
# found 0 changed rows over a 3-day window), but s2_secop2_procesos
# periodically bulk-republishes its ENTIRE table -- confirmed via the live
# API, min(:updated_at) == max(:updated_at) across all 8.77M rows at the
# same millisecond, i.e. Colombia Compra Eficiente's own republish
# mechanism touches every row, not 8.77M individual edits. On those weeks
# `--refresh` for s2 degrades to something close to a full pull (still
# correct, still bounded by the 6-hour GH Actions job cap, just not fast).
# This is a real characteristic of that upstream dataset, not a bug here.
pull-refresh:
	cd pipeline && uv run python -m pipeline.extract.pull --refresh --dataset s1_secop2_contratos
	cd pipeline && uv run python -m pipeline.extract.pull --refresh --dataset s2_secop2_procesos
	cd pipeline && uv run python -m pipeline.extract.pull --refresh --dataset e1_rues_santarosa

marts:
	@echo "Building DuckDB marts (mode=$(MODE))"
	@if [ "$(MODE)" = "full" ]; then \
		cd pipeline && uv run python -m pipeline.clean.build --full; \
	else \
		cd pipeline && uv run python -m pipeline.clean.build --sample; \
	fi
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
# MODE=full` pulls the complete multi-year S1/S2 history instead (hours,
# resumable) and builds marts from that -- the real production run.
all:
	$(MAKE) pull
	@if [ "$(MODE)" = "full" ]; then \
		$(MAKE) pull-full; \
	else \
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

# The recurring-refresh path (used by the weekly GitHub Actions cron): small
# datasets pull in full (cheap), the big three refresh incrementally instead
# of re-pulling from scratch, then marts/flags/score/export/web rebuild from
# whatever is now on disk. Minutes, not hours -- see PLAN.md's Verification
# notes on `pull-refresh` for why this is safe (refresh parts never replace
# originals; the mart-build glob and :id dedup already pick them up).
weekly:
	$(MAKE) pull
	$(MAKE) pull-refresh
	$(MAKE) marts MODE=full
	$(MAKE) rues-coverage
	$(MAKE) flags
	$(MAKE) score
	$(MAKE) export
	$(MAKE) web
