import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.conformance import (
    capture_conformance_trace,
    compare_conformance_traces,
    run_environment_conformance,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import Observation


class LeakyMockEnvironment(MockSpireEnvironment):
    def _observation(self) -> Observation:
        original = super()._observation()
        public_state = {**original.public_state, "rng": {"next": 0.25}}
        encoded = json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        return Observation(
            schema_version=original.schema_version,
            patch_id=original.patch_id,
            decision_type=original.decision_type,
            public_state=public_state,
            state_hash=hashlib.sha256(encoded).hexdigest(),
        )


def test_mock_passes_every_environment_contract_check() -> None:
    report = run_environment_conformance(MockSpireEnvironment)
    assert report.verdict == "pass"
    assert {check.status.value for check in report.checks} == {"pass"}
    assert {check.check_id for check in report.checks} == {
        "identity",
        "reset",
        "legal_actions",
        "stepping",
        "illegal_action",
        "faithful_clone",
        "hidden_resampling",
        "replay",
        "public_state_isolation",
        "terminal_reward",
    }


def test_public_state_leak_is_reported_as_failure() -> None:
    report = run_environment_conformance(LeakyMockEnvironment)
    public_check = next(
        check for check in report.checks if check.check_id == "public_state_isolation"
    )
    assert report.verdict == "fail"
    assert public_check.status.value == "fail"
    assert "public_state.rng" in public_check.detail


def test_trace_comparison_reports_exact_field_divergence() -> None:
    reference = capture_conformance_trace(MockSpireEnvironment(), seed=7, fixture_id="reference")
    candidate = cast(dict[str, Any], copy.deepcopy(reference))
    candidate["fixture_id"] = "candidate"
    candidate["steps"][1]["next_observation"]["public_state"]["victory"] = False

    report = compare_conformance_traces(reference, candidate)

    assert report["verdict"] == "diverged"
    assert report["mismatch_count"] == 1
    assert cast(list[object], report["divergences"])[0] == {
        "path": "steps[1].next_observation.public_state.victory",
        "expected": True,
        "actual": False,
    }


def test_trace_comparison_refuses_different_patches() -> None:
    reference = capture_conformance_trace(MockSpireEnvironment(), seed=7, fixture_id="reference")
    candidate = cast(dict[str, Any], copy.deepcopy(reference))
    candidate["fixture_id"] = "candidate"
    candidate["ruleset"]["patch_id"] = "different-patch"

    report = compare_conformance_traces(reference, candidate)

    assert report["verdict"] == "incomparable"
    assert report["comparability_errors"] == ["patch_mismatch"]


def test_external_evidence_is_content_addressed_and_keeps_raw_fixtures_external() -> None:
    path = Path("docs/evidence/evangambit-v0.107.1-conformance.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    evidence_id = document.pop("evidence_id")

    assert evidence_id == manifest_identifier(document)
    assert document["differential_result"]["observed_divergences"] == 0
    assert document["admission"]["status"] == "pending_conformance"
    assert "/tmp/" not in path.read_text(encoding="utf-8")
