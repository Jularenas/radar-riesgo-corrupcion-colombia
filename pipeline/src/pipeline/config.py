"""
Constants and dataset registry for the corruption-risk pipeline.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Socrata / datos.gov.co
# ---------------------------------------------------------------------------

SOCRATA_DOMAIN = "www.datos.gov.co"

# Logical name → Socrata 4x4 dataset ID
DATASETS: dict[str, str] = {
    # SECOP II
    "s1_secop2_contratos": "jbjy-vk9h",
    "s2_secop2_procesos": "p6dx-8zbt",
    # SECOP I
    "s3_secop1_procesos": "f789-7hwg",
    "s4_secop1_contratos": "79ga-5jck",
    "s4b_secop_integrado": "rpmr-utcd",
    "s5_secop1_proponentes": "tauh-5jvn",
    # Labels / sanctions
    "l1_responsabilidad_fiscal": "jr8e-e8tu",
    "l2_multas_secop1": "4n4q-k399",
    "l3_multas_secop2": "it5q-hg94",
    "l4_siri": "iaeu-rcn6",
    # Entity registries (RUES)
    "e1_rues_santarosa": "c82u-588k",
    "e1_rues_ibague": "gwqv-sqvs",
    # Geography (discovered in M1 via Socrata catalog — ID confirmed live)
    "e2_divipola": "gdxc-w37w",
}

# ---------------------------------------------------------------------------
# Data directories (resolved relative to the pipeline/ project root)
# ---------------------------------------------------------------------------

_PIPELINE_ROOT = Path(__file__).resolve().parents[2]  # src/pipeline/config.py → pipeline/

DATA_DIR = _PIPELINE_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
STAGING_DIR = DATA_DIR / "staging"
MARTS_DIR = DATA_DIR / "marts"
EXPORT_DIR = DATA_DIR / "export"
