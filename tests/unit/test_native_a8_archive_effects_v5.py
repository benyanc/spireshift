from typing import Any

import pytest

from spireshift.native_a8_archive_effects_v5 import (
    STOLEN_CARD_LABEL,
    compile_intents,
    discarded_opening_copies,
    installed,
    next_choice,
    with_discards,
)
from spireshift.native_a8_replay_probe import Divergence
from spireshift.native_a8_replay_source import Intent, Journal

PLACE = {"act": 1, "floor": 11}


def source_rows(*rows: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"s": index, **PLACE, **row} for index, row in enumerate(rows)]


def test_opening_discard_tracks_the_copy_through_redraw() -> None:
    rows = source_rows(
        {"t": "combat_start"},
        {"t": "pick", "n_picked": 1, "archive_opening": {}},
        {"t": "discard", "c": 2, "id": "STRIKE"},
        {"t": "play", "c": 1, "auto": False},
        {"t": "shuffle", "order_c": [2]},
        {"t": "draw", "c": 2, "id": "STRIKE"},
        {"t": "play", "c": 2, "auto": False},
    )
    prior = Intent("play", rows[3], hand=((1, "STRIKE"), (2, "STRIKE")))
    after = Intent("play", rows[6], hand=((2, "STRIKE"),))
    discards = discarded_opening_copies(rows, (Intent("pick", rows[1]), prior, after))
    assert discards == {3: ((2, "STRIKE"),)}
    corrected = with_discards(prior, discards[3])
    assert corrected.hand == ((1, "STRIKE"),)
    assert corrected.discard == ((2, "STRIKE"),)


def combat_journal() -> Journal:
    rows = source_rows(
        {"t": "header", "starting_deck": []},
        {"t": "combat_start", "enemies": []},
        {"t": "draw", "c": 1, "id": "BRAND"},
        {"t": "draw", "c": 2, "id": "SHOCKWAVE"},
        {"t": "play", "c": 1, "id": "BRAND", "auto": False, "play_index": 0, "turn": 1, "up": 1},
        {
            "t": "pick",
            "n_picked": 1,
            "selector": "human",
            "cards": [{"c": 2, "id": "SHOCKWAVE", "up": 0}],
        },
        {"t": "exhaust", "c": 2, "id": "SHOCKWAVE", "ethereal": False},
        {"t": "draw", "c": 3, "id": "BASH"},
        {"t": "end_turn", "side": "player", "round": 1},
    )
    return Journal("SEED", {}, 70, "", "", {}, frozenset(), compile_intents(rows))


def card(name: str, slot: int, *, upgraded: bool = False) -> dict[str, Any]:
    return {"definition_id": name, "is_upgraded": upgraded, "entity_id": {"public_slot": slot}}


def combat_frame(
    hand: list[dict[str, Any]], exhaust: list[dict[str, Any]], *, selector: bool = False
) -> dict[str, Any]:
    action: dict[str, Any] = {"verb": "end_turn", "arguments": [], "subject": None}
    if selector:
        action = {
            "verb": "confirm",
            "arguments": [{"role": "selected_card", "entity": {"public_slot": 2}}],
        }
    elif hand[0]["definition_id"] == "BRAND":
        action = {
            "verb": "play",
            "arguments": [],
            "subject": {"public_slot": 1, "properties": hand[0]},
        }
    return {
        "public_input": {
            "context": {
                "persistent": {"run": PLACE},
                "interaction": {
                    "kind": "card_selection" if selector else "combat_turn",
                    "content": {
                        "surface": {"cards": hand} if selector else {},
                        "context": {
                            "round": 1,
                            "turn_owner": "player",
                            "is_play_phase": not selector,
                            "player": {"hand": hand},
                        },
                    },
                },
                "reads": [
                    {
                        "kind": "combat_piles",
                        "content": {"zones": [{"zone": "exhaust", "cards": exhaust}]},
                    }
                ],
            },
            "candidates": [action],
        }
    }


def test_automatic_exhaust_requires_native_successor_and_keeps_real_selector() -> None:
    journal = combat_journal()
    assert [i.kind for i in journal.intents] == [
        "combat_start",
        "play",
        "forced_exhaust",
        "pick",
        "end_turn",
    ]
    chosen = card("SHOCKWAVE", 2)
    before = combat_frame([card("BRAND", 1, upgraded=True), chosen], [])
    with installed():
        assert next_choice(before, journal, 1, 5) == (0, 2, "native")
        assert next_choice(combat_frame([card("BASH", 3)], [chosen]), journal, 2, 5) == (
            0,
            5,
            "native",
        )
        assert next_choice(combat_frame([chosen], [], selector=True), journal, 2, 5) == (
            0,
            4,
            "native",
        )
        with pytest.raises(Divergence, match="forced exhausted card"):
            next_choice(combat_frame([card("BASH", 3)], []), journal, 2, 5)
        with pytest.raises(Divergence, match="forced exhaust successor hand"):
            next_choice(combat_frame([card("STRIKE", 3)], [chosen]), journal, 2, 5)


def test_stolen_card_reward_uses_its_owner_and_exact_deck_successor() -> None:
    original = {"c": 1, "id": "STRIKE", "up": 0}
    stolen = {"c": 2, "id": "WHIRLWIND", "up": 0}
    rows = source_rows(
        {"t": "header", "starting_deck": [original, stolen]},
        {"t": "decision", "floor": 10, "decision_id": 6, "decision_type": "card_reward"},
        {"t": "remove", **stolen},
        {"t": "deck", "cards": [original]},
        {"t": "acquire", "source": "reward", "decision_id": 6, **stolen},
        {"t": "resolve", "reward_kind": "SpecialCardReward", "decision_id": 7},
        {"t": "deck", "cards": [original, stolen]},
    )
    journal = Journal("SEED", {}, 70, "", "", {}, frozenset(), compile_intents(rows))
    reward = {
        "kind": "SpecialCardReward",
        "label": STOLEN_CARD_LABEL,
        "description": STOLEN_CARD_LABEL,
        "enabled": True,
        "entity_id": {"public_slot": 30},
    }
    action = {
        "verb": "activate",
        "arguments": [],
        "subject": {
            "role": "reward",
            "public_slot": 30,
            "properties": reward,
            "state": {"enabled": True, "visible": True},
        },
    }
    frame: dict[str, Any] = {
        "public_input": {
            "candidates": [action],
            "context": {
                "persistent": {"run": PLACE},
                "interaction": {
                    "kind": "reward_claim",
                    "content": {"surface": {"rewards": [reward]}},
                },
                "reads": [{"kind": "run_deck", "content": {"cards": [card("STRIKE", 1)]}}],
            },
        }
    }
    with installed():
        assert next_choice(frame, journal, 0, 2) == (0, 1, "native")
        context = frame["public_input"]["context"]
        with pytest.raises(Divergence, match="restored reward deck"):
            next_choice(frame, journal, 1, 2)
        context["reads"][0]["content"]["cards"].append(card("WHIRLWIND", 2))
        with pytest.raises(Divergence, match="stolen card claim consumed"):
            next_choice(frame, journal, 1, 2)
        context["interaction"]["content"]["surface"]["rewards"] = []
        assert next_choice(frame, journal, 1, 2) == (None, 2, "native")
