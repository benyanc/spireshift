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
        ("dataset-index-v1.json", "splits/dataset-index-v1.json"),
        ("dataset-split-audit-v1.json", "splits/dataset-split-audit-v1.json"),
        ("live-fixture-corpus-v1.json", "live/public-state-corpus-v1.json"),
        ("live-action-coverage-spec-v1.json", "../../configs/live-coverage-v0.107.1.json"),
        ("model-input-v1.json", "model-input-v1.json"),
        ("vectorized-model-input-v1.json", "vectorized-model-input-v1.json"),
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


def test_observation_rejects_unmarked_privileged_state() -> None:
    fixture = _load(FIXTURE_DIR / "observation-v1.json")
    fixture["privileged_state"] = {"future_rng": 0.01}
    validator = Draft202012Validator(
        _load(SCHEMA_DIR / "observation-v1.json"), registry=_registry()
    )
    with pytest.raises(ValidationError):
        validator.validate(fixture)
