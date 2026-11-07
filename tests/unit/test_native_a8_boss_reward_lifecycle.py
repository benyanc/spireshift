from __future__ import annotations

from typing import Any

from spireshift.engine_worker import LIVENESS_POLICY, _EpisodeLiveness
from spireshift.native_a8_boss2_game import liveness_limit
from spireshift.native_a8_boss2_policy import CONTINUE, intervention


def reward(kind: str, label: str, *, declined: bool = False) -> dict[str, Any]:
    return {
        "verb": "activate",
        "label": label,
        "subject": {"role": "reward", "properties": {"kind": kind}},
        "history": {"card_reward_declined": declined},
    }


def menu(*candidates: dict[str, Any]) -> dict[str, Any]:
    return {
        "context": {"interaction": {"kind": "reward_claim", "content": {}}},
        "candidates": list(candidates),
    }


def test_declined_offer_cannot_be_reopened_by_either_proposal() -> None:
    public = menu(
        reward("card", "Claim Add a card to your deck.", declined=True),
        reward("exit", CONTINUE[0]),
    )
    assert intervention(public, [0, 1], 0) == (1, "declined_reward_progress")
    assert intervention(public, [0, 1], 1) == (1, "")


def test_other_same_label_card_and_gold_remain_available() -> None:
    card = "Claim Add a card to your deck."
    public = menu(
        reward("card", card, declined=True),
        reward("exit", CONTINUE[0]),
        reward("card", card),
        reward("gold", "Claim Gold"),
    )
    for proposed in (0, 1):
        assert intervention(public, [0, 1, 2, 3], proposed)[0] == 2
        assert intervention(public, [0, 1, 3], proposed)[0] == 3


def test_alternating_exact_public_menus_trip_the_existing_liveness_bound() -> None:
    guard = _EpisodeLiveness()
    for _ in range(LIVENESS_POLICY["maximum_visits_per_public_state"]):
        assert not liveness_limit(guard, {"input_digest": "claim"})
        assert not liveness_limit(guard, {"input_digest": "skip"})
    assert liveness_limit(guard, {"input_digest": "claim"})
