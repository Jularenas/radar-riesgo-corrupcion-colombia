"""
Shared constants for red-flag detection (M3).

Single source of truth for thresholds so they are not scattered as magic
numbers across the 14 flag modules. Weights and Spanish names come from the
"Red-flag catalog (v1)" table in PLAN.md, and are canonically defined in
`score/weights.yaml` (M5) -- see that file's module docstring
(`pipeline.score.weights`) for why weights live there instead of here.
"""

from __future__ import annotations

from pipeline.score.weights import FLAG_WEIGHTS as _FLAG_WEIGHTS

# ---------------------------------------------------------------------------
# Flag registry: id -> (nombre ES, nivel, peso)
# ---------------------------------------------------------------------------
# nivel: "contract" -> written to flag_contrato (key = id_contrato)
#        "entity"   -> written to flag_entidad  (key = nit_entidad_norm)
#
# Derived from score/weights.yaml (single source of truth) rather than
# hardcoded here a second time -- do NOT edit a "peso" in this dict; edit
# weights.yaml instead, both this module and the scorer read it from there.
FLAG_META: dict[str, dict] = {
    fid: {"nombre": meta["nombre"], "nivel": meta["nivel"], "peso": meta["peso"]}
    for fid, meta in _FLAG_WEIGHTS.items()
}

CONTRACT_FLAG_IDS = [fid for fid, m in FLAG_META.items() if m["nivel"] == "contract"]
ENTITY_FLAG_IDS = [fid for fid, m in FLAG_META.items() if m["nivel"] == "entity"]

# ---------------------------------------------------------------------------
# F01 — Único oferente
# ---------------------------------------------------------------------------
F01_MIN_OFERENTES_UNICOS = 1  # fires when num_oferentes_unicos == this value

# ---------------------------------------------------------------------------
# F02 — Empresa exprés
# ---------------------------------------------------------------------------
F02_EXPRESS_DAYS = 90  # supplier registered (RUES fecha_matricula) within N days
#                        before process publication

# ---------------------------------------------------------------------------
# F03 — Adiciones excesivas
# ---------------------------------------------------------------------------
F03_TIME_ADDITION_RATIO = 0.5   # dias_adicionados >= ratio * duracion_dias_inicial
F03_MONEY_ADDITION_RATIO = 0.4  # money added >= ratio * base value

# ---------------------------------------------------------------------------
# F04 — Abuso de contratación directa
# ---------------------------------------------------------------------------
F04_Z_SCORE_THRESHOLD = 2.0
# Adaptation (real-data): z-scores computed on peer groups smaller than this,
# or for entities with fewer than this many total contracts, are noisy/
# degenerate (e.g. a 1-contract entity trivially has a 0%/100% direct share).
# Both the evaluated entity and its peer group are required to clear this
# floor. Not in PLAN.md; documented deviation.
F04_MIN_CONTRATOS_ENTIDAD = 5
F04_MIN_PEER_GROUP_SIZE = 5

# ---------------------------------------------------------------------------
# F05 — Fraccionamiento
# ---------------------------------------------------------------------------
F05_MIN_CONTRATOS = 3
F05_WINDOW_DAYS = 90
F05_SMMLV_MULTIPLE = 280

# ---------------------------------------------------------------------------
# F06 — Carrusel
# ---------------------------------------------------------------------------
F06_WINDOW_DAYS = 730  # ~24 months, used as a centered bucket width (see module docstring)
F06_MIN_PROCESOS = 8
F06_MIN_WINNERS = 2
F06_MAX_WINNERS = 4
F06_MIN_WINNER_SHARE = 0.15
F06_MIN_ALTERNATION_INDEX = 0.6

# ---------------------------------------------------------------------------
# F07 — Ventana de licitación corta
# ---------------------------------------------------------------------------
# Days(publicación -> fecha de recepción de ofertas) floor, per modality.
# Only modalities with a defined floor in PLAN.md are in scope; other
# competitive modalities (e.g. concurso de méritos) are not applicable.
F07_FLOOR_DAYS = {
    "LICITACION_PUBLICA": 10,
    "SELECCION_ABREVIADA": 5,
}

# ---------------------------------------------------------------------------
# F08 — Precio calcado
# ---------------------------------------------------------------------------
F08_TOLERANCE = 0.005  # +-0.5% of precio_base

# ---------------------------------------------------------------------------
# F09 — Afán de diciembre
# ---------------------------------------------------------------------------
F09_MONTH = 12
F09_START_DAY = 15  # fires for fecha_firma in [Dec 15, Dec 31]

# ---------------------------------------------------------------------------
# F10 — Ventana electoral
# ---------------------------------------------------------------------------
# Uses ref_ventanas (inicio/fin) loaded from refs/ventanas_electorales.csv.
# Only direct-contracting modality is in scope per PLAN.md.
F10_MODALIDAD = "CONTRATACION_DIRECTA"

# ---------------------------------------------------------------------------
# F11 — Proveedor sancionado
# ---------------------------------------------------------------------------
# No numeric threshold: join sanciones on doc_norm, keep only
# fecha_sancion < fecha_firma for the scoring-relevant "fired" value.

# ---------------------------------------------------------------------------
# F12 — Concentración/dependencia
# ---------------------------------------------------------------------------
F12_ENTITY_SHARE_THRESHOLD = 0.5     # supplier > 50% of entity's annual value
F12_MIN_CONTRATOS_ENTIDAD = 5        # "(>= 5 contratos)" per PLAN.md
F12_SUPPLIER_DEPENDENCE_THRESHOLD = 0.8  # supplier > 80% of its annual revenue from entity
# Adaptation (real-data): PLAN.md doesn't give a minimum contract count for
# the supplier-dependence leg. Applied naively, it fires for ~95% of
# suppliers because most suppliers in a single-year sample only ever work
# with one entity (trivially 100% "dependent"). Reuse the same >=5 floor so
# the flag reflects an established, evaluable relationship rather than a
# one-off coincidence. Documented deviation.
F12_MIN_CONTRATOS_PROVEEDOR = 5

# ---------------------------------------------------------------------------
# F13 — Objeto vago
# ---------------------------------------------------------------------------
F13_MIN_LENGTH = 40
# "Top-decile boilerplate similarity" is operationalized as: normalize the
# contract object text (trim/upper/collapse whitespace), count how many
# contracts in the mart share the exact same normalized text, and flag rows
# whose repetition count falls in the top decile (P90) of that distribution
# computed across all contracts. This is a concrete, cheap-to-compute proxy
# for "boilerplate" that avoids needing fuzzy text similarity in SQL.
F13_BOILERPLATE_PERCENTILE = 0.9

# ---------------------------------------------------------------------------
# F14 — Valor redondo
# ---------------------------------------------------------------------------
F14_MIN_VALUE = 1_000_000_000  # >= 1,000M COP
F14_ROUND_UNIT = 100_000_000   # multiple of 100M COP
