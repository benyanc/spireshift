from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.core.types import BudgetTier, LegalAction
from spireshift.recording.jsonl import load_records


@dataclass(frozen=True, slots=True)
class ReplayResult:
    valid: bool
    steps: int
    victory: bool
    message: str


def verify_mock_replay(path: Path) -> ReplayResult:
    verified_steps = 0
    victory = False
    try:
        records = load_records(path)
        if len(records) < 2:
            return ReplayResult(False, 0, False, "Expected exactly one header and summary")
        if records[0].get("record_type") != "header" or records[-1].get("record_type") != "summary":
            return ReplayResult(False, 0, False, "Expected exactly one header and summary")
        if any(record.get("record_type") != "step" for record in records[1:-1]):
            return ReplayResult(False, 0, False, "Run record order or type is invalid")

        header = records[0]
        summary = records[-1]
        steps = records[1:-1]
        environment = MockSpireEnvironment()
        if header.get("schema_version") != "run-v1":
            return ReplayResult(False, 0, False, "Unsupported run record schema")
        if header.get("ruleset") != environment.ruleset.as_dict():
            return ReplayResult(False, 0, False, "Ruleset identity mismatch")
        seed = _integer(header["seed"], "header seed")
        observation = environment.reset(seed)
        if observation.state_hash != header.get("initial_state_hash"):
            return ReplayResult(False, 0, False, "Initial state hash mismatch")

        objective = _mapping(header["objective"])
        remaining_budget = _integer(objective["whole_run_budget"], "whole-run budget")
        compute_used = 0
        for index, record in enumerate(steps):
            if record.get("decision_index") != index:
                return ReplayResult(False, index, victory, f"Decision index mismatch at {index}")
            legal_actions = tuple(environment.legal_actions())
            if record.get("legal_actions") != [action.as_dict() for action in legal_actions]:
                return ReplayResult(
                    False, index, victory, f"Legal actions mismatch at decision {index}"
                )
            transition_record = _mapping(record["transition"])
            if transition_record.get("observation") != observation.as_dict():
                return ReplayResult(False, index, victory, f"State mismatch at decision {index}")
            action_record = _mapping(transition_record["action"])
            action = LegalAction(
                action_id=str(action_record["action_id"]),
                kind=str(action_record["kind"]),
                payload=_mapping(action_record["payload"]),
            )
            transition = environment.step(action)
            if transition_record != transition.as_dict():
                return ReplayResult(
                    False,
                    index,
                    victory,
                    f"Transition mismatch at decision {index}",
                )
            tier = BudgetTier(str(record["budget_tier"]))
            compute_cost = _integer(record["compute_cost"], "compute cost")
            if compute_cost != tier.nominal_cost:
                return ReplayResult(
                    False, index, victory, f"Compute tier mismatch at decision {index}"
                )
            remaining_budget -= compute_cost
            compute_used += compute_cost
            if record.get("remaining_budget") != remaining_budget:
                return ReplayResult(
                    False,
                    index,
                    victory,
                    f"Remaining budget mismatch at decision {index}",
                )
            observation = transition.next_observation
            victory = transition.victory
            verified_steps = index + 1

        if not bool(observation.public_state["terminal"]):
            return ReplayResult(False, verified_steps, victory, "Run record is not terminal")
        if summary.get("victory") is not victory:
            return ReplayResult(False, verified_steps, victory, "Terminal result mismatch")
        if summary.get("terminal_reward") != (1.0 if victory else 0.0):
            return ReplayResult(False, verified_steps, victory, "Terminal reward mismatch")
        if summary.get("decisions") != verified_steps:
            return ReplayResult(False, verified_steps, victory, "Decision count mismatch")
        if summary.get("compute_used") != compute_used:
            return ReplayResult(False, verified_steps, victory, "Compute total mismatch")
        if observation.state_hash != summary.get("final_state_hash"):
            return ReplayResult(False, verified_steps, victory, "Final state hash mismatch")
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        return ReplayResult(False, verified_steps, victory, f"Malformed run record: {error}")
    return ReplayResult(True, verified_steps, victory, "Replay verified")


def _mapping(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Expected an object in replay record")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value
