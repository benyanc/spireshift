from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier

SPLIT_MANIFEST_SCHEMA_VERSION = "split-manifest-v1"
DATASET_INDEX_SCHEMA_VERSION = "dataset-index-v1"
DATASET_SPLIT_AUDIT_SCHEMA_VERSION = "dataset-split-audit-v1"
SPLIT_ASSIGNMENT_ALGORITHM = "sha256-ranked-v1"


class SplitName(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


SPLIT_NAMES = tuple(SplitName)


@dataclass(frozen=True, slots=True)
class SeedUniverse:
    start: int
    stop_exclusive: int

    @property
    def size(self) -> int:
        return self.stop_exclusive - self.start

    def as_dict(self) -> dict[str, int]:
        return {"start": self.start, "stop_exclusive": self.stop_exclusive}


@dataclass(frozen=True, slots=True)
class SplitManifest:
    manifest_id: str
    split_id: str
    ruleset_manifest_id: str
    objective_id: str
    universe: SeedUniverse
    salt: str
    counts: tuple[int, int, int]
    partitions: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]

    @classmethod
    def from_mapping(cls, value: object) -> SplitManifest:
        document = _mapping(value, "split manifest")
        _exact_keys(
            document,
            {
                "schema_version",
                "manifest_id",
                "split_id",
                "ruleset_manifest_id",
                "objective_id",
                "unit",
                "seed_universe",
                "assignment",
                "encounter_policy",
                "partitions",
            },
            "split manifest",
        )
        if document.get("schema_version") != SPLIT_MANIFEST_SCHEMA_VERSION:
            raise ValueError("Unsupported split manifest schema")
        if document.get("unit") != "complete_run":
            raise ValueError("Split manifest unit must be complete_run")

        universe_document = _mapping(document.get("seed_universe"), "seed_universe")
        _exact_keys(universe_document, {"start", "stop_exclusive"}, "seed_universe")
        universe = SeedUniverse(
            _integer(universe_document.get("start"), "seed_universe.start"),
            _integer(
                universe_document.get("stop_exclusive"),
                "seed_universe.stop_exclusive",
            ),
        )
        if universe.start < 0 or universe.stop_exclusive <= universe.start:
            raise ValueError("Seed universe must be a non-empty, non-negative half-open range")

        assignment = _mapping(document.get("assignment"), "assignment")
        _exact_keys(assignment, {"algorithm", "salt", "counts"}, "assignment")
        if assignment.get("algorithm") != SPLIT_ASSIGNMENT_ALGORITHM:
            raise ValueError("Unsupported split assignment algorithm")
        salt = _string(assignment.get("salt"), "assignment.salt")
        count_document = _split_mapping(assignment.get("counts"), "assignment.counts")
        counts = tuple(
            _integer(count_document[name.value], f"assignment.counts.{name.value}")
            for name in SPLIT_NAMES
        )
        if any(count < 0 for count in counts) or sum(counts) != universe.size:
            raise ValueError("Split counts must be non-negative and cover the seed universe")
        typed_counts = cast(tuple[int, int, int], counts)

        encounter_policy = _mapping(document.get("encounter_policy"), "encounter_policy")
        _exact_keys(
            encounter_policy,
            {"unit", "inherits_split_from", "identifier_fields", "cross_partition_reuse"},
            "encounter_policy",
        )
        if encounter_policy != _encounter_policy():
            raise ValueError("Unsupported encounter split policy")

        partition_document = _split_mapping(document.get("partitions"), "partitions")
        partitions = tuple(
            _integer_tuple(partition_document[name.value], f"partitions.{name.value}")
            for name in SPLIT_NAMES
        )
        if tuple(len(partition) for partition in partitions) != counts:
            raise ValueError("Partition sizes do not match the frozen split counts")
        flattened = tuple(seed for partition in partitions for seed in partition)
        expected_seeds = set(range(universe.start, universe.stop_exclusive))
        if len(flattened) != len(set(flattened)) or set(flattened) != expected_seeds:
            raise ValueError("Partitions must contain every seed exactly once")
        expected_partitions = _derive_partitions(universe, salt, typed_counts)
        if partitions != expected_partitions:
            raise ValueError("Partition assignments do not match the declared algorithm and salt")

        manifest = cls(
            manifest_id=_string(document.get("manifest_id"), "manifest_id"),
            split_id=_string(document.get("split_id"), "split_id"),
            ruleset_manifest_id=_manifest_id(
                document.get("ruleset_manifest_id"), "ruleset_manifest_id"
            ),
            objective_id=_string(document.get("objective_id"), "objective_id"),
            universe=universe,
            salt=salt,
            counts=typed_counts,
            partitions=partitions,
        )
        expected_id = manifest_identifier(manifest.body_dict())
        if manifest.manifest_id != expected_id:
            raise ValueError(
                f"Split manifest identity mismatch: expected {expected_id}, "
                f"got {manifest.manifest_id}"
            )
        return manifest

    def seeds(self, split: SplitName) -> tuple[int, ...]:
        return self.partitions[SPLIT_NAMES.index(split)]

    def split_for_seed(self, seed: int) -> SplitName:
        if seed < self.universe.start or seed >= self.universe.stop_exclusive:
            raise ValueError(f"Seed {seed} is outside split manifest {self.split_id}")
        for split, partition in zip(SPLIT_NAMES, self.partitions, strict=True):
            if seed in partition:
                return split
        raise RuntimeError(f"Seed {seed} is missing from a validated split manifest")

    def body_dict(self) -> dict[str, object]:
        return {
            "schema_version": SPLIT_MANIFEST_SCHEMA_VERSION,
            "split_id": self.split_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "unit": "complete_run",
            "seed_universe": self.universe.as_dict(),
            "assignment": {
                "algorithm": SPLIT_ASSIGNMENT_ALGORITHM,
                "salt": self.salt,
                "counts": {
                    name.value: count for name, count in zip(SPLIT_NAMES, self.counts, strict=True)
                },
            },
            "encounter_policy": _encounter_policy(),
            "partitions": {
                name.value: list(partition)
                for name, partition in zip(SPLIT_NAMES, self.partitions, strict=True)
            },
        }

    def as_dict(self) -> dict[str, object]:
        return {**self.body_dict(), "manifest_id": self.manifest_id}


