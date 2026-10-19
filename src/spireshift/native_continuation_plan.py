"""Finite two-player continuation plan and sealed, development-only stopping rule."""

from __future__ import annotations

from typing import Any

from spireshift.engine_learning import summarize
from spireshift.native_action_context import CROSSED
from spireshift.native_confirmation_metrics import counted_floor, counted_win

ARM = {"name": "standard", "batch_games": 32, "epoch_multiplier": 1}
STOP_RULE = "pooled_wins_then_floor_two_stale_checks_after_512_new_games_v1"


def validate(cfg: dict[str, Any], seeds: dict[str, Any]) -> None:
    short = cfg.get("stage") == "short_bridge_control"
    if (
        cfg.get("schema_version") != "native-policy-continuation-config-v1"
        or cfg.get("stage") not in {"short_bridge_control", "bounded_standard_continuation"}
        or cfg.get("training_seeds") != [2, 3]
        or cfg.get("starting_training_games") != 512
        or cfg.get("starting_round") != 16
        or cfg.get("additional_games_per_player") != (2 if short else 1024)
        or cfg.get("batch_games") != (2 if short else 32)
        or cfg.get("chunk_games") != (2 if short else 8)
        or cfg.get("evaluation_games") != (2 if short else 32)
        or cfg.get("holdout_games") != (0 if short else 64)
        or cfg.get("milestones") != ([514] if short else [768, 1024, 1280, 1536])
        or cfg.get("stopping_rule") != STOP_RULE
        or cfg.get("checkpoint_selection") != "both_current_stopping_states_not_best_seen"
        or cfg.get("invocation_wall_seconds") != (240 if short else 14400)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 240 if short else 900,
            "cpu_seconds": 480 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 8000000000,
        }
    ):
        raise ValueError(
            "Freeze both players, continuation horizon, absolute rounds, stop rule and caps"
        )
    rows = seeds["seeds"]
    expected = {
        "control" if short else "train": cfg["additional_games_per_player"],
        "control_eval" if short else "development": cfg["evaluation_games"],
    }
    if not short:
        expected["holdout"] = cfg["holdout_games"]
    if (
        len(rows) != 2 * sum(expected.values())
        or len({s["id"] for s in rows}) != len(rows)
        or len({s["seed"] for s in rows}) != len(rows)
        or any(
            type(s["id"]) is not int
            or not isinstance(s["seed"], str)
            or not s["seed"]
            or s["numerical_seed"] not in (2, 3)
            or s["partition"] not in expected
            for s in rows
        )
        or any(
            sum(s["numerical_seed"] == n and s["partition"] == p for s in rows) != size
            for n in (2, 3)
            for p, size in expected.items()
        )
    ):
        raise ValueError(
            "Fresh continuation seeds repeat, cross partitions or miss whole-run ownership"
        )


def task_collect(
    cfg: dict[str, Any],
    state: str,
    number: int,
    milestone: int,
    rows: list[dict[str, Any]],
    panel: str,
    training: bool,
    failure_group: str,
) -> list[dict[str, Any]]:
    return [
        {
            "key": f"seed-{number}-{panel}-{i // cfg['chunk_games']:02d}",
            "kind": "collect",
            "state": state,
            "arm": ARM,
            "mode": CROSSED,
            "numerical_seed": number,
            "round": milestone // 32,
            "milestone": milestone,
            "training": training,
            "seeds": rows[i : i + cfg["chunk_games"]],
            "panel": "train" if training else panel,
            "failure_group": failure_group,
        }
        for i in range(0, len(rows), cfg["chunk_games"])
    ]


def training_plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    short = cfg["stage"] == "short_bridge_control"
    train_partition, dev_partition = (
        ("control", "control_eval") if short else ("train", "development")
    )
    own = {
        n: [
            s
            for s in seeds["seeds"]
            if s["numerical_seed"] == n and s["partition"] == train_partition
        ]
        for n in cfg["training_seeds"]
    }
    dev = {
        n: [
            s
            for s in seeds["seeds"]
            if s["numerical_seed"] == n and s["partition"] == dev_partition
        ]
        for n in cfg["training_seeds"]
    }
    result: list[dict[str, Any]] = []
    initial_evals: list[str] = []
    states = {}
    for ref in cfg["players"]:
        n = ref["numerical_seed"]
        states[n] = f"seed-{n}-restore"
        result.append(
            {
                "key": states[n],
                "kind": "restore",
                "numerical_seed": n,
                "player": ref,
                "round": cfg["starting_round"],
            }
        )
    for n in cfg["training_seeds"]:
        tasks = task_collect(
            cfg,
            states[n],
            n,
            512,
            dev[n],
            "development-at-0512",
            False,
            f"seed-{n}-development-at-0512",
        )
        result.extend(tasks)
        initial_evals.extend(t["key"] for t in tasks)
    decisions: list[str] = []
    previous = 512
    for milestone in cfg["milestones"]:
        for offset in range(previous - 512, milestone - 512, cfg["batch_games"]):
            for n in cfg["training_seeds"]:
                # Continue the original absolute round / minibatch shuffle schedule.
                round_number = cfg["starting_round"] + offset // cfg["batch_games"] + 1
                actual_games = 512 + offset + cfg["batch_games"]
                batch = own[n][offset : offset + cfg["batch_games"]]
                tasks = task_collect(
                    cfg,
                    states[n],
                    n,
                    actual_games,
                    batch,
                    f"train-round-{round_number:03d}",
                    True,
                    f"seed-{n}-train-stage-{milestone}",
                )
                result.extend(tasks)
                key = f"seed-{n}-round-{round_number:03d}-fit"
                result.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "state": states[n],
                        "arm": ARM,
                        "mode": CROSSED,
                        "numerical_seed": n,
                        "round": round_number,
                        "milestone": actual_games,
                        "collections": [t["key"] for t in tasks],
                        "round_seed_ids": [s["id"] for s in batch],
                    }
                )
                states[n] = key
        evaluations: list[str] = []
        for n in cfg["training_seeds"]:
            tasks = task_collect(
                cfg,
                states[n],
                n,
                milestone,
                dev[n],
                f"development-at-{milestone:04d}",
                False,
                f"seed-{n}-development-at-{milestone:04d}",
            )
            result.extend(tasks)
            evaluations.extend(t["key"] for t in tasks)
        key = f"decision-at-{milestone:04d}"
        result.append(
            {
                "key": key,
                "kind": "decide",
                "milestone": milestone,
                "states": {str(n): k for n, k in states.items()},
                "initial_evaluations": initial_evals,
                "evaluations": evaluations,
                "prior_decisions": list(decisions),
            }
        )
        decisions.append(key)
        previous = milestone
    return result


