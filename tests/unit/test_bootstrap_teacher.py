from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spireshift.agents.baseline import ProgressBootstrapPolicy
from spireshift.bootstrap_teacher import (
    BootstrapConfig,
    BootstrapPolicyArtifacts,
    BootstrapSimulationTask,
    BootstrapStateSet,
    CurriculumStateSet,
    bootstrap_utility,
    capture_bootstrap_combat_state,
    capture_curriculum_state,
    combine_curriculum_datasets,
    discover_curriculum_state_set,
    execute_bootstrap_task,
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
PRODUCTION_TRAIN_LEARNED_CURRICULUM = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json"
)
PRODUCTION_VALIDATION_LEARNED_CURRICULUM = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-validation-learned-curriculum-v3.json"
)
PRODUCTION_TRAIN_LEARNED_SUPPLEMENT = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-supplement-v3.json"
)
PRODUCTION_TRAIN_TERMINAL_FRONTIER = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-train-terminal-frontier-v4.json"
)
PRODUCTION_VALIDATION_TERMINAL_FRONTIER = Path(
    "manifests/bootstrap/sts2-v0.107.1-evangambit-validation-terminal-frontier-v4.json"
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


def test_learned_policy_curricula_are_frozen_to_later_disjoint_runs() -> None:
    split = load_split_manifest(PRODUCTION_SPLIT)
    train = load_bootstrap_state_set(PRODUCTION_TRAIN_LEARNED_CURRICULUM)
    validation = load_bootstrap_state_set(PRODUCTION_VALIDATION_LEARNED_CURRICULUM)

    assert isinstance(train, CurriculumStateSet)
    assert isinstance(validation, CurriculumStateSet)
    assert train.state_set_id == (
        "sha256:07c21103e14a3e21a56bedfba936578071fc5fc1e084f764a0e583e04a7c4542"
    )
    assert validation.state_set_id == (
        "sha256:75f35e8bc1e843853dd933e0fae8db406acddcc5a85e325522705a486b4ec7a6"
    )
    assert train.capture_policy == validation.capture_policy
    assert train.capture_policy is not None
    assert train.capture_policy["model_id"] == (
        "sha256:b0b727319ecd5544df519d703c190a01d08b0aa37f8098a3bc8bcbcfd33a0571"
    )
    assert len(train.cases) == 711
    assert len(validation.cases) == 256
    train_seeds = {case.run_seed for case in train.cases}
    validation_seeds = {case.run_seed for case in validation.cases}
    assert len(train_seeds) == 64
    assert len(validation_seeds) == 24
    assert train_seeds.isdisjoint(validation_seeds)
    assert all(split.split_for_seed(seed) is SplitName.TRAIN for seed in train_seeds)
    assert all(split.split_for_seed(seed) is SplitName.VALIDATION for seed in validation_seeds)
    assert max(case.expected_source_floor or 0 for case in train.cases) == 11
    assert max(case.expected_source_floor or 0 for case in validation.cases) == 10
    assert sum((case.expected_source_floor or 0) >= 4 for case in train.cases) == 354
    assert sum((case.expected_source_floor or 0) >= 4 for case in validation.cases) == 117
    shared_hashes = {case.expected_state_hash for case in train.cases} & {
        case.expected_state_hash for case in validation.cases
    }
    assert len(shared_hashes) == 8
    actionable_shared_hashes = {
        case.expected_state_hash
        for case in (*train.cases, *validation.cases)
        if case.expected_state_hash in shared_hashes and case.expected_legal_actions > 1
    }
    assert len(actionable_shared_hashes) == 1


def test_learned_policy_supplement_is_frozen_to_unused_train_runs() -> None:
    split = load_split_manifest(PRODUCTION_SPLIT)
    original = load_bootstrap_state_set(PRODUCTION_TRAIN_LEARNED_CURRICULUM)
    supplement = load_bootstrap_state_set(PRODUCTION_TRAIN_LEARNED_SUPPLEMENT)

    assert isinstance(original, CurriculumStateSet)
    assert isinstance(supplement, CurriculumStateSet)
    assert supplement.state_set_id == (
        "sha256:ebdbb798da5a82cba5a27936207e6e8972a4039ac1cd1194b11cb3d5c806a49c"
    )
    assert supplement.capture_policy == original.capture_policy
    assert supplement.discovery["run_offset"] == 64
    assert len(supplement.cases) == 268
    assert len({case.expected_state_hash for case in supplement.cases}) == 268
    supplement_seeds = {case.run_seed for case in supplement.cases}
    original_seeds = {case.run_seed for case in original.cases}
    assert len(supplement_seeds) == 16
    assert supplement_seeds.isdisjoint(original_seeds)
    assert supplement_seeds == set(split.seeds(SplitName.TRAIN)[64:80])
    assert len({case.decision_type for case in supplement.cases}) == 9
    assert (
        len(
            {
                case.expected_source_floor
                for case in supplement.cases
                if case.expected_source_floor is not None
            }
        )
        == 8
    )
    assert max(case.expected_source_floor or 0 for case in supplement.cases) == 8
    assert supplement.discovery["step_limited_runs"] == 0


def test_terminal_frontier_curricula_freeze_deep_unused_complete_runs() -> None:
    split = load_split_manifest(PRODUCTION_SPLIT)
    train = load_bootstrap_state_set(PRODUCTION_TRAIN_TERMINAL_FRONTIER)
    validation = load_bootstrap_state_set(PRODUCTION_VALIDATION_TERMINAL_FRONTIER)

    assert isinstance(train, CurriculumStateSet)
    assert isinstance(validation, CurriculumStateSet)
    assert train.state_set_id == (
        "sha256:9e09a8a180e15eb503a229ee8bd109ebf32ab7f9ba9e4f0aee747c8898d8463f"
    )
    assert validation.state_set_id == (
        "sha256:55b4181550ad5c573f8caab52272a2aa8df2b4bf40de330832243a20029b593a"
    )
    assert train.capture_policy == validation.capture_policy
    assert train.capture_policy is not None
    assert train.capture_policy["model_id"] == (
        "sha256:327ba33da07880634c8d884312220ac61b8923f2ad0354b25c11d2ad4c56db2c"
    )
    assert len(train.cases) == 674
    assert len(validation.cases) == 311
    assert len({case.expected_state_hash for case in train.cases}) == 674
    assert len({case.expected_state_hash for case in validation.cases}) == 311
    train_seeds = {case.run_seed for case in train.cases}
    validation_seeds = {case.run_seed for case in validation.cases}
    assert train_seeds <= set(split.seeds(SplitName.TRAIN)[80:240])
    assert validation_seeds <= set(split.seeds(SplitName.VALIDATION)[24:100])
    assert train_seeds.isdisjoint(split.seeds(SplitName.TRAIN)[:80])
    assert validation_seeds.isdisjoint(split.seeds(SplitName.VALIDATION)[:24])
    assert len(train_seeds) == 89
    assert len(validation_seeds) == 40
    assert train_seeds.isdisjoint(validation_seeds)
    assert {case.expected_state_hash for case in train.cases}.isdisjoint(
        {case.expected_state_hash for case in validation.cases}
    )
    assert all((case.expected_source_floor or 0) >= 7 for case in (*train.cases, *validation.cases))
    assert all(case.expected_legal_actions >= 2 for case in (*train.cases, *validation.cases))
    assert train.discovery["run_offset"] == 80
    assert validation.discovery["run_offset"] == 24
    assert train.discovery["victorious_runs"] == 0
    assert validation.discovery["victorious_runs"] == 0
    assert train.signal_spec.requires_terminal_signal
    assert validation.signal_spec.requires_terminal_signal


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
    with pytest.raises(ValueError, match="different configuration"):
        run_bootstrap_teacher_dataset(
            backend=SearchBackendSpec.tactical_mock(),
            state_set=state_set,
            split_manifest=split,
            objective=load_objective(Path("configs/default.toml")),
            config=BootstrapConfig(
                samples_per_candidate=2,
                maximum_prefix_steps=4,
                maximum_rollout_steps=4,
                workers=1,
                worker_timeout_seconds=30.0,
            ),
            output_directory=output,
            resume=True,
        )
    assert failed.report_path.is_file()

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
    assert (output / "failed-dataset-0001.json").is_file()
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


def test_learned_policy_discovery_and_tasks_bind_exact_artifact_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = capture_curriculum_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        decision_type=DecisionType.COMBAT,
        decision_index=0,
        maximum_prefix_steps=4,
    )
    split = _tactical_split(captured.checkpoint.ruleset_manifest_id)
    model_id = "sha256:" + "a" * 64
    report_id = "sha256:" + "b" * 64
    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "training-report.json"
    checkpoint_path.write_text("{}", encoding="utf-8")
    report_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "spireshift.production_models.load_production_model_checkpoint",
        lambda _path: {
            "model_id": model_id,
            "split_manifest_id": split.manifest_id,
            "ruleset_manifest_id": split.ruleset_manifest_id,
        },
    )
    monkeypatch.setattr(
        "spireshift.production_models.load_production_training_report",
        lambda _path, *, checkpoint: {
            "model_id": checkpoint["model_id"],
            "report_id": report_id,
        },
    )
    artifacts = BootstrapPolicyArtifacts.from_paths(checkpoint_path, report_path)
    monkeypatch.setattr(
        BootstrapPolicyArtifacts,
        "load_policy",
        lambda _self, _ruleset: ProgressBootstrapPolicy(),
    )
    specification = _curriculum_spec(split)
    specification.update(
        {
            "schema_version": "bootstrap-curriculum-discovery-spec-v2",
            "capture_policy_id": artifacts.policy_id,
        }
    )

    document = discover_curriculum_state_set(
        specification,
        backend=SearchBackendSpec.tactical_mock(),
        split_manifest=split,
        policy_artifacts=artifacts,
    )
    state_set = load_bootstrap_state_set_document(document)

    assert isinstance(state_set, CurriculumStateSet)
    assert state_set.as_dict()["schema_version"] == "bootstrap-state-set-v3"
    assert state_set.capture_policy == artifacts.provenance()
    task = BootstrapSimulationTask(
        "00000000-0000-4000-8000-000000000001",
        SearchBackendSpec.tactical_mock(),
        captured.checkpoint,
        captured.legal_actions[0].action_id,
        123,
        4,
        artifacts,
    )
    restored = BootstrapSimulationTask.from_mapping(task.as_dict())
    assert restored.as_dict() == task.as_dict()
    assert restored.continuation_policy_id == artifacts.policy_id

    mismatched = BootstrapPolicyArtifacts(
        checkpoint_path=artifacts.checkpoint_path,
        training_report_path=artifacts.training_report_path,
        policy_id=artifacts.policy_id,
        model_id=artifacts.model_id,
        training_report_id="sha256:" + "c" * 64,
        split_manifest_id=artifacts.split_manifest_id,
        ruleset_manifest_id=artifacts.ruleset_manifest_id,
    )
    with pytest.raises(ValueError, match="differ from frozen"):
        run_bootstrap_teacher_dataset(
            backend=SearchBackendSpec.tactical_mock(),
            state_set=state_set,
            split_manifest=split,
            objective=load_objective(Path("configs/default.toml")),
            config=BootstrapConfig(
                samples_per_candidate=1,
                maximum_prefix_steps=4,
                maximum_rollout_steps=4,
                workers=1,
            ),
            output_directory=tmp_path / "mismatch",
            policy_artifacts=mismatched,
        )


