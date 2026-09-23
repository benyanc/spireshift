from __future__ import annotations

import json
from pathlib import Path

import pytest

from spireshift.agents.baseline import ProgressBootstrapPolicy
from spireshift.bootstrap_teacher import (
    BootstrapConfig,
    bootstrap_utility,
    capture_bootstrap_combat_state,
    freeze_bootstrap_state_set,
    load_bootstrap_state_set,
    load_bootstrap_state_set_document,
    run_bootstrap_teacher_dataset,
    verify_bootstrap_teacher_dataset,
)
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.rollouts import sha256_file
from spireshift.search_workers import SearchBackendSpec
from spireshift.splits import SplitManifest, freeze_split_manifest

PRODUCTION_SPLIT = Path("manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json")
PRODUCTION_STATE_SET = Path("manifests/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json")
PRODUCTION_STATE_SPECIFICATION = Path(
    "configs/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json"
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
    from spireshift.splits import SplitName, load_split_manifest

    split = load_split_manifest(PRODUCTION_SPLIT)
    state_set = load_bootstrap_state_set(PRODUCTION_STATE_SET)
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
