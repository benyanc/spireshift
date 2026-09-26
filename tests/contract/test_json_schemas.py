import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

SCHEMA_DIR = Path("schemas")
FIXTURE_DIR = Path("tests/fixtures")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object in {path}")
    return value


def _registry() -> Registry[Any]:
    resources = []
    for path in SCHEMA_DIR.glob("*.json"):
        schema = _load(path)
        resources.append((str(schema["$id"]), Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@pytest.mark.parametrize(
    ("schema_name", "fixture_name"),
    [
        ("observation-v1.json", "observation-v1.json"),
        ("action-v1.json", "action-v1.json"),
        ("transition-v1.json", "transition-v1.json"),
        ("game-installation-v1.json", "game-installation-v1.json"),
        ("patch-manifest-v1.json", "patch-manifest-v1.json"),
        ("conformance-report-v1.json", "conformance-report-v1.json"),
        ("conformance-trace-v1.json", "conformance-trace-v1.json"),
        ("differential-report-v1.json", "differential-report-v1.json"),
        ("live-snapshot-v1.json", "live-snapshot-v1.json"),
        ("bound-action-v1.json", "bound-action-v1.json"),
        ("action-receipt-v1.json", "action-receipt-v1.json"),
        (
            "rollout-batch-v1.json",
            "rollout/mock-batch-v1/rollout-report.json",
        ),
        (
            "rollout-worker-result-v1.json",
            "rollout/mock-batch-v1/attempts/seed-0/attempt-1/worker-result.json",
        ),
        ("rollout-batch-replay-v1.json", "rollout-batch-replay-v1.json"),
        (
            "split-manifest-v1.json",
            "../../manifests/splits/mock-v1-seeds-000000-000999-v1.json",
        ),
        (
            "split-manifest-v1.json",
            "../../manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json",
        ),
        ("dataset-index-v1.json", "splits/dataset-index-v1.json"),
        ("dataset-split-audit-v1.json", "splits/dataset-split-audit-v1.json"),
        ("live-fixture-corpus-v1.json", "live/public-state-corpus-v1.json"),
        ("live-action-coverage-spec-v1.json", "../../configs/live-coverage-v0.107.1.json"),
        ("model-input-v1.json", "model-input-v1.json"),
        ("vectorized-model-input-v1.json", "vectorized-model-input-v1.json"),
        ("teacher-dataset-v1.json", "teacher-dataset-v1.json"),
        ("dataset-index-v1.json", "teacher-dataset-index-v1.json"),
        (
            "teacher-dataset-verification-v1.json",
            "teacher-dataset-verification-v1.json",
        ),
        ("model-checkpoint-v1.json", "model-checkpoint-v1.json"),
        ("model-training-report-v1.json", "model-training-report-v1.json"),
        ("model-checkpoint-v1.json", "model-checkpoint-dagger-v1.json"),
        ("model-training-report-v1.json", "model-training-report-dagger-v1.json"),
        ("model-calibration-v1.json", "model-calibration-v1.json"),
        ("model-calibration-report-v1.json", "model-calibration-report-v1.json"),
        ("tactical-handoff-report-v1.json", "tactical-handoff-report-v1.json"),
        (
            "conformance-report-v1.json",
            "../../docs/evidence/evangambit-v0.107.1-spireshift-conformance.json",
        ),
        (
            "backend-admission-report-v1.json",
            "../../docs/evidence/evangambit-v0.107.1-spireshift-admission.json",
        ),
        ("dagger-iteration-v1.json", "dagger-iteration-v1.json"),
        ("dagger-verification-v1.json", "dagger-verification-v1.json"),
        ("dataset-index-v1.json", "dagger-dataset-index-v1.json"),
        ("mechanics-fixture-v1.json", "mechanics/mock-v1.json"),
        (
            "search-simulation-task-v1.json",
            "search-workers/mock-batch-v1/tasks/00000000-0000-4000-8000-000000000000/request.json",
        ),
        (
            "search-worker-result-v1.json",
            "search-workers/mock-batch-v1/tasks/00000000-0000-4000-8000-000000000000/result.json",
        ),
        (
            "search-worker-result-v2.json",
            "search-workers/mock-batch-v2/tasks/00000000-0000-4000-8000-000000000000/result.json",
        ),
        (
            "search-worker-batch-v1.json",
            "search-workers/mock-batch-v1/search-worker-report.json",
        ),
        (
            "search-worker-batch-v2.json",
            "search-workers/mock-batch-v2/search-worker-report.json",
        ),
        (
            "fixed-search-report-v1.json",
            "fixed-search/tactical-mock-v1/fixed-search-report.json",
        ),
        (
            "fixed-search-report-v2.json",
            "fixed-search/tactical-mock-v2/fixed-search-report.json",
        ),
        (
            "fixed-search-verification-v1.json",
            "fixed-search-verification-v1.json",
        ),
        (
            "fixed-search-verification-v1.json",
            "fixed-search-verification-v2-target.json",
        ),
        (
            "search-benchmark-state-set-v1.json",
            "search-benchmark-state-set-v1.json",
        ),
        (
            "search-benchmark-state-set-v1.json",
            "../../manifests/benchmarks/sts2-v0.107.1-evangambit-validation-v1.json",
        ),
        (
            "search-compute-quality-report-v1.json",
            "search-compute-quality-report-v1.json",
        ),
        (
            "search-compute-quality-verification-v1.json",
            "search-compute-quality-verification-v1.json",
        ),
        (
            "bootstrap-state-set-v1.json",
            "bootstrap/tactical-mock-v1/state-set.json",
        ),
        (
            "bootstrap-state-set-v1.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json",
        ),
        (
            "bootstrap-state-set-v2.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json",
        ),
        (
            "bootstrap-state-set-v2.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json",
        ),
        (
            "bootstrap-state-set-v3.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json",
        ),
        (
            "bootstrap-state-set-v3.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-validation-learned-curriculum-v3.json",
        ),
        (
            "bootstrap-state-set-v3.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-supplement-v3.json",
        ),
        (
            "bootstrap-state-set-v4.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-train-terminal-frontier-v4.json",
        ),
        (
            "bootstrap-state-set-v4.json",
            "../../manifests/bootstrap/sts2-v0.107.1-evangambit-validation-terminal-frontier-v4.json",
        ),
        (
            "bootstrap-simulation-task-v1.json",
            "bootstrap/tactical-mock-v1/dataset/cases/train-seed-000007-combat-000/attempt-0001/tasks/588634b5-e038-51ce-97f1-591206578543/request.json",
        ),
        (
            "bootstrap-worker-result-v1.json",
            "bootstrap/tactical-mock-v1/dataset/cases/train-seed-000007-combat-000/attempt-0001/tasks/588634b5-e038-51ce-97f1-591206578543/result.json",
        ),
        (
            "bootstrap-worker-batch-v1.json",
            "bootstrap/tactical-mock-v1/dataset/cases/train-seed-000007-combat-000/attempt-0001/bootstrap-worker-report.json",
        ),
        (
            "bootstrap-teacher-dataset-v1.json",
            "bootstrap/tactical-mock-v1/dataset/bootstrap-teacher-dataset.json",
        ),
        (
            "bootstrap-teacher-verification-v1.json",
            "bootstrap/tactical-mock-v1/verification.json",
        ),
        (
            "bootstrap-curriculum-smoke-evidence-v1.json",
            "../../docs/evidence/bootstrap-curriculum-v2-admitted-smoke.json",
        ),
        (
            "production-model-inference-smoke-v1.json",
            "../../docs/evidence/production-model-inference-smoke-v0.107.1.json",
        ),
        (
            "production-model-inference-smoke-v1.json",
            "../../docs/evidence/production-model-inference-smoke-v3-v0.107.1.json",
        ),
        (
            "base-model-readiness-spec-v1.json",
            "../../configs/readiness/sts2-v0.107.1-base-v2-validation-v1.json",
        ),
        (
            "base-model-readiness-report-v1.json",
            "../../docs/evidence/production-base-v2-readiness-v1.json",
        ),
        (
            "production-model-readiness-audit-v1.json",
            "production-model-readiness-audit-v1.json",
        ),
        ("experiment-metrics-v1.json", "experiment-metrics-v1.json"),
        ("experiment-resources-v1.json", "experiment-resources-v1.json"),
    ],
)
def test_fixture_conforms_to_versioned_schema(schema_name: str, fixture_name: str) -> None:
    validator = Draft202012Validator(_load(SCHEMA_DIR / schema_name), registry=_registry())
    validator.validate(_load(FIXTURE_DIR / fixture_name))


def test_external_conformance_evidence_conforms_to_schema() -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "external-conformance-evidence-v1.json"),
        registry=_registry(),
    )
    validator.validate(_load(Path("docs/evidence/evangambit-v0.107.1-conformance.json")))


