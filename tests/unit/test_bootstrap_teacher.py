from __future__ import annotations

import json
from pathlib import Path

import pytest

from spireshift.agents.baseline import ProgressBootstrapPolicy
from spireshift.bootstrap_teacher import (
    BootstrapConfig,
    BootstrapStateSet,
    CurriculumStateSet,
    bootstrap_utility,
    capture_bootstrap_combat_state,
    capture_curriculum_state,
    discover_curriculum_state_set,
    freeze_bootstrap_state_set,
    load_bootstrap_state_set,
    load_bootstrap_state_set_document,
    load_curriculum_policy_examples,
    run_bootstrap_teacher_dataset,
    verify_bootstrap_teacher_dataset,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.core.types import DecisionType
from spireshift.rollouts import sha256_file
from spireshift.search_workers import SearchBackendSpec
from spireshift.splits import SplitManifest, SplitName, freeze_split_manifest, load_split_manifest

PRODUCTION_SPLIT = Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
PRODUCTION_STATE_SET = Path("manifests/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json")
PRODUCTION_STATE_SPECIFICATION = Path(
    "configs/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json"
)
PRODUCTION_TRAIN_CURRICULUM = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json"
)
PRODUCTION_VALIDATION_CURRICULUM = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json"
)


def _tactical_split(ruleset_manifest_id: str) -> SplitManifest:
    return freeze_split_manifest(
        {
            "schema_version": "split-manifest-v1",
            "split_id": "tactical-bootstrap-train-v1",
            "ruleset_manifest_id": ruleset_manifest_id,
            "objective_id": "terminal-victory-v1",
            "unit": "complete_run",
            "seed_universe": {"start": 7, "stop_exclusive": 8},
            "assignment": {
                "algorithm": "sha256-ranked-v1",
                "salt": "spireshift/tactical-bootstrap/train-v1",
                "counts": {"train": 1, "validation": 0, "test": 0},
            },
            "encounter_policy": {
                "unit": "encounter_instance",
                "inherits_split_from": "complete_run",
                "identifier_fields": ["run_id", "encounter_id"],
                "cross_partition_reuse": "forbidden",
            },
        }
    )


def _partitioned_tactical_split(ruleset_manifest_id: str) -> SplitManifest:
    return freeze_split_manifest(
        {
            "schema_version": "split-manifest-v1",
            "split_id": "tactical-bootstrap-partitions-v1",
            "ruleset_manifest_id": ruleset_manifest_id,
            "objective_id": "terminal-victory-v1",
            "unit": "complete_run",
            "seed_universe": {"start": 7, "stop_exclusive": 10},
            "assignment": {
                "algorithm": "sha256-ranked-v1",
                "salt": "spireshift/tactical-bootstrap/partitions-v1",
                "counts": {"train": 1, "validation": 1, "test": 1},
            },
            "encounter_policy": {
                "unit": "encounter_instance",
                "inherits_split_from": "complete_run",
                "identifier_fields": ["run_id", "encounter_id"],
                "cross_partition_reuse": "forbidden",
            },
        }
    )


def _state_set_document() -> tuple[dict[str, object], SplitManifest]:
    captured = capture_bootstrap_combat_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        combat_state_index=0,
        maximum_prefix_steps=4,
    )
    split = _tactical_split(captured.checkpoint.ruleset_manifest_id)
    document = freeze_bootstrap_state_set(
        {
            "split_manifest_id": split.manifest_id,
            "ruleset_manifest_id": split.ruleset_manifest_id,
            "objective_id": split.objective_id,
            "capture_policy_id": ProgressBootstrapPolicy.policy_id,
            "partition": "train",
            "selection_policy": "single-tactical-train-state-v1",
            "cases": [
                {
                    "state_id": "train-seed-000007-combat-000",
                    "run_seed": 7,
                    "combat_state_index": 0,
                    "expected_state_hash": captured.checkpoint.state_hash,
                    "expected_legal_actions": len(captured.legal_actions),
                }
            ],
        },
        split_manifest=split,
    )
    return document, split


def test_bootstrap_state_set_is_content_addressed_and_train_only(tmp_path: Path) -> None:
    document, split = _state_set_document()
    path = tmp_path / "states.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    loaded = load_bootstrap_state_set(path)

    assert loaded.state_set_id == document["state_set_id"]
    assert loaded.partition == "train"
    tampered = dict(document)
    tampered["partition"] = "validation"
    with pytest.raises(ValueError, match="identity mismatch"):
        load_bootstrap_state_set_document(tampered)
    with pytest.raises(ValueError, match="train partition"):
        freeze_bootstrap_state_set(
            {
                **{
                    key: value
                    for key, value in document.items()
                    if key not in {"schema_version", "state_set_id"}
                },
                "partition": "validation",
            },
            split_manifest=split,
        )


