from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_a8_mix_data import RoomPool, room_evidence
from spireshift.native_a8_mix_fit import ARMS, balanced_draws
from spireshift.native_a8_mix_session import (
    DEVELOPMENT,
    ENDING_SEED,
    PREFIX_SEED,
    control_tasks,
    tasks,
)
from spireshift.native_a8_own_ppo import Decision


def frame(interaction: str, **details: str) -> dict[str, Any]:
    return {
        "candidates": [{}, {}],
        "context": {
            "persistent": {"run": {"act": 3, "floor": 46}, "player": {"hp": 12}},
            "interaction": {"kind": interaction, "content": {"context": details}},
        },
    }


def test_combat_selector_gets_room_credit_when_practice_stops_at_reward() -> None:
    fight = frame("combat_turn", encounter_type="boss")
    selector = frame("card_selection", kind="combat", encounter_type="boss")
    reward = frame("reward_claim", reward_kind="room_rewards")
    evidence = room_evidence([fight, selector], {"terminal": False, "public_input": reward}, 2)

    assert evidence.decisions == [(3, 46), (3, 46)]
    assert evidence.outcomes == {(3, 46): ("boss", True)}
    assert selector["context"]["interaction"]["kind"] == "card_selection"

    with pytest.raises(ValueError, match="read-only goal"):
        room_evidence([fight], {"terminal": False, "public_input": fight}, 1)


def test_auxiliary_draws_cycle_worlds_independently_of_room_and_choice_counts() -> None:
    small = Decision((), (), 0.0, 0.0, -1.0)
    large = Decision((), (), 0.0, 0.0, 1.0)
    pool = RoomPool({"small": [[small]], "large": [[large] * 8, [large] * 4]}, {}, {})

    draws = balanced_draws(pool, 8, seed=42)

    assert draws == balanced_draws(pool, 8, seed=42)
    assert all(set(draws[i : i + 2]) == {small, large} for i in range(0, len(draws), 2))


def test_development_uses_all_arms_on_each_world_and_holds_out_controls() -> None:
    config = {"development": DEVELOPMENT, "prefix_seed": PREFIX_SEED, "ending_seed": ENDING_SEED}
    planned = tasks(config)
    controls = control_tasks(config)

    assert len(planned) == len({row["key"] for row in planned}) == 72
    for seed in DEVELOPMENT:
        assert {(row["player"], row["arm"]) for row in planned if row["seed"] == seed} == {
            (player, arm) for player in (2, 3) for arm in ARMS
        }
    assert {row["seed"] for row in planned}.isdisjoint(row["seed"] for row in controls)
