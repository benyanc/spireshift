"""Nested fresh world pools; fixed update rounds and all finals before evaluation."""

from __future__ import annotations

import statistics
from typing import Any

from spireshift.native_combat_behavior_data import intervals
from spireshift.native_experience_inputs import ARMS


def plan(cfg: dict[str, Any], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = [{"key": "policy-checks", "kind": "qualify"}]
    states = {}
    for p in (2, 3):
        tasks.append({"key": f"initial-p{p}", "kind": "import", "player": p, "arm": "initial"})
        for arm in ARMS:
            states[p, arm] = f"initial-p{p}"
    train = [s for s in seeds if s["partition"] == "train"]
    broad = cfg["batch_sizes"][ARMS[1]]
    for index in range(1, cfg["rounds"] + 1):
        pool = train[(index - 1) * broad : index * broad]
        for p in (2, 3):
            for arm in ARMS if (p + index) % 2 else ARMS[::-1]:
                rows = pool[: cfg["batch_sizes"][arm]]
                collections = []
                for start in range(0, len(rows), cfg["chunk_games"]):
                    key = f"train-p{p}-{arm}-r{index:02d}-c{start // cfg['chunk_games']:02d}"
                    tasks.append(
                        {
                            "key": key,
                            "kind": "collect",
                            "player": p,
                            "arm": arm,
                            "round": index,
                            "state": states[p, arm],
                            "seeds": rows[start : start + cfg["chunk_games"]],
                        }
                    )
                    collections.append(key)
                key = f"fit-p{p}-{arm}-r{index:02d}"
                tasks.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "player": p,
                        "arm": arm,
                        "round": index,
                        "state": states[p, arm],
                        "collections": collections,
                        "seeds": rows,
                    }
                )
                states[p, arm] = key
    variants = ("initial", *ARMS)
    for i, seed in enumerate(s for s in seeds if s["partition"] == "development"):
        for p in (2, 3):
            offset = (i + p) % 3
            for arm in variants[offset:] + variants[:offset]:
                tasks.append(
                    {
                        "key": f"eval-{seed['id']}-p{p}-{arm}",
                        "kind": "evaluate",
                        "player": p,
                        "arm": arm,
                        "seed": seed,
                        "state": f"initial-p{p}" if arm == "initial" else states[p, arm],
                    }
                )
    return tasks


def request(task: dict[str, Any], done: dict[str, dict[str, Any]]) -> dict[str, Any]:
    r = {"task": task, "contract": "fresh_nested_experience_budget_fixed_rounds_v1"}
    if "state" in task:
        r["predecessor_state_id"] = done[task["state"]]["state_id"]
    if task["kind"] == "fit":
        r["collection_ids"] = [done[k]["collection_id"] for k in task["collections"]]
    return r


def summarize(
    cfg: dict[str, Any], seeds: list[dict[str, Any]], done: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    worlds = [s for s in seeds if s["partition"] == "development"]
    cells = {
        (r["player"], r["seed_id"], r["arm"]): r for r in done.values() if r["kind"] == "evaluate"
    }
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    pairs = ((ARMS[1], ARMS[0]), (ARMS[0], "initial"), (ARMS[1], "initial"))
    values, players = {}, []
    for p in (2, 3):
        arms = {}
        for arm in ("initial", *ARMS):
            observed = [cells[p, s["id"], arm] for s in worlds if (p, s["id"], arm) in cells]
            v = [
                [float(row[k]) if row and row["status"] == "terminal" else 0.0 for k in columns]
                for row in (cells.get((p, s["id"], arm)) for s in worlds)
            ]
            values[p, arm] = v
            arms[arm] = {
                "denominator": len(worlds),
                "recorded": len(observed),
                "failed_games": sum(r["status"] != "terminal" for r in observed),
                "wins": int(sum(x[0] for x in v)),
                "mean_floor": statistics.fmean(x[2] for x in v),
                "mean_completed_acts": statistics.fmean(x[1] for x in v),
            }
        players.append({"player": p, "arms": arms})
    pooled = {}
    for a, b in pairs:
        diff = [
            [
                statistics.fmean(values[p, a][i][j] - values[p, b][i][j] for p in (2, 3))
                for j in range(4)
            ]
            for i in range(len(worlds))
        ]
        ci = (
            intervals(diff)
            if len(cells) == len(worlds) * 6 and cfg["stage"] != "short_control"
            else [None] * 4
        )
        pooled[f"{a}_minus_{b}"] = {
            name: {"mean": statistics.fmean(v[j] for v in diff), "interval95": ci[j]}
            for j, name in enumerate(columns)
        }
    return {
        "players": players,
        "pooled_paired_comparisons": pooled,
        "primary_comparison": "batch128_minus_batch32",
        "terminal_victory_primary": True,
        "independent_training_worlds": cfg["rounds"] * cfg["batch_sizes"][ARMS[1]],
        "independent_development_worlds": len(worlds),
        "fixed_parent_initializers": 2,
        "interval_method": "world_clustered_bootstrap_jointly_across_two_fixed_parents",
        "interval_covers_population_of_initializers": False,
        "training_attempts_or_decisions_are_independent_worlds": False,
        "failure_and_unattempted_values": 0,
        "checkpoint_promoted": False,
    }
