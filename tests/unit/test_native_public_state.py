from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_rest_exploration import rest

from spireshift.native_public_state import PublicVocabulary, public_state_facts


def graph() -> dict[str, Any]:
    public = rest()
    card = {
        "entity_id": {"public_slot": 13},
        "definition_id": "FOREIGN_CARD",
        "cost": "1",
        "is_upgraded": False,
        "enchantment": {"name": "Example", "amount": 2},
    }
    enemy = {
        "entity_id": {"public_slot": 7},
        "definition_id": "ENEMY",
        "hp": 20,
        "statuses": [{"name": "Strength", "amount": 2}, {"name": "Dexterity", "amount": 7}],
        "intents": [{"type": "Attack", "damage": 6, "hits": 2}],
    }
    public["context"]["interaction"]["content"] = {
        "enemies": [enemy],
        "hand": [card],
        "energy": 2,
        "stars": 3,
        "orbs": [{"name": "Lightning", "passive": 3}],
    }
    public["context"]["persistent"]["player"]["relics"] = [
        {"definition_id": "RELIC_A", "counter": 2}
    ]
    public["context"]["reads"] = [
        {
            "kind": "run_deck",
            "content": {
                "card_count": 2,
                "cards": [card, {"definition_id": "OTHER_CARD", "cost": "0"}],
            },
        },
        {
            "kind": "combat_piles",
            "content": {
                "zones": [
                    {
                        "zone": "draw",
                        "ordering_semantics": "unordered_multiset",
                        "cards": [card, {"definition_id": "OTHER_CARD", "cost": "0"}],
                    }
                ]
            },
        },
    ]
    public["candidates"][0]["subject"] = {"public_slot": 13, "role": "card", "properties": card}
    public["candidates"][0]["arguments"] = [{"role": "target", "entity_id": {"public_slot": 7}}]
    return public


def test_representation_preserves_owned_amounts_and_identity_not_only_counts() -> None:
    source = graph()
    original = copy.deepcopy(source)
    facts = public_state_facts(source)
    paths = [
        ("context", "persistent", "player", "relics", 0, "definition_id"),
        ("context", "interaction", "content", "hand", 0, "cost"),
        ("context", "interaction", "content", "hand", 0, "is_upgraded"),
        ("context", "interaction", "content", "hand", 0, "enchantment", "amount"),
        ("context", "interaction", "content", "enemies", 0, "intents", 0, "hits"),
        ("context", "interaction", "content", "stars"),
        ("context", "interaction", "content", "orbs", 0, "passive"),
    ]
    for path in paths:
        changed = copy.deepcopy(source)
        node: Any = changed
        for key in path[:-1]:
            node = node[key]
        value = node[path[-1]]
        node[path[-1]] = (
            not value
            if isinstance(value, bool)
            else value + 1
            if isinstance(value, int)
            else value + "_changed"
        )
        assert public_state_facts(changed) != facts
    swapped = copy.deepcopy(source)
    statuses = swapped["context"]["interaction"]["content"]["enemies"][0]["statuses"]
    statuses[0]["amount"], statuses[1]["amount"] = 7, 2
    assert public_state_facts(swapped) != facts
    assert source == original


def test_slots_menu_order_and_unordered_pile_order_are_not_game_facts() -> None:
    source = graph()
    facts = public_state_facts(source)
    source["candidates"].reverse()
    source["context"]["reads"].reverse()
    for read in source["context"]["reads"]:
        if read["kind"] == "run_deck":
            read["content"]["cards"].reverse()
        else:
            read["content"]["zones"][0]["cards"].reverse()
    assert public_state_facts(source) == facts

    def rename(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "public_slot":
                    value[key] = 1000 - item
                else:
                    rename(item)
        elif isinstance(value, list):
            for item in value:
                rename(item)

    rename(source)
    assert public_state_facts(source) == facts
    assert not any("1000" in k or "public_slot" in k for k in facts)


def test_ordered_visible_sequences_and_public_relationships_remain_distinct() -> None:
    source = graph()
    before = public_state_facts(source)
    source["context"]["interaction"]["content"]["hand"].append({"definition_id": "DIFFERENT"})
    ordered = public_state_facts(source)
    source["context"]["interaction"]["content"]["hand"].reverse()
    assert ordered != public_state_facts(source)
    source = graph()
    source["candidates"][0]["arguments"][0]["entity_id"] = {"public_slot": 13}
    assert public_state_facts(source) != before
    source["candidates"][0]["arguments"][0]["entity_id"] = {"public_slot": 999}
    with pytest.raises(ValueError, match="Unresolved"):
        public_state_facts(source)


@pytest.mark.parametrize("field", ["rng_state", "snapshot_id"])
def test_public_boundary_rejects_hidden_or_transport_inputs(field: str) -> None:
    source = graph()
    source["context"][field] = 1
    with pytest.raises(ValueError):
        public_state_facts(source)


def test_vocabulary_uses_only_supplied_fitting_games_and_exposes_missing_facts() -> None:
    vocabulary = PublicVocabulary.fit(
        [[{"card_A": 1, "cost": 0}, {"card_B": 1}], [{"card_A": 2}]], 2
    )
    assert vocabulary.names == ("card_A", "card_B")
    values, report = vocabulary.encode({"card_A": 3, "UNSEEN_RELIC": 1})
    assert values == (3, 0) and report["unrepresented_facts"] == 1
    with pytest.raises(ValueError):
        PublicVocabulary.fit([], 0)