def test_production_bootstrap_states_are_frozen_to_complete_train_runs() -> None:
    split = load_split_manifest(PRODUCTION_SPLIT)
    state_set = load_bootstrap_state_set(PRODUCTION_STATE_SET)
    assert isinstance(state_set, BootstrapStateSet)
    specification = json.loads(PRODUCTION_STATE_SPECIFICATION.read_text(encoding="utf-8"))

    assert state_set.state_set_id == (
        "sha256:82296066af173dce00b4685c8698aa246d50d21ab0cf2eae326e0c8c0fffeeec"
    )
    assert state_set.split_manifest_id == split.manifest_id
    assert len(state_set.cases) == 32
    assert tuple(case.run_seed for case in state_set.cases) == split.seeds(SplitName.TRAIN)[:32]
    assert all(case.combat_state_index == 0 for case in state_set.cases)
    assert all(case.expected_legal_actions > 0 for case in state_set.cases)
    assert freeze_bootstrap_state_set(specification, split_manifest=split) == state_set.as_dict()


def test_production_curricula_are_frozen_to_disjoint_complete_runs() -> None:
    split = load_split_manifest(PRODUCTION_SPLIT)
    train = load_bootstrap_state_set(PRODUCTION_TRAIN_CURRICULUM)
    validation = load_bootstrap_state_set(PRODUCTION_VALIDATION_CURRICULUM)

    assert isinstance(train, CurriculumStateSet)
    assert isinstance(validation, CurriculumStateSet)
    assert train.state_set_id == (
        "sha256:df1f686764bf14ea0022d5d8425b039917b775e93acadfd12caf02033be45ab6"
    )
    assert validation.state_set_id == (
        "sha256:7cdf551662333a1f9320811a739ca904d992beec9b297271517d16366a9a7c40"
    )
    assert len(train.cases) == 545
    assert len(validation.cases) == 204
    train_seeds = {case.run_seed for case in train.cases}
    validation_seeds = {case.run_seed for case in validation.cases}
    assert len(train_seeds) == 64
    assert len(validation_seeds) == 24
    assert train_seeds.isdisjoint(validation_seeds)
    assert all(split.split_for_seed(seed) is SplitName.TRAIN for seed in train_seeds)
    assert all(split.split_for_seed(seed) is SplitName.VALIDATION for seed in validation_seeds)
    shared_hashes = {case.expected_state_hash for case in train.cases} & {
        case.expected_state_hash for case in validation.cases
    }
    assert len(shared_hashes) == 5
    actionable_shared_hashes = {
        case.expected_state_hash
        for case in (*train.cases, *validation.cases)
        if case.expected_state_hash in shared_hashes and case.expected_legal_actions > 1
    }
    assert len(actionable_shared_hashes) == 1


def test_bootstrap_dataset_uses_paired_terminal_first_targets_and_verifies(
    tmp_path: Path,
) -> None:
    document, split = _state_set_document()
    state_set = load_bootstrap_state_set_document(document)

    result = run_bootstrap_teacher_dataset(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=state_set,
        split_manifest=split,
        objective=load_objective(Path("configs/default.toml")),
        config=BootstrapConfig(
            samples_per_candidate=4,
            maximum_prefix_steps=4,
            maximum_rollout_steps=4,
            workers=3,
            worker_timeout_seconds=30.0,
        ),
        output_directory=tmp_path / "dataset",
    )

    assert result.successful
    assert result.report["auxiliary_reward_allowed"] is False
    assert result.report["claim_scope"] == "train_curriculum_only"
    summary = result.report["summary"]
    assert summary["benchmark_denominator"] == 1
    assert summary["completed_cases"] == 1
    assert summary["simulations"] == 12
    assert summary["transitions"] == 24
    case_path = result.report_path.parent / result.report["cases"][0]["path"]
    case = json.loads(case_path.read_text(encoding="utf-8"))
    target = case["record"]["target"]
    assert target["terminal_reward_is_primary"] is True
    assert target["progress_utility_is_auxiliary"] is True
    assert {candidate["sample_count"] for candidate in target["candidates"]} == {4}
    assert {candidate["mean_final_gold"] for candidate in target["candidates"]} == {120.0}
    assert all(
        candidate["mean_final_potion_count"] is not None for candidate in target["candidates"]
    )
    assert all(
        candidate["mean_final_relic_count"] is not None for candidate in target["candidates"]
    )
    seed_sets = [
        {outcome["simulation_seed"] for outcome in candidate["outcomes"]}
        for candidate in target["candidates"]
    ]
    assert all(seeds == seed_sets[0] for seeds in seed_sets[1:])
    assert sum(target["one_hot_policy_target"]) == 1.0

    verification = verify_bootstrap_teacher_dataset(
        result.report_path,
        split_manifest=split,
        replay_cases=1,
    )
    assert verification.valid
    assert verification.verified_cases == 1
    assert verification.replayed_cases == 1

    case["record"]["target"]["selected_action_id"] = "tampered-action"
    record_body = {key: value for key, value in case["record"].items() if key != "record_id"}
    case["record"]["record_id"] = manifest_identifier(record_body)
    case_body = {key: value for key, value in case.items() if key != "case_id"}
    case["case_id"] = manifest_identifier(case_body)
    case_path.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    report["cases"][0]["case_id"] = case["case_id"]
    report["cases"][0]["sha256"] = sha256_file(case_path)
    report_body = {key: value for key, value in report.items() if key != "dataset_id"}
    report["dataset_id"] = manifest_identifier(report_body)
    result.report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    tampered = verify_bootstrap_teacher_dataset(
        result.report_path,
        split_manifest=split,
    )
    assert not tampered.valid
    assert any("target differs from worker evidence" in error for error in tampered.errors)


