from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.native_exploration_plan import ARMS, comparisons, plan, validate


def recipe(short: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg: dict[str, Any] = {
        "schema_version": "native-rest-exploration-config-v1",
        "stage": "short_bridge_control" if short else "bounded_rest_exploration",
        "arms": copy.deepcopy(ARMS),
        "training_seeds": [2, 3],
        "starting_round": 56,
        "starting_training_games": 1792,
        "rounds": 1 if short else 4,
        "batch_games": 2 if short else 32,
        "chunk_games": 2 if short else 8,
        "holdout_games": 2 if short else 64,
        "checkpoint_selection": "all_current_final_states_no_selection_or_early_stopping",
        "evaluation_uniform_weight": 0.0,
        "invocation_wall_seconds": 240 if short else 7200,
        "session_limits": {
            "wall_seconds": 240 if short else 900,
            "cpu_seconds": 480 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 4000000000,
        },
        "players": [{"numerical_seed": n} for n in (2, 3)],
    }
    rows: list[dict[str, Any]] = []
    for n in (2, 3):
        for part, size in [
            ("control" if short else "train", cfg["rounds"] * cfg["batch_games"]),
            ("control_eval" if short else "holdout", cfg["holdout_games"]),
        ]:
            for i in range(size):
                rows.append(
                    {
                        "id": 1600000 + len(rows),
                        "seed": f"REST{n}{part}{i}",
                        "numerical_seed": n,
                        "partition": part,
                    }
                )
    return cfg, {"seeds": rows}


def test_matched_forks_and_no_holdout_until_all_training_finished() -> None:
    cfg, seeds = recipe()
    validate(cfg, seeds)
    tasks = plan(cfg, seeds)
    assert sum(len(t.get("seeds", [])) for t in tasks) == 896
    fits = [t for t in tasks if t["kind"] == "fit"]
    assert (
        len(fits) == 16
        and min(t["round"] for t in fits) == 57
        and max(t["round"] for t in fits) == 60
    )
    first_test = next(
        i for i, t in enumerate(tasks) if t["kind"] == "collect" and not t["training"]
    )
    assert all(t["kind"] != "fit" for t in tasks[first_test:])
    for n in (2, 3):
        restores = [t for t in tasks if t["kind"] == "restore" and t["numerical_seed"] == n]
        assert restores[0]["player"] == restores[1]["player"]
        sets = []
        for arm in ARMS:
            chosen = [
                t
                for t in tasks
                if t["kind"] == "collect"
                and t["training"]
                and t["numerical_seed"] == n
                and t["arm"] == arm
            ]
            sets.append([r["id"] for t in chosen for r in t["seeds"]])
        assert sets[0] == sets[1]
    assert all(
        t["uniform_weight"] == 0.0 for t in tasks if t["kind"] == "collect" and not t["training"]
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("starting_round", 0),
        ("rounds", 100),
        ("evaluation_uniform_weight", 0.2),
        ("checkpoint_selection", "best_seen"),
    ],
)
def test_plan_refuses_reset_expansion_and_exploratory_final_test(key: str, value: Any) -> None:
    cfg, seeds = recipe()
    cfg[key] = value
    with pytest.raises(ValueError):
        validate(cfg, seeds)


def test_primary_comparison_uses_exact_paired_test_seeds_and_counts_failures() -> None:
    cfg, seeds = recipe(True)
    rows: list[dict[str, Any]] = []
    for n in (2, 3):
        own = [
            r
            for r in seeds["seeds"]
            if r["numerical_seed"] == n and r["partition"] == "control_eval"
        ]
        for version in ("holdout-original", "holdout-standard", "holdout-rest-mix20"):
            outcomes = [
                {
                    "seed_id": s["id"],
                    "seed": s["seed"],
                    "status": "failed"
                    if version == "holdout-rest-mix20" and i == 0
                    else "terminal",
                    "maximum_floor": 10,
                    "victory": False,
                }
                for i, s in enumerate(own)
            ]
            rows.append({"numerical_seed": n, "version": version, "outcomes": outcomes})
    result = comparisons(rows, seeds)["primary_rest_exploration_vs_standard"]
    assert result["aggregate"]["trained"]["denominator"] == 4
    assert result["aggregate"]["trained"]["failed_games"] == 2
    assert result["mean_floor_change"] == -5.0
    assert result["auxiliary_progress_confirmed"] is False
