from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.core.types import LegalAction
from spireshift.recording.jsonl import load_records, records_of_type


@dataclass(frozen=True, slots=True)
class ReplayResult:
    valid: bool
    steps: int
    victory: bool
    message: str


def verify_mock_replay(path: Path) -> ReplayResult:
    records = load_records(path)
    headers = records_of_type(records, "header")
    summaries = records_of_type(records, "summary")
    steps = records_of_type(records, "step")
    if len(headers) != 1 or len(summaries) != 1:
        return ReplayResult(False, 0, False, "Expected exactly one header and summary")

    header = headers[0]
    environment = MockSpireEnvironment()
    observation = environment.reset(int(header["seed"]))
    if observation.state_hash != header["initial_state_hash"]:
        return ReplayResult(False, 0, False, "Initial state hash mismatch")

    victory = False
    for index, record in enumerate(steps):
        transition_record = _mapping(record["transition"])
        recorded_observation = _mapping(transition_record["observation"])
        if observation.state_hash != recorded_observation["state_hash"]:
            return ReplayResult(False, index, False, f"State mismatch at decision {index}")
        action_record = _mapping(transition_record["action"])
        action = LegalAction(
            action_id=str(action_record["action_id"]),
            kind=str(action_record["kind"]),
            payload=_mapping(action_record["payload"]),
        )
        transition = environment.step(action)
        recorded_next = _mapping(transition_record["next_observation"])
        if transition.next_observation.state_hash != recorded_next["state_hash"]:
            return ReplayResult(False, index, False, f"Next-state mismatch at decision {index}")
        if transition.reward != transition_record["reward"]:
            return ReplayResult(False, index, False, f"Reward mismatch at decision {index}")
        observation = transition.next_observation
        victory = transition.victory

    summary = summaries[0]
    if victory != bool(summary["victory"]):
        return ReplayResult(False, len(steps), victory, "Terminal result mismatch")
    if observation.state_hash != summary["final_state_hash"]:
        return ReplayResult(False, len(steps), victory, "Final state hash mismatch")
    return ReplayResult(True, len(steps), victory, "Replay verified")


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Expected an object in replay record")
    return value
