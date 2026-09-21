from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.cli import main
from spireshift.core.objective import load_objective
from spireshift.dagger import (
    DaggerConfig,
    dagger_dataset_index,
    generate_mock_dagger_iteration,
    selected_relabel_records,
    verify_mock_dagger_iteration,
    write_dagger_iteration,
)
from spireshift.models import TrainingConfig, train_initial_models
from spireshift.splits import SplitName, audit_dataset_index_document, load_split_manifest
from spireshift.teacher_data import (
    TeacherConfig,
    generate_mock_teacher_dataset,
    write_teacher_dataset,
)

SPLIT_MANIFEST_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
OBJECTIVE_PATH = Path("configs/default.toml")
CHECKPOINT_PATH = Path("tests/fixtures/model-checkpoint-v1.json")
ITERATION_FIXTURE_PATH = Path("tests/fixtures/dagger-iteration-v1.json")
VERIFICATION_FIXTURE_PATH = Path("tests/fixtures/dagger-verification-v1.json")
INDEX_FIXTURE_PATH = Path("tests/fixtures/dagger-dataset-index-v1.json")
AUGMENTED_CHECKPOINT_PATH = Path("tests/fixtures/model-checkpoint-dagger-v1.json")
AUGMENTED_REPORT_PATH = Path("tests/fixtures/model-training-report-dagger-v1.json")


def _config() -> DaggerConfig:
    return DaggerConfig(
        probe_teacher=TeacherConfig(
            search_simulations=4,
            evaluation_samples_per_candidate=4,
            sampling_seed=3,
        ),
        relabel_teacher=TeacherConfig(
            search_simulations=16,
            evaluation_samples_per_candidate=16,
            sampling_seed=23,
        ),
        rare_state_max_fraction=0.4,
        high_entropy_threshold=0.95,
        confident_error_threshold=0.65,
        confident_error_regret=0.25,
    )


@lru_cache(maxsize=1)
def _reference_and_validation() -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = load_split_manifest(SPLIT_MANIFEST_PATH)
    objective = load_objective(OBJECTIVE_PATH)
    teacher = TeacherConfig(search_simulations=16, evaluation_samples_per_candidate=16)
    reference = generate_mock_teacher_dataset(
        seeds=manifest.seeds(SplitName.TRAIN)[:12],
        partition=SplitName.TRAIN,
        split_manifest=manifest,
        objective=objective,
        config=teacher,
    )
    validation = generate_mock_teacher_dataset(
        seeds=manifest.seeds(SplitName.VALIDATION)[:8],
        partition=SplitName.VALIDATION,
        split_manifest=manifest,
        objective=objective,
        config=teacher,
    )
    return reference, validation


def _checkpoint() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _iteration() -> dict[str, Any]:
    reference, _ = _reference_and_validation()
    return generate_mock_dagger_iteration(
        iteration_index=0,
        seeds=(13, 15, 16),
        partition=SplitName.TRAIN,
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        objective=load_objective(OBJECTIVE_PATH),
        source_checkpoint=_checkpoint(),
        reference_dataset=reference,
        config=_config(),
    )


def _outcome_seeds(target: dict[str, Any]) -> set[int]:
    return {
        int(outcome["simulation_seed"])
        for candidate in target["candidates"]
        for estimate_name in ("search", "independent_evaluation")
        for outcome in candidate[estimate_name]["outcomes"]
    }


def test_iteration_runs_student_on_policy_and_selectively_relabels() -> None:
    iteration = _iteration()
    records = cast(list[dict[str, Any]], iteration["records"])
    summary = iteration["summary"]

    assert summary == {
        "runs": 3,
        "decisions": 6,
        "candidates": 9,
        "victories": 3,
        "defeats": 0,
        "selected_for_relabel": 4,
        "relabels_avoided": 2,
        "selection_reason_counts": {
            "teacher_disagreement": 1,
            "rare_state": 3,
            "confident_error": 1,
            "high_entropy": 0,
        },
        "probe_search_simulations": 24,
        "probe_evaluation_simulations": 36,
        "relabel_search_simulations": 64,
        "relabel_evaluation_simulations": 80,
    }
    assert len(selected_relabel_records(iteration)) == 4
    assert any(not record["selected_for_relabel"] for record in records)
    assert all(
        (record["relabel_target"] is not None) == record["selected_for_relabel"]
        for record in records
    )
    assert {reason for record in records for reason in record["selection_reasons"]} == {
        "teacher_disagreement",
        "rare_state",
        "confident_error",
    }
    assert all(
        record["observed_transition"]["selected_action_id"]
        == record["student_prediction"]["selected_action_id"]
        for record in records
    )


def test_complete_run_ownership_and_teacher_sample_domains_are_preserved() -> None:
    iteration = _iteration()
    records = cast(list[dict[str, Any]], iteration["records"])
    by_run: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_run.setdefault(record["run_id"], []).append(record)
        if record["relabel_target"] is not None:
            assert _outcome_seeds(record["probe_teacher_target"]).isdisjoint(
                _outcome_seeds(record["relabel_target"])
            )
    for run in iteration["runs"]:
        run_records = sorted(by_run[run["run_id"]], key=lambda item: item["decision_index"])
        assert [record["decision_index"] for record in run_records] == list(range(len(run_records)))
        assert run["record_ids"] == [record["record_id"] for record in run_records]
        assert run_records[-1]["observed_transition"]["terminal"] is True


