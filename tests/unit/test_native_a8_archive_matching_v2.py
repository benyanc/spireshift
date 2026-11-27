from dataclasses import replace
from typing import Any

import pytest

from spireshift.native_a8_archive_matching_v2 import installed, opening_effect, shop_records
from spireshift.native_a8_replay_probe import Divergence, next_choice
from spireshift.native_a8_replay_source import Intent, Journal


def sequence(*rows: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"s": i, "act": 1, "floor": 3, **row} for i, row in enumerate(rows)]


def journal(*intents: Intent) -> Journal:
    return Journal("SEED", {}, 70, "OVERGROWTH", "VANTOM_BOSS", {}, frozenset(), intents)


def merchant() -> list[dict[str, Any]]:
    starter = {"c": 1, "id": "STRIKE_IRONCLAD", "up": 0}
    bought = {"c": 2, "id": "RUPTURE", "up": 0}
    return sequence(
        {"t": "header", "floor": 0, "starting_deck": [starter]},
        {"t": "decision", "floor": 2, "decision_id": 5, "decision_type": "card_reward"},
        {
            "t": "shop",
            "gold": 150,
            "removal_cost": 100,
            "removal_stocked": True,
            "cards": [{"slot": 4, "id": "RUPTURE", "cost": 40, "stocked": True}],
        },
        {"t": "room", "kind": "merchant"},
        {"t": "acquire", "source": "reward", "decision_id": 5, **bought},
        {
            "t": "buy",
            "kind": "card",
            "slot": 4,
            "id": "RUPTURE",
            "cost_current": 40,
            "cost_resource": "gold",
            "gold_on_hand": 110,
        },
        {"t": "deck", "cards": [starter, bought]},
        {"t": "shop", "gold": 110, "removal_cost": 100, "removal_stocked": True, "cards": []},
        {
            "t": "decision",
            "decision_id": 6,
            "decision_type": "deck_select_remove",
            "min_select": 1,
            "max_select": 1,
            "decline_available": True,
            "gold_on_hand": 110,
        },
        {"t": "pick", "selector": "human", "n_picked": 0, "cards": []},
        {"t": "buy", "kind": "potion", "id": "FIRE_POTION"},
        {
            "t": "outcome",
            "decision_id": 6,
            "outcome": "decline",
            "n_selected": 0,
            "selected_option_indices": [],
        },
    )


def test_corroborated_shop_purchase_and_delayed_removal_decline_keep_order() -> None:
    rows = merchant()
    normalized, cancellations = shop_records(rows)
    assert normalized[4]["source"] == "shop"
    assert rows[4]["source"] == "reward"
    assert normalized[5]["archive_shop_after"]["gold"] == 110
    assert normalized[5]["archive_shop_after"]["deck"] == [
        ("STRIKE_IRONCLAD", 0, ""),
        ("RUPTURE", 0, ""),
    ]
    open_removal, cancel, successor = cancellations[9]
    assert [i.kind for i in (open_removal, cancel, successor)] == [
        "removal_owner",
        "shop_removal_cancel",
        "shop_effect",
    ]
    assert open_removal.record["cost_current"] == 100
    assert cancel.record["s"] == 9 < normalized[10]["s"]
    assert successor.record["archive_shop_after"] == cancel.record["archive_shop_before"]


@pytest.mark.parametrize("field,value", [("slot", 3), ("id", "CINDER"), ("gold_on_hand", 111)])
def test_stale_reward_tag_without_matching_purchase_is_rejected(field: str, value: Any) -> None:
    rows = merchant()
    rows[5][field] = value
    with pytest.raises(ValueError, match="exact purchase witness"):
        shop_records(rows)


def test_reward_with_current_offer_keeps_its_owner() -> None:
    rows = merchant()
    rows[1]["floor"] = 3
    normalized, _ = shop_records(rows)
    assert normalized[4] == rows[4]
    assert "archive_shop_after" not in normalized[5]


def test_decline_with_charge_is_rejected() -> None:
    rows = merchant()
    rows[10].update(decision_id=6, kind="removal_service")
    with pytest.raises(ValueError, match="recorded charge or effect"):
        shop_records(rows)


def test_cancel_requires_a_recorded_empty_human_pick() -> None:
    rows = merchant()
    rows[9]["selector"] = "automatic"
    with pytest.raises(ValueError, match="exact cancellation witness"):
        shop_records(rows)


def card(name: str, slot: int) -> dict[str, Any]:
    return {"definition_id": name, "entity_id": {"public_slot": slot}, "is_upgraded": False}


