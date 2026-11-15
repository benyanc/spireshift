from typing import Any

import pytest

from spireshift.native_a8_replay_probe import Divergence, next_choice, ordered_slots, victory
from spireshift.native_a8_replay_source import Intent, Journal, compile_intents


def test_transformation_and_revival_preserve_physical_operands() -> None:
    rows: list[dict[str, Any]] = [
        {"t": "combat_start", "enemies": [{"i": 0, "cid": 18, "id": "BOSS"}]},
        {"t": "draw", "c": 1, "id": "STRIKE"},
        {"t": "draw", "c": 2, "id": "DEFEND"},
        {"t": "transform", "from_c": 1, "to_c": 3, "to_id": "ROCK"},
        {"t": "generate", "c": 3, "id": "ROCK"},
        {"t": "death", "tgt_cid": 18, "removal_prevented": False},
        {"t": "hp", "dst_cid": 18, "hp": 100},
        {"t": "play", "auto": False, "play_index": 0, "c": 3},
    ]
    _, played = compile_intents(rows)
    assert played.hand == ((3, "ROCK"), (2, "DEFEND"))
    assert played.generated == frozenset()
    assert played.enemies == ((18, "BOSS"),)


def test_generated_copies_require_one_possible_public_slot() -> None:
    intent = Intent(
        "play",
        {},
        hand=((1, "ANGER"), (2, "DEFEND"), (3, "ANGER"), (4, "ANGER")),
        generated=frozenset({3, 4}),
    )
    hand = [
        {"definition_id": card, "entity_id": {"public_slot": slot}}
        for card, slot in (("ANGER", 10), ("DEFEND", 20), ("ANGER", 30), ("ANGER", 40))
    ]
    assert ordered_slots(intent, hand, [4]) == [40]
    assert ordered_slots(intent, hand[:-1], [4]) == [30]

    ambiguous = Intent(
        "play", {}, hand=((3, "ANGER"), (4, "ANGER"), (5, "ANGER")), generated=frozenset({3, 4, 5})
    )
    with pytest.raises(Divergence, match="physical card copy"):
        ordered_slots(ambiguous, [hand[2], hand[3]], [4])
    assert ordered_slots(ambiguous, [hand[2], hand[3]], [4], legal={4: {40}}) == [40]


def test_returned_copy_uses_recorded_enchantment_and_current_public_slot() -> None:
    intent = Intent(
        "play",
        {"c": 1, "up": 1},
        hand=((2, "BODY_SLAM"),),
        returns=((1, "BODY_SLAM"),),
        enchantments=((1, "GLAM"), (2, None)),
    )
    hand = [
        {
            "definition_id": "BODY_SLAM",
            "is_upgraded": True,
            "entity_id": {"public_slot": slot},
            "existing_enchantment": enchantment,
        }
        for slot, enchantment in ((3, {"definition_id": "GLAM"}), (4, None))
    ]
    assert ordered_slots(intent, hand, [1]) == [3]
    assert ordered_slots(intent, list(reversed(hand)), [1]) == [3]


def test_a_complete_archive_cannot_supply_native_victory() -> None:
    journal = Journal(
        "SEED", {}, 64, "ACT", "BOSS", {"terminal_reason": "left_run"}, frozenset(), ()
    )
    frame = {
        "terminal": True,
        "ending": {"victory": True},
        "public_input": {"context": {"persistent": {"run": {}, "player": {}}}},
    }
    ending: dict[str, Any] = {
        "native_ending_evidence_agrees": True,
        "private_final_identity": {
            "seed": "SEED",
            "native_game_over": True,
            "native_victory_room": False,
        },
    }
    with pytest.raises(Divergence, match="native victory"):
        victory(frame, journal, ending)


def test_forced_dialogue_still_requires_the_recorded_proceed_owner() -> None:
    here = {"act": 3, "floor": 48}
    offer = {
        "event_id": "THE_ARCHITECT",
        "options": [{"option_index": 0, "label": "Proceed", "presented": True, "selectable": True}],
    }
    intents = (
        Intent("event", here, dialogue_only=True),
        Intent("event", {**here, "option_index": 0, "label": "Proceed"}, offer),
    )
    journal = Journal("SEED", {}, 64, "ACT", "BOSS", {}, frozenset(), intents)
    owner = {"event_id": "THE_ARCHITECT"}
    frame = {
        "public_input": {
            "context": {
                "persistent": {"run": here},
                "interaction": {
                    "kind": "event_option",
                    "content": {
                        "context": owner,
                        "surface": {
                            "options": [
                                {
                                    "index": 0,
                                    "title": "Proceed",
                                    "is_proceed": False,
                                    "is_enabled": True,
                                }
                            ]
                        },
                    },
                },
            },
            "candidates": [
                {
                    "verb": "activate",
                    "label": "Proceed",
                    "arguments": [],
                    "subject": {"properties": {"index": 0}},
                }
            ],
        },
    }
    assert next_choice(frame, journal, 0, 2) == (0, 2, "native")
    owner["event_id"] = "ANOTHER_EVENT"
    with pytest.raises(Divergence, match="event definition"):
        next_choice(frame, journal, 0, 2)