def test_checked_iteration_is_reproducible_and_tamper_evident(tmp_path: Path) -> None:
    iteration = _iteration()
    checked = json.loads(ITERATION_FIXTURE_PATH.read_text(encoding="utf-8"))
    reference, _ = _reference_and_validation()
    verification = verify_mock_dagger_iteration(
        iteration,
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        source_checkpoint=_checkpoint(),
        reference_dataset=reference,
    )

    assert iteration == checked
    assert verification.valid, verification.errors
    assert verification.as_dict() == json.loads(
        VERIFICATION_FIXTURE_PATH.read_text(encoding="utf-8")
    )
    index = dagger_dataset_index(iteration, load_split_manifest(SPLIT_MANIFEST_PATH))
    assert index == json.loads(INDEX_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert audit_dataset_index_document(index, load_split_manifest(SPLIT_MANIFEST_PATH)).valid
    output = tmp_path / "iteration.json"
    write_dagger_iteration(iteration, output)
    write_dagger_iteration(iteration, output)
    output.write_text("{}\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_dagger_iteration(iteration, output)

    tampered = copy.deepcopy(iteration)
    tampered["records"][0]["student_prediction"]["selected_action_id"] = "tampered"
    rejected = verify_mock_dagger_iteration(
        tampered,
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        source_checkpoint=_checkpoint(),
        reference_dataset=reference,
    )
    assert not rejected.valid
    assert "iteration identity mismatch" in rejected.errors


def test_collection_rejects_split_leakage_and_reference_seed_reuse() -> None:
    reference, _ = _reference_and_validation()
    with pytest.raises(ValueError, match="not in the frozen train partition"):
        generate_mock_dagger_iteration(
            iteration_index=0,
            seeds=(1,),
            partition=SplitName.TRAIN,
            split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
            objective=load_objective(OBJECTIVE_PATH),
            source_checkpoint=_checkpoint(),
            reference_dataset=reference,
            config=_config(),
        )
    with pytest.raises(ValueError, match="must be new train runs"):
        generate_mock_dagger_iteration(
            iteration_index=0,
            seeds=(0,),
            partition=SplitName.TRAIN,
            split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
            objective=load_objective(OBJECTIVE_PATH),
            source_checkpoint=_checkpoint(),
            reference_dataset=reference,
            config=_config(),
        )


def test_selected_labels_augment_the_next_model_checkpoint() -> None:
    reference, validation = _reference_and_validation()
    iteration = _iteration()
    result = train_initial_models(
        train_dataset=reference,
        validation_dataset=validation,
        split_manifest=load_split_manifest(SPLIT_MANIFEST_PATH),
        config=TrainingConfig(
            epochs=10,
            vector_dimension=256,
            interaction_dimension=512,
        ),
        augmentation_iterations=((iteration, _checkpoint()),),
    )

    assert result.checkpoint["augmentation_iteration_ids"] == [iteration["iteration_id"]]
    assert result.report["base_training_records"] == 21
    assert result.report["augmentation_records"] == 4
    assert result.report["training_records"] == 25
    assert result.report["data_provenance"]["augmentations"] == [
        {
            "iteration_id": iteration["iteration_id"],
            "iteration_index": 0,
            "source_model_id": iteration["source_model_id"],
            "runs": 3,
            "decisions": 6,
            "selected_records": 4,
        }
    ]
    assert result.checkpoint == json.loads(AUGMENTED_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    assert result.report == json.loads(AUGMENTED_REPORT_PATH.read_text(encoding="utf-8"))


def test_cli_collects_verifies_and_trains_with_iteration(tmp_path: Path) -> None:
    reference, validation = _reference_and_validation()
    reference_path = tmp_path / "reference.json"
    validation_path = tmp_path / "validation.json"
    iteration_path = tmp_path / "iteration.json"
    verification_path = tmp_path / "verification.json"
    checkpoint_path = tmp_path / "augmented-checkpoint.json"
    report_path = tmp_path / "augmented-report.json"
    write_teacher_dataset(reference, reference_path)
    write_teacher_dataset(validation, validation_path)

    collected = main(
        [
            "dagger",
            "collect-mock",
            str(CHECKPOINT_PATH),
            str(reference_path),
            str(iteration_path),
            "--seeds",
            "13",
            "15",
            "16",
            "--probe-search-simulations",
            "4",
            "--probe-evaluation-samples",
            "4",
            "--probe-sampling-seed",
            "3",
            "--relabel-search-simulations",
            "16",
            "--relabel-evaluation-samples",
            "16",
            "--relabel-sampling-seed",
            "23",
            "--rare-state-max-fraction",
            "0.4",
            "--high-entropy-threshold",
            "0.95",
            "--confident-error-threshold",
            "0.65",
            "--confident-error-regret",
            "0.25",
        ]
    )
    verified = main(
        [
            "dagger",
            "verify",
            str(iteration_path),
            str(CHECKPOINT_PATH),
            str(reference_path),
            "--output",
            str(verification_path),
        ]
    )
    trained = main(
        [
            "model",
            "train",
            str(reference_path),
            str(validation_path),
            str(checkpoint_path),
            "--report",
            str(report_path),
            "--epochs",
            "5",
            "--vector-dimension",
            "256",
            "--interaction-dimension",
            "512",
            "--augmentation",
            str(iteration_path),
            str(CHECKPOINT_PATH),
        ]
    )

    assert collected == 0
    assert verified == 0
    assert trained == 0
    assert (tmp_path / "iteration-index.json").is_file()
    assert json.loads(verification_path.read_text(encoding="utf-8"))["valid"] is True
    augmented = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert augmented["augmentation_iteration_ids"] == [_iteration()["iteration_id"]]
