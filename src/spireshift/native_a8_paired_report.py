"""Read verified native journals and summarize paired development outcomes."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import fmean
from typing import Any

from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_combat_behavior_data import BOOTSTRAP_SEED, RESAMPLES, intervals
from spireshift.native_flow_verification_v12 import records

ARMS = ("original", "fitted")
TERMINAL = {"win", "loss"}


def diagnostics(path: Path, won: bool) -> dict[str, Any]:
    maximum_act = maximum_floor = 0
    bosses: set[tuple[int, str]] = set()
    defeated_acts: set[int] = set()
    route: Counter[str] = Counter()
    shop_actions: Counter[str] = Counter()
    shop_gold: dict[tuple[int, int], list[int]] = {}
    frame: dict[str, Any] | None = None
    first = True
    for row in records(path):
        if row["kind"] in {"policy_input", "final_observation"}:
            frame = row["frame"]
            ctx = frame["public_input"]["context"]
            run, player = ctx["persistent"]["run"], ctx["persistent"]["player"]
            act, floor = run["act"], run["floor"]
            if first:
                if (
                    act != 1
                    or floor > 1
                    or run["ascension"] != 8
                    or player["character_definition_id"] != "IRONCLAD"
                    or frame["terminal"]
                ):
                    raise ValueError("Expected a normal Ironclad/A8 Act 1 start")
                first = False
            maximum_act, maximum_floor = max(maximum_act, act), max(maximum_floor, floor)
            state = ctx["interaction"]["content"].get("context", {})
            if state.get("encounter_type") == "boss":
                bosses.update((act, boss["definition_id"]) for boss in run["bosses"])
            if state.get("completed_boss_combat") is True:
                defeated_acts.add(act)
            shop_key = act, floor
            if frame["source_family"] in {"shop_room", "shop_inventory"}:
                shop_gold.setdefault(shop_key, [player["gold"], player["gold"]])
            if shop_key in shop_gold:
                shop_gold[shop_key][1] = player["gold"]
        elif row["kind"] == "policy_choice" and row["receipt"]["delivery_domain"] == "native":
            if frame is None:
                raise ValueError("A native delivery is missing its public decision")
            candidate = frame["public_input"]["candidates"][row["choice"]["action_index"]]
            subject = candidate.get("subject") or {}
            properties = subject.get("properties", {})
            family = frame["source_family"]
            if family == "map_navigation" and "point_type" in properties:
                route[properties["point_type"]] += 1
            if family in {"shop_room", "shop_inventory"}:
                if properties.get("can_purchase") is True:
                    kind = (
                        "removal_opened"
                        if subject["role"] == "card_removal"
                        else f"buy_{subject['role']}"
                    )
                    shop_actions[kind] += 1
                elif subject.get("role") != "potion" or candidate["verb"] == "use":
                    shop_actions[candidate["label"]] += 1
    if frame is None or first:
        raise ValueError("Missing verified public observations")
    completed_acts = 3 if won else max(0, maximum_act - 1)
    defeated_acts.update(range(1, completed_acts + 1))
    return {
        "maximum_act": maximum_act,
        "maximum_floor": maximum_floor,
        "completed_acts": completed_acts,
        "bosses_reached": [{"act": a, "boss": b} for a, b in sorted(bosses)],
        "bosses_cleared": [{"act": a, "boss": b} for a, b in sorted(bosses) if a in defeated_acts],
        "map_destinations": dict(route),
        "shop_visits": [
            {"act": a, "floor": f, "first_gold": gold[0], "last_gold": gold[1]}
            for (a, f), gold in sorted(shop_gold.items())
        ],
        "shop_actions": dict(shop_actions),
    }


def summarize(
    worlds: list[str], games: dict[tuple[str, int, str], dict[str, Any]]
) -> dict[str, Any]:
    def outcome(world: str, player: int, arm: str) -> str:
        return str(games.get((world, player, arm), {}).get("outcome", "unattempted"))

    def bounds(value: str) -> tuple[int, int]:
        if value in TERMINAL:
            win = int(value == "win")
            return win, win
        return 0, 1

    comparisons: dict[str, Any] = {}
    differences: dict[int, list[tuple[int, int]]] = {}
    for player in PLAYERS:
        outcomes = [
            (outcome(world, player, "original"), outcome(world, player, "fitted"))
            for world in worlds
        ]
        lower_upper = []
        for original, fitted in outcomes:
            olo, ohi = bounds(original)
            flo, fhi = bounds(fitted)
            lower_upper.append((flo - ohi, fhi - olo))
        differences[player] = lower_upper
        paired = Counter((a, b) for a, b in outcomes if a in TERMINAL and b in TERMINAL)
        comparisons[str(player)] = {
            "planned_worlds_per_arm": len(worlds),
            "arms": {
                arm: {
                    name: sum(row[index] == name for row in outcomes)
                    for name in ("win", "loss", "capped", "failed", "unattempted")
                }
                for index, arm in enumerate(ARMS)
            },
            "terminal_pairs": sum(paired.values()),
            "fitted_only_wins": paired["loss", "win"],
            "original_only_wins": paired["win", "loss"],
            "both_win": paired["win", "win"],
            "both_loss": paired["loss", "loss"],
            "fitted_minus_original_win_rate_bounds": [
                fmean(x) for x in zip(*lower_upper, strict=True)
            ],
        }
    rows = [bound for row in differences.values() for bound in row]
    result: dict[str, Any] = {
        "by_initializer": comparisons,
        "pooled_fitted_minus_original_win_rate_bounds": [fmean(x) for x in zip(*rows, strict=True)],
        "seed_clustered_bootstrap_95": None,
    }
    # Unknown outcomes stay in the denominator as bounds. A complete seed is
    # the unit resampled jointly for both numerical initializers.
    if all(lo == hi for lo, hi in rows):
        effects = []
        for index, world in enumerate(worlds):
            p2, p3 = (differences[p][index][0] for p in PLAYERS)
            acts = fmean(
                games[world, p, "fitted"]["completed_acts"]
                - games[world, p, "original"]["completed_acts"]
                for p in PLAYERS
            )
            effects.append([float(p2), float(p3), (p2 + p3) / 2, acts])
        result["seed_clustered_bootstrap_95"] = {
            "resamples": RESAMPLES,
            "seed": BOOTSTRAP_SEED,
            "intervals": dict(
                zip(
                    ("player_2_wins", "player_3_wins", "pooled_wins", "pooled_completed_acts"),
                    intervals(effects),
                    strict=True,
                )
            ),
            "scope": "descriptive_for_these_worlds_and_two_fixed_initializers",
        }
    return result
