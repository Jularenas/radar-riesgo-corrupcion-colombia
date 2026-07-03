"""Smoke tests for pipeline.config."""

import re

from pipeline.config import DATASETS

SOCRATA_4X4 = re.compile(r"^[a-z0-9]{4}-[a-z0-9]{4}$")


def test_datasets_count() -> None:
    assert len(DATASETS) >= 10, f"Expected ≥10 datasets, got {len(DATASETS)}"


def test_dataset_ids_format() -> None:
    bad = {name: did for name, did in DATASETS.items() if not SOCRATA_4X4.match(did)}
    assert not bad, f"Dataset IDs with invalid Socrata 4x4 format: {bad}"
