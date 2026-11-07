"""Fresh whole-game checks of original and both supervised forks, with matched draws."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_combat_behavior_data import intervals
from spireshift.native_consequence_config import EVAL_ARMS

CONTRASTS = (
    ("consequence", "return_only"),
    ("consequence", "original"),
    ("return_only", "original"),
)


def game_key(seed_id: int, player: int, variant: str) -> str:
    return f"game-{seed_id}-p{player}-{variant.replace('_', '-')}"


def tasks(seeds: list[dict[str, Any]], control: bool) -> list[dict[str, Any]]:
    result = []
    for i, seed in enumerate(seeds):
        for player in [seed["numerical_seed"]] if control else [2, 3]:
            offset = (i + player) % len(EVAL_ARMS)
            order = (*EVAL_ARMS[offset:], *EVAL_ARMS[:offset])
            for variant in order:
                result.append(
                    {
                        "key": game_key(seed["id"], player, variant),
                        "stage": "game",
                        "seed": seed,
                        "numerical_seed": player,
                        "variant": variant,
                        "arm": "greedy",
                        "duplicate_of": None,
                    }
                )
    if control:
        result.extend(
            {**t, "key": f"duplicate-p{t['numerical_seed']}", "duplicate_of": t["key"]}
            for t in list(result)
            if t["variant"] == "consequence"
        )
    return result


def duplicates(planned: list[dict[str, Any]], completed: dict[str, dict[str, Any]]) -> bool | None:
    comparisons = []
    for task in planned:
        if not task["duplicate_of"] or task["key"] not in completed:
            continue
        a, b = completed[task["key"]], completed[task["duplicate_of"]]
        same = a["status"] == b["status"] == "terminal" and a["trace_id"] == b["trace_id"]
        if not same:
            raise ValueError("The exact native consequence control repeat changed")
        comparisons.append(same)
    return all(comparisons) if comparisons else None


def matched_draws(root: Path, completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cells = {
        (v["numerical_seed"], v["seed_id"], v["variant"]): v
        for v in completed.values()
        if v.get("stage") == "game" and v["status"] == "terminal" and not v["duplicate_of"]
    }
    pairs = shared = same = changed = 0
    for player, seed, variant in cells:
        if variant != "consequence":
            continue
        for reference in ("original", "return_only"):
            if (player, seed, reference) not in cells:
                continue
            maps = []
            for name in (reference, "consequence"):
                v = cells[player, seed, name]
                receipt = identified(root / v["rng_receipt_path"])
                if receipt["report_id"] != v["rng_receipt_id"]:
                    raise ValueError("Changed saved consequence-policy randomness receipt")
                rows = {r["draw_key"]: r for r in receipt["noncombat"]}
                if len(rows) != len(receipt["noncombat"]):
                    raise ValueError("A learned fork reused a noncombat sampling slot")
                maps.append(rows)
            pairs += 1
            for key in maps[0].keys() & maps[1].keys():
                a, b = maps[0][key], maps[1][key]
                if a["draw"] != b["draw"]:
                    raise ValueError("Model/variant identity shifted a matched noncombat draw")
                shared += 1
                if a["effective_input_id"] == b["effective_input_id"]:
                    same += 1
                    changed += a["action_index"] != b["action_index"]
    return {
        "valid": True,
        "paired_model_seed_cells": pairs,
        "shared_noncombat_draw_keys": shared,
        "identical_public_input_pairs": same,
        "identical_inputs_with_changed_learned_choice": changed,
        "same_rule_and_draws_not_frozen_noncombat_weights": True,
    }


def summarize(
    seeds: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    control: bool,
) -> dict[str, Any]:
    planned = tasks(seeds, control)
    games = {k: v for k, v in completed.items() if v.get("stage") == "game"}
    if not set(games).issubset({t["key"] for t in planned}):
        raise ValueError("Unplanned or replacement evaluation game")
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    players: list[dict[str, Any]] = []
    differences = {}
    for player in (2, 3):
        own_seeds = [s for s in seeds if not control or s["numerical_seed"] == player]
        outcomes, arms = {}, {}
        for variant in EVAL_ARMS:
            values, observed = [], []
            for seed in own_seeds:
                v = games.get(game_key(seed["id"], player, variant))
                if v is not None and (
                    v["numerical_seed"] != player
                    or v["seed_id"] != seed["id"]
                    or v["variant"] != variant
                ):
                    raise ValueError("A saved game belongs to another player/seed/variant")
                clean = v is not None and v["status"] == "terminal"
                values.append([float(v[k]) if clean and v else 0.0 for k in columns])
                if v is not None:
                    observed.append(v)
            outcomes[variant] = values
            terminal = [v for v in observed if v["status"] == "terminal"]
            arms[variant] = {
                "denominator": len(own_seeds),
                "completed_games": len(terminal),
                "failed_games": len(observed) - len(terminal),
                "not_attempted_games": len(own_seeds) - len(observed),
                "wins": int(sum(v[0] for v in values)),
                "mean_completed_acts": statistics.fmean(v[1] for v in values),
                "mean_floor": statistics.fmean(v[2] for v in values),
                "mean_bootstrap_return": statistics.fmean(v[3] for v in values),
                "best_floor": max((v["maximum_floor"] for v in terminal), default=0),
                "cpu_seconds": sum(v["cpu_seconds"] for v in observed),
            }
        comparisons = {}
        for treatment, reference in CONTRASTS:
            label = f"{treatment}_minus_{reference}"
            diff = [
                [a - b for a, b in zip(x, y, strict=True)]
                for x, y in zip(outcomes[treatment], outcomes[reference], strict=True)
            ]
            differences[player, label] = diff
            complete = all(arms[a]["not_attempted_games"] == 0 for a in (reference, treatment))
            ci = intervals(diff) if complete and not control else [None] * len(columns)
            comparisons[label] = {
                k: {"mean": statistics.fmean(v[j] for v in diff), "interval95": ci[j]}
                for j, k in enumerate(columns)
            }
        players.append({"numerical_seed": player, "arms": arms, "comparisons": comparisons})
    pooled = {}
    for a, b in CONTRASTS:
        label = f"{a}_minus_{b}"
        if not control:
            values = [
                [
                    statistics.fmean((differences[2, label][i][j], differences[3, label][i][j]))
                    for j in range(len(columns))
                ]
                for i in range(len(seeds))
            ]
            complete = all(not p["arms"][v]["not_attempted_games"] for p in players for v in (a, b))
            ci = intervals(values) if complete else [None] * len(columns)
            pooled[label] = {
                k: {"mean": statistics.fmean(v[j] for v in values), "interval95": ci[j]}
                for j, k in enumerate(columns)
            }
    body = {
        "players": players,
        "pooled_paired_comparisons": pooled,
        "planned_games": len(planned),
        "completed_games": sum(v["status"] == "terminal" for v in games.values()),
        "failed_games": sum(v["status"] != "terminal" for v in games.values()),
        "not_attempted_games": len(planned) - len(games),
        "fixed_players": 2,
        "independent_development_worlds": len(seeds),
        "short_control_not_strength_evidence": control,
        "failure_and_unattempted_evaluation_value": 0,
        "interval_method": "seed_clustered_percentile_bootstrap_jointly_across_two_fixed_parents",
        "uncertainty_covers_population_of_training_initializers": False,
        "no_multiplicity_corrected_gameplay_success_claim": True,
        "terminal_victory_primary": True,
        "base_readiness_passed": False,
        "checkpoint_promoted": False,
    }
    return {**body, "report_id": manifest_identifier(body)}
