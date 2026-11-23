from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


def test_visible_inventory_join_requires_exact_physical_provenance() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for public inventory identity checks")
    result = subprocess.run(
        [
            node,
            "--test",
            "scripts/engine-owned-inventory-identity-v1.test.mjs",
            "scripts/engine-executable-card-answer-v1.test.mjs",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_completion_recipe_keeps_its_parent_pin_when_reusing_the_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_selector_paired_v2 as parent
    from spireshift import native_selector_paired_v3 as current

    names = {
        current.PARENT_RECIPE,
        "baseline.py",
        "src/spireshift/native_selector_paired_v3.py",
        "scripts/compare-official-selectors-v3.sh",
        current.CONNECTOR,
        "configs/engine-qualification/sts2-v0.111.0-connector-ordered-completion-build-v34.json",
        "patches/engine/sts2-connector-v0.111.0-ordered-completion-v34.patch",
    }
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("scoped source\n")
    (tmp_path / current.PARENT_RECIPE).write_text(
        json.dumps({"implementation": {"baseline.py": "historical-pin"}})
    )
    # The CLI temporarily changes the reused runner's active recipe. Its
    # immutable parent declaration must not become a self-referential hash.
    monkeypatch.setattr(parent, "RECIPE", current.RECIPE)
    assert set(current.implementation(tmp_path)) == names


@pytest.mark.parametrize("compact", [False, True])
def test_enchant_menu_contains_every_executable_answer_and_no_empty_commit(compact: bool) -> None:
    from itertools import permutations

    from spireshift.native_selector_executable_checks import check_selector
    from spireshift.native_systematic_selectors_v2 import COMPACT, DIRECT

    count = 13 if compact else 3
    cards = [{"entity_id": f"physical-{i}"} for i in range(count)]
    actions: list[dict[str, Any]] = (
        [
            {"verb": "select", "subject_referent_id": row["entity_id"], "arguments": []}
            for row in cards
        ]
        if compact
        else [
            {
                "verb": "confirm",
                "subject_referent_id": None,
                "arguments": [
                    {"role": "selected_card", "referent_id": row["entity_id"]} for row in answer
                ],
            }
            for n in (1, 2, 3)
            for answer in permutations(cards, n)
        ]
    )
    surface = {
        "cards": cards,
        "min_select": 1,
        "max_select": 3,
        "cancelable": False,
        "selection_contract": COMPACT if compact else DIRECT,
        "answer_plan": {"selected": []},
    }
    observation = {
        "snapshot": {
            "interaction": {
                "kind": "card_selection",
                "content": {"context": {"kind": "shop"}, "surface": surface},
            },
            "bound_actions": {"actions": actions},
        },
        "reads": [
            {"kind": "run_deck", "content": {"cards": cards, "card_count": count}},
            {
                "kind": "shop_catalog",
                "content": {"cards": [], "relics": [], "potions": [], "card_removal": None},
            },
        ],
    }
    assert check_selector(observation, count, False)["min_select"] == 1
    actions.append({"verb": "confirm", "subject_referent_id": None, "arguments": []})
    with pytest.raises(ValueError, match="extra answer"):
        check_selector(observation, count, False)


@pytest.mark.parametrize("alteration", ["policy", "presentation", "receipt", "owner", "status"])
def test_startup_reset_refuses_delivered_input_or_a_reached_game_owner(alteration: str) -> None:
    from spireshift.native_selector_startup_reset import zero_action_startup

    control = {"policy_decisions": 0, "presentation_steps": 0, "shutdown_requested": False}
    rows: list[dict[str, Any]] = [
        {
            "kind": "observed",
            "snapshot": {"interaction": {"kind": "no_action"}, "status": "settling"},
        }
    ]
    zero_action_startup(rows, control)
    if alteration == "policy":
        control["policy_decisions"] = 1
    elif alteration == "presentation":
        control["presentation_steps"] = 1
    elif alteration == "receipt":
        rows[0]["kind"] = "receipt"
    elif alteration == "owner":
        rows[0]["snapshot"]["interaction"]["kind"] = "main_menu"
    else:
        rows[0]["snapshot"]["status"] = "ready"
    with pytest.raises(ValueError, match="zero delivered inputs"):
        zero_action_startup(rows, control)
