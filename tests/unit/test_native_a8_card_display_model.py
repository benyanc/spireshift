from __future__ import annotations

import math
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score

from spireshift.engine_neural import DIRECT, INPUT_SCHEMA
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_bank_fit import Decision, Factor, update
from spireshift.native_a8_card_display_model import (
    HAND_VIEW,
    CardDisplayModel,
    candidate_stats,
    encode,
    extend,
    load,
)
from spireshift.native_a8_head_policy import HeadState, initialize, save
from spireshift.native_context_cache import cached_model
from spireshift.native_structured_model import BASE, resize


def menu() -> dict[str, Any]:
    hand: list[dict[str, Any]] = [
        {
            "entity_id": {"public_slot": slot},
            "definition_id": "STRIKE_IRONCLAD",
            "cost": "1",
            "public_card_views": {
                HAND_VIEW: {
                    "can_play": True,
                    "stats": {"damage": damage, "block": 0} if slot == 5 else {"damage": damage},
                    "after_upgrade": {"stats": {"damage": 99}},
                },
                "read:deck:/cards/*": {"stats": {"damage": 101}},
            },
        }
        for slot, damage in ((4, 6), (5, 9))
    ]
    return {
        "schema_version": INPUT_SCHEMA,
        "context": {
            "interaction": {
                "kind": "combat_turn",
                "content": {"context": {"kind": "combat", "player": {"hand": hand}}},
            },
            "persistent": {"player": {"hp": 50, "max_hp": 80}, "run": {"act": 1, "floor": 2}},
        },
        "candidates": [
            {
                "verb": "play",
                "subject": {
                    "role": "playable_card",
                    "public_slot": card["entity_id"]["public_slot"],
                    "properties": card,
                },
                "arguments": [],
            }
            for card in hand
        ]
        + [{"verb": "end_turn", "subject": None, "arguments": []}],
    }


def parent() -> HeadState:
    base = cached_model(model(mode="native-original-quarter-v1"))
    adam = Adam(10, (0.01,) * base.parameter_count, (0.005,) * base.parameter_count)
    return initialize(base, adam, "shared")


def test_current_stats_resolve_distinct_copies_and_never_use_the_upgrade_preview() -> None:
    public = menu()
    assert candidate_stats(public) == ({"damage": 6.0}, {"damage": 9.0, "block": 0.0}, {})
    public["candidates"].reverse()
    assert candidate_stats(public) == ({}, {"damage": 9.0, "block": 0.0}, {"damage": 6.0})
    public["candidates"][1]["subject"]["public_slot"] = 4
    with pytest.raises(ValueError, match="exact current hand card"):
        candidate_stats(public)


def test_adds_direct_stats_with_presence_and_keeps_the_complete_menu() -> None:
    public = menu()
    old = parent().model
    new = extend(parent(), ("block", "damage")).model
    reference, state = encode(public, old, score())
    rows, expanded_state = encode(public, new, score())
    assert all(DIRECT.index("damage") not in row for row in reference)
    assert [row.get(BASE) for row in rows] == [None, 1.0, None]
    assert [row.get(BASE + 1) for row in rows] == [None, 0.0, None]
    assert [row.get(BASE + 3) for row in rows] == [math.asinh(6) / 5, math.asinh(9) / 5, None]
    assert tuple({i: v for i, v in row.items() if i < BASE} for row in rows) == reference
    assert score_features(cast(Any, new.actor), rows) == pytest.approx(
        score_features(cast(Any, old.actor), reference), abs=1e-10
    )
    assert new.value(expanded_state) == pytest.approx(old.value(state), abs=1e-10)


def test_added_display_columns_learn_and_round_trip_every_inherited_moment(tmp_path: Path) -> None:
    before = parent()
    extended = extend(before, ("block", "damage"))
    model = extended.model
    for old, expanded in (
        (before.model.weights(), model.weights()),
        (
            before.actor_adam.first + before.value_adam.first,
            extended.actor_adam.first + extended.value_adam.first,
        ),
        (
            before.actor_adam.second + before.value_adam.second,
            extended.actor_adam.second + extended.value_adam.second,
        ),
    ):
        assert resize(expanded, model.actor.dimension, BASE, model.actor.hidden_units) == old
    state = tmp_path / "full.json"
    sealed = save(state, extended)
    restored, state_id = load(state)
    assert (restored, state_id) == (extended, sealed)
    assert restored.model.model_id == model.model_id
    assert isinstance(restored.model, CardDisplayModel)
    rows, _ = encode(menu(), restored.model, score())
    adam = Adam(
        restored.actor_adam.steps,
        restored.actor_adam.first + restored.value_adam.first,
        restored.actor_adam.second + restored.value_adam.second,
    )
    updated, _, _ = update(restored.model, adam, (Decision("combat_turn", (Factor(rows, 1, ""),)),))
    assert isinstance(updated, CardDisplayModel)
    assert updated.actor.genome[-1] != 0.0
    assert updated.value_weights == model.value_weights