def test_terminal_frontier_curriculum_requires_completed_action_dependent_outcomes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = capture_curriculum_state(
        backend=SearchBackendSpec.mock(),
        run_seed=7,
        decision_type=DecisionType.PATH,
        decision_index=0,
        maximum_prefix_steps=4,
    )
    split = _tactical_split(captured.checkpoint.ruleset_manifest_id)
    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "training-report.json"
    checkpoint_path.write_text("{}", encoding="utf-8")
    report_path.write_text("{}", encoding="utf-8")
    model_id = "sha256:" + "1" * 64
    report_id = "sha256:" + "2" * 64
    monkeypatch.setattr(
        "spireshift.production_models.load_production_model_checkpoint",
        lambda _path: {
            "model_id": model_id,
            "split_manifest_id": split.manifest_id,
            "ruleset_manifest_id": split.ruleset_manifest_id,
        },
    )
    monkeypatch.setattr(
        "spireshift.production_models.load_production_training_report",
        lambda _path, *, checkpoint: {
            "model_id": checkpoint["model_id"],
            "report_id": report_id,
        },
    )
    artifacts = BootstrapPolicyArtifacts.from_paths(checkpoint_path, report_path)
    monkeypatch.setattr(
        BootstrapPolicyArtifacts,
        "load_policy",
        lambda _self, _ruleset: ProgressBootstrapPolicy(),
    )
    specification = {
        "schema_version": "bootstrap-curriculum-discovery-spec-v3",
        "split_manifest_id": split.manifest_id,
        "ruleset_manifest_id": split.ruleset_manifest_id,
        "objective_id": split.objective_id,
        "capture_policy_id": artifacts.policy_id,
        "partition": "train",
        "selection_policy": "deepest-actionable-terminal-frontier-smoke-v1",
        "run_count": 1,
        "frontier_selection": {
            "decision_types": ["path", "combat"],
            "minimum_source_floor": 0,
            "minimum_legal_actions": 2,
            "maximum_states_per_run": 1,
        },
        "maximum_steps_per_run": 4,
        "signal_spec": {
            "minimum_states": 1,
            "minimum_source_floors": 1,
            "minimum_decision_types": 1,
            "minimum_effective_labeled_states": 0.1,
            "minimum_half_split_agreement": 0.0,
            "minimum_occupied_maximum_floor_bins": 1,
            "minimum_terminal_victories": 1,
            "minimum_terminal_defeats": 1,
            "minimum_states_with_candidate_terminal_variation": 1,
        },
    }
    document = discover_curriculum_state_set(
        specification,
        backend=SearchBackendSpec.mock(),
        split_manifest=split,
        policy_artifacts=artifacts,
    )
    state_set = load_bootstrap_state_set_document(document)

    assert isinstance(state_set, CurriculumStateSet)
    assert state_set.as_dict()["schema_version"] == "bootstrap-state-set-v4"
    assert len(state_set.cases) == 1
    assert state_set.cases[0].decision_type is DecisionType.PATH
    assert state_set.cases[0].expected_legal_actions == 2
    assert state_set.discovery["eligible_coordinates"] == 1
    assert state_set.discovery["terminal_runs"] == 1
    assert state_set.discovery["victorious_runs"] + state_set.discovery["defeated_runs"] == 1

    result = run_bootstrap_teacher_dataset(
        backend=SearchBackendSpec.mock(),
        state_set=state_set,
        split_manifest=split,
        objective=load_objective(Path("configs/default.toml")),
        config=BootstrapConfig(
            samples_per_candidate=32,
            maximum_prefix_steps=4,
            maximum_rollout_steps=4,
            workers=4,
        ),
        output_directory=tmp_path / "terminal-frontier",
        task_runner=execute_bootstrap_task,
        policy_artifacts=artifacts,
    )

    assert result.successful
    assert result.report["schema_version"] == "bootstrap-teacher-dataset-v4"
    summary = result.report["summary"]
    assert summary["terminal_outcome_classes"] == {
        "victory": summary["terminal_victories"],
        "defeat": summary["terminal_defeats"],
        "censored": 0,
    }
    assert summary["terminal_victories"] > 0
    assert summary["terminal_defeats"] > 0
    assert summary["states_with_complete_candidate_terminal_observation"] == 1
    assert summary["states_with_candidate_terminal_variation"] == 1
    assert result.report["signal_assessment"]["terminal_head_promotion_pass"] is True
    assert result.report["signal_assessment"]["schema_version"] == (
        "bootstrap-curriculum-signal-assessment-v2"
    )
    schemas = [
        json.loads(path.read_text(encoding="utf-8")) for path in Path("schemas").glob("*.json")
    ]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    Draft202012Validator(
        next(
            schema
            for schema in schemas
            if schema["$id"].endswith("/bootstrap-teacher-dataset-v4.json")
        ),
        registry=registry,
    ).validate(result.report)
    verification = verify_bootstrap_teacher_dataset(
        result.report_path,
        split_manifest=split,
    )
    assert verification.valid


