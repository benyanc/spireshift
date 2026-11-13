from typing import Any

import pytest

from spireshift.native_a8_archive_rewards_v3 import compile_intents, installed
from spireshift.native_a8_replay_probe import Divergence, next_choice
from spireshift.native_a8_replay_source import Journal


def rows(*records: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"s": i, "act": 2, "floor": 30, **record} for i, record in enumerate(records)]


def gold_journal(*, after_second: int = 211) -> Journal:
    source = rows(
        {"t": "header", "starting_deck": []},
        {"t": "gold", "gold": 196},
        {"t": "resolve", "reward_kind": "GoldReward", "gold": 15, "decision_id": 7},
        {"t": "gold", "gold": after_second},
        {"t": "resolve", "reward_kind": "GoldReward", "gold": 15, "decision_id": 7},
    )
    return Journal("SEED", {}, 70, "", "", {}, frozenset(), compile_intents(source))


def reward_frame(balance: int, slots: list[int]) -> dict[str, Any]:
    rewards: list[dict[str, Any]] = [
        {
            "kind": "gold",
            "label": "15 Gold",
            "description": "15 Gold",
            "enabled": True,
            "entity_id": {"public_slot": slot},
        }
        for slot in slots
    ]
    candidates = [
        {
            "verb": "activate",
            "arguments": [],
            "subject": {
                "role": "reward",
                "public_slot": reward["entity_id"]["public_slot"],
                "properties": reward,
                "state": {"enabled": True, "visible": True},
            },
        }
        for reward in reversed(rewards)
    ]
    return {
        "public_input": {
            "candidates": candidates,
            "context": {
                "persistent": {"run": {"act": 2, "floor": 30}, "player": {"gold": balance}},
                "interaction": {
                    "kind": "reward_claim",
                    "content": {"surface": {"rewards": rewards}},
                },
            },
        }
    }


def test_claims_follow_native_occurrences_and_verify_each_balance() -> None:
    journal = gold_journal()
    assert [i.kind for i in journal.intents] == [
        "repeated_gold",
        "gold_successor",
        "repeated_gold",
        "gold_successor",
    ]
    with installed():
        assert next_choice(reward_frame(181, [33, 34]), journal, 0, 4) == (1, 1, "native")
        assert next_choice(reward_frame(196, [34]), journal, 1, 4) == (0, 3, "native")
        assert next_choice(reward_frame(211, []), journal, 3, 4) == (None, 4, "native")


@pytest.mark.parametrize(
    "balance,slots,reason",
    [(195, [34], "recorded gold balance"), (196, [33, 34], "remaining gold occurrences")],
)
def test_no_second_delivery_after_a_wrong_successor(
    balance: int,
    slots: list[int],
    reason: str,
) -> None:
    with installed(), pytest.raises(Divergence, match=reason):
        next_choice(reward_frame(balance, slots), gold_journal(), 1, 4)


def test_mixed_stolen_and_ordinary_claims_require_separate_evidence() -> None:
    frame = reward_frame(181, [33, 34])
    frame["public_input"]["context"]["interaction"]["content"]["surface"]["rewards"][1]["label"] = (
        "15 Gold (stolen back)"
    )
    with installed(), pytest.raises(Divergence, match="ordinary equivalent gold reward"):
        next_choice(frame, gold_journal(), 0, 4)


def test_source_must_corroborate_both_claims() -> None:
    assert [i.kind for i in gold_journal(after_second=212).intents] == ["reward", "reward"]


def restored_card_records() -> list[dict[str, Any]]:
    stay = {"c": 1, "id": "STRIKE", "up": 0}
    card = {"c": 2, "id": "WHIRLWIND", "up": 0}
    return rows(
        {"t": "header", "starting_deck": [stay, card]},
        {"t": "decision", "floor": 29, "decision_id": 6, "decision_type": "card_reward"},
        {"t": "remove", "c": 2, "id": "WHIRLWIND"},
        {"t": "deck", "cards": [stay]},
        {"t": "acquire", "source": "reward", "decision_id": 6, **card},
        {"t": "resolve", "reward_kind": "SpecialCardReward", "decision_id": 7},
        {"t": "deck", "cards": [stay, card]},
    )


def test_restored_card_uses_current_reward_and_exact_deck_effect() -> None:
    source = restored_card_records()
    claim, effect = compile_intents(source)
    assert claim.kind == "reward" and claim.record["id"] == "WHIRLWIND"
    assert claim.record["restoration_before"] == [("STRIKE", 0, "")]
    assert effect.kind == "restoration_successor"
    assert effect.record["restoration_after"] == [("STRIKE", 0, ""), ("WHIRLWIND", 0, "")]
    assert source[4]["source"] == "reward"


def test_mismatched_restored_card_copy_does_not_supply_a_choice() -> None:
    source = restored_card_records()
    source[-1]["cards"][-1] = {"c": 3, "id": "WHIRLWIND", "up": 0}
    with pytest.raises(ValueError, match="recorded special reward acquisition"):
        compile_intents(source)
