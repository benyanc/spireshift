"""Scripted diagnostic controls; no choice labels or fixtures enter learning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.native_mixed_handoff_checks_v1 import (
    answer,
    belt_controls,
    capacity_menu,
    native_belt,
    native_state,
    potion_effect,
    rest_menu,
    stock_entry,
)
from spireshift.native_mixed_handoff_worker_v1 import MixedWorker
from spireshift.native_selector_executable_checks import check_selector
from spireshift.native_selector_lifecycle_cases import card_choice, gold_amount
from spireshift.native_selector_lifecycle_checks import (
    catalog_facts,
    deck,
    enter_next_room,
    leave_shop,
    owner,
    player,
    read,
    settled,
    surface,
)
from spireshift.native_selector_lifecycle_trace import Trace, label, verb


def option(name: str) -> Any:
    return lambda raw, candidate: (
        raw["verb"] == "activate"
        and (candidate.get("subject") or {}).get("properties", {}).get("option_id") == name
    )


def choose_subject(trace: Trace, identifier: str) -> None:
    trace.take(lambda raw, _: raw["subject_referent_id"] == identifier)


def finish_rewards(trace: Trace, directory: Path, initial_gold: int) -> int:
    (offer,) = [row for row in surface(trace.current)["rewards"] if row["kind"] == "gold"]
    amount = gold_amount(directory)
    choose_subject(trace, offer["entity_id"])
    if player(trace.current)["gold"] != initial_gold + amount:
        raise ValueError("Replacement lost or repeated the sibling gold")
    trace.take(
        label(
            "Skip remaining rewards and continue"
            if surface(trace.current)["rewards"]
            else "Continue from rewards"
        )
    )
    enter_next_room(trace)
    return amount


def reward(trace: Trace, case: dict[str, Any], directory: Path) -> dict[str, Any]:
    for _ in range(8):
        if owner(trace.current) == "reward_claim":
            break
        if owner(trace.current) != "combat_turn":
            raise ValueError("The replacement fixture did not retain native combat ownership")
        action = next(
            row
            for row in trace.current["snapshot"]["bound_actions"]["actions"]
            if row["verb"] == "play"
        )
        bound = action["bound_action_id"]

        def plays(raw: dict[str, Any], _: dict[str, Any], bound: str = bound) -> bool:
            return bool(raw["bound_action_id"] == bound)

        trace.take(plays)
    initial = trace.current
    if owner(initial) != "reward_claim" or len(player(initial)["potions"]) != 2:
        raise ValueError("Require an actual full-belt native reward set")
    offers = surface(initial)["rewards"]
    (potion_offer,) = [row for row in offers if row["kind"] == "potion"]
    (card_offer,) = [row for row in offers if row["kind"] == "card"]
    raw_potion = next(row for row in native_state(trace)["rewards"] if row["kind"] == "potion")
    if potion_offer["enabled"] is not False:
        raise ValueError("A full belt still enabled the pending potion reward")
    initial_deck = deck(initial)
    original_belt = native_belt(trace)
    choose_subject(trace, card_offer["entity_id"])
    if owner(trace.current) != "card_reward_selection":
        raise ValueError("The current card reward did not open its child")
    name = original_belt[case["slot"]][1]
    potion_effect(trace, case["replacement"], name, case["slot"])
    if case["take"]:
        card_choice(trace)
    else:
        trace.take(label("Skip"))
    (current_offer,) = [row for row in surface(trace.current)["rewards"] if row["kind"] == "potion"]
    if owner(trace.current) != "reward_claim" or current_offer != {**potion_offer, "enabled": True}:
        raise ValueError("The original pending potion was replaced or failed to become claimable")
    if len(deck(trace.current)) != len(initial_deck) + int(case["take"]) or any(
        deck(trace.current).get(key) != value for key, value in initial_deck.items()
    ):
        raise ValueError("Potion replacement changed card take/skip semantics")
    before = player(trace.current)
    survivors = native_belt(trace)
    choose_subject(trace, current_offer["entity_id"])
    after = player(trace.current)
    actual = native_belt(trace)
    added = actual.keys() - survivors.keys()
    if (
        added != {case["slot"]}
        or actual[case["slot"]][1] != raw_potion["value"].removeprefix("POTION.")
        or any(actual.get(slot) != bottle for slot, bottle in survivors.items())
        or after["gold"] != before["gold"]
        or after["hp"] != before["hp"]
        or any(row["kind"] == "potion" for row in surface(trace.current)["rewards"])
    ):
        raise ValueError("The pending reward did not fill exactly the freed physical slot once")
    belt_controls(trace.current)
    amount = finish_rewards(trace, directory, before["gold"])
    return {
        "replaced_slot": case["slot"],
        "potion_received": actual[case["slot"]][1],
        "sibling_gold_received": amount,
        "card_taken": case["take"],
    }


def buy(trace: Trace, group: str, index: int, courier: bool) -> dict[str, Any]:
    before = trace.current
    quote = stock_entry(trace, group, index)
    old_deck = deck(before)
    old_belt = native_belt(trace)
    if not all(quote[key] for key in ("stocked", "affordable", "can_purchase")):
        raise ValueError("Purchase requires the current available stock and quote")
    choose_subject(trace, quote["entity_id"])
    if (
        owner(trace.current) != "shop_inventory"
        or player(trace.current)["gold"] != player(before)["gold"] - quote["price"]
    ):
        raise ValueError("The purchase did not restore the shop and charge its current quote once")
    replacement = stock_entry(trace, group, index)
    if replacement["stocked"] is not courier:
        raise ValueError("The purchased slot has incorrect native restock behavior")
    if group == "cards":
        current = deck(trace.current)
        (added,) = current.keys() - old_deck.keys()
        if any(current.get(key) != value for key, value in old_deck.items()) or any(
            current[added][key] != quote["card"][key]
            for key in ("definition_id", "is_upgraded", "cost")
        ):
            raise ValueError("Card restocking changed the wrong physical deck copy")
    else:
        current_belt = native_belt(trace)
        (added_slot,) = current_belt.keys() - old_belt.keys()
        if current_belt[added_slot][1] != quote["definition_id"] or any(
            current_belt.get(slot) != value for slot, value in old_belt.items()
        ):
            raise ValueError("Potion purchase overwrote an occupied slot")
        capacity_menu(trace)
    return {"price_paid": quote["price"], "inventory_index": index, "restocked": courier}


def shop(trace: Trace, case: dict[str, Any]) -> dict[str, Any]:
    trace.take(label("Open shop inventory"))
    capacity_menu(trace)
    group = {"card": "cards", "potion": "potions", "relic": "relics"}[case["operation"]]
    entries = read(trace.current, "shop_catalog")[group]
    entry = (
        next(row for row in entries if (row.get("relic") or {}).get("definition_id") == "KIFUDA")
        if group == "relics"
        else entries[0]
    )
    index = entry["inventory_index"]
    purchases = []
    if group == "potions":
        for _ in range(2 if case["courier"] else 1):
            name = native_belt(trace)[1][1]
            potion_effect(trace, "discard", name, 1)
            capacity_menu(trace)
            purchases.append(buy(trace, group, index, case["courier"]))
    elif group == "cards":
        purchases = [buy(trace, group, index, True), buy(trace, group, index, True)]
        original = trace.current
        removal = read(original, "shop_catalog")["card_removal"]
        choose_subject(trace, removal["entity_id"])
        trace.take(verb("cancel"))
        if (
            player(trace.current) != player(original)
            or deck(trace.current) != deck(original)
            or catalog_facts(read(trace.current, "shop_catalog"))
            != catalog_facts(read(original, "shop_catalog"))
        ):
            raise ValueError("Cancel after restocking changed stock, deck, gold or service")
        choose_subject(trace, read(trace.current, "shop_catalog")["card_removal"]["entity_id"])
        selected = answer(trace, ["STRIKE_IRONCLAD"])
        if (
            player(trace.current)["gold"] != player(original)["gold"] - removal["price"]
            or deck(trace.current)
            != {key: value for key, value in deck(original).items() if key not in selected}
            or read(trace.current, "shop_catalog")["card_removal"]["stocked"]
        ):
            raise ValueError("Confirmed removal did not preserve restocked purchases")
    else:
        original = trace.current
        initial_deck = deck(original)
        choose_subject(trace, entry["entity_id"])
        check_selector(trace.current, 13, False)
        potion_effect(trace, "use", "BLOOD_POTION")
        potion_effect(trace, "discard", "FOUL_POTION")
        form = check_selector(trace.current, 13, False)
        selected = form["cards"][12]["entity_id"]
        trace.take(
            lambda raw, _: raw["verb"] == "select" and raw["subject_referent_id"] == selected,
            domain="local_answer_factor",
        )
        check_selector(trace.current, 13, False)
        trace.take(verb("confirm"))
        if (
            owner(trace.current) != "shop_inventory"
            or player(trace.current)["gold"] != player(original)["gold"] - entry["price"]
            or not stock_entry(trace, group, index)["stocked"]
        ):
            raise ValueError("Courier relic restock did not wait for its acquisition child")
        final_deck = deck(trace.current)
        if (
            final_deck.keys() != initial_deck.keys()
            or any(card != initial_deck[key] for key, card in final_deck.items() if key != selected)
            or (final_deck[selected].get("enchantment") or {}).get("definition_id") != "ADROIT"
            or final_deck[selected]["enchantment"]["amount"] != 3
        ):
            raise ValueError("The restocked relic enchanted a different physical card")
        if sum(row["definition_id"] == "KIFUDA" for row in player(trace.current)["relics"]) != 1:
            raise ValueError("Acquisition completed more than once")
        purchases = [{"price_paid": entry["price"], "restocked": True, "inventory_index": index}]
    leave_shop(trace)
    enter_next_room(trace)
    return {"purchases": purchases, "courier": case["courier"], "stock_group": group}


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
        referents = {row["referent_id"]: row for row in trace.current["snapshot"]["referents"]}
        node = next(
            raw
            for raw in trace.current["snapshot"]["bound_actions"]["actions"]
            if referents.get(raw["subject_referent_id"], {}).get("properties", {}).get("point_type")
            == "rest_site"
        )
        choose_subject(trace, node["subject_referent_id"])
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


def run_case(
    ctx: dict[str, Any], case: dict[str, Any], fixture: Path, area: Path, deadline: float
) -> dict[str, Any]:
    worker = MixedWorker(ctx, area / "worker")
    trace = Trace(ctx, worker, area, deadline)
    try:
        trace.observe(worker.request("load", seed=case["seed"], save_json=fixture.read_text()))
        facts = {
            "reward": lambda: reward(trace, case, area),
            "shop": lambda: shop(trace, case),
            "rest": lambda: rest(trace, case),
        }[case["family"]]()
        settled(worker.request("inspect"))
        proof = trace.finish()
        shutdown = worker.close()
        trace.close()
        if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
            raise ValueError("The mixed handoff worker did not shut down cleanly")
        return {**proof, **facts}
    finally:
        trace.stop()
        worker.stop()
