from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.splits import (
    SplitManifest,
    SplitName,
    audit_dataset_index_document,
    freeze_dataset_index,
    freeze_split_manifest,
    load_split_manifest,
    partition_dataset_records,
    write_frozen_dataset_index,
    write_frozen_split_manifest,
)

MANIFEST_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
SPECIFICATION_PATH = Path("configs/splits/mock-v1.json")
DATASET_INDEX_PATH = Path("tests/fixtures/splits/dataset-index-v1.json")


def test_checked_manifest_freezes_disjoint_seed_partitions() -> None:
    manifest = load_split_manifest(MANIFEST_PATH)

    assert manifest.manifest_id == (
        "sha256:7010c687c42c5ecc47239da7ccd13ebd40d7af9be012b6774be63bb0a160dfe1"
    )
    assert tuple(len(manifest.seeds(split)) for split in SplitName) == (800, 100, 100)
    all_seeds = tuple(seed for split in SplitName for seed in manifest.seeds(split))
    assert len(all_seeds) == len(set(all_seeds)) == 1000
    assert set(all_seeds) == set(range(1000))
    assert manifest.split_for_seed(0) is SplitName.TRAIN
    assert manifest.split_for_seed(20) is SplitName.VALIDATION
    assert manifest.split_for_seed(1) is SplitName.TEST


def test_specification_reproduces_checked_manifest_and_cannot_replace_it(tmp_path: Path) -> None:
    specification = json.loads(SPECIFICATION_PATH.read_text(encoding="utf-8"))
    generated = freeze_split_manifest(specification)
    checked = load_split_manifest(MANIFEST_PATH)
    assert generated == checked

    output = tmp_path / "split.json"
    write_frozen_split_manifest(generated, output)
    write_frozen_split_manifest(generated, output)
    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_frozen_split_manifest(generated, output)


def test_manifest_rejects_a_reassigned_seed_even_with_complete_coverage() -> None:
    document = _load(MANIFEST_PATH)
    partitions = _mapping(document["partitions"])
    train = _list(partitions["train"])
    validation = _list(partitions["validation"])
    train[0], validation[0] = validation[0], train[0]

    with pytest.raises(ValueError, match="declared algorithm and salt"):
        SplitManifest.from_mapping(document)


def test_dataset_index_keeps_every_record_and_encounter_with_its_complete_run() -> None:
    manifest = load_split_manifest(MANIFEST_PATH)
    document = _load(DATASET_INDEX_PATH)
    audit = audit_dataset_index_document(document, manifest)

    assert audit.valid, audit.errors
    assert audit.dataset_index_id == (
        "sha256:a12a8526b0b23746b648b3d782f75c65ff56eefa0c82186ac73cfddb88dffd77"
    )
    assert audit.partition_runs == {"train": 1, "validation": 1, "test": 1}
    assert audit.partition_records == {"train": 2, "validation": 2, "test": 2}
    grouped = partition_dataset_records(document, manifest)
    for split, records in grouped.items():
        assert len(records) == 2
        run_ids = {record["run_id"] for record in records}
        assert len(run_ids) == 1, f"{split} contains a divided run"
        assert [record["decision_index"] for record in records] == [0, 1]


def test_dataset_index_is_reproducible_and_immutable(tmp_path: Path) -> None:
    manifest = load_split_manifest(MANIFEST_PATH)
    checked = _load(DATASET_INDEX_PATH)
    generated = freeze_dataset_index(checked, manifest)
    assert generated == checked

    output = tmp_path / "index.json"
    write_frozen_dataset_index(generated, output)
    write_frozen_dataset_index(generated, output)
    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_frozen_dataset_index(generated, output)


def test_dataset_index_rejects_a_run_declared_in_the_wrong_partition() -> None:
    manifest = load_split_manifest(MANIFEST_PATH)
    document = _load(DATASET_INDEX_PATH)
    first_run = _mapping(_list(document["runs"])[0])
    first_run["split"] = "test"

    audit = audit_dataset_index_document(document, manifest)
    assert not audit.valid
    assert any("seed 0 is frozen to train" in error for error in audit.errors)
    with pytest.raises(ValueError, match="Dataset split audit failed"):
        partition_dataset_records(document, manifest)


def test_dataset_index_rejects_record_level_split_and_incomplete_runs() -> None:
    manifest = load_split_manifest(MANIFEST_PATH)
    document = _load(DATASET_INDEX_PATH)
    first_record = _mapping(_list(document["records"])[0])
    first_record["split"] = "test"
    first_run = _mapping(_list(document["runs"])[0])
    first_run["terminal"] = False

    audit = audit_dataset_index_document(document, manifest)
    assert not audit.valid
    assert any("unexpected=['split']" in error for error in audit.errors)
    assert any("not a complete terminal trajectory" in error for error in audit.errors)


def test_dataset_index_rejects_missing_adjacent_state() -> None:
    manifest = load_split_manifest(MANIFEST_PATH)
    document = copy.deepcopy(_load(DATASET_INDEX_PATH))
    records = _list(document["records"])
    first_record = _mapping(records[0])
    first_record["decision_index"] = 2

    audit = audit_dataset_index_document(document, manifest)
    assert not audit.valid
    assert any("decision indices are not contiguous from zero" in error for error in audit.errors)


def test_seed_outside_the_frozen_universe_is_rejected() -> None:
    manifest = load_split_manifest(MANIFEST_PATH)
    with pytest.raises(ValueError, match="outside split manifest"):
        manifest.split_for_seed(1000)


def _load(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _mapping(value: object) -> dict[str, Any]:
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _list(value: object) -> list[Any]:
    assert isinstance(value, list)
    return value
