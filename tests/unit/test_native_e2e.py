from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_e2e_contract import (
    compare_observations,
    difference_paths,
    equivalent_replayed_choice,
    terminal_facts,
)
from spireshift.native_e2e_live import native_run
from spireshift.native_flow_verification_v12 import records


def frame(terminal: bool = False, gold: int = 7) -> dict[str, Any]:
    return {
        "terminal": terminal,
        "source_family": "game_over" if terminal else "combat_turn",
        "terminal_actions_are_presentation": terminal,
        "ending": {"victory": False, "basis": "native_public_explicit_terminal_boolean"}
        if terminal
        else None,
        "binding_id": "binding",
        "observation": {"snapshot_id": "current", "runtime_instance_id": "one"},
        "actions": [{"key": "end", "raw_index": 0, "bound_action_id": "end"}],
        "public_input": {
            "context": {
                "persistent": {
                    "scope": "active_single_player_run",
                    "run": {"ascension": 8},
                    "player": {"gold": gold},
                },
                "reads": [{"kind": "run_deck", "content": {"cards": [], "card_count": 0}}],
                "interaction": {"kind": "game_over" if terminal else "combat_turn"},
            },
            "candidates": [],
        },
    }


def test_different_terminal_ui_presentation_does_not_discard_game_facts() -> None:
    native, official = frame(True), frame(True)
    official["ending"]["basis"] = "shipped_public_RunHistory_Win_context"
    official["public_input"]["candidates"] = [{"label": "Continue"}]
    assert compare_observations([frame(), native], [frame(), official])["complete_workflow_equal"]
    official["public_input"]["context"]["persistent"]["new_native_fact"] = 2
    assert not compare_observations([frame(), native], [frame(), official])[
        "complete_workflow_equal"
    ]


def test_equal_endings_never_realign_a_divergent_prefix() -> None:
    result = compare_observations([frame(gold=1), frame(True)], [frame(gold=2), frame(True)])
    assert not result["complete_workflow_equal"]
    assert result["matching_policy_inputs"] == 0
    assert not result["later_divergent_states_realigned"]


@pytest.mark.parametrize(
    "ending", [None, {}, {"victory": 0}, {"victory": False, "basis": "HP_zero"}]
)
def test_only_explicit_native_boolean_endings_qualify(ending: Any) -> None:
    value = frame(True)
    value["ending"] = ending
    with pytest.raises(ValueError):
        terminal_facts(value)


def test_metadata_only_replay_exception_is_narrow() -> None:
    old = {
        "model_id": "old",
        "binding_id": "old",
        "action_index": 0,
        "draw": 0.4,
        "log_probability": -0.2,
        "unfamiliar_field": 3,
    }
    current = {**old, "model_id": "new", "binding_id": "new"}
    assert equivalent_replayed_choice(current, old)
    for name in ["action_index", "draw", "log_probability", "unfamiliar_field"]:
        assert not equivalent_replayed_choice({**current, name: 99}, old)


def test_public_comparison_preserves_false_zero_missing_and_all_difference_paths() -> None:
    assert difference_paths({"flag": False}, {"flag": 0}) == ["/flag"]
    assert difference_paths([{"flag": False}], [{"flag": 0}]) == ["/0/flag"]
    assert difference_paths({"flag": False, "a": 1, "b": None}, {"flag": 0, "a": 2}) == [
        "/a",
        "/b",
        "/flag",
    ]


@pytest.mark.parametrize("terminal_at_guard", [True, False])
def test_native_choice_guard_captures_final_successor_and_never_calls_it_a_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal_at_guard: bool,
) -> None:
    values = [frame(), frame(), frame(terminal_at_guard)]

    class Worker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.index = 0

        def request(self, command: str, **kwargs: Any) -> dict[str, Any]:
            if command == "step":
                self.index += 1
            return {"snapshot": {"snapshot_id": "current", "index": self.index}, "reads": []}

        def cpu_seconds(self) -> float:
            return 0.0

        def close(self) -> dict[str, Any]:
            return {"clean_exit": True, "runtime_errors": []}

        def stop(self) -> None:
            pass

    class Converter:
        def __init__(self, *args: Any) -> None:
            pass

        def project(self, snapshot: dict[str, Any], *args: Any) -> dict[str, Any]:
            return copy.deepcopy(values[snapshot["index"]])

        def commit(self, *args: Any) -> None:
            pass

        def close(self) -> None:
            pass

        def stop(self) -> None:
            pass

    class Policy:
        decisions = 0

        def choose(self, value: dict[str, Any]) -> dict[str, Any]:
            assert value["terminal"] is False
            return {"action_index": 0}

        def acknowledge(self, *args: Any) -> None:
            self.decisions += 1

    import time
    from types import SimpleNamespace

    import spireshift.native_e2e_live as module

    monkeypatch.setattr(module, "RelicWorker", Worker)
    monkeypatch.setattr(module, "JsonLines", Converter)
    monkeypatch.setattr(module, "converter_cpu_seconds", lambda converter: 0.0)
    context = {
        "qualification": SimpleNamespace(root=tmp_path),
        "config": {"node": "node", "maximum_decisions": 2},
        "native": {},
        "native_helpers": {},
    }
    policy: Any = Policy()
    result = native_run(
        context, {"seed": "SEED"}, tmp_path / "case", policy, time.monotonic() + 120
    )
    rows = list(records(tmp_path / "case/shared-public.jsonl.gz"))
    assert result["policy_decisions"] == 2
    assert result["ending"] is not None if terminal_at_guard else result["ending"] is None
    assert (result["status"] == "native_natural_ending_pass") is terminal_at_guard
    assert rows[-1]["kind"] == ("policy_input" if terminal_at_guard else "final_observation")
