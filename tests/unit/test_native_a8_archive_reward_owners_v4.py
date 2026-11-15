from typing import Any

import pytest

from spireshift.native_a8_archive_reward_owners_v4 import CARD_LABEL, compile_intents, installed
from spireshift.native_a8_replay_probe import Divergence, next_choice
from spireshift.native_a8_replay_source import Journal


def journal(*entries: dict[str, Any]) -> Journal:
    rows = [{"s": index, "act": 1, "floor": 1, **row} for index, row in enumerate(entries)]
    return Journal("SEED", {}, 64, "", "", {}, frozenset(), compile_intents(rows))


def frame(kind: str, surface: dict[str, Any], actions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "public_input": {
            "candidates": actions,
            "context": {
                "interaction": {"kind": kind, "content": {"surface": surface, "context": {}}},
                "persistent": {
                    "run": {"act": 1, "floor": 1},
                    "player": {"gold": 211, "relics": []},
                },
                "reads": [{"kind": "run_deck", "content": {"cards": []}}],
            },
        }
    }


def activate(role: str, slot: int, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "verb": "activate",
        "arguments": [],
        "subject": {
            "role": role,
            "public_slot": slot,
            "properties": properties,
        },
    }


def offer(number: int, name: str) -> dict[str, Any]:
    return {
        "t": "decision",
        "decision_id": number,
        "decision_type": "card_reward",
        "offer_generation": 0,
        "can_reroll": False,
        "options": [{"option_kind": "card", "option_id": name, "up": 0, "selectable": True}],
    }


def test_card_reward_opening_follows_generation_order_and_checks_the_child() -> None:
    a = {"c": 1, "id": "BASH", "up": 0}
    b = {"c": 2, "id": "DARKNESS", "up": 0}
    j = journal(
        {"t": "header", "starting_deck": []},
        offer(10, "BASH"),
        offer(11, "DARKNESS"),
        {"t": "acquire", "source": "reward", "decision_id": 11, "option_index": 0, **b},
        {"t": "resolve", "reward_kind": "CardReward"},
        {"t": "deck", "cards": [b]},
        {"t": "acquire", "source": "reward", "decision_id": 10, "option_index": 0, **a},
        {"t": "resolve", "reward_kind": "CardReward"},
        {"t": "deck", "cards": [b, a]},
    )
    available = [
        {
            "kind": "card",
            "label": CARD_LABEL,
            "description": CARD_LABEL,
            "enabled": True,
            "entity_id": {"public_slot": slot},
        }
        for slot in (14, 15)
    ]
    parent = frame(
        "reward_claim",
        {"rewards": available},
        [activate("reward", 14, available[0]), activate("reward", 15, available[1])],
    )
    child = frame(
        "card_reward_selection",
        {
            "cards": [
                {"definition_id": "BASH", "is_upgraded": False, "entity_id": {"public_slot": 1}},
            ]
        },
        [],
    )
    with installed():
        assert next_choice(parent, j, 0, 4) == (1, 0, "native")
        with pytest.raises(Divergence, match="ordered card rewards"):
            next_choice(child, j, 0, 4)
        child["public_input"]["context"]["interaction"]["content"]["surface"]["cards"][0][
            "definition_id"
        ] = "DARKNESS"
        action = activate("card", 1, {})
        child["public_input"]["candidates"] = [{**action, "verb": "select"}]
        assert next_choice(child, j, 0, 4) == (0, 1, "native")


def test_slotless_relic_matches_item_and_price_and_checks_ownership() -> None:
    j = journal(
        {"t": "header", "starting_deck": []},
        {"t": "relic", "id": "FAKE_LEES_WAFFLE"},
        {
            "t": "buy",
            "kind": "relic",
            "id": "FAKE_LEES_WAFFLE",
            "cost_resource": "gold",
            "cost_current": 53,
            "gold_on_hand": 158,
        },
    )
    stock = [
        {
            "price": 53,
            "can_purchase": True,
            "stocked": True,
            "entity_id": {"public_slot": slot},
            "relic": {"definition_id": name},
        }
        for slot, name in ((40, "FAKE_SNECKO_EYE"), (41, "FAKE_LEES_WAFFLE"))
    ]
    observed = frame(
        "shop_inventory",
        {"inventory_open": True, "relics": stock},
        [activate("relic", slot, {"price": 53}) for slot in (40, 41)],
    )
    player = observed["public_input"]["context"]["persistent"]["player"]
    with installed():
        assert next_choice(observed, j, 0, 2) == (1, 1, "native")
        player["gold"] = 158
        with pytest.raises(Divergence, match="merchant relic copies"):
            next_choice(observed, j, 1, 2)
        player["relics"] = [{"definition_id": "FAKE_LEES_WAFFLE"}]
        assert next_choice(observed, j, 1, 2) == (None, 2, "native")