def test_failed_case_remains_in_denominator_and_resume_preserves_evidence(
    tmp_path: Path,
) -> None:
    document, split = _state_set_document()
    state_set = load_bootstrap_state_set_document(document)
    output = tmp_path / "dataset"
    configuration = BootstrapConfig(
        samples_per_candidate=1,
        maximum_prefix_steps=4,
        maximum_rollout_steps=4,
        workers=1,
        worker_timeout_seconds=30.0,
    )

    failed = run_bootstrap_teacher_dataset(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=state_set,
        split_manifest=split,
        objective=load_objective(Path("configs/default.toml")),
        config=configuration,
        output_directory=output,
        task_runner=lambda _task: (_ for _ in ()).throw(RuntimeError("injected failure")),
    )

    assert not failed.successful
    assert failed.report["summary"]["benchmark_denominator"] == 1
    assert failed.report["summary"]["failed_cases"] == 1
    failed.report_path.unlink()

    resumed = run_bootstrap_teacher_dataset(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=state_set,
        split_manifest=split,
        objective=load_objective(Path("configs/default.toml")),
        config=configuration,
        output_directory=output,
        resume=True,
    )

    assert resumed.successful
    case_root = output / "cases" / state_set.cases[0].state_id
    assert (case_root / "failed-case-0001.json").is_file()
    assert (case_root / "case.json").is_file()
    assert (case_root / "attempt-0001").is_dir()
    assert (case_root / "attempt-0002").is_dir()


def test_terminal_victory_dominates_progress_curriculum_utility() -> None:
    victory: dict[str, object] = {"terminal": True, "victory": True}
    deep_loss: dict[str, object] = {
        "terminal": True,
        "victory": False,
        "maximum_floor": 99,
        "act_completed": True,
        "final_hp": 80,
        "final_max_hp": 80,
    }

    assert bootstrap_utility(victory) == 1.0
    assert bootstrap_utility(deep_loss) < bootstrap_utility(victory)


def _curriculum_spec(split: SplitManifest, partition: str = "train") -> dict[str, object]:
    return {
        "schema_version": "bootstrap-curriculum-discovery-spec-v1",
        "split_manifest_id": split.manifest_id,
        "ruleset_manifest_id": split.ruleset_manifest_id,
        "objective_id": split.objective_id,
        "capture_policy_id": ProgressBootstrapPolicy.policy_id,
        "partition": partition,
        "selection_policy": "tactical-exact-decision-smoke-v1",
        "run_count": 1,
        "decision_occurrences": {"combat": [0], "reward": [0], "shop": [0]},
        "maximum_steps_per_run": 4,
        "signal_spec": {
            "minimum_states": 1,
            "minimum_source_floors": 1,
            "minimum_decision_types": 1,
            "minimum_effective_labeled_states": 0.1,
            "minimum_half_split_agreement": 0.0,
            "minimum_occupied_maximum_floor_bins": 1,
        },
    }


