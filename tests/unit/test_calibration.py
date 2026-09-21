from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.calibration import (
    CalibrationConfig,
    calibrate_model,
    calibrated_model_from_artifacts,
    calibration_subfolds,
    load_calibration_artifact,
    load_calibration_report,
    verify_calibration_artifacts,
    write_calibration_artifact,
)
from spireshift.cli import main
from spireshift.core.objective import load_objective
from spireshift.models import load_model_checkpoint
from spireshift.representations import model_input_from_mapping
from spireshift.splits import SplitName, load_split_manifest
from spireshift.teacher_data import (
    TeacherConfig,
    generate_mock_teacher_dataset,
    write_teacher_dataset,
)

SPLIT_MANIFEST_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
OBJECTIVE_PATH = Path("configs/default.toml")
CHECKPOINT_PATH = Path("tests/fixtures/model-checkpoint-v1.json")
CALIBRATION_FIXTURE_PATH = Path("tests/fixtures/model-calibration-v1.json")
REPORT_FIXTURE_PATH = Path("tests/fixtures/model-calibration-report-v1.json")


@lru_cache(maxsize=1)
def _validation_dataset() -> dict[str, Any]:
    manifest = load_split_manifest(SPLIT_MANIFEST_PATH)
    return generate_mock_teacher_dataset(
        seeds=manifest.seeds(SplitName.VALIDATION)[:8],
        partition=SplitName.VALIDATION,
        split_manifest=manifest,
        objective=load_objective(OBJECTIVE_PATH),
        config=TeacherConfig(
            search_simulations=16,
            evaluation_samples_per_candidate=16,
        ),
    )


@lru_cache(maxsize=1)
def _result() -> tuple[dict[str, Any], dict[str, Any]]:
    result = calibrate_model(
        checkpoint=load_model_checkpoint(CHECKPOINT_PATH),
        validation_dataset=_validation_dataset(),
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
    )
    return result.calibration, result.report


def test_calibration_uses_disjoint_complete_run_subfolds_deterministically() -> None:
    checkpoint = load_model_checkpoint(CHECKPOINT_PATH)
    dataset = _validation_dataset()

    first = calibration_subfolds(
        dataset,
        model_id=cast(str, checkpoint["model_id"]),
        fit_fraction=0.5,
        salt="calibration-v1",
    )
    second = calibration_subfolds(
        dataset,
        model_id=cast(str, checkpoint["model_id"]),
        fit_fraction=0.5,
        salt="calibration-v1",
    )
    all_run_ids = {run["run_id"] for run in dataset["runs"]}

    assert first == second
    assert not first[0] & first[1]
    assert first[0] | first[1] == all_run_ids
    assert len(first[0]) == len(first[1]) == 4


def test_report_scores_only_audit_runs_and_exposes_required_metrics() -> None:
    calibration, report = _result()
    fit_ids = set(calibration["subfold"]["fit_run_ids"])
    audit_ids = set(calibration["subfold"]["audit_run_ids"])
    records = cast(list[dict[str, Any]], report["records"])

    assert {record["run_id"] for record in records} == audit_ids
    assert not fit_ids & {record["run_id"] for record in records}
    assert report["audit"]["runs"] == 4
    for head in ("run_value", "tactical_death_risk"):
        for mode in ("raw", "calibrated"):
            metrics = report["metrics"][head][mode]
            assert 0.0 <= metrics["brier_score"] <= 1.0
            assert metrics["log_loss"] >= 0.0
            assert 0.0 <= metrics["expected_calibration_error"] <= 1.0
            assert metrics["sharpness_variance"] >= 0.0
            assert 0.0 <= metrics["normalized_confidence_sharpness"] <= 1.0
    failure = report["failure_analysis"]
    assert failure["high_confidence_catastrophic_errors"] == len(
        failure["high_confidence_catastrophic_record_ids"]
    )
    assert failure["false_safe_tactical_risk_errors"] == len(
        failure["false_safe_tactical_risk_record_ids"]
    )


