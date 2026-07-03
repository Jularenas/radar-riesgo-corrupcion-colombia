# Radar de Riesgo de Corrupcion -- Colombia
# Compatible with GNU Make 3.81 (POSIX, no GNU-4-only features)

.PHONY: check web pull marts flags score export all

check:
	cd pipeline && uv run ruff check . && uv run pytest -q

web:
	cd web && npm run build

pull:
	@echo "TODO (M1)"

marts:
	@echo "TODO (M2)"

flags:
	@echo "TODO (M3)"

score:
	@echo "TODO (M5)"

export:
	@echo "TODO (M6)"

all: pull marts flags score export web
