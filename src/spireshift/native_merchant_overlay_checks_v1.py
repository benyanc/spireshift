"""Prove the native potion effect and actual room exit, not an overlay exit."""

from __future__ import annotations

from typing import Any

from spireshift.native_mixed_handoff_checks_v1 import native_belt, native_state
from spireshift.native_selector_lifecycle_checks import (
    choice_contents,
    deck,
    enter_next_room,
    owner,
    player,
    surface,
)
from spireshift.native_selector_lifecycle_trace import Trace, label, potion


def merchant_target(trace: Trace, enabled: bool) -> None:
    state = native_state(trace)
    (raw,) = [row for row in state["player"]["potions"] if row["id"] == "FOUL_POTION"]
    (visible,) = [
        row
        for row in surface(trace.current)["potion_states"]
        if row["definition_id"] == "FOUL_POTION"
    ]
    targets = visible["target_entity_ids"]
    referents = trace.current["snapshot"]["referents"]
    merchants = [row for row in referents if row["role"] == "merchant"]
    actions = [
        row
        for row in trace.frame["public_input"]["candidates"]
        if row["verb"] == "use"
        and (row.get("subject") or {}).get("properties", {}).get("definition_id") == "FOUL_POTION"
    ]
    if (
        raw["can_use"] is not enabled
        or visible["can_use"] is not enabled
        or len(raw["valid_target_refs"]) != int(enabled)
        or len(targets) != int(enabled)
        or len(actions) != int(enabled)
        or (enabled and (len(merchants) != 1 or targets != [merchants[0]["referent_id"]]))
    ):
        raise ValueError("Merchant target permission or exact current operand differs")


def merchant_map_use(trace: Trace, _: dict[str, Any]) -> dict[str, Any]:
    merchant_target(trace, True)
    trace.take(label("Open shop inventory"))
    merchant_target(trace, False)
    trace.take(label("Close shop inventory"))
    merchant_target(trace, True)
    trace.take(label("Leave shop and open map"))
    if owner(trace.current) != "map_navigation":
        raise ValueError("The map did not become the current navigation owner")
    merchant_target(trace, True)
    before, before_deck, belt = player(trace.current), deck(trace.current), native_belt(trace)
    offered = choice_contents(trace.current)
    (slot,) = [slot for slot, row in belt.items() if row[1] == "FOUL_POTION"]
    trace.take(potion("use", "FOUL_POTION"))
    after = player(trace.current)
    if (
        owner(trace.current) != "map_navigation"
        or after
        != {
            **before,
            "gold": before["gold"] + 100,
            "potions": [row for row in before["potions"] if row["slot"] != slot],
        }
        or deck(trace.current) != before_deck
        or native_belt(trace) != {key: row for key, row in belt.items() if key != slot}
        or choice_contents(trace.current) != offered
        or any(
            row["role"] == "merchant" for row in trace.frame["public_input"]["context"]["referents"]
        )
    ):
        raise ValueError("Foul Potion did not grant 100 gold once and preserve map, deck and belt")
    enter_next_room(trace)
    if owner(trace.current) == "map_navigation" or native_state(trace).get("merchant_map_target"):
        raise ValueError("The old merchant room survived actual map travel")
    return {"merchant_map_gold_received": 100, "native_room_exit_verified": True}
