"""Finite fresh-world PPO schedule and final-only, paired gameplay comparison."""

from __future__ import annotations

import statistics
from typing import Any

from spireshift.native_combat_behavior_data import intervals


def plan(cfg: dict[str, Any], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    training = [s for s in seeds if s["partition"] == "train"]
    evaluation = [s for s in seeds if s["partition"] == "development"]
    tasks: list[dict[str, Any]] = [{"key": "policy-update-checks", "kind": "qualify"}]
    states = {p: f"initial-p{p}" for p in (2, 3)}
    tasks.extend({"key": states[p], "kind": "import", "player": p} for p in (2, 3))
    for index in range(1, cfg["rounds"] + 1):
        rows = training[(index - 1) * cfg["batch_games"] : index * cfg["batch_games"]]
        for player in (2, 3):
            collections = []
            for start in range(0, len(rows), cfg["chunk_games"]):
                key = f"train-p{player}-r{index:02d}-c{start // cfg['chunk_games']:02d}"
                tasks.append(
                    {
                        "key": key,
                        "kind": "collect",
                        "player": player,
                        "round": index,
                        "state": states[player],
                        "seeds": rows[start : start + cfg["chunk_games"]],
                    }
                )
                collections.append(key)
            key = f"fit-p{player}-r{index:02d}"
            tasks.append(
                {
                    "key": key,
                    "kind": "fit",
                    "player": player,
                    "round": index,
                    "state": states[player],
                    "collections": collections,
                    "seed_ids": [s["id"] for s in rows],
                    "native_seeds": [s["seed"] for s in rows],
                }
            )
            states[player] = key
    # All final states exist before the first evaluation; no outcome selects an epoch.
    for i, seed in enumerate(evaluation):
        for player in (2, 3):
            for variant in ("original", "ppo") if (i + player) % 2 else ("ppo", "original"):
                tasks.append(
                    {
                        "key": f"eval-{seed['id']}-p{player}-{variant}",
                        "kind": "evaluate",
                        "player": player,
                        "variant": variant,
                        "state": f"initial-p{player}" if variant == "original" else states[player],
                        "seed": seed,
                    }
                )
    return tasks


def request(task: dict[str, Any], completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = {"task": task, "contract": "fresh_on_policy_update_v1"}
    if "state" in task:
        result["predecessor_state_id"] = completed[task["state"]]["state_id"]
    if task["kind"] == "fit":
        result["collection_ids"] = [completed[k]["collection_id"] for k in task["collections"]]
    return result


def summary(
    cfg: dict[str, Any], seeds: list[dict[str, Any]], done: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    worlds = [s for s in seeds if s["partition"] == "development"]
    rows = {
        (r["player"], r["seed_id"], r["variant"]): r
        for r in done.values()
        if r["kind"] == "evaluate"
    }
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    players, differences = [], {}
    for player in (2, 3):
        outcomes, arms = {}, {}
        for variant in ("original", "ppo"):
            observed = [
                rows[player, s["id"], variant] for s in worlds if (player, s["id"], variant) in rows
            ]
            values = []
            for seed in worlds:
                r = rows.get((player, seed["id"], variant))
                values.append(
                    [float(r[k]) if r and r["status"] == "terminal" else 0.0 for k in columns]
                )
            outcomes[variant] = values
            arms[variant] = {
                "denominator": len(worlds),
                "recorded": len(observed),
                "failed_games": sum(r["status"] != "terminal" for r in observed),
                "not_attempted_games": len(worlds) - len(observed),
                "wins": int(sum(v[0] for v in values)),
                "mean_completed_acts": statistics.fmean(v[1] for v in values),
                "mean_floor": statistics.fmean(v[2] for v in values),
                "mean_bootstrap_return": statistics.fmean(v[3] for v in values),
            }
        diff = [
            [a - b for a, b in zip(x, y, strict=True)]
            for x, y in zip(outcomes["ppo"], outcomes["original"], strict=True)
        ]
        differences[player] = diff
        complete = all(v["not_attempted_games"] == 0 for v in arms.values())
        ci = intervals(diff) if complete and cfg["stage"] != "short_control" else [None] * 4
        players.append(
            {
                "numerical_seed": player,
                "arms": arms,
                "ppo_minus_original": {
                    name: {"mean": statistics.fmean(v[j] for v in diff), "interval95": ci[j]}
                    for j, name in enumerate(columns)
                },
            }
        )
    pooled = [
        [statistics.fmean((differences[2][i][j], differences[3][i][j])) for j in range(4)]
        for i in range(len(worlds))
    ]
    complete = len(rows) == len(worlds) * 4
    ci = intervals(pooled) if complete and cfg["stage"] != "short_control" else [None] * 4
    return {
        "players": players,
        "pooled_ppo_minus_original": {
            name: {"mean": statistics.fmean(v[j] for v in pooled), "interval95": ci[j]}
            for j, name in enumerate(columns)
        },
        "evaluation_games_recorded": len(rows),
        "planned_evaluation_games": len(worlds) * 4,
        "independent_development_worlds": len(worlds),
        "fixed_parent_initializers": 2,
        "failure_and_unattempted_values": 0,
        "interval_method": "seed_clustered_bootstrap_jointly_across_two_fixed_parents",
        "interval_covers_population_of_training_initializers": False,
        "zero_observed_wins_do_not_establish_zero_true_win_probability": True,
        "terminal_victory_primary": True,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
    }