def test_live_fixture_audit_evidence_conforms_to_schema() -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "live-fixture-audit-v1.json"), registry=_registry()
    )
    validator.validate(_load(Path("docs/evidence/live-fixture-audit-v0.107.1.json")))


def test_live_action_coverage_evidence_conforms_to_schema() -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "live-action-coverage-v1.json"), registry=_registry()
    )
    validator.validate(_load(Path("docs/evidence/live-action-coverage-v0.107.1.json")))


def test_mock_mechanics_audit_evidence_conforms_to_schema() -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "mechanics-audit-v1.json"), registry=_registry()
    )
    validator.validate(_load(Path("docs/evidence/mock-mechanics-audit-v1.json")))


@pytest.mark.parametrize(
    "configuration",
    [
        "configs/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json",
        "configs/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json",
    ],
)
def test_curriculum_discovery_configuration_conforms_to_schema(configuration: str) -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "bootstrap-curriculum-discovery-spec-v1.json"),
        registry=_registry(),
    )
    validator.validate(_load(Path(configuration)))


@pytest.mark.parametrize(
    "configuration",
    [
        "configs/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json",
        "configs/bootstrap/sts2-v0.107.1-evangambit-validation-learned-curriculum-v3.json",
        "configs/bootstrap/sts2-v0.107.1-evangambit-train-learned-supplement-v3.json",
    ],
)
def test_learned_curriculum_discovery_configuration_conforms_to_schema(
    configuration: str,
) -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "bootstrap-curriculum-discovery-spec-v2.json"),
        registry=_registry(),
    )
    validator.validate(_load(Path(configuration)))


