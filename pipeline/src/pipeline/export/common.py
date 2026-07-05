"""
Shared helpers for the M6 web-artifact export (`build_artifacts.py` /
`build_fixtures.py`). Both modules import from here so the fixture generator
and the real builder can never disagree about geo-code padding, JSON
serialization, or flag descriptions.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any

from pipeline.config import REPO_ROOT

# ---------------------------------------------------------------------------
# DIVIPOLA geo-code padding
# ---------------------------------------------------------------------------
# The mart (pipeline.clean.build) stores cod_dpto/cod_mpio as VARCHAR without
# left-zero-padding (e.g. Antioquia is '5'/'5001', not the canonical DIVIPOLA
# '05'/'05001') -- verified live via DESCRIBE + sample queries against
# corruption.duckdb. PLAN.md's web artifact contract explicitly asks for
# "zero-padded 2-digit code matching DIVIPOLA" for department filenames; this
# module applies that padding uniformly (departments to 2 digits, municipios
# to 5 = 2-digit dept prefix + 3-digit municipio suffix) everywhere a geo code
# is written into an artifact -- not just filenames -- so the frontend never
# has to guess whether a given code is already padded.


def pad_dpto(cod_dpto: str | None) -> str | None:
    """Zero-pad a DIVIPOLA department code to 2 digits ('5' -> '05'). `None` passes through."""
    if cod_dpto is None:
        return None
    return str(cod_dpto).strip().zfill(2)


def pad_mpio(cod_mpio: str | None) -> str | None:
    """Zero-pad a DIVIPOLA municipality code to 5 digits ('5001' -> '05001'). `None` passes through."""
    if cod_mpio is None:
        return None
    return str(cod_mpio).strip().zfill(5)


# ---------------------------------------------------------------------------
# Build metadata
# ---------------------------------------------------------------------------

def git_short_hash(repo_root: Path = REPO_ROOT) -> str | None:
    """
    Best-effort short git commit hash for `meta.json`'s version block.
    Never raises: returns `None` if git is unavailable, the directory isn't a
    repo, or the command fails for any other reason (e.g. a source tarball
    with no `.git/` -- "best effort" per the M6 brief).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a 'Z' suffix, e.g. '2026-07-04T22:31:00Z'."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def json_default(obj: Any) -> Any:
    """`json.dumps(..., default=json_default)` hook for date/datetime objects."""
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def write_json(path: Path, data: Any, *, indent: int | None = None) -> int:
    """
    Write `data` as JSON to `path` (UTF-8, parent dirs created as needed).
    Returns the size written in bytes (used for the size-budget check).
    `indent=None` (the default) produces compact output -- used for
    production artifacts, where every byte counts against the 60MB/5MB
    budget; `build_fixtures.py` passes `indent=2` since fixtures are small,
    committed to git, and benefit from being human-readable/diffable.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, default=json_default, indent=indent)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def load_banderas(evidence_json: str | None) -> list[dict]:
    """
    Parse a `flags_disparados` JSON string (as stored in `contrato_score` /
    `entidad_score`, e.g. `pipeline.score.scorer._fetch_fired_evidence`'s
    output) into a list of `{flag_id, nombre, peso, evidence}` dicts. Empty
    string / `None` -> `[]` (never raises on missing data).
    """
    if not evidence_json:
        return []
    return json.loads(evidence_json)


def chunk_list(items: list, chunk_size: int) -> list[list]:
    """Split `items` into consecutive chunks of at most `chunk_size` items each (last chunk may be shorter)."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


