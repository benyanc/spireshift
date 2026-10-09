from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.backend_admission import MANDATORY_CONFORMANCE_CHECKS
from spireshift.core.manifest import load_patch_manifest
from spireshift.full_run_a8_admission import check_a8_evidence


def evidence() -> tuple[Any, ...]:
    """Synthetic summaries test validation, not an execution or admission claim."""
    manifest = load_patch_manifest(
        Path("manifests/patches/sts2-v0.107.1-evangambit-event-choices-v4-retry2-pending.json")
    )
    sha = next(a.digest.value for a in manifest.mechanics if a.kind == "compiled-simulator-library")
    assembly = next(a for a in manifest.mechanics if a.kind == "authoritative-game-assembly")
    build = {
        "candidate_revision": manifest.engine.revision,
        "native_sha256": sha,
        "regression_tests": {"passed": 240, "failed": 0},
        "report_id": "synthetic-build",
    }
    native = {
        "build_report_id": "synthetic-build",
        "candidate_revision": manifest.engine.revision,
        "native_sha256": sha,
        "counts": {"passed": 4942, "failed": 0},
        "skips": ["StepCostProbe"],
    }
    python = {
        "candidate_revision": manifest.engine.revision,
        "native_sha256": sha,
        "executions": [
            {"suite": "test_sts2_gym.py", "status": "pass", "failed": 0, "passed": 31},
            {
                "suite": "test_live_fixtures.py",
                "status": "pass",
                "failed": 0,
                "passed": 420,
                "skipped": 6,
                "skip_reasons": ["capture predates per-turn hands"],
            },
        ],
    }
    contract = {
        "ruleset_manifest_id": manifest.manifest_id,
        "conformance": {
            "ruleset": {"manifest_id": manifest.manifest_id},
            "verdict": "pass",
            "checks": [{"check_id": c, "status": "pass"} for c in MANDATORY_CONFORMANCE_CHECKS],
        },
    }
    audit = json.loads(Path("docs/evidence/frozen-run-rule-audit-v1-evidence.json").read_text())
    profile = json.loads(Path("docs/evidence/public-a8-policy-admission-v1.json").read_text())[
        "profile"
    ]
    return (
        manifest,
        build,
        native,
        python,
        contract,
        audit,
        assembly.digest.value,
        assembly.size_bytes,
        profile,
    )


def test_executed_scope_is_policy_learning_and_preserves_live_limits() -> None:
    assert check_a8_evidence(*evidence()) == ()
    saved = json.loads(Path("docs/evidence/public-a8-policy-admission-v1.json").read_text())
    assert saved["verdict"] == "admitted_for_policy_only_a8_learning"
    assert saved["empirical_later_act_ui_parity"] is False
    assert saved["foundation_readiness_established"] is False
    assert saved["agent_games_played"] == saved["optimizer_steps"] == 0


@pytest.mark.parametrize(
    "kind",
    [
        "native_identity",
        "failed_suite",
        "fixtures",
        "contract",
        "hidden_limits",
        "wrong_difficulty",
        "missing_rule",
    ],
)
def test_bad_or_mislabelled_admission_evidence_is_rejected(kind: str) -> None:
    data = list(copy.deepcopy(evidence()))
    if kind == "native_identity":
        data[1]["native_sha256"] = "bad"
    elif kind == "failed_suite":
        data[2]["counts"]["failed"] = 1
    elif kind == "fixtures":
        data[3]["executions"][1]["passed"] = 419
    elif kind == "contract":
        data[4]["conformance"]["checks"][0]["status"] = "fail"
    elif kind == "hidden_limits":
        data[5]["all_ascension8_effects_verified"] = True
    elif kind == "wrong_difficulty":
        data[8]["source_declared_ascension_level"] = 0
    else:
        data[5]["source_findings"].pop()
    assert check_a8_evidence(*data)
