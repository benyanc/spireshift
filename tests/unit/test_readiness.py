import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.production_inference import load_production_inference_smoke
from spireshift.production_models import (
    load_production_model_checkpoint,
    load_production_training_report,
)
from spireshift.readiness import (
    assess_base_model_readiness,
    load_readiness_audit,
    load_readiness_report,
    load_readiness_spec,
    summarize_readiness_audit,
)
from spireshift.splits import SplitName, load_split_manifest

SPLIT_PATH = Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
SPEC_PATH = Path("configs/readiness/sts2-v0.107.1-base-v2-validation-v1.json")
CHECKPOINT_PATH = Path("artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json")
TRAINING_REPORT_PATH = Path("artifacts/models/sts2-v0.107.1-base-v2/training-report.json")
SMOKE_PATH = Path("artifacts/models/sts2-v0.107.1-base-v2/inference-smoke.json")
ASSESSMENT_PATH = Path("docs/evidence/production-base-v2-readiness-v1.json")


def _inputs() -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    split = load_split_manifest(SPLIT_PATH)
    spec = load_readiness_spec(SPEC_PATH, split_manifest=split)
    checkpoint = load_production_model_checkpoint(CHECKPOINT_PATH)
    report = load_production_training_report(TRAINING_REPORT_PATH, checkpoint=checkpoint)
    smoke = load_production_inference_smoke(
        SMOKE_PATH,
        model_id=str(checkpoint["model_id"]),
        training_report_id=str(report["report_id"]),
    )
    return split, spec, checkpoint, report, smoke


def test_frozen_base_v2_scorecard_fails_only_closed_terminal_gates() -> None:
    split, spec, checkpoint, report, smoke = _inputs()
    assessment = assess_base_model_readiness(
        spec=spec,
        checkpoint=checkpoint,
        training_report=report,
        split_manifest=split,
        inference_smoke=smoke,
        policy_evaluation=None,
        readiness_audit=None,
    )

    assert assessment == load_readiness_report(
        ASSESSMENT_PATH,
        scorecard_id=str(spec["scorecard_id"]),
        model_id=str(checkpoint["model_id"]),
    )
    statuses = {check["check_id"]: check["status"] for check in assessment["checks"]}
    assert statuses["identity.frozen_binding"] == "passed"
    assert statuses["auxiliary.policy_quality"] == "passed"
    assert statuses["auxiliary.tactical_risk_calibration"] == "passed"
    assert statuses["inference.candidate_alignment_and_latency"] == "passed"
    assert statuses["terminal.value_head_available"] == "failed"
    assert assessment["ready"] is False
    assert all(
        check_id.startswith(("terminal.", "full_run."))
        for check_id in assessment["blocking_check_ids"]
    )


def test_scorecard_can_pass_complete_nondegenerate_validation_evidence() -> None:
    split, spec, checkpoint, report, smoke = _inputs()
    promoted_report = copy.deepcopy(report)
    promoted_report["terminal_value_status"] = {
        "promoted": True,
        "reason": "nondegenerate_terminal_victory_evidence",
        "train_victories": 12,
        "validation_victories": 8,
    }
    seeds = spec["evaluation_contract"]["seeds"]
    learned = _policy_summary(15, 100)
    baseline = _policy_summary(0, 100)
    evaluation = {
        "report_id": manifest_identifier({"complete": "evaluation"}),
        "partition": "validation",
        "configuration": {"seeds": seeds},
        "summary": {
            "learned": learned,
            "baseline": baseline,
            "paired": {
                "completed_pairs": 100,
                "learned_only_victories": 15,
                "baseline_only_victories": 0,
                "mean_maximum_floor_difference": 4.0,
            },
        },
    }
    audit = {
        "audit_id": manifest_identifier({"complete": "audit"}),
        "calibration": {
            "calibration_id": manifest_identifier({"calibration": "passing"}),
            "method": "platt-logit-affine-v1",
            "fit_fraction": 0.5,
            "split_salt": "production-base-readiness-calibration-v1",
        },
        "configuration": {
            "calibration_bins": 10,
            "policy_confidence_threshold": 0.8,
            "catastrophic_regret_threshold": 0.1,
            "false_safe_predicted_risk_threshold": 0.2,
            "false_safe_observed_risk_threshold": 0.5,
        },
        "summary": {
            "decisions": 100,
            "terminal_samples": 1600,
            "terminal_victories": 200,
            "terminal_defeats": 1400,
            "action_value_variation_decisions": 50,
            "terminal_value": {
                "brier_skill_score": 0.2,
                "expected_calibration_error": 0.05,
            },
            "tactical_death_risk": {},
            "independent_value_regret": {"mean": 0.02, "p95": 0.1},
            "failure_analysis": {
                "high_confidence_decisions": 50,
                "high_confidence_catastrophic_errors": 1,
                "high_confidence_catastrophic_rate": 0.02,
                "false_safe_tactical_risk_errors": 2,
                "false_safe_tactical_risk_rate": 0.02,
            },
        },
    }
    passing_spec = copy.deepcopy(spec)
    passing_spec["binding"]["calibration_id"] = cast(dict[str, Any], audit["calibration"])[
        "calibration_id"
    ]
    assessment = assess_base_model_readiness(
        spec=passing_spec,
        checkpoint=checkpoint,
        training_report=promoted_report,
        split_manifest=split,
        inference_smoke=smoke,
        policy_evaluation=evaluation,
        readiness_audit=audit,
    )

    assert assessment["ready"] is True
    assert assessment["blocking_check_ids"] == []
    assert all(check["status"] == "passed" for check in assessment["checks"])


