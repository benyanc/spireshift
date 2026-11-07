from __future__ import annotations

from typing import Any

from spireshift.native_a8_boss_game import ARMS
from spireshift.native_a8_boss_inputs import CONTROL, GATE, worlds
from spireshift.native_a8_boss_policy import Move, Turn, advance, boss_choice
from spireshift.native_a8_boss_session import qualify


def attack(slot: int, damage: int, hp_loss: int = 0) -> dict[str, Any]:
    return {
        "verb": "play",
        "subject": {
            "role": "playable_card",
            "properties": {
                "entity_id": {"public_slot": slot},
                "cost": "1",
                "stats": {"damage": damage, "hploss": hp_loss},
            },
        },
        "arguments": [
            {"role": "target", "entity": {"properties": {"entity_id": {"public_slot": 9}}}}
        ],
    }


def test_boss_turn_uses_two_legal_hits_to_prevent_lethal_and_rejects_fatal_hp_cost() -> None:
    block = {
        "verb": "play",
        "subject": {
            "role": "playable_card",
            "properties": {
                "entity_id": {"public_slot": 4},
                "cost": "1",
                "stats": {"block": 10},
            },
        },
        "arguments": [],
    }
    public: dict[str, Any] = {
        "context": {
            "persistent": {"player": {"hp": 9, "max_hp": 80}},
            "interaction": {
                "content": {
                    "context": {
                        "round": 3,
                        "player": {"energy": 2, "block": 0},
                        "enemies": [
                            {
                                "entity_id": {"public_slot": 9},
                                "hp": 12,
                                "block": 0,
                                "intents": [{"type": "Attack", "damage": 15}],
                            }
                        ],
                    }
                }
            },
        },
        "candidates": [{"verb": "end_turn"}, attack(1, 6), attack(2, 6), attack(3, 40, 9), block],
    }
    assert boss_choice(public, [0, 1, 2, 3, 4], proposed=4) == 1
    # With one energy left, the same incoming intent requires block now.
    public["context"]["interaction"]["content"]["context"]["player"]["energy"] = 1
    assert boss_choice(public, [0, 1, 3, 4], proposed=4) == 4


def test_turn_never_spends_one_physical_card_twice_or_overspends_hp() -> None:
    turn = Turn((), frozenset(), 2, 8, 0, ((10, 0), (10, 0)))
    a = Move(1, 3, 1, False, 0, 4, 0, (6, 0), 0, 0)
    other_target = Move(2, 3, 1, False, 0, 0, 0, (0, 6), 0, 0)
    other_card = Move(3, 4, 1, False, 0, 4, 0, (6, 0), 0, 0)
    after = advance(turn, a)
    assert after is not None
    assert advance(after, other_target) is None
    assert advance(after, other_card) is None


def test_gate_needs_three_reproductions_two_initializers_and_complete_worlds() -> None:
    cases = worlds()
    assert len({case["seed"] for case in cases} | {CONTROL["seed"]}) == 9
    rows = [
        {
            "case": case,
            "outcomes": {
                arm: "act1_clear" if arm == "boss" and i < 3 else "act1_loss" for arm in ARMS
            },
            "episodes": {
                arm: {"actual_boss_combat_observed": arm == "boss" and i < 3} for arm in ARMS
            },
            "confirmed_clear": i < 3,
            "strict_rescue_confirmed": i < 2,
        }
        for i, case in enumerate(cases)
    ]
    assert qualify(len(cases), GATE, rows)["passed"]
    assert not qualify(len(cases), GATE, rows[:-1])["passed"]
    rows[1]["strict_rescue_confirmed"] = False
    assert not qualify(len(cases), GATE, rows)["passed"]
    rows[1]["strict_rescue_confirmed"] = True
    rows[2]["confirmed_clear"] = False
    assert not qualify(len(cases), GATE, rows)["passed"]
