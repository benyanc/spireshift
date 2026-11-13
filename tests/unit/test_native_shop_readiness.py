from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_shop_live import ScriptedPolicy, select_action


def frame(family: str, rows: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "source_family": family,
        "public_input": {"candidates": [{"verb": v, "label": text} for v, text in rows]},
    }


def test_shop_control_never_substitutes_an_unrelated_action() -> None:
    current = frame(
        "shop_inventory",
        [("activate", "Buy a card"), ("open", "Choose a card to remove for 100 gold")],
    )
    assert select_action(current, "remove_card") == 1
    with pytest.raises(ValueError, match="owner"):
        select_action(current, "confirm_first_card")
    with pytest.raises(ValueError, match="unique"):
        select_action(frame("shop_inventory", [("activate", "Leave shop")]), "remove_card")


def test_shop_control_declares_exact_confirm_or_cancel_and_public_order() -> None:
    current = frame(
        "card_selection",
        [("cancel", "Cancel"), ("confirm", "First legal card"), ("confirm", "Second legal card")],
    )
    assert select_action(current, "confirm_first_card") == 1
    assert select_action(current, "cancel_removal") == 0
    with pytest.raises(ValueError):
        select_action(
            frame("card_selection", [("activate", "Show previews")]), "confirm_first_card"
        )


def test_shop_control_refuses_duplicate_open_controls() -> None:
    current = frame("shop_room", [("activate", "Open inventory"), ("activate", "Open inventory")])
    with pytest.raises(ValueError, match="unique"):
        select_action(current, "open_inventory")


def test_control_stops_at_its_declared_final_delivery_without_retry() -> None:
    policy = ScriptedPolicy(["open_inventory"])
    current = frame("shop_room", [("activate", "Open inventory")])
    current.update(
        binding_id="b",
        actions=[{"bound_action_id": "a"}],
        observation={"snapshot_id": "s", "runtime_instance_id": "r"},
    )
    policy.choose(current)
    with pytest.raises(ValueError):
        policy.choose(current)
    policy.acknowledge(
        {
            "delivery": "delivered",
            "binding_id": "b",
            "bound_action_id": "a",
            "runtime_instance_id": "r",
            "before_snapshot_id": "s",
            "successor_snapshot_id": "t",
        }
    )
    assert policy.done and policy.decisions == 1
    with pytest.raises(ValueError):
        policy.choose(current)
