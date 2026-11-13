from __future__ import annotations

import ast
import copy
import inspect
from typing import Any

import pytest

from spireshift import native_chest_endings, native_e2e_live
from spireshift.native_chest_live import ScriptedPolicy, compare_frames, select_action


def chest_frame() -> dict[str, Any]:
    candidates = [
        {"verb": "activate", "subject": {"role": "relic"}, "label": "Take Relic", "arguments": []},
        {
            "verb": "skip",
            "subject": None,
            "label": "Skip the visible treasure relic",
            "arguments": [],
        },
    ]
    return {
        "binding_id": "current-binding",
        "observation": {"snapshot_id": "before", "runtime_instance_id": "one"},
        "actions": [
            {"bound_action_id": "take", "key": "take"},
            {"bound_action_id": "skip", "key": "skip"},
        ],
        "public_input": {
            "context": {
                "interaction": {
                    "kind": "treasure_room",
                    "content": {
                        "surface": {
                            "stage": "relic_choice",
                            "can_choose": True,
                            "can_skip": True,
                            "can_proceed": False,
                        }
                    },
                }
            },
            "candidates": candidates,
        },
    }


@pytest.mark.parametrize("flag", [False, None, 0, 1, "true"])
def test_partial_or_untyped_skip_never_narrows_the_scripted_menu(flag: Any) -> None:
    frame = chest_frame()
    frame["public_input"]["context"]["interaction"]["content"]["surface"]["can_skip"] = flag
    with pytest.raises(ValueError, match="not settled"):
        select_action(frame, "take_relic")


def test_unknown_or_ambiguous_script_has_no_first_action_fallback() -> None:
    frame = chest_frame()
    with pytest.raises(ValueError, match="unique"):
        select_action(frame, "unknown")
    frame["public_input"]["candidates"].append(
        copy.deepcopy(frame["public_input"]["candidates"][0])
    )
    with pytest.raises(ValueError, match="unique"):
        select_action(frame, "take_relic")


@pytest.mark.parametrize(
    "change", ["delivery", "runtime_instance_id", "bound_action_id", "before_snapshot_id"]
)
def test_scripted_receipt_rejects_uncertain_or_foreign_delivery(change: str) -> None:
    policy = ScriptedPolicy(["skip_relic"])
    choice = policy.choose(chest_frame())
    ack = {
        "binding_id": "current-binding",
        "delivery": "delivered",
        "bound_action_id": choice["bound_action_id"],
        "runtime_instance_id": "one",
        "before_snapshot_id": "before",
        "successor_snapshot_id": "after",
    }
    ack[change] = "foreign"
    with pytest.raises(ValueError, match="no retry"):
        policy.acknowledge(ack)
    assert policy.decisions == 0
    with pytest.raises(ValueError, match="No diagnostic retry"):
        policy.choose(chest_frame())


def test_saved_comparison_keeps_boolean_number_differences_and_never_realigns() -> None:
    left, right = chest_frame(), chest_frame()
    right["public_input"]["context"]["interaction"]["content"]["surface"]["can_skip"] = 1
    result = compare_frames([left, chest_frame()], [right, chest_frame()])
    assert result["equal"] is False
    assert result["matching_states"] == 0
    assert result["later_divergent_states_realigned"] is False


def test_natural_ending_choice_cpu_time_and_final_successor_guards_are_preserved() -> None:
    previous = ast.parse(inspect.getsource(native_e2e_live.native_run))
    current = ast.parse(inspect.getsource(native_chest_endings.native_run))
    for node in ast.walk(previous):
        if isinstance(node, ast.Name) and node.id == "RelicWorker":
            node.id = "ChestWorker"
        if isinstance(node, ast.Constant) and node.value == "scripts/engine-shared-input-v15.mjs":
            node.value = "scripts/engine-shared-input-v16.mjs"
    assert ast.dump(previous) == ast.dump(current)