def test_calibrated_inference_returns_bounded_candidate_aligned_signals() -> None:
    calibration, _ = _result()
    checkpoint = load_model_checkpoint(CHECKPOINT_PATH)
    model = calibrated_model_from_artifacts(checkpoint, calibration)
    first_record = _validation_dataset()["records"][0]

    prediction = model.predict(model_input_from_mapping(first_record["model_input"]))

    assert prediction.source_action_ids == tuple(
        candidate["source_action_id"] for candidate in first_record["teacher_target"]["candidates"]
    )
    assert len(prediction.tactical_death_risk) == len(prediction.source_action_ids)
    assert 0.0 <= prediction.run_value <= 1.0
    assert all(0.0 <= value <= 1.0 for value in prediction.tactical_death_risk)
    assert all(0.0 <= value <= 1.0 for value in prediction.uncertainty.as_dict().values())


def test_checked_calibration_artifacts_are_reproducible_and_tamper_evident(
    tmp_path: Path,
) -> None:
    calibration, report = _result()
    assert calibration == json.loads(CALIBRATION_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert report == json.loads(REPORT_FIXTURE_PATH.read_text(encoding="utf-8"))

    calibration_path = tmp_path / "calibration.json"
    report_path = tmp_path / "report.json"
    write_calibration_artifact(calibration, calibration_path, label="model calibration")
    write_calibration_artifact(report, report_path, label="model calibration report")
    loaded = load_calibration_artifact(
        calibration_path,
        checkpoint=load_model_checkpoint(CHECKPOINT_PATH),
    )
    assert loaded == calibration
    assert load_calibration_report(report_path, calibration=loaded) == report

    verification = verify_calibration_artifacts(
        calibration=calibration,
        report=report,
        checkpoint=load_model_checkpoint(CHECKPOINT_PATH),
        validation_dataset=_validation_dataset(),
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
    )
    assert verification.valid

    tampered = copy.deepcopy(calibration)
    tampered["heads"]["run_value"]["intercept"] += 0.1
    with pytest.raises(ValueError, match="identity mismatch"):
        calibrated_model_from_artifacts(load_model_checkpoint(CHECKPOINT_PATH), tampered)


def test_cli_fits_and_verifies_calibration_artifacts(tmp_path: Path) -> None:
    validation_path = tmp_path / "validation.json"
    calibration_path = tmp_path / "calibration.json"
    report_path = tmp_path / "report.json"
    verification_path = tmp_path / "verification.json"
    write_teacher_dataset(_validation_dataset(), validation_path)

    fitted = main(
        [
            "calibrate",
            "fit",
            str(CHECKPOINT_PATH),
            str(validation_path),
            str(calibration_path),
            "--report",
            str(report_path),
        ]
    )
    verified = main(
        [
            "calibrate",
            "verify",
            str(calibration_path),
            str(report_path),
            str(CHECKPOINT_PATH),
            str(validation_path),
            "--output",
            str(verification_path),
        ]
    )

    assert fitted == 0
    assert verified == 0
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    assert verification["valid"] is True
    assert verification["errors"] == []


def test_calibration_rejects_train_partition_and_too_few_runs() -> None:
    checkpoint = load_model_checkpoint(CHECKPOINT_PATH)
    train_dataset = copy.deepcopy(_validation_dataset())
    train_dataset["partition"] = "train"
    with pytest.raises(ValueError, match="verification"):
        calibrate_model(
            checkpoint=checkpoint,
            validation_dataset=train_dataset,
            split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        )

    one_run = copy.deepcopy(_validation_dataset())
    one_run["runs"] = one_run["runs"][:1]
    one_run["records"] = [
        record for record in one_run["records"] if record["run_id"] == one_run["runs"][0]["run_id"]
    ]
    with pytest.raises(ValueError, match="at least two complete validation runs"):
        calibration_subfolds(
            one_run,
            model_id=cast(str, checkpoint["model_id"]),
            fit_fraction=CalibrationConfig().fit_fraction,
            salt=CalibrationConfig().split_salt,
        )
