from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import TerminalVictoryPolicy
from spireshift.cli import main
from spireshift.core.objective import ObjectiveSpec, load_objective
from spireshift.splits import (
    SplitManifest,
    SplitName,
    audit_dataset_index_document,
    load_split_manifest,
)
from spireshift.teacher_data import (
    TeacherConfig,
    build_teacher_target,
    generate_mock_teacher_dataset,
    teacher_dataset_index,
    verify_teacher_dataset,
    write_teacher_dataset,
)

SPLIT_MANIFEST_PATH = Path("manifests/splits/mock-v1-seeds-000000-000999-v1.json")
OBJECTIVE_PATH = Path("configs/default.toml")
FIXTURE_PATH = Path("tests/fixtures/teacher-dataset-v1.json")
INDEX_FIXTURE_PATH = Path("tests/fixtures/teacher-dataset-index-v1.json")


def _manifest() -> SplitManifest:
    return load_split_manifest(SPLIT_MANIFEST_PATH)


def _objective() -> ObjectiveSpec:
    return load_objective(OBJECTIVE_PATH)


def _config(*, search: int = 32, evaluation: int = 32) -> TeacherConfig:
    return TeacherConfig(
        search_simulations=search,
        evaluation_samples_per_candidate=evaluation,
    )


def _dataset(*, search: int = 32, evaluation: int = 32) -> dict[str, Any]:
    return generate_mock_teacher_dataset(
        seeds=(0,),
        partition=SplitName.TRAIN,
        split_manifest=_manifest(),
        objective=_objective(),
        config=_config(search=search, evaluation=evaluation),
    )


def _records(document: dict[str, Any]) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], document["records"])


def _candidates(record: dict[str, Any]) -> list[dict[str, Any]]:
    target = cast(dict[str, Any], record["teacher_target"])
    return cast(list[dict[str, Any]], target["candidates"])


def test_teacher_dataset_is_deterministic_complete_and_independently_verified() -> None:
    first = _dataset()
    second = _dataset()
    verification = verify_teacher_dataset(first, _manifest())

    assert first == second
    assert verification.valid, verification.errors
    assert verification.runs == 1
    assert verification.records == 2
    assert verification.search_simulations == 64
    assert verification.evaluation_simulations == 96
    assert first["summary"] == {
        "runs": 1,
        "records": 2,
        "candidates": 3,
        "victories": 1,
        "defeats": 0,
        "search_simulations": 64,
        "evaluation_simulations": 96,
    }
    assert all(record["run_terminal_victory"] is True for record in _records(first))


def test_search_and_evaluation_use_disjoint_seed_domains_and_equal_grading_budgets() -> None:
    first_record = _records(_dataset())[0]
    candidates = _candidates(first_record)
    search_seeds = {
        outcome["simulation_seed"]
        for candidate in candidates
        for outcome in candidate["search"]["outcomes"]
    }
    evaluation_seed_sets = [
        {outcome["simulation_seed"] for outcome in candidate["independent_evaluation"]["outcomes"]}
        for candidate in candidates
    ]
    evaluation_seeds = set().union(*evaluation_seed_sets)

    assert len(search_seeds) == 32
    assert all(len(seeds) == 32 for seeds in evaluation_seed_sets)
    assert search_seeds.isdisjoint(evaluation_seeds)
    assert all(seed % 2 == 0 for seed in search_seeds)
    assert all(seed % 2 == 1 for seed in evaluation_seeds)
    assert len(evaluation_seeds) == 64


def test_independent_grader_does_not_choose_the_teacher_action() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(0)
    target = build_teacher_target(
        environment=environment,
        observation=observation,
        legal_actions=environment.legal_actions(),
        continuation_policy=TerminalVictoryPolicy(),
        config=TeacherConfig(
            search_simulations=4,
            evaluation_samples_per_candidate=16,
            sampling_seed=6,
        ),
        run_seed=0,
        decision_index=0,
    )

    assert target.selected_action_id == "safe_path"
    by_id = {candidate.source_action_id: candidate for candidate in target.candidates}
    assert len(by_id["safe_path"].search.samples) > len(by_id["elite_path"].search.samples)
    assert (
        by_id["elite_path"].independent_evaluation.value
        > by_id["safe_path"].independent_evaluation.value
    )
    assert len(by_id["safe_path"].independent_evaluation.samples) == len(
        by_id["elite_path"].independent_evaluation.samples
    )


