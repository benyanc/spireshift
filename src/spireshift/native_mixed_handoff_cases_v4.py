"""Rest handoffs selected by current legal coordinates and actual arrived owner."""

from __future__ import annotations

from typing import Any

from spireshift.native_mixed_handoff_cases_v1 import option
from spireshift.native_mixed_handoff_checks_v1 import answer, belt_controls, potion_effect
from spireshift.native_mixed_handoff_checks_v2 import rest_menu
from spireshift.native_mixed_handoff_checks_v3 import control_label as label
from spireshift.native_selector_lifecycle_checks import (
    deck,
    enter_next_room,
    owner,
    player,
    surface,
)
from spireshift.native_selector_lifecycle_trace import Trace, verb


def enter_declared_rest(trace: Trace) -> None:
    if owner(trace.current) != "map_navigation":
        raise ValueError("Require the current legal map for the declared next rest")
    target = surface(trace.current)["next_options"][0]
    coords = (target["col"], target["row"])
    referents = {row["referent_id"]: row for row in trace.current["snapshot"]["referents"]}

    def matches(raw: dict[str, Any], _: dict[str, Any]) -> bool:
        props = referents.get(raw["subject_referent_id"], {}).get("properties", {})
        return (
            raw["verb"] == "activate"
            and not raw["arguments"]
            and (props.get("col"), props.get("row")) == coords
        )

    trace.take(matches)
    if owner(trace.current) != "rest_site":
        raise ValueError("The configured next rest did not become the actual native owner")


def rest(trace: Trace, case: dict[str, Any]) -> dict[str, Any]:
    operation = case["operation"]
    options = {"HEAL": True, "SMITH": operation != "spent"}
    if operation == "return":
        options["LIFT"] = True
    if operation == "cook":
        options["COOK"] = True
    if operation == "cap":
        options["DIG"] = True
    proceed = False

    def menu() -> None:
        rest_menu(trace, options, proceed)

    def open_child(name: str) -> None:
        previous, previous_deck = player(trace.current), deck(trace.current)
        trace.take(option(name))
        if (
            owner(trace.current) != "card_selection"
            or player(trace.current) != previous
            or deck(trace.current) != previous_deck
        ):
            raise ValueError("Opening a rest child consumed its parent or a native effect")
        belt_controls(trace.current)

    def cancel_child() -> None:
        previous, previous_deck = player(trace.current), deck(trace.current)
        trace.take(verb("cancel"))
        if player(trace.current) != previous or deck(trace.current) != previous_deck:
            raise ValueError("Rest cancellation changed committed player state")
        menu()

    def heal() -> None:
        nonlocal proceed
        before = player(trace.current)
        expected = min(before["max_hp"], before["hp"] + before["max_hp"] * 30 // 100 + 15)
        trace.take(option("HEAL"))
        if player(trace.current) != {**before, "hp": expected}:
            raise ValueError("Regal Pillow healing or its HP cap differs from the native rule")
        options.pop("HEAL")
        if "MINIATURE_TENT" not in case["relics"]:
            options.clear()
        proceed = True
        menu()

    menu()
    if operation in {"return", "single", "cook"}:
        child = "COOK" if operation == "cook" else "SMITH"
        open_child(child)
        potion_effect(trace, "use", "ENTROPIC_BREW")
        cancel_child()
        if operation != "single":
            open_child(child)
            before, before_deck = player(trace.current), deck(trace.current)
            selected = answer(
                trace, ["STRIKE_IRONCLAD", "DEFEND_IRONCLAD"] if child == "COOK" else ["BASH"]
            )
            after = player(trace.current)
            if child == "COOK":
                if after != {
                    **before,
                    "hp": before["hp"] + 5,
                    "max_hp": before["max_hp"] + 5,
                } or deck(trace.current) != {
                    key: value for key, value in before_deck.items() if key not in selected
                }:
                    raise ValueError(
                        "Cook did not remove exactly two cards and grant five maximum HP"
                    )
                options["SMITH"] = False
            else:
                expected_deck = {
                    key: {**card, "is_upgraded": True} if key in selected else card
                    for key, card in before_deck.items()
                }
                if after != before or any(
                    deck(trace.current)[key]["is_upgraded"] != card["is_upgraded"]
                    for key, card in expected_deck.items()
                ):
                    raise ValueError("Smith upgraded the wrong physical copy")
            options.pop(child)
            proceed = True
            menu()
        if operation == "return":
            trace.take(option("LIFT"))
            (girya,) = [
                row for row in player(trace.current)["relics"] if row["definition_id"] == "GIRYA"
            ]
            if girya["counter"] != 3:
                raise ValueError("The third lift did not reach the native Girya cap")
            options.pop("LIFT")
            menu()
    else:
        if operation == "spent":
            potion_effect(trace, "discard", "FOUL_POTION")
        potion_effect(trace, "use", "ENTROPIC_BREW")
        menu()
    heal()
    if operation == "cap":
        open_child("SMITH")
        cancel_child()
    trace.take(label("Proceed to map"))
    if operation == "return":
        enter_declared_rest(trace)
        options = {"HEAL": True, "SMITH": True}
        proceed = False
        menu()
        heal()
        trace.take(label("Proceed to map"))
    enter_next_room(trace)
    return {
        "rest_operation": operation,
        "final_hp": player(trace.current)["hp"],
        "final_max_hp": player(trace.current)["max_hp"],
        "second_rest_verified": operation == "return",
    }
