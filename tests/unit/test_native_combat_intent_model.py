from __future__ import annotations

import math
from typing import Any

import pytest
from test_native_a8_card_display_model import menu, parent
from test_native_action_context import score

from spireshift.native_a8_card_display_model import encode as historical_encode
from spireshift.native_a8_card_display_model import extend
from spireshift.native_combat_intent_model import (
    TARGET_ATTACK,
    candidate_attack,
    copy_with_intents,
    encode,
    intent_total,
)


def enemy(slot: int, intents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "role": "target",
        "entity": {"role": "enemy", "public_slot": slot, "properties": {"intents": intents}},
    }


def test_repaired_damage_reaches_the_existing_actor_column() -> None:
    public = menu()
    public["candidates"][0]["arguments"] = [
        enemy(7, [{"type": "Attack", "damage": 4, "hits": 3, "total_damage": 12}, {"type": "Buff"}])
    ]
    source = extend(parent(), ("damage",))
    copied = copy_with_intents(source)
    old, old_context = historical_encode(public, source.model, score())
    new, new_context = encode(public, copied.model, score())
    assert old[0][TARGET_ATTACK] == math.asinh(4) / 5
    assert new[0] == {**old[0], TARGET_ATTACK: math.asinh(12) / 5}
    assert new[1:] == old[1:] and new_context == old_context
    assert copied.model.native == source.model.native
    assert copied.actor_adam == source.actor_adam and copied.value_adam == source.value_adam


def test_conditional_damage_and_multiple_targets_keep_exact_owners() -> None:
    first = enemy(7, [{"type": "DeathBlow", "damage": 8}, {"type": "Buff"}])
    second = enemy(9, [{"type": "Attack", "damage": 4, "hits": 2}])
    assert candidate_attack({"arguments": [first, second, first]}) == 16
    assert candidate_attack({"arguments": []}) is None
    assert intent_total({"type": "Defend"}) == 0
    assert intent_total({"type": "Attack", "total_damage": 0}) == 0


@pytest.mark.parametrize(
    "intent",
    [
        {"type": "Attack"},
        {"damage": True, "hits": 1},
        {"damage": 5, "hits": 0},
        {"damage": 5, "hits": 2, "total_damage": 5},
    ],
)
def test_incomplete_or_conflicting_attack_facts_raise(intent: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        intent_total(intent)