def test_checked_fixture_and_dataset_index_are_reproducible() -> None:
    generated = _dataset()
    checked = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    index = teacher_dataset_index(generated, _manifest())
    checked_index = json.loads(INDEX_FIXTURE_PATH.read_text(encoding="utf-8"))

    assert generated == checked
    assert index == checked_index
    index_audit = audit_dataset_index_document(index, _manifest())
    assert index_audit.valid, index_audit.errors
    assert index_audit.partition_runs == {"train": 1, "validation": 0, "test": 0}
    assert index_audit.partition_records == {"train": 2, "validation": 0, "test": 0}


def test_verifier_rejects_reused_or_tampered_evaluation_outcomes() -> None:
    reused = copy.deepcopy(_dataset())
    reused_record = _records(reused)[0]
    reused_candidates = _candidates(reused_record)
    search_outcome = reused_candidates[0]["search"]["outcomes"][0]
    reused_candidates[0]["independent_evaluation"]["outcomes"][0]["simulation_seed"] = (
        search_outcome["simulation_seed"]
    )

    reused_result = verify_teacher_dataset(reused, _manifest())

    assert not reused_result.valid
    assert any("overlap" in error or "parity" in error for error in reused_result.errors)

    tampered = copy.deepcopy(_dataset())
    tampered_candidate = _candidates(_records(tampered)[0])[0]
    outcome = tampered_candidate["independent_evaluation"]["outcomes"][0]
    outcome["terminal_reward"] = 1.0 - outcome["terminal_reward"]

    tampered_result = verify_teacher_dataset(tampered, _manifest())

    assert not tampered_result.valid
    assert any("terminal value mismatch" in error for error in tampered_result.errors)


def test_generation_rejects_split_leakage_duplicate_seeds_and_insufficient_search() -> None:
    with pytest.raises(ValueError, match="not in the frozen train partition"):
        generate_mock_teacher_dataset(
            seeds=(1,),
            partition=SplitName.TRAIN,
            split_manifest=_manifest(),
            objective=_objective(),
            config=_config(),
        )
    with pytest.raises(ValueError, match="unique"):
        generate_mock_teacher_dataset(
            seeds=(0, 0),
            partition=SplitName.TRAIN,
            split_manifest=_manifest(),
            objective=_objective(),
            config=_config(),
        )
    with pytest.raises(ValueError, match="visit every legal candidate"):
        generate_mock_teacher_dataset(
            seeds=(0,),
            partition=SplitName.TRAIN,
            split_manifest=_manifest(),
            objective=_objective(),
            config=_config(search=1),
        )


def test_dataset_writer_is_immutable(tmp_path: Path) -> None:
    dataset = _dataset()
    output = tmp_path / "teacher.json"

    write_teacher_dataset(dataset, output)
    write_teacher_dataset(dataset, output)
    output.write_text("{}\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Refusing to replace"):
        write_teacher_dataset(dataset, output)


def test_cli_generates_and_verifies_teacher_dataset(tmp_path: Path) -> None:
    dataset_path = tmp_path / "teacher.json"
    verification_path = tmp_path / "verification.json"

    generated = main(
        [
            "teacher",
            "generate-mock",
            str(dataset_path),
            "--seeds",
            "0",
            "--search-simulations",
            "32",
            "--evaluation-samples",
            "32",
        ]
    )
    verified = main(
        [
            "teacher",
            "verify",
            str(dataset_path),
            "--output",
            str(verification_path),
        ]
    )

    assert generated == 0
    assert verified == 0
    assert dataset_path.is_file()
    assert (tmp_path / "teacher-index.json").is_file()
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    assert verification["valid"] is True
