import json
from pathlib import Path

import pytest

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import PolicyOnlyBudgetController, TerminalVictoryPolicy
from spireshift.core.objective import load_objective
from spireshift.recording.jsonl import JsonlRecorder, load_records
from spireshift.replay import verify_mock_replay
from spireshift.rollouts import verify_rollout_batch
from spireshift.runner import run_episode


def test_run_records_and_replays(tmp_path: Path) -> None:
    output = tmp_path / "run.jsonl"
    result = run_episode(
        environment=MockSpireEnvironment(),
        policy=TerminalVictoryPolicy(),
        budget_controller=PolicyOnlyBudgetController(),
        recorder=JsonlRecorder(output),
        objective=load_objective(Path("configs/default.toml")),
        seed=7,
    )
    records = load_records(output)
    assert records[0]["record_type"] == "header"
    assert records[0]["ruleset"] == MockSpireEnvironment.ruleset.as_dict()
    assert records[-1]["record_type"] == "summary"
    assert records[-1]["terminal_reward"] in (0.0, 1.0)
    assert result.compute_used == result.decisions

    replay = verify_mock_replay(output)
    assert replay.valid, replay.message
    assert replay.steps == result.decisions


def test_policy_takes_terminally_better_risky_path(tmp_path: Path) -> None:
    output = tmp_path / "run.jsonl"
    run_episode(
        environment=MockSpireEnvironment(),
        policy=TerminalVictoryPolicy(),
        budget_controller=PolicyOnlyBudgetController(),
        recorder=JsonlRecorder(output),
        objective=load_objective(Path("configs/default.toml")),
        seed=7,
    )
    step = next(record for record in load_records(output) if record["record_type"] == "step")
    assert step["transition"]["action"]["action_id"] == "elite_path"


def test_replay_rejects_a_different_ruleset(tmp_path: Path) -> None:
    output = tmp_path / "run.jsonl"
    run_episode(
        environment=MockSpireEnvironment(),
        policy=TerminalVictoryPolicy(),
        budget_controller=PolicyOnlyBudgetController(),
        recorder=JsonlRecorder(output),
        objective=load_objective(Path("configs/default.toml")),
        seed=7,
    )
    records = load_records(output)
    records[0]["ruleset"]["manifest_id"] = "sha256:" + "0" * 64
    output.write_text("".join(json.dumps(record) + "\n" for record in records))

    replay = verify_mock_replay(output)
    assert not replay.valid
    assert replay.message == "Ruleset identity mismatch"


def test_replay_rejects_a_tampered_transition_even_when_hashes_are_unchanged(
    tmp_path: Path,
) -> None:
    output = tmp_path / "run.jsonl"
    run_episode(
        environment=MockSpireEnvironment(),
        policy=TerminalVictoryPolicy(),
        budget_controller=PolicyOnlyBudgetController(),
        recorder=JsonlRecorder(output),
        objective=load_objective(Path("configs/default.toml")),
        seed=7,
    )
    records = load_records(output)
    step = next(record for record in records if record["record_type"] == "step")
    step["transition"]["action"]["payload"] = {"risk": "forged"}
    output.write_text("".join(json.dumps(record) + "\n" for record in records))

    replay = verify_mock_replay(output)
    assert not replay.valid
    assert replay.message == "Transition mismatch at decision 0"


def test_run_rejects_environment_patch_identity_drift(tmp_path: Path) -> None:
    environment = MockSpireEnvironment()
    environment.patch_id = "unexpected-patch"

    with pytest.raises(RuntimeError, match="does not match its ruleset"):
        run_episode(
            environment=environment,
            policy=TerminalVictoryPolicy(),
            budget_controller=PolicyOnlyBudgetController(),
            recorder=JsonlRecorder(tmp_path / "run.jsonl"),
            objective=load_objective(Path("configs/default.toml")),
            seed=7,
        )


def test_checked_parallel_rollout_fixture_replays() -> None:
    replay = verify_rollout_batch(Path("tests/fixtures/rollout/mock-batch-v1/rollout-report.json"))
    assert replay.valid, replay.errors
    assert replay.runs == 2
    assert replay.verified_runs == 2