def test_curriculum_discovery_uses_exact_decision_coordinates_and_accounts_for_gaps() -> None:
    captured = capture_curriculum_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        decision_type=DecisionType.REWARD,
        decision_index=0,
        maximum_prefix_steps=4,
    )
    assert captured.observation.decision_type is DecisionType.REWARD

    split = _tactical_split(captured.checkpoint.ruleset_manifest_id)
    document = discover_curriculum_state_set(
        _curriculum_spec(split),
        backend=SearchBackendSpec.tactical_mock(),
        split_manifest=split,
    )
    state_set = load_bootstrap_state_set_document(document)

    assert isinstance(state_set, CurriculumStateSet)
    assert {case.decision_type for case in state_set.cases} == {
        DecisionType.COMBAT,
        DecisionType.REWARD,
    }
    assert state_set.discovery["requested_coordinates"] == 3
    assert state_set.discovery["captured_coordinates"] == 2
    assert state_set.discovery["unreachable_coordinates"] == [
        {
            "run_seed": 7,
            "decision_type": "shop",
            "decision_index": 0,
            "reason": "terminal_or_step_limit_before_coordinate",
        }
    ]


def test_curriculum_dataset_emits_confidence_aware_targets_and_signal_gate(
    tmp_path: Path,
) -> None:
    captured = capture_curriculum_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        decision_type=DecisionType.COMBAT,
        decision_index=0,
        maximum_prefix_steps=4,
    )
    split = _tactical_split(captured.checkpoint.ruleset_manifest_id)
    state_set = load_bootstrap_state_set_document(
        discover_curriculum_state_set(
            _curriculum_spec(split),
            backend=SearchBackendSpec.tactical_mock(),
            split_manifest=split,
        )
    )
    assert isinstance(state_set, CurriculumStateSet)

    result = run_bootstrap_teacher_dataset(
        backend=SearchBackendSpec.tactical_mock(),
        state_set=state_set,
        split_manifest=split,
        objective=load_objective(Path("configs/default.toml")),
        config=BootstrapConfig(
            samples_per_candidate=4,
            maximum_prefix_steps=4,
            maximum_rollout_steps=4,
            workers=2,
            worker_timeout_seconds=30.0,
        ),
        output_directory=tmp_path / "curriculum",
    )

    assert result.successful
    assert result.report["schema_version"] == "bootstrap-teacher-dataset-v2"
    assert result.report["claim_scope"] == "train_curriculum_only"
    assert result.report["summary"]["decision_type_histogram"] == {
        "combat": 1,
        "reward": 1,
    }
    assert result.report["summary"]["unreachable_coordinates"] == 1
    assert result.report["signal_assessment"]["terminal_head_promotion_pass"] in {
        True,
        False,
    }
    for reference in result.report["cases"]:
        case = json.loads(
            (result.report_path.parent / reference["path"]).read_text(encoding="utf-8")
        )
        target = case["record"]["target"]
        assert target["policy_training_interface"] == "paired-preference-soft-target-v1"
        assert sum(target["soft_policy_target"]) == pytest.approx(1.0)
        assert len(target["paired_preference_matrix"]) == len(target["candidates"])
        assert 0.0 <= target["policy_target_weight"] <= 1.0

    verification = verify_bootstrap_teacher_dataset(
        result.report_path,
        split_manifest=split,
    )
    assert verification.valid
    assert verification.verified_cases == 2
    examples = load_curriculum_policy_examples(
        result.report_path,
        split_manifest=split,
    )
    assert len(examples) == 2
    assert all(sum(example.policy_target) == pytest.approx(1.0) for example in examples)
    assert all(0.0 <= example.policy_target_weight <= 1.0 for example in examples)
    assert all(
        len(example.paired_preference_matrix) == len(example.model_input.candidates)
        for example in examples
    )


def test_curriculum_train_and_validation_discovery_are_complete_run_disjoint() -> None:
    captured = capture_curriculum_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        decision_type=DecisionType.COMBAT,
        decision_index=0,
        maximum_prefix_steps=4,
    )
    split = _partitioned_tactical_split(captured.checkpoint.ruleset_manifest_id)
    train = load_bootstrap_state_set_document(
        discover_curriculum_state_set(
            _curriculum_spec(split, "train"),
            backend=SearchBackendSpec.tactical_mock(),
            split_manifest=split,
        )
    )
    validation = load_bootstrap_state_set_document(
        discover_curriculum_state_set(
            _curriculum_spec(split, "validation"),
            backend=SearchBackendSpec.tactical_mock(),
            split_manifest=split,
        )
    )
    assert isinstance(train, CurriculumStateSet)
    assert isinstance(validation, CurriculumStateSet)
    assert {case.run_seed for case in train.cases}.isdisjoint(
        {case.run_seed for case in validation.cases}
    )