@dataclass(frozen=True, slots=True)
class DatasetSplitAudit:
    valid: bool
    dataset_id: str
    dataset_index_id: str
    split_manifest_id: str
    runs: int
    records: int
    partition_runs: dict[str, int]
    partition_records: dict[str, int]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": DATASET_SPLIT_AUDIT_SCHEMA_VERSION,
            "valid": self.valid,
            "dataset_id": self.dataset_id,
            "dataset_index_id": self.dataset_index_id,
            "split_manifest_id": self.split_manifest_id,
            "runs": self.runs,
            "records": self.records,
            "partition_runs": self.partition_runs,
            "partition_records": self.partition_records,
            "errors": list(self.errors),
        }


def freeze_split_manifest(specification: object) -> SplitManifest:
    spec = _mapping(specification, "split specification")
    _exact_keys(
        spec,
        {
            "schema_version",
            "split_id",
            "ruleset_manifest_id",
            "objective_id",
            "unit",
            "seed_universe",
            "assignment",
            "encounter_policy",
        },
        "split specification",
    )
    if spec.get("schema_version") != SPLIT_MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unsupported split specification schema")
    universe_document = _mapping(spec.get("seed_universe"), "seed_universe")
    universe = SeedUniverse(
        _integer(universe_document.get("start"), "seed_universe.start"),
        _integer(universe_document.get("stop_exclusive"), "seed_universe.stop_exclusive"),
    )
    assignment = _mapping(spec.get("assignment"), "assignment")
    counts_document = _split_mapping(assignment.get("counts"), "assignment.counts")
    counts = cast(
        tuple[int, int, int],
        tuple(_integer(counts_document[name.value], name.value) for name in SPLIT_NAMES),
    )
    salt = _string(assignment.get("salt"), "assignment.salt")
    partitions = _derive_partitions(universe, salt, counts)
    body = {
        **spec,
        "partitions": {
            name.value: list(partition)
            for name, partition in zip(SPLIT_NAMES, partitions, strict=True)
        },
    }
    document = {**body, "manifest_id": manifest_identifier(body)}
    return SplitManifest.from_mapping(document)


