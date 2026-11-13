from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from spireshift import native_action_lifecycle_endings, native_entry_text_endings
from spireshift.native_action_lifecycle_audit import audit_inventory, command_rows
from spireshift.native_action_lifecycle_live import ScriptedPolicy, effects, select_action


def test_new_lifecycle_inventory_rejects_unreviewed_cli_command() -> None:
    layer: dict[str, Any] = {
        "files": [
            {
                "path": "RunSimulator.cs",
                "methods": [
                    {
                        "name": "ExecuteAction",
                        "switches": [
                            {
                                "expression": "action",
                                "arms": [
                                    {
                                        "labels": ['case "new_unreviewed_action":'],
                                        "calls": ["DoNewAction"],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    with pytest.raises(ValueError, match="Unreviewed CLI action"):
        command_rows(layer)


def test_partial_inventory_cannot_claim_all_execution_layers() -> None:
    with pytest.raises(ValueError, match="all original"):
        audit_inventory({"layers": []})


@pytest.mark.parametrize("name", ["native_run", "observations", "preflight", "run", "main"])
def test_whole_run_budgets_endings_and_no_retry_guards_remain_exact(name: str) -> None:
    assert ast.dump(
        ast.parse(inspect.getsource(getattr(native_action_lifecycle_endings, name)))
    ) == ast.dump(ast.parse(inspect.getsource(getattr(native_entry_text_endings, name))))


def test_script_cannot_invent_missing_potion_or_play_another_card() -> None:
    frame = {"source_family": "reward_claim", "public_input": {"candidates": []}}
    with pytest.raises(ValueError, match="exact declared"):
        select_action(frame, "use_blood")
    frame["source_family"] = "combat_turn"
    with pytest.raises(ValueError, match="diagnostic attack"):
        select_action(frame, "use_blood")


def test_unowned_final_capture_is_not_a_completed_control() -> None:
    with pytest.raises(ValueError, match="Unowned"):
        ScriptedPolicy(["use_blood"] * 8).observe_successor({})


def test_premature_unhealed_successor_rejects_saved_failure_shape() -> None:
    before = {
        "persistent": {
            "player": {"hp": 54, "max_hp": 80, "potions": [{"definition_id": "BLOOD_POTION"}]}
        },
        "interaction": {"kind": "reward_claim"},
    }
    after = {
        "persistent": {"player": {"hp": 54, "max_hp": 80, "potions": []}},
        "interaction": {"kind": "reward_claim"},
    }
    frames = [{}, {"public_input": {"context": before}}, {"public_input": {"context": after}}]
    with pytest.raises(ValueError, match="Premature"):
        effects({"instructions": ["use_blood"] * 8}, frames)
