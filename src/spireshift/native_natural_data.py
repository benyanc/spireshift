"""Local natural-fight targets, not estimates of full-run strategic value."""

from __future__ import annotations

from collections import Counter
from typing import Any

from spireshift.engine_neural import validate_public_input
from spireshift.native_inventory_credit_features import inventory
from spireshift.native_turn_teacher_policy import POST_COMBAT, room, round_number

CONTRACT = "natural_native_multiturn_teacher_curriculum_v1"
ARMS = ("reference_clone", "teacher_clone")
LIMITS = {"maximum_actions": 192, "maximum_rounds": 12, "prefix_decisions": 512}
LEARNING = {
    "epochs": 16,
    "steps_per_epoch": 4,
    "batch_choices": 32,
    "actor_learning_rate": 0.001,
    "gradient_clip": 1.0,
    "temperature": 0.8,
}


def ending(root: dict[str, Any], public: dict[str, Any]) -> str | None:
    validate_public_input(public)
    p = public["context"]["persistent"]["player"]
    if float(p["hp"]) <= 0:
        return "loss"
    context = public["context"]["interaction"]
    content = context.get("content", {}).get("context", {})
    kind = content.get("kind")
    if kind == "reward_flow" and content.get("reward_kind") == "room_rewards":
        return "win"
    if room(public) != room(root):
        raise ValueError("A natural fight must stop before leaving its original room")
    if kind in POST_COMBAT:
        return "alive_exit"  # Escape or another reward is not proven encounter victory.
    if context["kind"] == "combat_turn" or kind == "selection":
        return None
    raise ValueError("Unrecognized natural encounter boundary; never invent a victory")


def resources(public: dict[str, Any]) -> dict[str, Any]:
    p = public["context"]["persistent"]["player"]
    # Persistent deck/relic changes cannot be priced by a local HP comparison.
    return {
        "hp": float(p["hp"]),
        "potions": sorted(x["definition_id"] for x in p["potions"] if x is not None),
        "deck": inventory(public)["deck_signature"],
        "relics": sorted(x["definition_id"] for x in p["relics"]),
        "gold": float(p["gold"]),
        "max_hp": float(p["max_hp"]),
    }


def improves(candidate: dict[str, Any], reference: dict[str, Any]) -> bool:
    """Verified fight win, or more HP without losing a retained permanent/consumable resource.

    This is explicitly a local teaching criterion, not a new full-game reward.
    Different remaining potion identities are compared as multisets, not counts.
    """
    if candidate["status"] != "complete" or candidate["outcome"] != "win":
        return False
    if reference["status"] != "complete":
        return False
    if reference["outcome"] == "loss":
        return True
    if reference["outcome"] != "win":
        return False
    a, b = candidate["resources"], reference["resources"]
    return bool(
        a["hp"] > b["hp"]
        and a["deck"] == b["deck"]
        and a["relics"] == b["relics"]
        and a["gold"] >= b["gold"]
        and a["max_hp"] >= b["max_hp"]
        and not (Counter(b["potions"]) - Counter(a["potions"]))
    )


def mutations(reference: dict[str, Any], maximum: int) -> list[dict[str, int]]:
    """Freeze first-divergence proposals at choices throughout the first three rounds.

    Uses only the reference's public menus/action scores, never candidate outcomes.
    End Turn and every other current action remain selectable in every rollout.
    """
    result = []
    seen_rounds: list[int] = []
    for index, step in enumerate(reference["steps"]):
        public = step["public_input"]
        if public["context"]["interaction"]["kind"] != "combat_turn":
            continue
        turn = round_number(public)
        if turn not in seen_rounds:
            seen_rounds.append(turn)
        if len(seen_rounds) > 3:
            break
        alternatives = sorted(
            (i for i in range(len(public["candidates"])) if i != step["action_index"]),
            key=lambda i: (-step["log_probabilities"][i], i),
        )
        for action in alternatives[:2]:
            result.append({"decision": index, "action": action})
    # Round-robin across public rounds before filling more decisions in one turn.
    result.sort(
        key=lambda x: (
            sum(
                1
                for s in reference["steps"][: x["decision"]]
                if s["public_input"]["context"]["interaction"]["kind"] == "combat_turn"
                and round_number(s["public_input"])
                == round_number(reference["steps"][x["decision"]]["public_input"])
            ),
            x["decision"],
            x["action"],
        )
    )
    return result[:maximum]


def select(rows: list[dict[str, Any]]) -> int:
    if not rows or rows[0]["candidate"] != 0:
        raise ValueError("Retain the declared greedy reference in its original denominator")
    preferred = [r for r in rows[1:] if improves(r, rows[0])]
    return (
        max(preferred, key=lambda r: (r["resources"]["hp"], -r["candidate"]))["candidate"]
        if preferred
        else 0
    )


def admit(roots: list[dict[str, Any]], summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if len({s["root_id"] for s in summaries}) != len(summaries):
        raise ValueError("Repeated summaries cannot manufacture independent fitting worlds")
    fit = {r["root_id"]: r for r in roots if r["partition"] == "fit"}
    usable = [
        s
        for s in summaries
        if s["root_id"] in fit
        and s["verified"]
        and s["selected_outcome"] == "win"
        and s["choice_decisions"] >= 4
        and s["public_rounds"] >= 2
    ]
    improved = [s for s in usable if s["strict_local_improvement"]]
    checks = {
        "four_fitting_worlds": len({fit[s["root_id"]]["world"] for s in usable}) >= 4,
        "two_strict_local_improvements": len(improved) >= 2,
        "two_encounters": len(
            {tuple(fit[s["root_id"]]["descriptor"]["enemy_definitions"]) for s in usable}
        )
        >= 2,
        "three_decks": len({fit[s["root_id"]]["descriptor"]["deck_signature"] for s in usable})
        >= 3,
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "usable_fitting_roots": [s["root_id"] for s in usable],
        "strictly_improved_fitting_roots": len(improved),
        "heldout_results_used": False,
        "full_run_utility_established": False,
    }
