"""Public sampling descriptors, never action-quality labels or a policy encoder."""

from __future__ import annotations

import math
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_inventory_credit_features import inventory

CONTRACT = "completed_train_public_situation_bank_v1"
SALT = "native-situation-bank-whole-world-v1"


def rank(value: Any) -> str:
    return manifest_identifier([SALT, value])


def amount(value: Any) -> float | None:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if type(value) not in (float, int) or not math.isfinite(value):
        return None
    return float(value)


def describe(public: dict[str, Any]) -> dict[str, Any]:
    """Describe offered choices, not the saved selected action or eventual outcome.

    Costs are the current advertised values attached to each card. A zero-cost
    play is not asserted to be discounted: a verified original cost is unavailable.
    Missing legacy combat counters remain explicitly unavailable, never filled in.
    """
    owned = inventory(public)  # Validates the public boundary and typed ownership.
    context, candidates = public["context"], public["candidates"]
    interaction = context["interaction"]
    run, player = context["persistent"]["run"], context["persistent"]["player"]
    hp, maximum = amount(player["hp"]), amount(player["max_hp"])
    if hp is None or maximum is None or maximum <= 0 or not 0 <= hp <= maximum:
        raise ValueError("Situation bank requires finite public health")
    if (
        type(run["floor"]) is not int
        or run["floor"] < 1
        or type(run["act"]) is not int
        or run["act"] < 1
        or run.get("ascension") != 8
        or player.get("character_definition_id") != "IRONCLAD"
        or len(candidates) < 2
    ):
        raise ValueError("Only choice-bearing public Ironclad/A8 situations enter the bank")
    family, content = interaction["kind"], interaction.get("content", {}).get("context", {})
    tags, costs, targets, rest = set(), [], set(), set()
    for action in candidates:
        verb, subject = action["verb"], action.get("subject") or {}
        role, props = subject.get("role"), subject.get("properties", {})
        if verb == "skip":
            tags.add("optional_skip_offered")
        if verb == "use" and role == "potion":
            tags.add("potion_use_offered")
        if role == "rest_option":
            rest.add(str(props["option_id"]).casefold())
        if family == "shop_inventory" and str(role).startswith("shop_"):
            tags.add("shop_purchase_or_service_offered")
        if role == "card" and verb == "select":
            tags.add("card_selection_offered")
        if verb == "play":
            cost = amount(props.get("cost"))
            costs.append([props.get("definition_id"), props.get("is_upgraded"), props.get("cost")])
            if cost == 0:
                tags.add("zero_current_cost_play_offered")
            for argument in action.get("arguments", []):
                entity = argument.get("entity") or {}
                if argument.get("role") == "target" and entity.get("role") == "enemy":
                    targets.add(manifest_identifier(entity))
    if len(targets) > 1:
        tags.add("multiple_enemy_targets_offered")
    if "smith" in rest and rest & {"rest", "heal"}:
        tags.add("healing_and_smith_offered")
    if family == "card_reward_selection" and "optional_skip_offered" in tags:
        tags.add("card_reward_take_or_skip_offered")
    if len({str(c[2]) for c in costs}) > 1:
        tags.add("different_current_play_costs_offered")
    floor = run["floor"]
    hp_band = "low" if hp / maximum < 0.25 else "high" if hp / maximum >= 0.75 else "middle"
    result = {
        "family": family,
        "act": run["act"],
        "floor": floor,
        "floor_band": "01-04"
        if floor <= 4
        else "05-08"
        if floor <= 8
        else "09-16"
        if floor <= 16
        else "17+",
        "hp_fraction": hp / maximum,
        "hp_band": hp_band,
        "encounter_type": content.get("encounter_type"),
        "enemy_definitions": sorted(e["definition_id"] for e in content.get("enemies", [])),
        "public_combat_round": content.get("round") if family == "combat_turn" else None,
        "choices": len(candidates),
        "tags": sorted(tags),
        "deck_signature": owned["deck_signature"],
        "relic_signature": owned["relic_signature"],
        "inventory_signature": owned["inventory_signature"],
        "deck_definitions": owned["deck_definitions"],
        "relic_definitions": owned["relic_definitions"],
        "relic_counters_available": owned["relic_counters_available"],
        "offered_card_cost_upgrade_signature": manifest_identifier(sorted(costs, key=rank)),
    }
    result["bucket"] = [family, run["act"], result["floor_band"], hp_band, result["encounter_type"]]
    return result
