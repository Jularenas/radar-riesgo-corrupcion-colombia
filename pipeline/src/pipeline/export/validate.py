"""
JSON-schema validation for M6 web artifacts.

Schemas live in `pipeline/src/pipeline/export/schemas/*.schema.json`, one per
artifact shape (see PLAN.md "Web artifact contract"). Both `build_artifacts.py`
(real mart) and `build_fixtures.py` (synthetic mart) validate every file they
write against the same schemas -- that's the whole point of the fixture
generator reusing the real builder functions (see build_fixtures.py's module
docstring): a fixture that "looks right" but silently drifts from the real
shape would defeat the purpose of M7 developing against it.

Usage:
    from pipeline.export.validate import validate_artifact
    validate_artifact("meta", data)                 # raises SchemaValidationError on failure
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

SCHEMAS_DIR = Path(__file__).with_name("schemas")

# artifact name -> schema filename (see SCHEMAS_DIR)
SCHEMA_FILES: dict[str, str] = {
    "meta": "meta.schema.json",
    "resumen_nacional": "resumen_nacional.schema.json",
    "departamento": "departamento.schema.json",
    "casos_prioritarios_chunk": "casos_prioritarios_chunk.schema.json",
    "entidades_top": "entidades_top.schema.json",
    "proveedores_top": "proveedores_top.schema.json",
}


class SchemaValidationError(Exception):
    """Raised when an artifact fails to validate against its JSON Schema. Carries the full jsonschema message."""


@lru_cache(maxsize=None)
def _load_schema(name: str) -> dict:
    if name not in SCHEMA_FILES:
        raise KeyError(f"unknown artifact schema {name!r} -- expected one of {sorted(SCHEMA_FILES)}")
    path = SCHEMAS_DIR / SCHEMA_FILES[name]
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_artifact(name: str, data: Any, *, source: str | None = None) -> None:
    """
    Validate `data` against the named schema (a key of `SCHEMA_FILES`).
    Raises `SchemaValidationError` with a clear, actionable message (the
    failing JSON path + reason) if it doesn't conform -- fails loudly per the
    M6 brief, never silently truncates or coerces. `source` (e.g. a file
    path) is included in the error message for context when validating many
    files in a loop (departamentos/*.json, casos_prioritarios/*.json).
    """
    schema = _load_schema(name)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        where = f" ({source})" if source else ""
        lines = [f"Artifact '{name}'{where} failed schema validation ({len(errors)} error(s)):"]
        for e in errors[:20]:
            loc = "/".join(str(p) for p in e.path) or "<root>"
            lines.append(f"  - at '{loc}': {e.message}")
        if len(errors) > 20:
            lines.append(f"  ... and {len(errors) - 20} more")
        raise SchemaValidationError("\n".join(lines))


def validate_many(name: str, items: list[tuple[Any, str]]) -> None:
    """Validate a list of (data, source_label) pairs against the same schema, collecting ALL failures before raising."""
    schema = _load_schema(name)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    failures: list[str] = []
    for data, source in items:
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if errors:
            for e in errors[:5]:
                loc = "/".join(str(p) for p in e.path) or "<root>"
                failures.append(f"  - {source} at '{loc}': {e.message}")
            if len(errors) > 5:
                failures.append(f"  - {source}: ... and {len(errors) - 5} more")
    if failures:
        header = f"Artifact '{name}' failed schema validation for {len(failures)} location(s) across {len(items)} file(s):"
        raise SchemaValidationError("\n".join([header, *failures]))
