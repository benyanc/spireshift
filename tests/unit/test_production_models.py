from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.production_models import (
    ProductionTrainingConfig,
    load_production_model_checkpoint,
    load_production_training_report,
    production_model_from_checkpoint,
    train_production_base_model,
    write_production_model_artifact,
)
from spireshift.representations import model_input_from_mapping
from spireshift.splits import load_split_manifest

SPLIT_PATH = Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
TRAIN_STATE_SET_PATH = Path("manifests/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json")
VALIDATION_STATE_SET_PATH = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json"
)


def _write_synthetic_curriculum(
    root: Path,
    *,
    state_set_path: Path,
    dataset_label: str,
) -> Path:
    state_set = json.loads(state_set_path.read_text(encoding="utf-8"))
    representation = json.loads(Path("tests/fixtures/model-input-v1.json").read_text())
    candidates = cast(list[dict[str, Any]], representation["candidates"])
    candidate_count = len(candidates)
    preference_matrix = [
        [0.5 if left == right else float(left < right) for right in range(candidate_count)]
        for left in range(candidate_count)
    ]
    raw_weights = [float(candidate_count - index) for index in range(candidate_count)]
    weight_total = sum(raw_weights)
    target_candidates = []
    for index, candidate in enumerate(candidates):
        target_candidates.append(
            {
                "source_action_id": candidate["source_action_id"],
                "mean_progress_utility": (candidate_count - index) / candidate_count,
                "outcomes": [
                    {
                        "maximum_floor": candidate_count - index,
                        "terminal": True,
                        "victory": False,
                        "transitions": index + 1,
                    }
                    for _ in range(4)
                ],
            }
        )
    run_seed = int(state_set["cases"][0]["run_seed"])
    case = {
        "status": "completed",
        "record": {
            "state_id": f"{dataset_label}-state",
            "run_seed": run_seed,
            "decision_type": "combat",
            "model_input": representation,
            "target": {
                "candidates": target_candidates,
                "paired_preference_matrix": preference_matrix,
                "soft_policy_target": [weight / weight_total for weight in raw_weights],
                "policy_target_weight": 0.75,
                "half_split_winner_agreement": True,
                "selected_candidate_index": 0,
            },
        },
    }
    case_path = root / "cases" / "case.json"
    case_path.parent.mkdir(parents=True)
    case_path.write_text(json.dumps(case), encoding="utf-8")
    dataset_id = manifest_identifier({"synthetic_curriculum": dataset_label})
    report = {
        "dataset_id": dataset_id,
        "state_set": state_set,
        "signal_assessment": {"auxiliary_policy_signal_pass": True},
        "summary": {"terminal_victories": 0},
        "cases": [{"path": "cases/case.json"}],
    }
    report_path = root / "bootstrap-teacher-dataset.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    return report_path