def action(verb: str, *slots: int) -> dict[str, Any]:
    return {
        "verb": verb,
        "label": verb,
        "subject": None,
        "arguments": [{"role": "selected_card", "entity": {"public_slot": s}} for s in slots],
    }


def opening() -> tuple[Intent, Intent, Intent]:
    enemy = {"id": "SPINNER", "hp": 42, "max_hp": 42}
    rows = sequence(
        {"t": "combat_start", "enemies": [enemy]},
        {"t": "draw", "c": 1, "id": "DEFEND", "turn_start": True},
        {"t": "draw", "c": 2, "id": "DEFEND", "turn_start": True},
        {"t": "turn", "n": 1, "round": 1, "side": "player"},
        {"t": "pick", "n_picked": 1, "cards": [{"c": 2, "id": "DEFEND", "up": 0}]},
        {"t": "discard", "c": 2, "id": "DEFEND"},
        {"t": "draw", "c": 3, "id": "STRIKE", "turn_start": False},
    )
    start = Intent("combat_start", rows[0])
    pick = Intent("pick", rows[4], hand=((1, "DEFEND"), (2, "DEFEND")))
    effect = opening_effect(rows, start, pick)
    assert effect is not None
    return (
        Intent("opening_discard_owner", {**rows[0], "archive_opening": effect}),
        replace(pick, record={**rows[4], "archive_opening": effect}),
        Intent("opening_discard_effect", {**rows[6], "archive_opening": effect}),
    )


def opening_frame(*, pending: bool, wrong_phase: bool = False) -> dict[str, Any]:
    hand = [card("DEFEND", 11), card("DEFEND", 12) if pending else card("STRIKE", 13)]
    return {
        "public_input": {
            "context": {
                "persistent": {"run": {"act": 1, "floor": 3}},
                "interaction": {
                    "kind": "card_selection" if pending else "combat_turn",
                    "content": {
                        "context": {
                            "kind": "selection" if pending else "combat",
                            "owner_kind": "combat",
                            "round": 2 if wrong_phase else 1,
                            "turn_owner": "player",
                            "is_play_phase": not pending,
                            "player": {"hand": hand},
                            "enemies": [{"definition_id": "SPINNER", "hp": 42, "max_hp": 42}],
                        },
                        "surface": {
                            "cards": hand,
                            "min_select": 0,
                            "max_select": 2,
                            "require_manual_confirmation": True,
                            "cancelable": False,
                        },
                    },
                },
                "reads": [
                    {
                        "kind": "combat_piles",
                        "content": {
                            "zones": [
                                {
                                    "zone": "discard",
                                    "cards": [] if pending else [card("DEFEND", 12)],
                                }
                            ]
                        },
                    }
                ],
            },
            "candidates": [action("confirm"), action("confirm", 11), action("confirm", 12)],
        }
    }


def test_opening_discard_selects_physical_copy_and_requires_replacement() -> None:
    j = journal(*opening())
    with installed():
        assert next_choice(opening_frame(pending=True), j, 0, 3) == (2, 2, "native")
        assert next_choice(opening_frame(pending=False), j, 2, 3) == (None, 3, "native")
        broken = opening_frame(pending=False)
        broken["public_input"]["context"]["interaction"]["content"]["context"]["player"]["hand"] = [
            card("DEFEND", 11),
            card("BASH", 13),
        ]
        with pytest.raises(Divergence, match="opening hand"):
            next_choice(broken, j, 2, 3)


def test_opening_discard_rejects_a_later_turn() -> None:
    with installed(), pytest.raises(Divergence, match="opening decision owner"):
        next_choice(opening_frame(pending=True, wrong_phase=True), journal(*opening()), 0, 3)


def test_opening_discard_factors_do_not_advance_until_native_confirm() -> None:
    j = journal(*opening())
    frame = opening_frame(pending=True)
    surface = frame["public_input"]["context"]["interaction"]["content"]["surface"]
    surface["answer_plan"] = {"selected": []}
    frame["public_input"]["candidates"].append(
        {
            **action("select"),
            "subject": {"public_slot": 12},
        }
    )
    with installed():
        assert next_choice(frame, j, 0, 3) == (3, 1, "local_answer_factor")
        surface["answer_plan"]["selected"] = [1]
        frame["public_input"]["candidates"] = [action("confirm")]
        assert next_choice(frame, j, 1, 3) == (0, 2, "native")
