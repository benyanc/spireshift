from copy import deepcopy
from typing import Any

import pytest

from spireshift.native_a8_combat_branch_policy import EEL_ATTACKS, eel_choice, giant_choice
from spireshift.native_a8_combat_branches import require_exact_menu


def play(label: str, slot: int, definition: str, **stats: int) -> dict[str, Any]:
    return {
        "verb": "play",
        "label": label,
        "subject": {
            "properties": {
                "cost": "1",
                "definition_id": definition,
                "entity_id": {"public_slot": slot},
                "stats": stats,
            }
        },
    }


def test_eel_line_requires_two_distinct_one_energy_strikes() -> None:
    thunderclap = play(EEL_ATTACKS[0], 34, "THUNDERCLAP")
    strike = play(EEL_ATTACKS[1], 33, "STRIKE_IRONCLAD")
    second_strike = play(EEL_ATTACKS[2], 36, "STRIKE_IRONCLAD")
    combat = {"round": 9, "player": {"energy": 3}, "enemies": [{"hp": 25}]}
    assert eel_choice({"candidates": [strike, thunderclap, second_strike]}, combat, 0) == 1
    with pytest.raises(ValueError, match="two distinct"):
        eel_choice({"candidates": [strike, thunderclap, strike]}, combat, 0)


def test_giant_uses_earlier_defense_and_ignores_damage_into_dying_phase() -> None:
    end = {"verb": "end_turn"}
    attack = play("Play Strike on Waterfall Giant", 4, "STRIKE_IRONCLAD", damage=9)
    defend = play("Play Defend", 5, "DEFEND_IRONCLAD", block=5)
    defend_plus = play("Play Defend+", 6, "DEFEND_IRONCLAD", block=8)
    public = {
        "candidates": [end, attack, defend, defend_plus],
        "context": {
            "interaction": {"kind": "combat_turn"},
            "persistent": {"player": {"hp": 21}},
            "reads": [{"kind": "combat_piles", "content": {"zones": []}}],
        },
    }
    enemy: dict[str, Any] = {
        "max_hp": 250,
        "intents": [{"type": "Attack", "damage": 10}],
    }
    combat = {"player": {"energy": 3, "block": 0}, "enemies": [enemy]}
    assert giant_choice(public, combat, None) == 3
    enemy.update(max_hp=999_999_999, intents=[{"type": "DeathBlow", "damage": 30}])
    assert giant_choice(public, combat, None) == 3
    public["candidates"] = [end, attack]
    assert giant_choice(public, combat, None) == 0


def test_exact_prefix_rejects_changed_public_state_and_action_key() -> None:
    saved: dict[str, Any] = {
        "input_digest": "same",
        "source_family": "combat_turn",
        "terminal": False,
        "actions": [{"key": "one", "bound_action_id": "saved"}],
        "public_input": {"context": {"player": {"hp": 37}}},
    }
    replay = deepcopy(saved)
    replay["actions"][0]["bound_action_id"] = "new-worker"
    require_exact_menu(replay, saved, 515)
    replay["actions"][0]["key"] = "other"
    with pytest.raises(ValueError, match="line 515"):
        require_exact_menu(replay, saved, 515)
    replay = deepcopy(saved)
    replay["public_input"]["context"]["player"]["hp"] = 36
    with pytest.raises(ValueError, match="/context/player/hp"):
        require_exact_menu(replay, saved, 515)
