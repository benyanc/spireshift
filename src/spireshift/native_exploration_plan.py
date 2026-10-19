"""Frozen matched training experiment; rest exploration is the sole treatment."""

from __future__ import annotations

from typing import Any

from spireshift.engine_learning import summarize
from spireshift.native_action_context import CROSSED
from spireshift.native_confirmation_metrics import compare

ARMS = [{"name": "standard", "uniform_weight": 0.0}, {"name": "rest_mix20", "uniform_weight": 0.2}]


def validate(cfg: dict[str, Any], seeds: dict[str, Any]) -> None:
    short = cfg.get("stage") == "short_bridge_control"
    if (
        cfg.get("schema_version") != "native-rest-exploration-config-v1"
        or cfg.get("stage") not in {"short_bridge_control", "bounded_rest_exploration"}
        or cfg.get("arms") != ARMS
        or cfg.get("training_seeds") != [2, 3]
        or cfg.get("starting_round") != 56
        or cfg.get("starting_training_games") != 1792
        or cfg.get("rounds") != (1 if short else 4)
        or cfg.get("batch_games") != (2 if short else 32)
        or cfg.get("chunk_games") != (2 if short else 8)
        or cfg.get("holdout_games") != (2 if short else 64)
        or cfg.get("checkpoint_selection")
        != "all_current_final_states_no_selection_or_early_stopping"
        or cfg.get("evaluation_uniform_weight") != 0.0
        or cfg.get("invocation_wall_seconds") != (240 if short else 7200)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if short else 900,
            "cpu_seconds": 480 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 4000000000,
        }
    ):
        raise ValueError(
            "Freeze a finite matched rest-only treatment, same starting players and caps"
        )
    rows = seeds["seeds"]
    expected = {
        "control" if short else "train": cfg["rounds"] * cfg["batch_games"],
        "control_eval" if short else "holdout": cfg["holdout_games"],
    }
    if (
        len(rows) != 2 * sum(expected.values())
        or len({r["id"] for r in rows}) != len(rows)
        or len({r["seed"] for r in rows}) != len(rows)
        or any(
            type(r["id"]) is not int
            or not isinstance(r["seed"], str)
            or not r["seed"]
            or r["numerical_seed"] not in (2, 3)
            or r["partition"] not in expected
            for r in rows
        )
        or any(
            sum(r["numerical_seed"] == n and r["partition"] == p for r in rows) != count
            for n in (2, 3)
            for p, count in expected.items()
        )
    ):
        raise ValueError("Distinct TRAIN and sealed holdout whole-run seeds are required")


def plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    short = cfg["stage"] == "short_bridge_control"
    rows = seeds["seeds"]
    tasks = []
    states = {}
    for ref in cfg["players"]:
        n = ref["numerical_seed"]
        for arm in cfg["arms"]:
            key = f"seed-{n}-{arm['name'].replace('_', '-')}-restore"
            states[n, arm["name"]] = key
            tasks.append(
                {"kind": "restore", "key": key, "numerical_seed": n, "arm": arm, "player": ref}
            )

    def collect(
        n: int,
        arm: dict[str, Any],
        rows: list[dict[str, Any]],
        label: str,
        training: bool,
        round_number: int,
    ) -> list[str]:
        keys = []
        for i in range(0, len(rows), cfg["chunk_games"]):
            key = f"seed-{n}-{arm['name'].replace('_', '-')}-{label}-{i // cfg['chunk_games']:02d}"
            keys.append(key)
            tasks.append(
                {
                    "kind": "collect",
                    "key": key,
                    "state": states[n, arm["name"]],
                    "numerical_seed": n,
                    "arm": arm,
                    "mode": CROSSED,
                    "seeds": rows[i : i + cfg["chunk_games"]],
                    "round": round_number,
                    "training": training,
                    "uniform_weight": arm["uniform_weight"] if training else 0.0,
                    "panel": "train" if training else label,
                    "version": label,
                    "failure_group": f"seed-{n}-{arm['name']}-{'train' if training else label}",
                }
            )
        return keys

    for index in range(cfg["rounds"]):
        round_number = cfg["starting_round"] + index + 1
        for n in cfg["training_seeds"]:
            own = [
                r
                for r in rows
                if r["numerical_seed"] == n and r["partition"] == ("control" if short else "train")
            ][index * cfg["batch_games"] : (index + 1) * cfg["batch_games"]]
            for arm in cfg["arms"]:
                collections = collect(
                    n, arm, own, f"train-round-{round_number:03d}", True, round_number
                )
                key = f"seed-{n}-{arm['name'].replace('_', '-')}-round-{round_number:03d}-fit"
                tasks.append(
                    {
                        "kind": "fit",
                        "key": key,
                        "state": states[n, arm["name"]],
                        "numerical_seed": n,
                        "arm": arm,
                        "round": round_number,
                        "collections": collections,
                        "round_seed_ids": [r["id"] for r in own],
                    }
                )
                states[n, arm["name"]] = key
    # No final test is opened until every arm/player finishes the declared horizon.
    for n in cfg["training_seeds"]:
        own = [
            r
            for r in rows
            if r["numerical_seed"] == n
            and r["partition"] == ("control_eval" if short else "holdout")
        ]
        current = states[n, "standard"]
        states[n, "standard"] = f"seed-{n}-standard-restore"
        collect(n, cfg["arms"][0], own, "holdout-original", False, 56)
        states[n, "standard"] = current
        for arm in cfg["arms"]:
            collect(
                n, arm, own, f"holdout-{arm['name'].replace('_', '-')}", False, 56 + cfg["rounds"]
            )
    return tasks


def panels(
    tasks: list[dict[str, Any]], completed: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for n in (2, 3):
        for version in ("holdout-original", "holdout-standard", "holdout-rest-mix20"):
            grouped = [
                t
                for t in tasks
                if t["kind"] == "collect"
                and not t["training"]
                and t["numerical_seed"] == n
                and t["version"] == version
            ]
            if not grouped or not all(t["key"] in completed for t in grouped):
                continue
            outcomes = [
                o for t in grouped for o in completed[t["key"]]["result"]["summary"]["outcomes"]
            ]
            result.append(
                {
                    "numerical_seed": n,
                    "version": version,
                    "outcomes": outcomes,
                    "summary": summarize(
                        [{**o, "decisions": range(o["decision_count"])} for o in outcomes],
                        sum(len(t["seeds"]) for t in grouped),
                    ),
                }
            )
    return result


def comparisons(holdout: list[dict[str, Any]], seeds: dict[str, Any]) -> dict[str, Any]:
    results = {}
    for name, before, after in (
        ("primary_rest_exploration_vs_standard", "holdout-standard", "holdout-rest-mix20"),
        ("secondary_standard_vs_original", "holdout-original", "holdout-standard"),
        ("secondary_exploration_vs_original", "holdout-original", "holdout-rest-mix20"),
    ):
        rows = [
            {**r, "version": "initial" if r["version"] == before else "trained"}
            for r in holdout
            if r["version"] in {before, after}
        ]
        results[name] = compare(
            {"training_seeds": [2, 3], "stage": "fresh_frozen_confirmation"},
            rows,
            {"seeds": [r for r in seeds["seeds"] if r["partition"] in {"holdout", "control_eval"}]},
        )
    return results
