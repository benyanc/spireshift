"""Finite three-arm training; freeze every final state before fresh evaluation."""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from spireshift.native_combat_behavior_data import intervals
from spireshift.native_structured_model import ARMS

PAIRS = (
    ("named", "hashed"),
    ("hashed", "unchanged"),
    ("named", "unchanged"),
    ("unchanged", "original"),
    ("hashed", "original"),
    ("named", "original"),
)


def plan(cfg: dict[str, Any], seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = [{"key": "input-checks", "kind": "qualify"}]
    states = {}
    for player in (2, 3):
        for arm in ARMS:
            key = f"initial-p{player}-{arm}"
            states[player, arm] = key
            result.append({"key": key, "kind": "import", "player": player, "arm": arm})
    training = [s for s in seeds if s["partition"] == "train"]
    for index in range(1, cfg["rounds"] + 1):
        rows = training[(index - 1) * cfg["batch_games"] : index * cfg["batch_games"]]
        for player in (2, 3):
            # Rotate arm execution order without changing any actor's sampling stream.
            order = ARMS[(player + index) % 3 :] + ARMS[: (player + index) % 3]
            for arm in order:
                collections = []
                for start in range(0, len(rows), cfg["chunk_games"]):
                    key = f"train-p{player}-{arm}-r{index:02d}-c{start // cfg['chunk_games']:02d}"
                    result.append(
                        {
                            "key": key,
                            "kind": "collect",
                            "player": player,
                            "arm": arm,
                            "round": index,
                            "state": states[player, arm],
                            "seeds": rows[start : start + cfg["chunk_games"]],
                        }
                    )
                    collections.append(key)
                key = f"fit-p{player}-{arm}-r{index:02d}"
                result.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "player": player,
                        "arm": arm,
                        "round": index,
                        "state": states[player, arm],
                        "collections": collections,
                        "seeds": rows,
                    }
                )
                states[player, arm] = key
    for i, seed in enumerate(s for s in seeds if s["partition"] == "development"):
        variants = ("original", *ARMS)
        for player in (2, 3):
            order = variants[(i + player) % 4 :] + variants[: (i + player) % 4]
            for arm in order:
                result.append(
                    {
                        "key": f"eval-{seed['id']}-p{player}-{arm}",
                        "kind": "evaluate",
                        "player": player,
                        "arm": arm,
                        "seed": seed,
                        "state": f"initial-p{player}-unchanged"
                        if arm == "original"
                        else states[player, arm],
                    }
                )
    return result


def request(task: dict[str, Any], done: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = {"task": task, "contract": "named_inputs_equal_capacity_fresh_on_policy_v1"}
    if "state" in task:
        result["predecessor_state_id"] = done[task["state"]]["state_id"]
    if task["kind"] == "fit":
        result["collection_ids"] = [done[k]["collection_id"] for k in task["collections"]]
    return result


def summarize(
    cfg: dict[str, Any], seeds: list[dict[str, Any]], done: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    worlds = [s for s in seeds if s["partition"] == "development"]
    cells = {
        (r["player"], r["seed_id"], r["arm"]): r for r in done.values() if r["kind"] == "evaluate"
    }
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    players, differences = [], {}
    for player in (2, 3):
        arms, values = {}, {}
        for arm in ("original", *ARMS):
            observed = [
                cells[player, s["id"], arm] for s in worlds if (player, s["id"], arm) in cells
            ]
            values[arm] = [
                [float(row[k]) if row and row["status"] == "terminal" else 0.0 for k in columns]
                for row in (cells.get((player, s["id"], arm)) for s in worlds)
            ]
            arms[arm] = {
                "denominator": len(worlds),
                "recorded": len(observed),
                "failed_games": sum(r["status"] != "terminal" for r in observed),
                "not_attempted_games": len(worlds) - len(observed),
                "wins": int(sum(v[0] for v in values[arm])),
                "mean_completed_acts": statistics.fmean(v[1] for v in values[arm]),
                "mean_floor": statistics.fmean(v[2] for v in values[arm]),
                "mean_cpu_seconds": statistics.fmean(r["cpu_seconds"] for r in observed)
                if observed
                else None,
                "decision_families": dict(
                    sum((Counter(r.get("decision_families", {})) for r in observed), Counter())
                ),
                "supplement_fact_occurrences": sum(
                    r.get("supplement_fact_occurrences", 0) for r in observed
                ),
                "supplement_known_occurrences": sum(
                    r.get("supplement_known_occurrences", 0) for r in observed
                ),
                "unfamiliar_fact_occurrences": sum(
                    r.get("unfamiliar_fact_occurrences", 0) for r in observed
                ),
                "fitting_facts_outside_supplement": sum(
                    r.get("fitting_facts_outside_supplement", 0) for r in observed
                ),
            }
        comparisons = {}
        for a, b in PAIRS:
            diff = [
                [x - y for x, y in zip(v, w, strict=True)]
                for v, w in zip(values[a], values[b], strict=True)
            ]
            differences[player, a, b] = diff
            complete = arms[a]["recorded"] == arms[b]["recorded"] == len(worlds)
            ci = intervals(diff) if complete and cfg["stage"] != "short_control" else [None] * 4
            comparisons[f"{a}_minus_{b}"] = {
                name: {"mean": statistics.fmean(v[j] for v in diff), "interval95": ci[j]}
                for j, name in enumerate(columns)
            }
        players.append({"player": player, "arms": arms, "comparisons": comparisons})
    pooled = {}
    for a, b in PAIRS:
        diff = [
            [
                statistics.fmean((differences[2, a, b][i][j], differences[3, a, b][i][j]))
                for j in range(4)
            ]
            for i in range(len(worlds))
        ]
        ci = (
            intervals(diff)
            if len(cells) == len(worlds) * 8 and cfg["stage"] != "short_control"
            else [None] * 4
        )
        pooled[f"{a}_minus_{b}"] = {
            name: {"mean": statistics.fmean(v[j] for v in diff), "interval95": ci[j]}
            for j, name in enumerate(columns)
        }
    return {
        "players": players,
        "pooled_paired_comparisons": pooled,
        "primary_comparison": "named_minus_hashed",
        "capacity_control": "hashed_minus_unchanged",
        "independent_development_worlds": len(worlds),
        "fixed_parent_initializers": 2,
        "interval_method": "world_clustered_bootstrap_jointly_across_two_fixed_parents",
        "interval_covers_population_of_initializers": False,
        "terminal_victory_primary": True,
        "failure_and_unattempted_values": 0,
        "zero_wins_do_not_prove_zero_true_win_probability": True,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
    }
