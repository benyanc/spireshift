"""Predeclared public-only sampling of later combat choices, not action labels."""

from __future__ import annotations

import math
from typing import Any

from spireshift.engine_neural import validate_public_input

SELECTION = "first_public_round_ge2_attack_exceeds_block_floor_ge5_two_play_or_use_prefix_le512"
QUOTAS = {"normal": 2, "elite": 1, "boss": 1}
# Frozen after public-only availability inspection, before any counterfactual outcomes.
QUOTAS_BY_PLAYER = {"2": QUOTAS, "3": {"normal": 3, "elite": 1, "boss": 0}}


def _amount(value: Any) -> float:
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError("Later teacher sampling needs finite nonnegative public amounts")
    return float(value)


def eligibility(public: dict[str, Any]) -> dict[str, Any] | None:
    """Use public round/menus/displayed attacks only; never the recorded final return.

    Displayed attack minus current block is a sampling proxy, not predicted HP loss.
    Native hooks, statuses and reactions still own the actual effects and ending.
    """
    context = public["context"]
    interaction = context["interaction"]
    if interaction["kind"] != "combat_turn":
        return None
    combat = interaction.get("content", {}).get("context", {})
    turn = combat.get("round")
    candidates = public["candidates"]
    floor = context["persistent"]["run"]["floor"]
    if (
        type(turn) is not int
        or turn < 2
        or type(floor) is not int
        or floor < 5
        or not 3 <= len(candidates) <= 12
        or combat.get("encounter_type") not in QUOTAS
        or combat.get("turn_owner") != "player"
        or combat.get("is_play_phase") is not True
        or sum(c["verb"] == "end_turn" for c in candidates) != 1
        or sum(c["verb"] in {"play", "use"} for c in candidates) < 2
    ):
        return None
    block = _amount(combat["player"]["block"])
    attack = 0.0
    for enemy in combat["enemies"]:
        if enemy["intends_attack"] is not True:
            continue
        known = [i["total_damage"] for i in enemy["intents"] if "total_damage" in i]
        if not known:
            return None  # Do not infer an unknown attack from text or hidden engine state.
        attack += math.fsum(_amount(value) for value in known)
    if attack <= block:
        return None
    validate_public_input(public)
    return {
        "encounter_type": combat["encounter_type"],
        "public_round": turn,
        "source_floor": floor,
        "displayed_attack_total": attack,
        "current_block": block,
        "displayed_attack_excess": attack - block,
        "play_or_use_candidates": sum(c["verb"] in {"play", "use"} for c in candidates),
        "selection_uses_final_outcomes": False,
        "attack_excess_is_exact_hp_loss_prediction": False,
    }


def first_positions(decisions: list[dict[str, Any]]) -> dict[str, tuple[int, dict[str, Any]]]:
    """One earliest eligible public position per encounter type in a fixed source run."""
    result: dict[str, tuple[int, dict[str, Any]]] = {}
    for index, row in enumerate(decisions[:513]):
        evidence = eligibility(row["public_input"])
        if evidence is not None:
            result.setdefault(evidence["encounter_type"], (index, evidence))
    return result
