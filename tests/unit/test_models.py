from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.models import (
    TrainingConfig,
    load_model_checkpoint,
    load_training_report,
    model_from_checkpoint,
    train_initial_models,
    write_model_artifact,
)
from spireshift.representations import model_input_from_mapping
from spireshift.splits import SplitName, load_split_manifest
from spireshift.teacher_data import (
    TeacherConfig,
    generate_mock_teacher_dataset,
    write_teacher_dataset,
)

SPLIT_MANIFEST_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
OBJECTIVE_PATH = Path("configs/default.toml")
CHECKPOINT_FIXTURE_PATH = Path("tests/fixtures/model-checkpoint-v1.json")
REPORT_FIXTURE_PATH = Path("tests/fixtures/model-training-report-v1.json")


def _training_config(*, epochs: int = 80) -> TrainingConfig:
    return TrainingConfig(
        epochs=epochs,
        learning_rate=0.03,
        vector_dimension=256,
        interaction_dimension=512,
    )


@lru_cache(maxsize=1)
def _datasets() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_split_manifest(SPLIT_MANIFEST_PATH)
    objective = load_objective(OBJECTIVE_PATH)
    teacher_config = TeacherConfig(
        search_simulations=16,
        evaluation_samples_per_candidate=16,
    )
    train = generate_mock_teacher_dataset(
        seeds=manifest.seeds(SplitName.TRAIN)[:12],
        partition=SplitName.TRAIN,
        split_manifest=manifest,
        objective=objective,
        config=teacher_config,
    )
    validation = generate_mock_teacher_dataset(
        seeds=manifest.seeds(SplitName.VALIDATION)[:8],
        partition=SplitName.VALIDATION,
        split_manifest=manifest,
        objective=objective,
        config=teacher_config,
    )
    return train, validation


@lru_cache(maxsize=1)
def _result() -> tuple[dict[str, Any], dict[str, Any]]:
    train, validation = _datasets()
    result = train_initial_models(
        train_dataset=train,
        validation_dataset=validation,
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        config=_training_config(),
    )
    return result.checkpoint, result.report


def test_model_input_fixture_deserializes_without_changing_features() -> None:
    document = json.loads(Path("tests/fixtures/model-input-v1.json").read_text())

    representation = model_input_from_mapping(document)

    assert representation.as_dict() == document
    tampered = copy.deepcopy(document)
    tampered["patch_id"] = "tampered-patch"
    with pytest.raises(ValueError, match="representation hash mismatch"):
        model_input_from_mapping(tampered)


def test_training_is_deterministic_and_all_three_losses_improve() -> None:
    checkpoint, report = _result()
    train, validation = _datasets()
    repeated = train_initial_models(
        train_dataset=train,
        validation_dataset=validation,
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        config=_training_config(),
    )

    assert checkpoint == repeated.checkpoint
    assert report == repeated.report
    history = cast(list[dict[str, float]], report["training_history"])
    assert history[-1]["policy_cross_entropy"] < history[0]["policy_cross_entropy"]
    assert history[-1]["run_value_cross_entropy"] < history[0]["run_value_cross_entropy"]
    assert history[-1]["tactical_risk_cross_entropy"] < history[0]["tactical_risk_cross_entropy"]
    assert checkpoint["model_id"] == manifest_identifier(
        {key: value for key, value in checkpoint.items() if key != "model_id"}
    )
    assert report["report_id"] == manifest_identifier(
        {key: value for key, value in report.items() if key != "report_id"}
    )