@pytest.fixture
def synthetic_curricula(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setattr(
        "spireshift.production_models.verify_bootstrap_teacher_dataset",
        lambda *_args, **_kwargs: SimpleNamespace(valid=True, errors=()),
    )
    train = _write_synthetic_curriculum(
        tmp_path / "train",
        state_set_path=TRAIN_STATE_SET_PATH,
        dataset_label="train",
    )
    validation = _write_synthetic_curriculum(
        tmp_path / "validation",
        state_set_path=VALIDATION_STATE_SET_PATH,
        dataset_label="validation",
    )
    return train, validation


def _config() -> ProductionTrainingConfig:
    return ProductionTrainingConfig(
        epochs=12,
        learning_rate=0.03,
        vector_dimension=128,
        interaction_dimension=256,
        tactical_horizon=4,
    )


def test_pairwise_curriculum_training_is_deterministic_and_reports_baseline(
    synthetic_curricula: tuple[Path, Path],
) -> None:
    train, validation = synthetic_curricula
    split = load_split_manifest(SPLIT_PATH)

    result = train_production_base_model(
        train_report_path=train,
        validation_report_path=validation,
        split_manifest=split,
        config=_config(),
    )
    repeated = train_production_base_model(
        train_report_path=train,
        validation_report_path=validation,
        split_manifest=split,
        config=_config(),
    )

    assert result == repeated
    history = cast(list[dict[str, float]], result.report["training_history"])
    assert (
        history[-1]["pairwise_policy_cross_entropy"] < history[0]["pairwise_policy_cross_entropy"]
    )
    assert (
        history[-1]["soft_target_baseline_cross_entropy"]
        < history[0]["soft_target_baseline_cross_entropy"]
    )
    policy_metrics = cast(
        dict[str, Any], cast(dict[str, Any], result.report["held_out_metrics"])["policy"]
    )
    assert policy_metrics["decisive_pairs"] > 0
    assert "soft_target_baseline" in policy_metrics
    assert set(policy_metrics["auxiliary_policy_gate"]["checks"]) == {
        "pairwise_cross_entropy_below_uniform",
        "decisive_pair_accuracy_above_chance",
        "regret_below_source_order",
        "pairwise_cross_entropy_below_soft_target",
    }
    assert result.report["terminal_value_status"] == {
        "promoted": False,
        "reason": "all_zero_terminal_victory_evidence",
        "train_victories": 0,
        "validation_victories": 0,
    }


def test_production_checkpoint_round_trip_and_schemas(
    synthetic_curricula: tuple[Path, Path], tmp_path: Path
) -> None:
    train, validation = synthetic_curricula
    result = train_production_base_model(
        train_report_path=train,
        validation_report_path=validation,
        split_manifest=load_split_manifest(SPLIT_PATH),
        config=_config(),
    )
    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "report.json"
    write_production_model_artifact(
        result.checkpoint, checkpoint_path, label="production checkpoint"
    )
    write_production_model_artifact(result.report, report_path, label="production report")

    checkpoint = load_production_model_checkpoint(checkpoint_path)
    assert load_production_training_report(report_path, checkpoint=checkpoint) == result.report
    model = production_model_from_checkpoint(checkpoint)
    representation = model_input_from_mapping(
        json.loads(Path("tests/fixtures/model-input-v1.json").read_text())
    )
    prediction = model.predict(representation)
    assert sum(prediction.policy) == pytest.approx(1.0)
    assert prediction.terminal_value is None
    assert prediction.maximum_floor_reach

    checkpoint_schema = json.loads(Path("schemas/production-model-checkpoint-v1.json").read_text())
    report_schema = json.loads(Path("schemas/production-model-training-report-v1.json").read_text())
    Draft202012Validator(checkpoint_schema).validate(result.checkpoint)
    Draft202012Validator(report_schema).validate(result.report)

    tampered = copy.deepcopy(result.checkpoint)
    tampered["heads"]["tactical_death_risk"]["bias"] += 0.1
    with pytest.raises(ValueError, match="identity mismatch"):
        production_model_from_checkpoint(tampered)


def test_production_cli_trains_and_verifies(
    synthetic_curricula: tuple[Path, Path], tmp_path: Path
) -> None:
    train, validation = synthetic_curricula
    checkpoint = tmp_path / "cli-checkpoint.json"
    report = tmp_path / "cli-report.json"
    verification = tmp_path / "verification.json"

    trained = main(
        [
            "model",
            "train-curriculum",
            str(train),
            str(validation),
            str(checkpoint),
            "--report",
            str(report),
            "--split-manifest",
            str(SPLIT_PATH),
            "--epochs",
            "3",
            "--vector-dimension",
            "128",
            "--interaction-dimension",
            "256",
        ]
    )
    verified = main(
        [
            "model",
            "verify-curriculum",
            str(checkpoint),
            "--report",
            str(report),
            "--output",
            str(verification),
        ]
    )

    assert trained == 0
    assert verified == 0
    assert json.loads(verification.read_text())["valid"] is True
