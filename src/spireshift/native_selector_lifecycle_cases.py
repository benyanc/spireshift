"""Verify purchases, canceled removal and card rewards through their real owners."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.full_run_experience import atomic_json
from spireshift.native_flow_verification_v12 import records
from spireshift.native_selector_lifecycle_checks import (
    answer,
    belt_sequence,
    catalog_facts,
    check_selector,
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
from spireshift.native_selector_lifecycle_worker import OwnerWorker


def card_choice(trace: Trace) -> None:
    snapshot = trace.current["snapshot"]
    card = surface(trace.current)["cards"][0]
    trace.take(
        lambda raw, _: raw["verb"] == "select" and raw["subject_referent_id"] == card["entity_id"]
    )
    if snapshot["interaction"]["kind"] == owner(trace.current):
        raise ValueError("Taking a reward did not return to its parent")


def gold_amount(directory: Path) -> int:
    amounts = {
        reward["value"]
        for row in records(directory / "worker/private-transcript.jsonl.gz")
        for reward in row["response"].get("rewards", [])
        if reward["kind"] == "gold"
    }
    (amount,) = amounts
    if type(amount) is not int or amount <= 0:
        raise ValueError("Missing the native sibling gold amount")
    return amount


def shop_case(
    ctx: dict[str, Any], case: dict[str, Any], directory: Path, deadline: float
) -> dict[str, Any]:
    preparation = OwnerWorker(ctx, directory / "preparation")
    try:
        fixture = preparation.request("prepare", seed=case["seed"], count=case["count"])
        preparation.close()
    finally:
        preparation.stop()
    atomic_json(directory / "fixture.save", fixture["save"])
    worker = OwnerWorker(ctx, directory / "worker")
    trace = Trace(ctx, worker, directory, deadline)
    try:
        trace.observe(
            worker.request("load", seed=case["seed"], save_json=json.dumps(fixture["save"]))
        )
        trace.take(label("Open shop inventory"))
        initial = trace.current
        original_deck = deck(initial)
        original = player(initial)
        removal = case["kind"] == "removal"
        catalog = read(initial, "shop_catalog")
        offer = (
            catalog["card_removal"]
            if removal
            else next(
                row
                for row in catalog["relics"]
                if (row.get("relic") or {}).get("definition_id") == "KIFUDA"
            )
        )
        if not offer["can_purchase"] or not offer["stocked"]:
            raise ValueError("Expected an available native shop offer")
        entry = offer["entity_id"]

        def purchase(raw: dict[str, Any], _: dict[str, Any]) -> bool:
            return bool(raw["subject_referent_id"] == entry)

        trace.take(purchase)
        check_selector(trace.current, case["count"], removal)
        belt_sequence(trace, discard_first=case["discard_first"])
        if removal:
            trace.take(verb("cancel"))
            expected_catalog = catalog_facts(catalog)
            for bottle in expected_catalog["potions"]:
                if (
                    bottle.pop("blocked_reason", None) != "potion_slots_full"
                    or bottle["can_purchase"]
                    or not all(bottle[key] for key in ("visible", "affordable", "stocked"))
                ):
                    raise ValueError("The original shop did not expose its full-belt restriction")
                bottle["can_purchase"] = True
            if (
                owner(trace.current) != "shop_inventory"
                or player(trace.current)["gold"] != original["gold"]
                or deck(trace.current) != original_deck
                or catalog_facts(read(trace.current, "shop_catalog")) != expected_catalog
            ):
                raise ValueError(
                    "Cancel consumed the removal service, charged gold or changed the deck"
                )
            settled(worker.request("inspect"))
            entry = read(trace.current, "shop_catalog")["card_removal"]["entity_id"]
            trace.take(purchase)
        selected = answer(trace, case["indices"], case["count"], removal)
        if owner(trace.current) != "shop_inventory":
            raise ValueError("Confirmed shop choice did not restore its original parent")
        after = player(trace.current)
        final_deck = deck(trace.current)
        if (
            after["hp"] != min(original["max_hp"], original["hp"] + original["max_hp"] // 5)
            or after["potions"]
            or after["gold"] != original["gold"] - offer["price"]
        ):
            raise ValueError(
                "Shop completion charged an incorrect price or repeated a potion effect"
            )
        completed_catalog = read(trace.current, "shop_catalog")
        if removal:
            used = completed_catalog["card_removal"]
            if (
                used["stocked"]
                or used["can_purchase"]
                or final_deck
                != {key: value for key, value in original_deck.items() if key not in selected}
                or after["relics"] != original["relics"]
            ):
                raise ValueError(
                    "Removal did not consume exactly the selected physical card and service"
                )
        else:
            (used,) = [
                row
                for row in completed_catalog["relics"]
                if row["inventory_index"] == offer["inventory_index"]
            ]
            if (
                used["stocked"]
                or used["can_purchase"]
                or set(final_deck) != set(original_deck)
                or sum(row["definition_id"] == "KIFUDA" for row in after["relics"]) != 1
            ):
                raise ValueError("Relic purchase did not consume its stock exactly once")
            for key, card in final_deck.items():
                enchantment = card.get("enchantment")
                if key in selected:
                    if not enchantment or (enchantment["definition_id"], enchantment["amount"]) != (
                        "ADROIT",
                        3,
                    ):
                        raise ValueError(
                            "Kifuda did not enchant the exact selected physical copies"
                        )
                elif card != original_deck[key]:
                    raise ValueError("Kifuda changed an unselected physical copy")
        settled(worker.request("inspect"))
        leave_shop(trace)
        result = trace.finish()
        if result["native_card_answer_commits"] != 1:
            raise ValueError("Expected one final native answer for the purchased service")
        shutdown = worker.close()
        trace.close()
        if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
            raise ValueError("Shop lifecycle worker did not stop cleanly")
        return {
            **result,
            "price_paid": offer["price"],
            "selected_physical_cards": selected,
            "final_hp": after["hp"],
            "removal_cancel_preserved_service": removal,
        }
    finally:
        trace.stop()
        worker.stop()


def reward_case(
    ctx: dict[str, Any], case: dict[str, Any], directory: Path, deadline: float
) -> dict[str, Any]:
    worker = OwnerWorker(ctx, directory / "worker")
    trace = Trace(ctx, worker, directory, deadline)
    try:
        trace.observe(worker.request("reward_fixture", seed=case["seed"]))
        for _ in range(5):
            if owner(trace.current) == "reward_claim":
                break
            if owner(trace.current) != "combat_turn":
                raise ValueError("The reward fixture left native combat unexpectedly")
            action = next(
                row
                for row in trace.current["snapshot"]["bound_actions"]["actions"]
                if row["verb"] == "play"
            )

            # Every supplied card is Bludgeon+, with one living native target.
            def plays(
                raw: dict[str, Any], _: dict[str, Any], bound: str = action["bound_action_id"]
            ) -> bool:
                return bool(raw["bound_action_id"] == bound)

            trace.take(plays)
        initial = trace.current
        if owner(initial) != "reward_claim":
            raise ValueError("The fixture did not finish its native fight")
        original_deck = deck(initial)
        original = player(initial)
        offers = surface(initial)["rewards"]
        (card_offer,) = [row for row in offers if row["kind"] == "card"]
        (gold_offer,) = [row for row in offers if row["kind"] == "gold"]
        trace.take(lambda raw, _: raw["subject_referent_id"] == card_offer["entity_id"])
        if owner(trace.current) != "card_reward_selection":
            raise ValueError("The reward did not open its native card choices")
        belt_sequence(trace, discard_first=case["discard_first"])
        chosen = surface(trace.current)["cards"][0]
        if case["kind"] == "reward_take":
            card_choice(trace)
        else:
            trace.take(label("Skip"))
        after = player(trace.current)
        final_deck = deck(trace.current)
        remaining = surface(trace.current)["rewards"]
        if (
            owner(trace.current) != "reward_claim"
            or after["gold"] != original["gold"]
            or after["hp"] != min(original["max_hp"], original["hp"] + original["max_hp"] // 5)
            or after["potions"]
            or after["relics"] != original["relics"]
            or any(final_deck.get(key) != value for key, value in original_deck.items())
            or len(final_deck) != len(original_deck) + (case["kind"] == "reward_take")
            or not any(row == gold_offer for row in remaining)
        ):
            raise ValueError(
                "Reward completion lost its sibling, repeated an effect or changed the wrong card"
            )
        expected_cards = 0 if case["kind"] == "reward_take" else 1
        if sum(row["kind"] == "card" for row in remaining) != expected_cards:
            raise ValueError("The skipped or accepted card reward has the wrong native status")
        if case["kind"] == "reward_take":
            (added,) = final_deck.keys() - original_deck.keys()
            if any(
                final_deck[added][key] != chosen[key]
                for key in ("definition_id", "is_upgraded", "rarity", "cost")
            ):
                raise ValueError("The new deck card differs from the selected native reward")
        amount = gold_amount(directory)
        trace.take(lambda raw, _: raw["subject_referent_id"] == gold_offer["entity_id"])
        gained_gold = player(trace.current)["gold"] - original["gold"]
        if gained_gold != amount:
            raise ValueError("The sibling gold reward did not apply")
        if surface(trace.current)["rewards"]:
            trace.take(label("Skip remaining rewards and continue"))
        else:
            trace.take(label("Continue from rewards"))
        if owner(trace.current) != "map_navigation":
            raise ValueError("Completed rewards did not return to the map")
        # Native map voting exits the old room and settles any unclaimed rewards.
        enter_next_room(trace)
        settled(worker.request("inspect"))
        result = trace.finish()
        shutdown = worker.close()
        trace.close()
        if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
            raise ValueError("Reward lifecycle worker did not stop cleanly")
        return {
            **result,
            "gold_received": gained_gold,
            "card_taken": case["kind"] == "reward_take",
            "final_hp": after["hp"],
        }
    finally:
        trace.stop()
        worker.stop()