def test_policy_artifact_validation_is_cached_until_file_metadata_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    report_path = tmp_path / "training-report.json"
    checkpoint_path.write_text("{}", encoding="utf-8")
    report_path.write_text("{}", encoding="utf-8")
    calls = {"checkpoint": 0, "report": 0}

    def load_checkpoint(_path: Path) -> dict[str, str]:
        calls["checkpoint"] += 1
        return {
            "model_id": "sha256:" + "a" * 64,
            "split_manifest_id": "sha256:" + "b" * 64,
            "ruleset_manifest_id": "sha256:" + "c" * 64,
        }

    def load_report(_path: Path, *, checkpoint: object) -> dict[str, str]:
        assert checkpoint
        calls["report"] += 1
        return {"report_id": "sha256:" + "d" * 64}

    monkeypatch.setattr(
        "spireshift.production_models.load_production_model_checkpoint", load_checkpoint
    )
    monkeypatch.setattr("spireshift.production_models.load_production_training_report", load_report)

    first = BootstrapPolicyArtifacts.from_paths(checkpoint_path, report_path)
    second = BootstrapPolicyArtifacts.from_paths(checkpoint_path, report_path)
    assert first == second
    assert calls == {"checkpoint": 1, "report": 1}

    checkpoint_path.write_text('{"changed": true}', encoding="utf-8")
    BootstrapPolicyArtifacts.from_paths(checkpoint_path, report_path)
    assert calls == {"checkpoint": 2, "report": 2}


