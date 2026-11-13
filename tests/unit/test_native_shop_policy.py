from __future__ import annotations

import copy
import random
from typing import Any

import pytest
from test_native_action_context import model, score

from spireshift.native_conditional_control import TASK
from spireshift.native_learning_control import public_input
from spireshift.native_shop_policy import ShopNavigation, choose, verified_samples


def shop(opened: bool, inspected: bool = True, foul: bool = False) -> dict[str, Any]:
    p = public_input(TASK, False)
    p["context"]["interaction"] = {
        "kind": "shop_inventory",
        "content": {"surface": {"inventory_open": opened}},
    }
    if opened:
        actions = [
            action("Buy card"),
            action("Buy card removal"),
            action("Close inventory", "close"),
        ]
    else:
        actions = [action("Open inventory"), action("Leave shop", "close")]
    if foul:
        actions.append(
            {
                **action("Use Foul Potion on Merchant", "use"),
                "subject": {"role": "potion", "properties": {"definition_id": "FOUL_POTION"}},
                "arguments": [{"role": "target", "entity": {"role": "merchant"}}],
            }
        )
    for c in actions:
        c["history"] = {"shop_inspected": inspected, "card_reward_declined": False}
    p["candidates"] = actions
    return p


def action(label: str, verb: str = "activate") -> dict[str, Any]:
    return {"label": label, "verb": verb, "subject": None, "arguments": []}


def test_inventory_navigation_cannot_reopen_after_finish_but_never_masks_purchases() -> None:
    nav = ShopNavigation()
    first = shop(False, False)
    effective, mapping, forced = nav.view(first)
    assert mapping == [0] and forced and effective["candidates"] == [first["candidates"][0]]
    nav.advance(first, 0)
    inventory = shop(True)
    effective, mapping, forced = nav.view(inventory)
    assert effective is inventory and mapping == [0, 1, 2] and not forced
    nav.advance(inventory, 2)
    closed = shop(False)
    effective, mapping, forced = nav.view(closed)
    assert mapping == [1] and not forced and effective["candidates"][0]["label"] == "Leave shop"
    # Even a learner assigning arbitrarily large weight to Open inventory cannot loop.
    for seed in range(100):
        selected = choose(model(), score(), closed, nav, random.Random(seed), 0.8)
        assert selected["action_index"] == 1 and selected["log_probability"] == 0


def test_merchant_potion_remains_a_real_choice_and_consumption_permits_reinspection() -> None:
    nav = ShopNavigation()
    closed = shop(False, True, True)
    effective, mapping, forced = nav.view(closed)
    assert mapping == [1, 2] and not forced
    assert [c["label"] for c in effective["candidates"]] == [
        "Leave shop",
        "Use Foul Potion on Merchant",
    ]
    nav.advance(closed, 2)
    changed = shop(False)
    assert nav.view(changed)[1:] == ([0], True)
    nav.advance(changed, 0)
    assert nav.view(shop(True))[1] == [0, 1, 2]
    assert nav.view(shop(False))[1:] == ([1], False)


def test_all_other_potions_and_discard_controls_are_preserved() -> None:
    p = shop(False)
    p["candidates"].extend([copy.deepcopy(p["candidates"][1]) for _ in range(2)])
    p["candidates"][2].update(label="Use Healing Potion", verb="use")
    p["candidates"][3].update(label="Discard Potion", verb="activate")
    assert ShopNavigation().view(p)[1:] == ([1, 2, 3], False)


@pytest.mark.parametrize("fault", ["missing_open", "duplicate_leave", "history"])
def test_missing_or_inconsistent_shop_controls_stop_without_guessing(fault: str) -> None:
    p = shop(False)
    if fault == "missing_open":
        p["candidates"].pop(0)
    elif fault == "duplicate_leave":
        p["candidates"].append(copy.deepcopy(p["candidates"][1]))
    else:
        p["candidates"][0]["history"]["shop_inspected"] = False
    with pytest.raises(ValueError):
        ShopNavigation().view(p)


@pytest.mark.parametrize("fault", [None, "logp", "contract", "forced", "partial", "legacy"])
def test_exact_effective_probabilities_and_forced_steps_reconstruct(fault: str | None) -> None:
    m, nav = model(), ShopNavigation()
    rows = []
    for p in [shop(False, False), public_input(TASK, False), shop(False)]:
        c = choose(m, score(), p, nav, random.Random(3), 0.8)
        rows.append({"public_input": p, "choice": c})
    case: dict[str, Any] = {
        "status": "terminal",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": rows,
    }
    if fault == "logp":
        rows[1]["choice"]["log_probability"] += 0.1
    elif fault == "contract":
        rows[1]["choice"]["policy_contract"] = "wrong"
    elif fault == "forced":
        rows[0]["choice"]["navigation_only"] = False
    elif fault == "partial":
        case["status"] = "failed"
    elif fault == "legacy":
        del rows[1]["choice"]["effective_input_id"]
    if fault:
        with pytest.raises(ValueError):
            verified_samples(case, m, score(), 0.03, 0.8)
    else:
        samples, effective = verified_samples(case, m, score(), 0.03, 0.8)
        assert len(samples) == len(effective) == 2
        assert samples[-1].action == 0 and len(samples[-1].rows) == 1
        assert len(case["decisions"]) == 3  # Raw automatic delivery remains auditable.
