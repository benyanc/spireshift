from typing import Any

import pytest

from spireshift.native_a8_archive_act1_selectors import (
    REST_CANCEL,
    REST_OPEN,
    REST_RETURN,
    automatic_upgrade,
    rest_cancellation,
    verify_upgrade,
)
from spireshift.native_a8_replay_probe import Divergence
from spireshift.native_a8_replay_source import Intent


def test_linked_rest_decline_precedes_the_completed_option() -> None:
    location = {"act": 1, "floor": 9}
    rows: list[dict[str, Any]] = [
        {"t": "header", "starting_deck": [{"id": "STRIKE_IRONCLAD", "up": 0}]},
        {"t": "hp", "dst": "player", "hp": 40},
        {
            "t": "decision",
            "options": [
                {"option_id": "smith", "option_index": 1, "presented": True, "selectable": True}
            ],
        },
        {
            "t": "decision",
            "decision_id": 4,
            "decision_type": "deck_select_upgrade",
            "decline_available": True,
            "gold_on_hand": 99,
        },
        {"t": "pick", "cards": [], "selector": "human", "n_picked": 0},
        {
            "t": "outcome",
            "decision_id": 4,
            "decision_type": "deck_select_upgrade",
            "outcome": "decline",
            "selected_option_indices": [],
            "n_selected": 0,
        },
        {"t": "hp", "dst": "player", "src": "heal", "hp": 64},
        {"t": "rest", "option": "heal", "option_index": 0},
    ]
    rows = [{**location, **row, "s": i} for i, row in enumerate(rows)]
    rest, pick = Intent("rest", rows[-1], rows[2]), Intent("pick", rows[4])
    plan = rest_cancellation(rows, rest, pick)
    assert plan is not None
    assert tuple(step.kind for step in plan) == (REST_OPEN, REST_CANCEL, REST_RETURN, "rest")
    assert plan[0].record["original_hp"] == 40
    assert plan[1].offer == rows[3]
    rows[5]["decision_id"] = 5
    assert rest_cancellation(rows, rest, pick) is None


def test_automatic_upgrade_requires_the_upgraded_physical_card() -> None:
    run = {"act": 1, "floor": 9}
    parent = Intent("play", {**run, "id": "ARMAMENTS", "up": 0, "turn": 2})
    pick = Intent(
        "pick",
        {**run, "s": 1, "n_picked": 1, "cards": [{"id": "STRIKE_IRONCLAD", "c": 7, "up": 0}]},
        hand=((7, "STRIKE_IRONCLAD"),),
    )
    rows = [parent.record, pick.record, {**run, "t": "upgrade", "id": "STRIKE_IRONCLAD", "c": 7}]
    effect = automatic_upgrade(rows, parent, pick)
    assert effect is not None
    card = {
        "definition_id": "STRIKE_IRONCLAD",
        "entity_id": {"public_slot": 3},
        "is_upgraded": True,
    }
    frame = {
        "public_input": {
            "context": {
                "persistent": {"run": run},
                "interaction": {
                    "kind": "combat_turn",
                    "content": {
                        "context": {
                            "round": 2,
                            "turn_owner": "player",
                            "is_play_phase": True,
                            "player": {"hand": [card]},
                        }
                    },
                },
            }
        }
    }
    verify_upgrade(frame, effect)
    card["is_upgraded"] = False
    with pytest.raises(Divergence, match="ordered hand"):
        verify_upgrade(frame, effect)
