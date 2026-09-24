from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from jsonschema import Draft202012Validator

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.cli import main
from spireshift.core.manifest import manifest_identifier
from spireshift.production_inference import (
    load_production_inference_smoke,
    run_production_inference_smoke,
    write_production_inference_smoke,
)
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
    references = []
    case_count = 4 if dataset_label == "train" else 2
    unique_seed_cases = []
    seen_seeds: set[int] = set()
    for state_case in state_set["cases"]:
        seed = int(state_case["run_seed"])
        if seed not in seen_seeds:
            unique_seed_cases.append(state_case)
            seen_seeds.add(seed)
        if len(unique_seed_cases) == case_count:
            break
    for offset, state_case in enumerate(unique_seed_cases):
        case = {
            "status": "completed",
            "record": {
                "state_id": f"{dataset_label}-state-{offset}",
                "run_seed": int(state_case["run_seed"]),
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
        relative_path = f"cases/case-{offset}.json"
        case_path = root / relative_path
        case_path.parent.mkdir(parents=True, exist_ok=True)
        case_path.write_text(json.dumps(case), encoding="utf-8")
        references.append({"path": relative_path})
    dataset_id = manifest_identifier({"synthetic_curriculum": dataset_label})
    report = {
        "dataset_id": dataset_id,
        "state_set": state_set,
        "signal_assessment": {"auxiliary_policy_signal_pass": True},
        "summary": {"terminal_victories": 0},
        "cases": references,
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
        learning_rate=0.005,
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
    history = cast(list[dict[str, Any]], result.report["training_history"])
    assert (
        history[-1]["selection"]["policy_pairwise_cross_entropy"]
        < history[0]["selection"]["policy_pairwise_cross_entropy"]
    )
    selected_epochs = result.report["model_selection"]["selected_epochs"]
    assert 1 <= selected_epochs["policy"] <= _config().epochs
    assert (
        selected_epochs["policy"]
        == min(
            history,
            key=lambda item: item["selection"]["policy_pairwise_cross_entropy"],
        )["epoch"]
    )
    assert (
        selected_epochs["soft_target_baseline"]
        == min(
            history,
            key=lambda item: item["selection"]["soft_target_pairwise_cross_entropy"],
        )["epoch"]
    )
    selection = result.report["model_selection"]
    assert set(selection["fit_runs"]).isdisjoint(selection["selection_runs"])
    assert len(selection["fit_runs"]) + len(selection["selection_runs"]) == 4
    policy_weights = result.checkpoint["heads"]["policy"]["weights"]
    assert max(abs(weight["value"]) for weight in policy_weights) < 1.0
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

    checkpoint_schema = json.loads(Path("schemas/production-model-checkpoint-v2.json").read_text())
    report_schema = json.loads(Path("schemas/production-model-training-report-v2.json").read_text())
    Draft202012Validator(checkpoint_schema).validate(result.checkpoint)
    Draft202012Validator(report_schema).validate(result.report)

    tampered = copy.deepcopy(result.checkpoint)
    tampered["heads"]["tactical_death_risk"]["bias"] += 0.1
    with pytest.raises(ValueError, match="identity mismatch"):
        production_model_from_checkpoint(tampered)

    legacy = copy.deepcopy(result.checkpoint)
    legacy["schema_version"] = "production-model-checkpoint-v1"
    legacy["model_type"] = "sparse-pairwise-curriculum-multihead-v1"
    for field in (
        "optimizer_id",
        "adagrad_epsilon",
        "selection_fraction",
        "selection_salt",
    ):
        del legacy["training_config"][field]
    legacy_body = {key: value for key, value in legacy.items() if key != "model_id"}
    legacy["model_id"] = manifest_identifier(legacy_body)
    assert production_model_from_checkpoint(legacy).predict(representation).source_action_ids


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


def test_production_policy_aligns_candidates_and_writes_bounded_smoke(
    synthetic_curricula: tuple[Path, Path], tmp_path: Path
) -> None:
    train, validation = synthetic_curricula
    result = train_production_base_model(
        train_report_path=train,
        validation_report_path=validation,
        split_manifest=load_split_manifest(SPLIT_PATH),
        config=_config(),
    )
    environment = MockSpireEnvironment()
    checkpoint = copy.deepcopy(result.checkpoint)
    checkpoint["ruleset_manifest_id"] = environment.ruleset.manifest_id
    checkpoint_body = {key: value for key, value in checkpoint.items() if key != "model_id"}
    checkpoint["model_id"] = manifest_identifier(checkpoint_body)
    report = copy.deepcopy(result.report)
    report["model_id"] = checkpoint["model_id"]
    report["held_out_metrics"]["policy"]["auxiliary_policy_gate"]["passed"] = True
    report_body = {key: value for key, value in report.items() if key != "report_id"}
    report["report_id"] = manifest_identifier(report_body)
    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "training-report.json"
    write_production_model_artifact(checkpoint, checkpoint_path, label="production checkpoint")
    write_production_model_artifact(report, report_path, label="production report")

    policy = ProductionCheckpointPolicy.from_paths(
        checkpoint_path,
        report_path,
        ruleset=environment.ruleset,
    )
    observation = environment.reset(3)
    actions = tuple(environment.legal_actions())
    decision = policy.predict(observation, actions)
    assert decision.source_action_ids == tuple(action.action_id for action in actions)
    assert decision.selected_action in actions
    assert sum(decision.policy) == pytest.approx(1.0)
    assert decision.inference_seconds >= 0.0

    smoke = run_production_inference_smoke(
        environment=environment,
        policy=policy,
        training_report_id=cast(str, report["report_id"]),
        seeds=(3, 4),
        maximum_decisions_per_seed=2,
    )
    assert smoke["summary"]["candidate_alignment_pass"] is True
    assert smoke["summary"]["legal_selection_pass"] is True
    assert 2 <= smoke["summary"]["decisions"] <= 4
    assert all(
        record["selected_action_id"] in record["candidate_action_ids"]
        for record in smoke["records"]
    )
    schema = json.loads(Path("schemas/production-model-inference-smoke-v1.json").read_text())
    Draft202012Validator(schema).validate(smoke)

    smoke_path = tmp_path / "smoke.json"
    write_production_inference_smoke(smoke, smoke_path)
    assert (
        load_production_inference_smoke(
            smoke_path,
            model_id=cast(str, checkpoint["model_id"]),
            training_report_id=cast(str, report["report_id"]),
        )
        == smoke
    )
    verification_path = tmp_path / "smoke-verification.json"
    assert (
        main(
            [
                "model",
                "verify-curriculum-smoke",
                str(smoke_path),
                str(checkpoint_path),
                "--report",
                str(report_path),
                "--output",
                str(verification_path),
            ]
        )
        == 0
    )
    assert json.loads(verification_path.read_text())["valid"] is True
    tampered = copy.deepcopy(smoke)
    tampered["records"][0]["selected_action_id"] = "illegal"
    smoke_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="identity mismatch"):
        load_production_inference_smoke(smoke_path)
    tampered_body = {key: value for key, value in tampered.items() if key != "report_id"}
    tampered["report_id"] = manifest_identifier(tampered_body)
    smoke_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="not candidate-aligned"):
        load_production_inference_smoke(smoke_path)


def test_production_policy_rejects_unadmitted_auxiliary_gate(
    synthetic_curricula: tuple[Path, Path],
) -> None:
    train, validation = synthetic_curricula
    result = train_production_base_model(
        train_report_path=train,
        validation_report_path=validation,
        split_manifest=load_split_manifest(SPLIT_PATH),
        config=_config(),
    )
    environment = MockSpireEnvironment()
    checkpoint = copy.deepcopy(result.checkpoint)
    checkpoint["ruleset_manifest_id"] = environment.ruleset.manifest_id
    checkpoint_body = {key: value for key, value in checkpoint.items() if key != "model_id"}
    checkpoint["model_id"] = manifest_identifier(checkpoint_body)
    report = copy.deepcopy(result.report)
    report["model_id"] = checkpoint["model_id"]

    with pytest.raises(ValueError, match="did not pass"):
        ProductionCheckpointPolicy(
            checkpoint=checkpoint,
            training_report=report,
            ruleset=environment.ruleset,
        )