def final_plan(
    cfg: dict[str, Any], seeds: dict[str, Any], decision: dict[str, Any]
) -> list[dict[str, Any]]:
    if not cfg["holdout_games"]:
        return []
    result = []
    for n in cfg["training_seeds"]:
        rows = [
            s for s in seeds["seeds"] if s["numerical_seed"] == n and s["partition"] == "holdout"
        ]
        for version in ("initial", "trained"):
            state = f"seed-{n}-restore" if version == "initial" else decision["states"][str(n)]
            result.extend(
                task_collect(
                    cfg,
                    state,
                    n,
                    512 if version == "initial" else decision["milestone"],
                    rows,
                    f"holdout-{version}",
                    False,
                    f"seed-{n}-holdout-{version}",
                )
            )
    return result


def outcomes(keys: list[str], completed: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [o for k in keys for o in completed[k]["result"]["summary"]["outcomes"]]


def pooled(keys: list[str], completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = outcomes(keys, completed)
    return {
        "denominator": len(rows),
        "wins": sum(counted_win(r) for r in rows),
        "mean_floor": sum(counted_floor(r) for r in rows) / len(rows),
        "failed_games": sum(r["status"] != "terminal" for r in rows),
    }


def decide(
    cfg: dict[str, Any], task: dict[str, Any], completed: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    current = pooled(task["evaluations"], completed)
    previous = [pooled(task["initial_evaluations"], completed)] + [
        completed[k]["result"]["current"] for k in task["prior_decisions"]
    ]

    def score(p: dict[str, Any]) -> tuple[int, float]:
        return p["wins"], p["mean_floor"]

    improved = score(current) > max(score(p) for p in previous)
    stale = (
        0
        if improved
        else (
            completed[task["prior_decisions"][-1]]["result"]["stale_checks"]
            if task["prior_decisions"]
            else 0
        )
        + 1
    )
    short = cfg["stage"] == "short_bridge_control"
    plateau = not short and task["milestone"] >= 1024 and stale >= 2
    horizon = task["milestone"] == cfg["milestones"][-1]
    return {
        "milestone": task["milestone"],
        "states": task["states"],
        "current": current,
        "improved_over_previous_best": improved,
        "stale_checks": stale,
        "stop": plateau or horizon,
        "reason": "short_control_complete"
        if short
        else ("development_plateau" if plateau else "finite_horizon" if horizon else "continue"),
        "checkpoint_selection": "both_current_stopping_states_not_best_seen",
        "holdout_consulted": False,
    }


def panels(
    cfg: dict[str, Any],
    tasks: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    *,
    holdout: bool = False,
) -> list[dict[str, Any]]:
    result = []
    for n in cfg["training_seeds"]:
        names = list(
            dict.fromkeys(
                t["panel"]
                for t in tasks
                if t.get("kind") == "collect" and not t["training"] and t["numerical_seed"] == n
            )
        )
        for label in names:
            chosen = [
                t
                for t in tasks
                if t.get("kind") == "collect"
                and not t["training"]
                and t["panel"] == label
                and t["numerical_seed"] == n
            ]
            if any(t["key"] not in completed for t in chosen):
                continue
            rows = outcomes([t["key"] for t in chosen], completed)
            body = {
                "numerical_seed": n,
                "panel": label,
                "training_games": chosen[0]["milestone"],
                "outcomes": rows,
                "model_id": completed[chosen[0]["key"]]["result"]["model_id"],
                "summary": summarize(
                    [{**r, "decisions": range(r["decision_count"])} for r in rows], len(rows)
                ),
            }
            if holdout:
                body["version"] = label.split("-")[-1]
            result.append(body)
    return result