@pytest.mark.parametrize(
    "configuration",
    [
        "configs/bootstrap/sts2-v0.107.1-evangambit-train-terminal-frontier-v4.json",
        "configs/bootstrap/sts2-v0.107.1-evangambit-validation-terminal-frontier-v4.json",
    ],
)
def test_terminal_frontier_discovery_configuration_conforms_to_schema(
    configuration: str,
) -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "bootstrap-curriculum-discovery-spec-v3.json"),
        registry=_registry(),
    )
    validator.validate(_load(Path(configuration)))


def test_combat_advancement_configuration_conforms_to_schema() -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "combat-advancement-config-v1.json"),
        registry=_registry(),
    )
    validator.validate(_load(Path("configs/combat-advancement/sts2-v0.107.1-base-v3-v1.json")))


@pytest.mark.parametrize(
    "configuration",
    [
        "configs/bootstrap/sts2-v0.107.1-evangambit-train-combat-advancement-frontier-v5.json",
        "configs/bootstrap/sts2-v0.107.1-evangambit-validation-combat-advancement-frontier-v5.json",
    ],
)
def test_combat_advancement_frontier_configuration_conforms_to_schema(
    configuration: str,
) -> None:
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "bootstrap-curriculum-discovery-spec-v4.json"),
        registry=_registry(),
    )
    validator.validate(_load(Path(configuration)))


def test_observation_rejects_unmarked_privileged_state() -> None:
    fixture = _load(FIXTURE_DIR / "observation-v1.json")
    fixture["privileged_state"] = {"future_rng": 0.01}
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "observation-v1.json"), registry=_registry()
    )
    with pytest.raises(ValidationError):
        validator.validate(fixture)
