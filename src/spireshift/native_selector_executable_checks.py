"""Menus are complete only for answers the frozen UI can actually finish."""

from __future__ import annotations

from collections import Counter
from itertools import permutations
from typing import Any

from spireshift.native_selector_lifecycle_checks import deck, owner, read, surface
from spireshift.native_systematic_selectors_v2 import COMPACT, DIRECT


def check_selector(observation: dict[str, Any], count: int, removal: bool) -> dict[str, Any]:
    snapshot = observation["snapshot"]
    content = snapshot["interaction"]["content"]
    form = surface(observation)
    ids = [card["entity_id"] for card in form["cards"]]
    compact = count == 13 and not removal
    lower, upper = (1, 1) if removal else (1, 3)
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
        if len(selected) >= lower:
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