# ---------------------------------------------------------------------------
# Flag catalog: user-facing Spanish descriptions (meta.json)
# ---------------------------------------------------------------------------
# Names/levels/weights come from score/weights.yaml (single source of truth,
# loaded via pipeline.score.weights.FLAG_WEIGHTS) -- NOT re-hardcoded here.
# These descriptions are the one piece of flag metadata that genuinely has no
# other home: PLAN.md's "Red-flag catalog" table gives the precise, testable
# definition (the one M3's code implements); these are a plain-language
# translation of that same definition for a non-technical dashboard visitor,
# informed also by the observed-behavior "Racional" column in
# docs/METHODOLOGY.md section 2. Keep in sync with both if a flag's logic
# changes.
FLAG_DESCRIPTIONS: dict[str, str] = {
    "F01": (
        "En procesos de modalidad competitiva (licitación pública, selección abreviada o concurso de "
        "méritos) -- abiertos en principio a cualquier proponente -- se presentó o fue habilitado un "
        "único oferente. La competencia fue solo nominal."
    ),
    "F02": (
        "El proveedor ganador se registró en el registro mercantil (RUES) menos de 90 días antes de la "
        "publicación del proceso: un patrón típico de 'empresa de papel' creada para ganar un contrato "
        "puntual."
    ),
    "F03": (
        "Después de adjudicado, el contrato fue modificado con adiciones de valor (40% o más del valor "
        "inicial) o de plazo (días adicionados igual o mayor al 50% de la duración inicial) -- la forma "
        "más documentada de inflar un contrato ya otorgado, sin nueva competencia."
    ),
    "F04": (
        "La entidad contrata de forma directa (sin proceso competitivo) muchísimo más que entidades "
        "comparables de su mismo departamento y nivel (2 o más desviaciones estándar por encima del "
        "grupo de pares)."
    ),
    "F05": (
        "La misma entidad firmó 3 o más contratos directos con el mismo proveedor, en la misma categoría "
        "de bienes/servicios, dentro de una ventana de 90 días, sumando más de 280 salarios mínimos -- un "
        "patrón para evadir el umbral que obligaría a licitar."
    ),
    "F06": (
        "Dentro de una misma entidad (o municipio y categoría), un grupo pequeño de 2 a 4 proveedores se "
        "reparte y alterna sistemáticamente la mayoría de los contratos competitivos en una ventana de 24 "
        "meses -- un patrón de reparto acordado del mercado."
    ),
    "F07": (
        "El tiempo entre la publicación del proceso y el cierre para recibir ofertas fue menor al mínimo "
        "reglamentario según la modalidad (10 días hábiles en licitación pública, 5 en selección "
        "abreviada) -- limita quién alcanza a enterarse y presentar oferta."
    ),
    "F08": (
        "El valor adjudicado quedó dentro de un margen de ±0,5% frente al precio base publicado por la "
        "entidad -- indicio de que el proponente ganador conocía de antemano el presupuesto oficial."
    ),
    "F09": (
        "El contrato se firmó entre el 15 y el 31 de diciembre, en el cierre de la vigencia fiscal, una "
        "ventana con menor escrutinio público y mediático."
    ),
    "F10": (
        "Contrato adjudicado de forma directa dentro de los períodos restringidos por la Ley de Garantías "
        "Electorales, cuando la contratación pública está sujeta a mayores límites precisamente para "
        "evitar su uso político."
    ),
    "F11": (
        "El proveedor tiene una sanción registrada (responsabilidad fiscal de la Contraloría, multas "
        "contractuales en SECOP, o antecedentes disciplinarios de la Procuraduría) con fecha anterior a "
        "la firma de este contrato -- la única bandera basada en un historial confirmado, no solo en un "
        "patrón estadístico; por eso tiene el mayor peso del catálogo."
    ),
    "F12": (
        "Un mismo proveedor concentra más del 50% del valor que la entidad contrató ese año, o ese "
        "proveedor depende de esa única entidad para más del 80% de sus ingresos por contratación pública "
        "-- señal de una relación cerrada entre las dos partes."
    ),
    "F13": (
        "El objeto del contrato tiene menos de 40 caracteres, o es un texto genérico que se repite en un "
        "número inusualmente alto de contratos -- dificulta saber, a partir del documento público, qué se "
        "contrató realmente."
    ),
    "F14": (
        "El valor del contrato es de al menos 1.000 millones de pesos y, además, es un múltiplo exacto de "
        "100 millones -- un indicio débil (por eso el peso mínimo del catálogo) de que la cifra no vino de "
        "un presupuesto detallado sino de una aproximación."
    ),
}
