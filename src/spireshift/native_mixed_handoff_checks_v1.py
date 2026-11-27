"""Independent slot, owner, menu and effect checks for mixed handoff controls."""

from __future__ import annotations

from collections import Counter
from itertools import permutations
from typing import Any

from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_lifecycle_checks import (
    catalog_facts,
    choice_contents,
    deck,
    native_selection,
    owner,
    player,
    read,
    surface,
)
from spireshift.native_selector_lifecycle_trace import Trace


def native_state(trace: Trace) -> dict[str, Any]:
    result = None
    for row in records(trace.directory / "worker/private-transcript.jsonl.gz"):
        response = row["response"]
        if isinstance(response.get("player"), dict) and "decision" in response:
            result = response
    if result is None:
        raise ValueError("Missing native state for independent effect assertions")
    return dict(result)


def native_belt(trace: Trace) -> dict[int, tuple[str, str]]:
    rows = native_state(trace)["player"]["potions"]
    result = {row["slot"]: (row["native_ref"], row["id"]) for row in rows}
    if len(result) != len(rows) or len({row[0] for row in result.values()}) != len(rows):
        raise ValueError("Native belt lost distinct physical bottle identities")
    return result


def belt_controls(observation: dict[str, Any]) -> None:
    snapshot = observation["snapshot"]
    bottles = snapshot["persistent"]["content"]["player"]["potions"]
    states = surface(observation).get("potion_states", [])
    if len(states) != len(bottles) or len({row["slot"] for row in states}) != len(states):
        raise ValueError("The current owner lost or duplicated a belt slot")
    expected: Counter[tuple[str, str, tuple[str, ...]]] = Counter()
    for bottle in bottles:
        (state,) = [row for row in states if row["slot"] == bottle["slot"]]
        if any(
            state[key] != bottle[key]
            for key in ("entity_id", "definition_id", "name", "description")
        ):
            raise ValueError("A current belt view describes a different physical bottle")
        if state["can_discard"]:
            expected["activate", bottle["entity_id"], ()] += 1
        if state["can_use"]:
            for target in state["target_entity_ids"] or [None]:
                expected["use", bottle["entity_id"], () if target is None else (target,)] += 1
    ids = {row["entity_id"] for row in bottles}
    actual = Counter(
        (
            raw["verb"],
            raw["subject_referent_id"],
            tuple(arg["referent_id"] for arg in raw["arguments"]),
        )
        for raw in snapshot["bound_actions"]["actions"]
        if raw["subject_referent_id"] in ids
    )
    if actual != expected:
        raise ValueError("Belt controls do not match the exact current owner and target domain")


