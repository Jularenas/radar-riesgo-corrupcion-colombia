"""
Canonical weights + tier-threshold loader (M5).

`weights.yaml` (next to this module) is the single source of truth for:
  - each flag's weight ("peso") -- `pipeline.flags.params.FLAG_META` derives
    its "peso" from `FLAG_WEIGHTS` here instead of hardcoding it a second
    time, so flag-firing modules (M3) and the scorer (M5) never disagree.
  - the four score tiers (Bajo/Medio/Alto/Crítico) and their boundaries.
  - the empirical-Bayes shrinkage constant `k` (and the "datos_insuficientes"
    contract-count cutoff) used by entity/municipio aggregation in scorer.py.

Nothing else in the codebase should hardcode a weight or a tier boundary.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import yaml

_WEIGHTS_PATH = Path(__file__).with_name("weights.yaml")


class Tier(NamedTuple):
    id: str
    nombre: str
    min_score: float
    max_score: float | None  # None = open-ended (score >= min_score)


def _load_raw(path: Path = _WEIGHTS_PATH) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


_RAW = _load_raw()

# flag_id -> {"nombre": str, "nivel": "contract"|"entity", "peso": int|float}
FLAG_WEIGHTS: dict[str, dict] = _RAW["flags"]

TIERS: list[Tier] = [Tier(**t) for t in _RAW["tiers"]]

SHRINKAGE_K: float = float(_RAW["shrinkage"]["k"])
MIN_CONTRATOS_RANK: int = int(_RAW["shrinkage"]["min_contratos_rank"])


def tier_for(score: float | None) -> str | None:
    """
    Tier id ('bajo'/'medio'/'alto'/'critico') for a 0-100 score.

    Boundaries are inclusive on the lower bound, exclusive on the upper
    bound (PLAN.md: "Bajo <20, Medio 20-40, Alto 40-60, Critico >=60"), so a
    score of exactly 20 is Medio, exactly 40 is Alto, exactly 60 is Critico.
    `None` in, `None` out (used for contracts/entities with zero applicable
    flags, i.e. no score at all).
    """
    if score is None:
        return None
    for t in TIERS:
        if score >= t.min_score and (t.max_score is None or score < t.max_score):
            return t.id
    raise ValueError(f"score {score!r} does not fall into any configured tier -- check weights.yaml `tiers:`")


def tier_nombre(tier_id: str | None) -> str | None:
    """Spanish display name for a tier id, e.g. 'critico' -> 'Crítico'."""
    if tier_id is None:
        return None
    for t in TIERS:
        if t.id == tier_id:
            return t.nombre
    raise ValueError(f"unknown tier id {tier_id!r}")


def total_weight(nivel: str | None = None) -> float:
    """Sum of all catalog weights, optionally restricted to one nivel ('contract'/'entity')."""
    return sum(m["peso"] for m in FLAG_WEIGHTS.values() if nivel is None or m["nivel"] == nivel)


def tier_case_sql(score_expr: str) -> str:
    """
    A SQL CASE expression computing the same tiers as `tier_for`, generated
    from the same `TIERS` list (so SQL-side and Python-side tiering can
    never drift apart even though scorer.py uses both -- see its module
    docstring for why municipio/entidad aggregation is done in SQL while
    contract-level tiering is done row-by-row in Python).
    """
    branches = []
    for t in TIERS:
        cond = f"{score_expr} >= {t.min_score}"
        if t.max_score is not None:
            cond += f" AND {score_expr} < {t.max_score}"
        branches.append(f"WHEN {cond} THEN '{t.id}'")
    return "CASE " + " ".join(branches) + " ELSE NULL END"
