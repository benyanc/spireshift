from pathlib import Path

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import PolicyOnlyBudgetController, TerminalVictoryPolicy
from spireshift.core.objective import load_objective
from spireshift.recording.jsonl import JsonlRecorder, load_records
from spireshift.replay import verify_mock_replay
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