def test_learned_curriculum_offset_and_seed_disjoint_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = capture_curriculum_state(
        backend=SearchBackendSpec.tactical_mock(),
        run_seed=7,
        decision_type=DecisionType.COMBAT,
        decision_index=0,
        maximum_prefix_steps=4,
    )
    split = freeze_split_manifest(
        {
            "schema_version": "split-manifest-v1",
            "split_id": "tactical-bootstrap-composition-v1",
            "ruleset_manifest_id": captured.checkpoint.ruleset_manifest_id,
            "objective_id": "terminal-victory-v1",
            "unit": "complete_run",
            "seed_universe": {"start": 7, "stop_exclusive": 9},
            "assignment": {
                "algorithm": "sha256-ranked-v1",
                "salt": "spireshift/tactical-bootstrap/composition-v1",
                "counts": {"train": 2, "validation": 0, "test": 0},
            },
            "encounter_policy": {
                "unit": "encounter_instance",
                "inherits_split_from": "complete_run",
                "identifier_fields": ["run_id", "encounter_id"],
                "cross_partition_reuse": "forbidden",
            },
        }
    )
    checkpoint_path = tmp_path / "checkpoint.json"
    training_report_path = tmp_path / "training-report.json"
    checkpoint_path.write_text("{}", encoding="utf-8")
    training_report_path.write_text("{}", encoding="utf-8")
    model_id = "sha256:" + "e" * 64
    report_id = "sha256:" + "f" * 64
    monkeypatch.setattr(
        "spireshift.production_models.load_production_model_checkpoint",
        lambda _path: {
            "model_id": model_id,
            "split_manifest_id": split.manifest_id,
            "ruleset_manifest_id": split.ruleset_manifest_id,
        },
    )
    monkeypatch.setattr(
        "spireshift.production_models.load_production_training_report",
        lambda _path, *, checkpoint: {
            "model_id": checkpoint["model_id"],
            "report_id": report_id,
        },
    )
    artifacts = BootstrapPolicyArtifacts.from_paths(checkpoint_path, training_report_path)
    monkeypatch.setattr(
        BootstrapPolicyArtifacts,
        "load_policy",
        lambda _self, _ruleset: ProgressBootstrapPolicy(),
    )
    specification = _curriculum_spec(split)
    specification.update(
        {
            "schema_version": "bootstrap-curriculum-discovery-spec-v2",
            "capture_policy_id": artifacts.policy_id,
        }
    )
    config = BootstrapConfig(
        samples_per_candidate=2,
        maximum_prefix_steps=4,
        maximum_rollout_steps=4,
        workers=2,
    )
    component_paths: list[Path] = []
    component_seeds: list[set[int]] = []
    for offset in (0, 1):
        state_set = load_bootstrap_state_set_document(
            discover_curriculum_state_set(
                specification,
                backend=SearchBackendSpec.tactical_mock(),
                split_manifest=split,
                policy_artifacts=artifacts,
                run_offset=offset,
            )
        )
        assert isinstance(state_set, CurriculumStateSet)
        assert state_set.discovery.get("run_offset") == (offset or None)
        component_seeds.append({case.run_seed for case in state_set.cases})
        result = run_bootstrap_teacher_dataset(
            backend=SearchBackendSpec.tactical_mock(),
            state_set=state_set,
            split_manifest=split,
            objective=load_objective(Path("configs/default.toml")),
            config=config,
            output_directory=tmp_path / f"component-{offset}",
            task_runner=execute_bootstrap_task,
            policy_artifacts=artifacts,
        )
        assert result.successful
        component_paths.append(result.report_path)

    assert component_seeds[0].isdisjoint(component_seeds[1])
    combined = combine_curriculum_datasets(
        component_paths,
        output_directory=tmp_path / "combined",
        split_manifest=split,
    )
    assert combined.successful
    assert combined.report["summary"]["completed_cases"] == sum(
        len(seeds) * 2 for seeds in component_seeds
    )
    combined_state_set = load_bootstrap_state_set_document(combined.report["state_set"])
    assert isinstance(combined_state_set, CurriculumStateSet)
    assert combined_state_set.discovery["component_state_set_ids"] == [
        json.loads(path.read_text(encoding="utf-8"))["state_set"]["state_set_id"]
        for path in component_paths
    ]
    verification = verify_bootstrap_teacher_dataset(
        combined.report_path,
        split_manifest=split,
    )
    assert verification.valid
