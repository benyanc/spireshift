from __future__ import annotations

from typing import Any

from spireshift.native_cycle_guard_v2 import CycleGuard

VERBS = {"Leave shop": "close", "Close shop inventory": "cancel"}


def option(label: str) -> dict[str, Any]:
    verb = VERBS.get(label, "activate")
    return {"label": label, "verb": verb, "subject": None, "arguments": []}


def state(kind: str, gold: int, *labels: str) -> dict[str, Any]:
    return {
        "candidates": [option(label) for label in labels],
        "context": {"interaction": {"kind": kind}, "persistent": {"gold": gold}},
    }


def labels(view: dict[str, Any]) -> list[str]:
    return [c["label"] for c in view["candidates"]]


def step(guard: CycleGuard, public: dict[str, Any], label: str) -> tuple[list[str], list[int]]:
    effective, indices, forced = guard.view(public)
    assert forced is False
    chosen = labels(public).index(label)
    assert chosen in indices
    guard.advance(public, chosen)
    return labels(effective), indices


def test_first_visit_offers_every_candidate() -> None:
    guard = CycleGuard()
    room = state("shop_room", 50, "Leave shop", "Open inventory")
    shown, indices = step(guard, room, "Open inventory")
    assert shown == ["Leave shop", "Open inventory"] and indices == [0, 1]


def test_round_trip_withholds_only_the_proved_action() -> None:
    guard = CycleGuard()
    room = state("shop_room", 50, "Leave shop", "Open inventory")
    inventory = state("shop_inventory", 50, "Buy Strike", "Close shop inventory")
    step(guard, room, "Open inventory")
    step(guard, inventory, "Close shop inventory")
    shown, indices = step(guard, room, "Leave shop")
    assert shown == ["Leave shop"] and indices == [0]


def test_public_change_restores_the_full_menu() -> None:
    guard = CycleGuard()
    room = state("shop_room", 50, "Leave shop", "Open inventory")
    inventory = state("shop_inventory", 50, "Buy Strike", "Close shop inventory")
    step(guard, room, "Open inventory")
    step(guard, inventory, "Close shop inventory")
    changed = state("shop_room", 20, "Leave shop", "Open inventory")
    shown, _ = step(guard, changed, "Open inventory")
    assert shown == ["Leave shop", "Open inventory"]


def test_exit_is_never_withheld_so_no_purchase_is_forced() -> None:
    # The native v1 control's failure: the first room differs from later ones, so the
    # inventory was the first repeated state and v1 withheld its Close.
    guard = CycleGuard()
    first_room = state("shop_room", 50, "Leave shop", "Open inventory", "Look")
    room = state("shop_room", 50, "Leave shop", "Open inventory")
    inventory = state("shop_inventory", 50, "Buy Strike", "Close shop inventory")
    step(guard, first_room, "Open inventory")
    step(guard, inventory, "Close shop inventory")
    step(guard, room, "Open inventory")
    shown, _ = step(guard, inventory, "Close shop inventory")
    assert shown == ["Buy Strike", "Close shop inventory"]
    shown, _ = step(guard, room, "Leave shop")
    assert shown == ["Leave shop"]


def test_every_candidate_withheld_falls_back_to_full_menu() -> None:
    guard = CycleGuard()
    a = state("event_option", 0, "Only")
    b = state("event_option", 1, "Back")
    step(guard, a, "Only")
    step(guard, b, "Back")
    # No exit would remain, so nothing is withheld.
    shown, indices = step(guard, a, "Only")
    assert shown == ["Only"] and indices == [0]


def test_repeated_reward_skip_withholds_reclaim() -> None:
    guard = CycleGuard()
    claim = state("reward_claim", 10, "Claim card", "Skip remaining rewards and continue")
    pick = state("card_reward_selection", 10, "Bash", "Skip")
    step(guard, claim, "Claim card")
    step(guard, pick, "Skip")
    shown, _ = step(guard, claim, "Skip remaining rewards and continue")
    assert shown == ["Skip remaining rewards and continue"]