def test_held_out_report_includes_agreement_regret_and_calibration() -> None:
    _, report = _result()
    metrics = cast(dict[str, Any], report["held_out_metrics"])

    assert metrics["policy"]["action_agreement"] >= 0.85
    assert metrics["policy"]["mean_independent_value_regret"] == 0.0
    assert metrics["policy"]["p95_independent_value_regret"] == 0.0
    assert 0.0 <= metrics["run_value"]["brier_score"] <= 1.0
    assert 0.0 <= metrics["run_value"]["expected_calibration_error"] <= 1.0
    assert metrics["run_value"]["samples"] > report["validation_records"]
    assert 0.0 <= metrics["tactical_death_risk"]["brier_score"] <= 1.0
    assert metrics["tactical_death_risk"]["samples"] > metrics["run_value"]["samples"]
    assert report["claim_scope"] == "mock_pipeline_validation"
    assert report["data_provenance"]["train"]["partition"] == "train"
    assert report["data_provenance"]["validation"]["partition"] == "validation"


def test_checkpoint_round_trip_preserves_candidate_aligned_predictions() -> None:
    checkpoint, _ = _result()
    model = model_from_checkpoint(checkpoint)
    _, validation = _datasets()
    first_record = cast(list[dict[str, Any]], validation["records"])[0]
    representation = model_input_from_mapping(first_record["model_input"])

    prediction = model.predict(representation)

    assert prediction.source_action_ids == tuple(
        candidate["source_action_id"] for candidate in first_record["teacher_target"]["candidates"]
    )
    assert sum(prediction.policy) == pytest.approx(1.0)
    assert all(0.0 <= probability <= 1.0 for probability in prediction.policy)
    assert 0.0 <= prediction.run_value <= 1.0
    assert all(0.0 <= risk <= 1.0 for risk in prediction.tactical_death_risk)


def test_training_refuses_partition_reuse() -> None:
    train, validation = _datasets()

    with pytest.raises(ValueError, match="train-partition"):
        train_initial_models(
            train_dataset=validation,
            validation_dataset=validation,
            split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
            config=_training_config(epochs=1),
        )
    with pytest.raises(ValueError, match="validation-partition"):
        train_initial_models(
            train_dataset=train,
            validation_dataset=train,
            split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
            config=_training_config(epochs=1),
        )


def test_checked_model_artifacts_are_reproducible_and_tamper_evident(tmp_path: Path) -> None:
    checkpoint, report = _result()
    checked_checkpoint = json.loads(CHECKPOINT_FIXTURE_PATH.read_text(encoding="utf-8"))
    checked_report = json.loads(REPORT_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert checkpoint == checked_checkpoint
    assert report == checked_report

    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "report.json"
    write_model_artifact(checkpoint, checkpoint_path, label="model checkpoint")
    write_model_artifact(report, report_path, label="model training report")
    assert load_model_checkpoint(checkpoint_path) == checkpoint
    assert load_training_report(report_path, checkpoint=checkpoint) == report

    tampered = copy.deepcopy(checkpoint)
    tampered["heads"]["run_value"]["bias"] += 0.1
    with pytest.raises(ValueError, match="identity mismatch"):
        model_from_checkpoint(tampered)

    checkpoint_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_model_artifact(checkpoint, checkpoint_path, label="model checkpoint")


def test_cli_trains_and_verifies_model_artifacts(tmp_path: Path) -> None:
    train, validation = _datasets()
    train_path = tmp_path / "train.json"
    validation_path = tmp_path / "validation.json"
    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "report.json"
    verification_path = tmp_path / "verification.json"
    write_teacher_dataset(train, train_path)
    write_teacher_dataset(validation, validation_path)

    trained = main(
        [
            "model",
            "train",
            str(train_path),
            str(validation_path),
            str(checkpoint_path),
            "--report",
            str(report_path),
            "--epochs",
            "20",
            "--vector-dimension",
            "256",
            "--interaction-dimension",
            "512",
        ]
    )
    verified = main(
        [
            "model",
            "verify",
            str(checkpoint_path),
            "--report",
            str(report_path),
            "--output",
            str(verification_path),
        ]
    )

    assert trained == 0
    assert verified == 0
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    assert verification["valid"] is True
    assert verification["model_id"].startswith("sha256:")
    assert verification["report_id"].startswith("sha256:")
