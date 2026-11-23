"""Independent menu, inventory and parent-owner assertions for selector fixtures."""

from __future__ import annotations

from collections import Counter
from itertools import permutations
from typing import Any

from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_lifecycle_trace import Trace, label, potion
from spireshift.native_systematic_selectors_v2 import COMPACT, DIRECT


def player(observation: dict[str, Any]) -> dict[str, Any]:
    result = dict(observation["snapshot"]["persistent"]["content"]["player"])
    result.pop("entity_id")
    for kind in ("potions", "relics"):
        result[kind] = [
            {key: value for key, value in item.items() if key != "entity_id"}
            for item in result[kind]
        ]
    return result


def read(observation: dict[str, Any], kind: str) -> dict[str, Any]:
    (content,) = [row["content"] for row in observation["reads"] if row["kind"] == kind]
    return dict(content)


def catalog_facts(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: catalog_facts(item)
            for key, item in value.items()
            if key not in {"entity_id", "slot_entity_id"}
        }
    if isinstance(value, list):
        return [catalog_facts(item) for item in value]
    return value


def deck(observation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    content = read(observation, "run_deck")
    cards = {card["entity_id"]: card for card in content["cards"]}
    if len(cards) != content["card_count"]:
        raise ValueError("Run deck lost distinct physical card copies")
    return cards


def owner(observation: dict[str, Any]) -> str:
    return str(observation["snapshot"]["interaction"]["kind"])


def surface(observation: dict[str, Any]) -> dict[str, Any]:
    return dict(observation["snapshot"]["interaction"]["content"]["surface"])


def native_selection(trace: Trace) -> tuple[Any, ...]:
    last = None
    for row in records(trace.directory / "worker/private-transcript.jsonl.gz"):
        response = row["response"]
        if response.get("decision") in {"card_select", "card_reward"}:
            last = response
    if last is None:
        raise ValueError("Missing the actual pending native selector")
    return (
        last["decision"],
        last.get("selection_ref"),
        [(card["native_ref"], card["id"]) for card in last["cards"]],
        [option["native_ref"] for option in last.get("alternatives", [])],
    )


def choice_contents(observation: dict[str, Any]) -> dict[str, Any]:
    content = surface(observation)
    content.pop("potion_states", None)
    if "selectable_card_entity_ids" in content and content.pop("selectable_card_entity_ids") != [
        card["entity_id"] for card in content["cards"]
    ]:
        raise ValueError("Reward choices do not bind their current physical offers")
    return dict(catalog_facts(content))


def check_belt_controls(observation: dict[str, Any]) -> None:
    snapshot = observation["snapshot"]
    referents = {row["referent_id"]: row for row in snapshot["referents"]}
    expected: Counter[tuple[str, str]] = Counter()
    for bottle in player(observation)["potions"]:
        name = bottle["definition_id"]
        expected["activate", name] += 1
        if name == "BLOOD_POTION":
            expected["use", name] += 1
        elif name != "FOUL_POTION":
            raise ValueError("Unexpected potion in the declared selector fixture")
    actual = Counter(
        (action["verb"], referents[action["subject_referent_id"]]["properties"]["definition_id"])
        for action in snapshot["bound_actions"]["actions"]
        if referents.get(action["subject_referent_id"], {}).get("role") == "potion"
    )
    if actual != expected:
        raise ValueError("The child lost a legal belt control or enabled an invalid potion target")


def check_selector(observation: dict[str, Any], count: int, removal: bool) -> dict[str, Any]:
    snapshot = observation["snapshot"]
    content = snapshot["interaction"]["content"]
    form = surface(observation)
    ids = [card["entity_id"] for card in form["cards"]]
    compact = count == 13 and not removal
    lower, upper = (1, 1) if removal else (0, 3)
    if (
        owner(observation) != "card_selection"
        or content["context"]["kind"] != "shop"
        or len(ids) != count
        or len(set(ids)) != count
        or set(ids) != deck(observation).keys()
        or (form["min_select"], form["max_select"], form["cancelable"]) != (lower, upper, removal)
        or form["selection_contract"] != (COMPACT if compact else DIRECT)
    ):
        raise ValueError("Selector does not expose its exact native deck and answer rules")
    actions = snapshot["bound_actions"]["actions"]
    actual = Counter(
        (
            action["verb"],
            action["subject_referent_id"],
            tuple(arg["referent_id"] for arg in action["arguments"]),
        )
        for action in actions
        if action["verb"] in {"select", "confirm", "cancel"}
    )
    if compact:
        selected = form["answer_plan"]["selected"]
        expected = Counter(
            ("select", card, ())
            for i, card in enumerate(ids)
            if i not in selected and len(selected) < upper
        )
        expected["confirm", None, tuple(ids[i] for i in selected)] = 1
    else:
        expected = Counter(
            ("confirm", None, answer)
            for n in range(lower, upper + 1)
            for answer in permutations(ids, n)
        )
    if removal:
        expected["cancel", None, ()] = 1
    if actual != expected:
        raise ValueError("Selector is missing a valid physical answer or exposes an extra answer")
    # The overlay can expose the catalog as a read without authorizing a purchase.
    catalog = read(observation, "shop_catalog")
    entries = [*catalog["cards"], *catalog["relics"], *catalog["potions"], catalog["card_removal"]]
    if any(entry and entry["can_purchase"] for entry in entries):
        raise ValueError("Shop catalog enables a purchase while its selector owns input")
    return form


def belt_sequence(trace: Trace, *, discard_first: bool) -> None:
    operations = [("use", "BLOOD_POTION"), ("discard", "FOUL_POTION")]
    if discard_first:
        operations.reverse()
    for operation, name in operations:
        before = trace.current
        check_belt_controls(before)
        original = player(before)
        before_surface = choice_contents(before)
        native_before = native_selection(trace)
        (bottle,) = [row for row in original["potions"] if row["definition_id"] == name]
        expected = {
            **original,
            "hp": min(original["max_hp"], original["hp"] + original["max_hp"] // 5)
            if operation == "use"
            else original["hp"],
            "potions": [row for row in original["potions"] if row["slot"] != bottle["slot"]],
        }
        trace.take(potion(operation, name))
        if (
            owner(trace.current) != owner(before)
            or choice_contents(trace.current) != before_surface
            or native_selection(trace) != native_before
            or player(trace.current) != expected
            or deck(trace.current) != deck(before)
        ):
            raise ValueError(
                "Potion operation changed the pending choice, deck or unrelated player state"
            )
    check_belt_controls(trace.current)


def answer(trace: Trace, indices: list[int], count: int, removal: bool) -> list[str]:
    initial = check_selector(trace.current, count, removal)
    selected = [initial["cards"][i]["entity_id"] for i in indices]
    if initial["selection_contract"] == COMPACT:
        for card_id in selected:

            def appends(raw: dict[str, Any], _: dict[str, Any], card_id: str = card_id) -> bool:
                return bool(raw["verb"] == "select" and raw["subject_referent_id"] == card_id)

            trace.take(appends, domain="local_answer_factor")
            check_selector(trace.current, count, removal)
        trace.take(lambda raw, _: raw["verb"] == "confirm")
    else:
        trace.take(
            lambda raw, _: (
                raw["verb"] == "confirm"
                and [arg["referent_id"] for arg in raw["arguments"]] == selected
            )
        )
    return selected


def settled(identity: dict[str, Any]) -> None:
    if (
        any(
            identity[key] is not False
            for key in (
                "pending_host_operation",
                "pending_card_selection",
                "pending_card_reward",
                "pending_reward_set",
                "pending_bundle",
                "pending_abandon_confirmation",
                "action_executor_running",
            )
        )
        or identity["pending_potion_discards"]
    ):
        raise ValueError("A parent was published before its native child completed")


def leave_shop(trace: Trace) -> None:
    if owner(trace.current) != "shop_inventory":
        raise ValueError("Shop child did not return to its original inventory")
    trace.take(label("Close shop inventory"))
    if owner(trace.current) != "shop_room":
        raise ValueError("Closing inventory did not restore the merchant approach")
    trace.take(label("Leave shop and open map"))
    if owner(trace.current) != "map_navigation":
        raise ValueError("Leaving the merchant did not return to the map")


def enter_next_room(trace: Trace) -> None:
    if owner(trace.current) != "map_navigation":
        raise ValueError("Require the current map before a native room transition")
    snapshot = trace.current["snapshot"]
    referents = {row["referent_id"]: row for row in snapshot["referents"]}
    action = next(
        action
        for action in snapshot["bound_actions"]["actions"]
        if referents.get(action["subject_referent_id"], {}).get("properties", {}).get("point_type")
        == "monster"
    )
    bound = action["bound_action_id"]
    trace.take(lambda raw, _: raw["bound_action_id"] == bound)
    if owner(trace.current) != "combat_turn":
        raise ValueError("The selected native monster room did not become playable")
