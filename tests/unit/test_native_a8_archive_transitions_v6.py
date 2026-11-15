from typing import Any

import pytest

from spireshift.native_a8_archive_delivery_audit_v6 import LOCAL, PLAN, ordered_deliveries
from spireshift.native_a8_archive_transitions_v6 import compile_intents, settled_enemies

LOCATION = {"act": 2, "floor": 20}


def source_rows(*entries: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"s": index, **LOCATION, **entry} for index, entry in enumerate(entries)]


def test_direct_grant_uses_same_stolen_copy_and_unchanged_deck() -> None:
    kept = {"c": 1, "id": "STRIKE", "up": 0}
    stolen = {"c": 2, "id": "RITUAL", "up": 1, "added_floor": 19}
    rows = source_rows(
        {"t": "header", "starting_deck": [kept, stolen]},
        {"t": "remove", "c": 2, "id": "RITUAL"},
        {"t": "deck", "cards": [kept]},
        {"t": "acquire", "source": "granted", "c": 2, "id": "RITUAL"},
        {"t": "resolve", "reward_kind": "SpecialCardReward"},
        {"t": "deck", "cards": [kept, {**stolen, "added_floor": 20}]},
    )
    claim, successor = compile_intents(rows)
    assert claim.record["restoration_before"] == [("STRIKE", 0, "")]
    assert successor.record["restoration_after"] == [("STRIKE", 0, ""), ("RITUAL", 1, "")]
    rows[-1]["cards"][-1] = {**stolen, "c": 3}
    (claim,) = compile_intents(rows)
    assert "restoration_before" not in claim.record


def test_opening_damage_preserves_each_enemy_and_requires_first_player_turn() -> None:
    enemies = [
        {"cid": 3, "id": "GUARD", "hp": 50, "max_hp": 50},
        {"cid": 4, "id": "GUARD", "hp": 60, "max_hp": 60},
    ]
    start, turn, hit = source_rows(
        {"t": "combat_start", "enemies": enemies},
        {"t": "turn", "side": "player", "round": 1, "n": 1},
        {
            "t": "hit",
            "src": "player",
            "dst": "GUARD",
            "dst_cid": 4,
            "dmg": 9,
            "blocked": 0,
            "killed": False,
            "dmg_type": ["unpowered"],
        },
    )
    assert settled_enemies(start, [turn, hit]) == [enemies[0], {**enemies[1], "hp": 51}]
    assert settled_enemies(start, [hit, turn]) is None
    assert settled_enemies(start, [turn, {**hit, "dmg": 8}]) is None
    assert settled_enemies(start, [turn, hit, hit]) is None


def local_factor() -> tuple[dict[str, Any], dict[str, Any]]:
    transcript = {
        "request": {
            "cmd": "action",
            "action": "ordered_answer_append",
            "args": {"selection_ref": "native-5", "index": 1, "prefix": ""},
        },
        "response": {
            "decision": "card_select",
            "selection_ref": "native-5",
            "answer_plan": {"contract": PLAN, "selected": [1]},
        },
        "transport": "local_selection_ui",
    }
    surface = {
        "answer_plan": {"selected": []},
        "cards": [
            {"entity_id": {"public_slot": 13}},
            {"entity_id": {"public_slot": 14}},
        ],
    }
    delivery = {
        "receipt": {"delivery_domain": LOCAL},
        "choice": {"action_index": 0},
        "frame": {
            "public_input": {
                "candidates": [{"verb": "select", "subject": {"public_slot": 14}}],
                "context": {
                    "interaction": {"kind": "card_selection", "content": {"surface": surface}}
                },
            }
        },
    }
    return transcript, delivery


def test_only_confirmed_native_commit_counts_as_a_decision() -> None:
    factor, local = local_factor()
    confirm: dict[str, Any] = {
        "request": {
            "cmd": "action",
            "action": "select_cards",
            "args": {"selection_ref": "native-5", "indices": "1"},
        }
    }
    native = {
        "receipt": {"delivery_domain": "native"},
        "choice": {"action_index": 0},
        "frame": {"public_input": {"candidates": [{"verb": "confirm"}]}},
    }
    assert ordered_deliveries([factor, confirm], [local, native]) == (1, 1)
    with pytest.raises(ValueError, match="lacks a native completion"):
        ordered_deliveries([factor], [local])
    confirm["request"]["args"]["indices"] = "0"
    with pytest.raises(ValueError, match="did not commit"):
        ordered_deliveries([factor, confirm], [local, native])
    factor["request"]["args"]["index"] = 0
    with pytest.raises(ValueError, match="did not preserve"):
        ordered_deliveries([factor, confirm], [local, native])