def load_split_manifest(path: Path) -> SplitManifest:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load split manifest {path}: {error}") from error
    return SplitManifest.from_mapping(value)


def write_frozen_split_manifest(manifest: SplitManifest, path: Path) -> None:
    encoded = json.dumps(manifest.as_dict(), indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable split manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def freeze_dataset_index(specification: object, manifest: SplitManifest) -> dict[str, Any]:
    specification_document = _mapping(specification, "dataset index specification")
    body = dict(specification_document)
    body.pop("index_id", None)
    document = {**body, "index_id": manifest_identifier(body)}
    audit = audit_dataset_index_document(document, manifest)
    if not audit.valid:
        raise ValueError("Dataset split audit failed: " + "; ".join(audit.errors))
    return document


def write_frozen_dataset_index(document: dict[str, Any], path: Path) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable dataset index: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def audit_dataset_index(path: Path, manifest: SplitManifest) -> DatasetSplitAudit:
    try:
        document: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return _invalid_audit(
            "", "", manifest.manifest_id, f"Cannot load dataset index {path}: {error}"
        )
    return audit_dataset_index_document(document, manifest)


def audit_dataset_index_document(document: object, manifest: SplitManifest) -> DatasetSplitAudit:
    errors: list[str] = []
    try:
        index = _mapping(document, "dataset index")
        _exact_keys(
            index,
            {
                "schema_version",
                "index_id",
                "dataset_id",
                "split_manifest_id",
                "ruleset_manifest_id",
                "runs",
                "records",
            },
            "dataset index",
        )
    except ValueError as error:
        return _invalid_audit("", "", manifest.manifest_id, str(error))
    dataset_id_value = index.get("dataset_id")
    dataset_id = dataset_id_value if isinstance(dataset_id_value, str) else ""
    index_id_value = index.get("index_id")
    dataset_index_id = index_id_value if isinstance(index_id_value, str) else ""
    if index.get("schema_version") != DATASET_INDEX_SCHEMA_VERSION:
        errors.append("unsupported dataset index schema")
    if not dataset_id:
        errors.append("dataset_id must be a non-empty string")
    index_body = {key: value for key, value in index.items() if key != "index_id"}
    expected_index_id = manifest_identifier(index_body)
    if dataset_index_id != expected_index_id:
        errors.append(
            f"dataset index identity mismatch: expected {expected_index_id}, got {dataset_index_id}"
        )
    if index.get("split_manifest_id") != manifest.manifest_id:
        errors.append("dataset index references a different split manifest")
    if index.get("ruleset_manifest_id") != manifest.ruleset_manifest_id:
        errors.append("dataset index references a different ruleset manifest")
    runs_value = index.get("runs")
    records_value = index.get("records")
    if not isinstance(runs_value, list) or not isinstance(records_value, list):
        return _invalid_audit(
            dataset_id,
            dataset_index_id,
            manifest.manifest_id,
            "dataset index runs and records must be arrays",
            errors,
        )

    run_documents: dict[str, dict[str, Any]] = {}
    run_record_ids: dict[str, tuple[str, ...]] = {}
    run_encounter_ids: dict[str, set[str]] = {}
    partition_runs = _zero_counts()
    for offset, value in enumerate(runs_value):
        label = f"runs[{offset}]"
        try:
            run = _mapping(value, label)
            _exact_keys(
                run,
                {"run_id", "seed", "split", "terminal", "record_ids", "encounter_ids"},
                label,
            )
            run_id = _string(run.get("run_id"), f"{label}.run_id")
            seed = _integer(run.get("seed"), f"{label}.seed")
            declared_split = SplitName(_string(run.get("split"), f"{label}.split"))
            record_ids = _string_tuple(run.get("record_ids"), f"{label}.record_ids")
            encounter_ids = _string_tuple(run.get("encounter_ids"), f"{label}.encounter_ids")
        except (ValueError, TypeError) as error:
            errors.append(str(error))
            continue
        if run_id in run_documents:
            errors.append(f"duplicate run_id: {run_id}")
            continue
        if run.get("terminal") is not True:
            errors.append(f"run {run_id} is not a complete terminal trajectory")
        if not record_ids or len(record_ids) != len(set(record_ids)):
            errors.append(f"run {run_id} must list unique, non-empty record_ids")
        if len(encounter_ids) != len(set(encounter_ids)):
            errors.append(f"run {run_id} has duplicate encounter_ids")
        try:
            expected_split = manifest.split_for_seed(seed)
        except ValueError as error:
            errors.append(f"run {run_id}: {error}")
        else:
            if declared_split is not expected_split:
                errors.append(
                    f"run {run_id} declares {declared_split.value}, "
                    f"but seed {seed} is frozen to {expected_split.value}"
                )
        run_documents[run_id] = run
        run_record_ids[run_id] = record_ids
        run_encounter_ids[run_id] = set(encounter_ids)
        partition_runs[declared_split.value] += 1

    declared_record_owners: dict[str, str] = {}
    for run_id, record_ids in run_record_ids.items():
        for record_id in record_ids:
            previous = declared_record_owners.setdefault(record_id, run_id)
            if previous != run_id:
                errors.append(f"record {record_id} is declared by runs {previous} and {run_id}")

    seen_record_ids: set[str] = set()
    observed_by_run: dict[str, list[int]] = {run_id: [] for run_id in run_documents}
    observed_encounters: dict[str, set[str]] = {run_id: set() for run_id in run_documents}
    partition_records = _zero_counts()
    for offset, value in enumerate(records_value):
        label = f"records[{offset}]"
        try:
            record = _mapping(value, label)
            _exact_keys(
                record,
                {"record_id", "run_id", "encounter_id", "decision_index"},
                label,
            )
            record_id = _string(record.get("record_id"), f"{label}.record_id")
            run_id = _string(record.get("run_id"), f"{label}.run_id")
            decision_index = _integer(record.get("decision_index"), f"{label}.decision_index")
            encounter_id = record.get("encounter_id")
            if encounter_id is not None:
                encounter_id = _string(encounter_id, f"{label}.encounter_id")
        except ValueError as error:
            errors.append(str(error))
            continue
        if record_id in seen_record_ids:
            errors.append(f"duplicate record_id: {record_id}")
            continue
        seen_record_ids.add(record_id)
        owner_run = run_documents.get(run_id)
        if owner_run is None:
            errors.append(f"record {record_id} references unknown run {run_id}")
            continue
        if declared_record_owners.get(record_id) != run_id:
            errors.append(f"record {record_id} is not declared by run {run_id}")
        if decision_index < 0:
            errors.append(f"record {record_id} has a negative decision_index")
        if encounter_id is not None and encounter_id not in run_encounter_ids[run_id]:
            errors.append(f"record {record_id} references undeclared encounter {encounter_id}")
        elif encounter_id is not None:
            observed_encounters[run_id].add(encounter_id)
        observed_by_run[run_id].append(decision_index)
        partition_records[str(owner_run["split"])] += 1

    missing_records = set(declared_record_owners) - seen_record_ids
    extra_records = seen_record_ids - set(declared_record_owners)
    if missing_records:
        errors.append(f"dataset index is missing {len(missing_records)} declared records")
    if extra_records:
        errors.append(f"dataset index has {len(extra_records)} undeclared records")
    for run_id, indices in observed_by_run.items():
        if sorted(indices) != list(range(len(indices))):
            errors.append(f"run {run_id} decision indices are not contiguous from zero")
        unused_encounters = run_encounter_ids[run_id] - observed_encounters[run_id]
        if unused_encounters:
            errors.append(
                f"run {run_id} has {len(unused_encounters)} declared encounters without records"
            )

    return DatasetSplitAudit(
        valid=not errors,
        dataset_id=dataset_id,
        dataset_index_id=dataset_index_id,
        split_manifest_id=manifest.manifest_id,
        runs=len(run_documents),
        records=len(seen_record_ids),
        partition_runs=partition_runs,
        partition_records=partition_records,
        errors=tuple(errors),
    )


def partition_dataset_records(
    document: object, manifest: SplitManifest
) -> dict[SplitName, tuple[dict[str, Any], ...]]:
    audit = audit_dataset_index_document(document, manifest)
    if not audit.valid:
        raise ValueError("Dataset split audit failed: " + "; ".join(audit.errors))
    index = _mapping(document, "dataset index")
    runs = cast(list[dict[str, Any]], index["runs"])
    records = cast(list[dict[str, Any]], index["records"])
    split_by_run = {str(run["run_id"]): SplitName(str(run["split"])) for run in runs}
    grouped: dict[SplitName, list[dict[str, Any]]] = {name: [] for name in SPLIT_NAMES}
    for record in records:
        grouped[split_by_run[str(record["run_id"])]].append(record)
    return {name: tuple(grouped[name]) for name in SPLIT_NAMES}


def _derive_partitions(
    universe: SeedUniverse,
    salt: str,
    counts: tuple[int, int, int],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    if universe.start < 0 or universe.stop_exclusive <= universe.start:
        raise ValueError("Seed universe must be a non-empty, non-negative half-open range")
    if any(count < 0 for count in counts) or sum(counts) != universe.size:
        raise ValueError("Split counts must cover the seed universe")
    ranked = sorted(
        range(universe.start, universe.stop_exclusive),
        key=lambda seed: (hashlib.sha256(f"{salt}\0{seed}".encode()).digest(), seed),
    )
    train_end = counts[0]
    validation_end = train_end + counts[1]
    return (
        tuple(sorted(ranked[:train_end])),
        tuple(sorted(ranked[train_end:validation_end])),
        tuple(sorted(ranked[validation_end:])),
    )


def _encounter_policy() -> dict[str, object]:
    return {
        "unit": "encounter_instance",
        "inherits_split_from": "complete_run",
        "identifier_fields": ["run_id", "encounter_id"],
        "cross_partition_reuse": "forbidden",
    }


def _zero_counts() -> dict[str, int]:
    return {name.value: 0 for name in SPLIT_NAMES}


def _invalid_audit(
    dataset_id: str,
    dataset_index_id: str,
    split_manifest_id: str,
    error: str,
    previous_errors: list[str] | None = None,
) -> DatasetSplitAudit:
    errors = [*(previous_errors or []), error]
    return DatasetSplitAudit(
        False,
        dataset_id,
        dataset_index_id,
        split_manifest_id,
        0,
        0,
        _zero_counts(),
        _zero_counts(),
        tuple(errors),
    )


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _split_mapping(value: object, label: str) -> dict[str, Any]:
    mapping = _mapping(value, label)
    _exact_keys(mapping, {name.value for name in SPLIT_NAMES}, label)
    return mapping


def _exact_keys(mapping: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(mapping)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _manifest_id(value: object, label: str) -> str:
    identifier = _string(value, label)
    prefix = "sha256:"
    digest = identifier.removeprefix(prefix)
    if (
        not identifier.startswith(prefix)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ValueError(f"{label} must be a sha256 manifest identifier")
    return identifier


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _integer_tuple(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return tuple(_integer(item, f"{label}[{offset}]") for offset, item in enumerate(value))


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return tuple(_string(item, f"{label}[{offset}]") for offset, item in enumerate(value))
