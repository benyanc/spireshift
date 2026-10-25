from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_atomic_inputs_v2 import load
from spireshift.native_atomic_verification_v2 import verify_atomic_completion
from spireshift.native_live_checkpoint_v10 import run


def test_invalid_atomic_recipe_has_no_effects(tmp_path: Path) -> None:
    recipe = tmp_path / "bad.json"
    recipe.write_text(json.dumps({"schema_version": "old"}))
    with pytest.raises(ValueError, match="finite"):
        load(tmp_path, recipe)
    assert list(tmp_path.iterdir()) == [recipe]


def test_saved_atomic_audit_cannot_launch_games(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot launch"):
        run(tmp_path, {"config": {"stage": "saved_only_checks"}})
    assert not list(tmp_path.iterdir())


def completion() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    frame = {
        "observation": {"snapshot_id": "root"},
        "actions": [
            {
                "raw_index": 0,
                "verb": "confirm",
                "arguments": [{"role": "selected_card", "referent_id": "a"}],
            }
        ],
    }
    choice = {"bound_action_id": "commit", "action_index": 0}
    row = {
        "root_bound_action_id": "commit",
        "root_snapshot_id": "root",
        "proof": {
            "root_snapshot_id": "root",
            "status": "committed",
            "game_committed": True,
            "request_id": "request",
            "chosen_card_ids": ["a"],
            "steps": [
                {"kind": "select", "card_id": "a", "candidate_id": "s", "accepted": True},
                {"kind": "preview", "candidate_id": "p", "accepted": True},
                {"kind": "confirm", "candidate_id": "c", "accepted": True},
            ],
        },
    }
    return row, frame, choice


def test_saved_completed_macro_reconstructs_exact_selected_copy() -> None:
    row, frame, choice = completion()
    verify_atomic_completion(row, frame, choice, {"bound_actions": {"actions": frame["actions"]}})


@pytest.mark.parametrize("mutation", ["wrong_copy", "stale", "pending", "rejected", "no_confirm"])
def test_saved_macro_requires_actual_completion(mutation: str) -> None:
    row, frame, choice = completion()
    proof = row["proof"]
    if mutation == "wrong_copy":
        proof["chosen_card_ids"] = ["b"]
    elif mutation == "stale":
        proof["root_snapshot_id"] = "old"
    elif mutation == "pending":
        proof["status"] = "pending"
    elif mutation == "rejected":
        proof["steps"][0]["accepted"] = False
    else:
        proof["steps"].pop()
    with pytest.raises(ValueError, match="Unverified"):
        verify_atomic_completion(
            row, frame, choice, {"bound_actions": {"actions": frame["actions"]}}
        )


def test_atomic_source_contracts_and_targeted_transactions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use pinned Node for the actual-game interface checks")
    result = subprocess.run(
        [
            node,
            "--test",
            "scripts/engine-atomic-selection-v1.test.mjs",
            "scripts/engine-input-layout-v6.test.mjs",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_proof_verification_does_not_modify_the_source_evidence() -> None:
    row, frame, choice = completion()
    before = copy.deepcopy((row, frame, choice))
    verify_atomic_completion(row, frame, choice, {"bound_actions": {"actions": frame["actions"]}})
    assert (row, frame, choice) == before


def test_removal_effect_requires_the_actual_chosen_physical_copy() -> None:
    from spireshift.native_selection_effects import removed_cards

    first = {"entity_id": "a", "name": "Strike", "cost": "1"}
    second = {"entity_id": "b", "name": "Strike", "cost": "0"}
    assert removed_cards([first, second], [second], ["a"])["other_cards_unchanged"]
    with pytest.raises(ValueError, match="different copies"):
        removed_cards([first, second], [first], ["a"])
    with pytest.raises(ValueError, match="different copies"):
        removed_cards([first, second], [{**second, "cost": "2"}], ["a"])


def test_owner_launcher_uses_the_qualified_runner_and_pinned_plan() -> None:
    import hashlib

    root = Path(__file__).resolve().parents[2]
    launcher = root / "scripts/compare-semantic-selection-v3.sh"
    text = launcher.read_text()
    assert "check-semantic-selection-v2.sh" in text
    assert "check-semantic-selection-v1.sh" not in text
    plan = json.loads(
        (
            root / "configs/native-compatibility/sts2-v0.111.0-a8-semantic-selection-canary-v1.json"
        ).read_text()
    )
    assert (
        plan["sources"]["scripts/compare-semantic-selection-v3.sh"]
        == hashlib.sha256(launcher.read_bytes()).hexdigest()
    )
    assert plan["maximum_decisions"] == 128
    assert plan["session_limits"]["wall_seconds"] == 900
    assert len(plan["cases"]) == 4
    assert {c["player"] for c in plan["cases"]} == {2, 3}
    assert len({c["seed"] for c in plan["cases"]}) == 2
    runner = (root / "scripts/check-semantic-selection-v2.sh").read_text()
    assert "spireshift.native_live_checkpoint_v10" in runner