def potion_effect(trace: Trace, operation: str, definition: str, slot: int | None = None) -> None:
    before = trace.current
    original = player(before)
    raw_before = native_belt(trace)
    belt_controls(before)
    if slot is None:
        (slot,) = [key for key, (_, name) in raw_before.items() if name == definition]
    if raw_before[slot][1] != definition:
        raise ValueError("The selected slot contains a different bottle")
    child = (
        native_selection(trace)
        if owner(before) in {"card_selection", "card_reward_selection"}
        else None
    )
    choices = choice_contents(before)
    (bottle,) = [
        row
        for row in before["snapshot"]["persistent"]["content"]["player"]["potions"]
        if row["slot"] == slot
    ]
    trace.take(
        lambda raw, _: (
            raw["subject_referent_id"] == bottle["entity_id"]
            and raw["verb"] == ("use" if operation == "use" else "activate")
            and (operation == "use" or raw["label"].startswith("Discard "))
        )
    )
    after = player(trace.current)
    raw_after = native_belt(trace)
    survivors = {key: value for key, value in raw_before.items() if key != slot}
    if any(raw_after.get(key) != value for key, value in survivors.items()):
        raise ValueError("Potion operation replaced an unrelated physical bottle")
    expected_hp = (
        min(original["max_hp"], original["hp"] + original["max_hp"] // 5)
        if operation == "use" and definition == "BLOOD_POTION"
        else original["hp"]
    )
    if (
        owner(trace.current) != owner(before)
        or (owner(before) != "shop_inventory" and choices != choice_contents(trace.current))
        or deck(trace.current) != deck(before)
        or {key: value for key, value in after.items() if key not in {"potions", "hp"}}
        != {key: value for key, value in original.items() if key not in {"potions", "hp"}}
        or after["hp"] != expected_hp
        or (child is not None and native_selection(trace) != child)
    ):
        raise ValueError("Potion operation consumed a pending choice or changed unrelated state")
    if owner(before) == "shop_inventory":
        expected_catalog = catalog_facts(read(before, "shop_catalog"))
        for row in expected_catalog["potions"]:
            row.pop("blocked_reason", None)
            row["can_purchase"] = bool(
                row["stocked"]
                and row["affordable"]
                and row["visible"]
                and len(after["potions"]) < after["max_potion_slots"]
            )
        if catalog_facts(read(trace.current, "shop_catalog")) != expected_catalog:
            raise ValueError("Freeing a belt slot changed shop stock, prices or an unrelated offer")
    if operation == "use" and definition == "ENTROPIC_BREW":
        if len(raw_after) != original["max_potion_slots"] or any(
            value == raw_before[slot] for value in raw_after.values()
        ):
            raise ValueError("Entropic Brew did not consume itself and fill the open slots")
    elif raw_after != survivors:
        raise ValueError("Potion removal changed the wrong slots")
    belt_controls(trace.current)


def rest_menu(trace: Trace, options: dict[str, bool], proceed: bool) -> None:
    form = surface(trace.current)
    expected = Counter(key for key, enabled in options.items() if enabled)
    if proceed:
        expected["Proceed to map"] = 1
    actual: Counter[str] = Counter()
    referents = {row["referent_id"]: row for row in trace.current["snapshot"]["referents"]}
    for raw in trace.current["snapshot"]["bound_actions"]["actions"]:
        subject = referents.get(raw["subject_referent_id"], {})
        if subject.get("role") == "potion":
            continue
        actual[(subject.get("properties") or {}).get("option_id", raw["label"])] += 1
    if (
        owner(trace.current) != "rest_site"
        or {row["option_id"]: row["enabled"] for row in form["options"]} != options
        or len(form["options"]) != len(options)
        or form["can_proceed"] is not proceed
        or actual != expected
    ):
        raise ValueError(
            f"Rest options do not match the remaining native choices: {actual}, {options}"
        )
    belt_controls(trace.current)


def answer(trace: Trace, definitions: list[str]) -> list[str]:
    form = surface(trace.current)
    cards = form["cards"]
    selected = []
    for definition in definitions:
        selected.append(
            next(
                row["entity_id"]
                for row in cards
                if row["definition_id"] == definition and row["entity_id"] not in selected
            )
        )
    if (form["min_select"], form["max_select"], form["cancelable"]) != (
        len(selected),
        len(selected),
        True,
    ):
        raise ValueError("Rest child has different native answer bounds")
    expected = Counter(permutations([row["entity_id"] for row in cards], len(selected)))
    actual = Counter(
        tuple(arg["referent_id"] for arg in raw["arguments"])
        for raw in trace.current["snapshot"]["bound_actions"]["actions"]
        if raw["verb"] == "confirm"
    )
    if actual != expected:
        raise ValueError("The rest child omits or duplicates a legal physical answer")
    actions = trace.current["snapshot"]["bound_actions"]["actions"]
    if sum(raw["verb"] == "cancel" for raw in actions) != 1 or any(
        raw["verb"] == "select" for raw in actions
    ):
        raise ValueError("The direct rest child lost its exact cancel/confirm controls")
    trace.take(
        lambda raw, _: (
            raw["verb"] == "confirm"
            and [arg["referent_id"] for arg in raw["arguments"]] == selected
        )
    )
    return selected


def stock_entry(trace: Trace, group: str, index: int) -> dict[str, Any]:
    from spireshift.native_selector_lifecycle_checks import read

    return dict(
        next(
            row
            for row in read(trace.current, "shop_catalog")[group]
            if row["inventory_index"] == index
        )
    )


def capacity_menu(trace: Trace) -> None:
    from spireshift.native_selector_lifecycle_checks import read

    current = player(trace.current)
    full = len(current["potions"]) == current["max_potion_slots"]
    for row in read(trace.current, "shop_catalog")["potions"]:
        expected = row["stocked"] and row["affordable"] and row["visible"] and not full
        if row["can_purchase"] is not expected or (
            full and row["stocked"] and row.get("blocked_reason") != "potion_slots_full"
        ):
            raise ValueError("A shop offer has stale potion-capacity permissions")
    belt_controls(trace.current)