def test_readiness_audit_recomputes_summary_and_rejects_tampering(tmp_path: Path) -> None:
    split, _, checkpoint, report, _ = _inputs()
    validation_seeds = split.seeds(SplitName.VALIDATION)
    records: list[dict[str, Any]] = []
    normalized_records: list[dict[str, Any]] = []
    for decision_index in range(2):
        candidates = [
            {
                "terminal_value_prediction": 0.5,
                "terminal_outcomes": [0, 1],
                "tactical_risk_prediction": 0.5,
                "tactical_death_outcomes": [0, 1],
            },
            {
                "terminal_value_prediction": 0.0,
                "terminal_outcomes": [0, 0],
                "tactical_risk_prediction": 0.0,
                "tactical_death_outcomes": [0, 0],
            },
        ]
        record_body = {
            "run_seed": validation_seeds[1],
            "decision_index": decision_index,
            "policy_confidence": 0.9,
            "selected_candidate_index": 0,
            "candidates": candidates,
        }
        records.append({**record_body, "record_id": manifest_identifier(record_body)})
        normalized_records.append(
            {
                **records[-1],
                "candidates": tuple(
                    {
                        **candidate,
                        "terminal_outcomes": tuple(cast(list[int], candidate["terminal_outcomes"])),
                        "tactical_death_outcomes": tuple(
                            cast(list[int], candidate["tactical_death_outcomes"])
                        ),
                    }
                    for candidate in candidates
                ),
            }
        )
    configuration = {
        "calibration_bins": 10,
        "policy_confidence_threshold": 0.8,
        "catastrophic_regret_threshold": 0.1,
        "false_safe_predicted_risk_threshold": 0.2,
        "false_safe_observed_risk_threshold": 0.5,
    }
    audit_body = {
        "schema_version": "production-model-readiness-audit-v1",
        "model_id": checkpoint["model_id"],
        "training_report_id": report["report_id"],
        "validation_dataset_id": report["validation_dataset_id"],
        "split_manifest_id": split.manifest_id,
        "ruleset_manifest_id": split.ruleset_manifest_id,
        "objective_id": split.objective_id,
        "partition": "validation",
        "calibration": {
            "calibration_id": manifest_identifier({"calibration": "fixture"}),
            "method": "platt-logit-affine-v1",
            "fit_fraction": 0.5,
            "split_salt": "production-base-readiness-calibration-v1",
            "fit_run_seeds": [validation_seeds[0]],
            "audit_run_seeds": [validation_seeds[1]],
        },
        "configuration": configuration,
        "records": records,
        "summary": summarize_readiness_audit(tuple(normalized_records), configuration),
        "claim_scope": "independent_validation_calibration_and_failure_audit",
    }
    audit = {**audit_body, "audit_id": manifest_identifier(audit_body)}
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    loaded = load_readiness_audit(
        audit_path,
        model_id=str(checkpoint["model_id"]),
        training_report_id=str(report["report_id"]),
        split_manifest=split,
        validation_dataset_id=str(report["validation_dataset_id"]),
    )
    assert loaded["audit_id"] == audit["audit_id"]

    audit["summary"]["terminal_victories"] = 0
    tampered_body = {key: item for key, item in audit.items() if key != "audit_id"}
    audit["audit_id"] = manifest_identifier(tampered_body)
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    with pytest.raises(ValueError, match="summary differs"):
        load_readiness_audit(
            audit_path,
            model_id=str(checkpoint["model_id"]),
            training_report_id=str(report["report_id"]),
            split_manifest=split,
            validation_dataset_id=str(report["validation_dataset_id"]),
        )


def _policy_summary(victories: int, denominator: int) -> dict[str, Any]:
    return {
        "benchmark_denominator": denominator,
        "completed_runs": denominator,
        "failed_runs": 0,
        "terminal_runs": denominator,
        "truncated_runs": 0,
        "victories": victories,
        "victory_rate": victories / denominator,
        "completion_rate": 1.0,
        "terminal_rate": 1.0,
        "mean_maximum_floor": 10.0,
        "decisions": 1000,
        "total_decision_seconds": 10.0,
        "mean_seconds_per_decision": 0.01,
        "nondegenerate_terminal_outcomes": 0 < victories < denominator,
        "policy_cycle_runs": 0,
        "decision_limit_runs": 0,
        "liveness_pass": True,
        "fallback_runs": 0,
        "fallback_invocations": 0,
        "suppressed_no_op_actions": 0,
        "fallback_exhausted_states": 0,
    }
