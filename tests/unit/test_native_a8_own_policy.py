from __future__ import annotations

from typing import Any

from test_native_action_context import model, score
from test_native_live_policy import ack, frame

from spireshift.native_a8_own_policy import CONTRACT, AllActions, OwnPolicy
from spireshift.native_context_cache import cached_model
from spireshift.native_shop_policy import ShopNavigation


def test_full_menu_keeps_leaving_and_reopening_the_shop() -> None:
    public: dict[str, Any] = {
        "context": {
            "persistent": {"run": {"act": 1, "floor": 7}},
            "interaction": {
                "kind": "shop_inventory",
                "content": {"surface": {"inventory_open": False}},
            },
        },
        "candidates": [
            {
                "verb": verb,
                "label": label,
                "subject": None,
                "arguments": [],
                "history": {"shop_inspected": False},
            }
            for verb, label in (("activate", "Open inventory"), ("close", "Leave shop"))
        ],
    }
    old = ShopNavigation()
    assert old.view(public)[1:] == ([0], True)
    assert AllActions().view(public) == (public, [0, 1], False)
    for choice in public["candidates"]:
        choice["history"]["shop_inspected"] = True
    assert old.view(public)[1:] == ([1], False)
    assert AllActions().view(public) == (public, [0, 1], False)


def test_own_policy_samples_all_rows_and_commits_only_after_receipt() -> None:
    m = cached_model(model())
    public = frame()
    player = OwnPolicy(m, score(), "OWNPOLICYTEST")
    choice = player.choose(public)
    assert choice["policy_contract"] == CONTRACT
    assert choice["behavior"] == "sampled_softmax"
    assert choice["draw_used"] and choice["optimizer_updates"] == 0
    assert choice["public_input_id"] == choice["effective_input_id"]
    assert choice["action_index"] == choice["effective_action_index"]
    assert player.decisions == 0
    player.acknowledge(ack(public, choice))
    assert player.decisions == 1
