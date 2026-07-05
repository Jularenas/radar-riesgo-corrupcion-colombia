# Radar de Riesgo de Corrupcion -- Colombia
# Compatible with GNU Make 3.81 (POSIX, no GNU-4-only features)

.PHONY: check web pull pull-sample pull-full marts rues-coverage flags score export all

check:
	cd pipeline && uv run ruff check . && uv run pytest -q

web:
	cd web && npm run build

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

export:
	@echo "TODO (M6)"

all: pull marts rues-coverage flags score export web
