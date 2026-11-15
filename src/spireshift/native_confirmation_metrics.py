"""Paired frozen-player summaries; complete-run seeds are the sampling unit.

Floor progress is auxiliary. Failures retain their denominator and count as zero
floor/wins in the confirmation endpoint. No result promotes or trains a player.
"""

from __future__ import annotations

import random
from typing import Any

RULE = "both_positive_floor_gain_pooled_lower95_positive_no_win_regression_zero_failures_v1"
BOOTSTRAPS = 10000
BOOTSTRAP_SEED = 20261019


def counted_floor(outcome: dict[str, Any]) -> int:
    return int(outcome["maximum_floor"]) if outcome["status"] == "terminal" else 0


def counted_win(outcome: dict[str, Any]) -> int:
    return int(outcome["status"] == "terminal" and outcome["victory"])


def interval(groups: list[list[float]]) -> list[float]:
    """Fixed percentile bootstrap, resampling seeds within each fixed initializer.

    This conditions on these two trained players; it is not uncertainty across a
    population of training initializers. There is one sampled trajectory per player/seed.
    """
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(
        sum(sum(rng.choices(g, k=len(g))) / len(g) for g in groups) / len(groups)
        for _ in range(BOOTSTRAPS)
    )
    return [means[int(0.025 * BOOTSTRAPS)], means[int(0.975 * BOOTSTRAPS) - 1]]


def compare(
    cfg: dict[str, Any], panels: list[dict[str, Any]], seeds: dict[str, Any]
) -> dict[str, Any]:
    players, differences = [], []
    for number in cfg["training_seeds"]:
        own = [s for s in seeds["seeds"] if s["numerical_seed"] == number]
        paired = {}
        versions = {}
        for version in ("initial", "trained"):
            rows = next(
                p["outcomes"]
                for p in panels
                if p["numerical_seed"] == number and p["version"] == version
            )
            by_id = {r["seed_id"]: r for r in rows}
            if (
                len(rows) != len(own)
                or len(by_id) != len(rows)
                or by_id.keys() != {s["id"] for s in own}
                or any(by_id[s["id"]]["seed"] != s["seed"] for s in own)
            ):
                raise ValueError("Confirmation needs exactly the reserved paired whole-run seeds")
            paired[version] = by_id
            versions[version] = {
                "denominator": len(own),
                "wins": sum(counted_win(r) for r in rows),
                "failed_games": sum(r["status"] != "terminal" for r in rows),
                "mean_floor": sum(counted_floor(r) for r in rows) / len(own),
            }
        delta = [
            float(
                counted_floor(paired["trained"][s["id"]])
                - counted_floor(paired["initial"][s["id"]])
            )
            for s in own
        ]
        differences.append(delta)
        players.append(
            {
                "numerical_seed": number,
                **versions,
                "mean_floor_change": sum(delta) / len(delta),
                "paired_floor_change_interval95": interval([delta]),
                "higher_floor_seeds": sum(d > 0 for d in delta),
                "tied_floor_seeds": sum(d == 0 for d in delta),
                "lower_floor_seeds": sum(d < 0 for d in delta),
                "trained_only_wins": sum(
                    counted_win(paired["trained"][s["id"]])
                    > counted_win(paired["initial"][s["id"]])
                    for s in own
                ),
                "initial_only_wins": sum(
                    counted_win(paired["initial"][s["id"]])
                    > counted_win(paired["trained"][s["id"]])
                    for s in own
                ),
            }
        )
    pooled = interval(differences)
    confirmed = (
        cfg["stage"] == "fresh_frozen_confirmation"
        and pooled[0] > 0
        and all(
            p["mean_floor_change"] > 0
            and p["trained"]["wins"] >= p["initial"]["wins"]
            and p["initial"]["failed_games"] + p["trained"]["failed_games"] == 0
            for p in players
        )
    )
    return {
        "players": players,
        "aggregate": {
            version: {
                "denominator": sum(p[version]["denominator"] for p in players),
                "wins": sum(p[version]["wins"] for p in players),
                "failed_games": sum(p[version]["failed_games"] for p in players),
                "mean_floor": sum(p[version]["mean_floor"] for p in players) / len(players),
            }
            for version in ("initial", "trained")
        },
        "mean_floor_change": sum(p["mean_floor_change"] for p in players) / len(players),
        "paired_floor_change_interval95": pooled,
        "interval_method": "fixed_percentile_seed_bootstrap_within_each_fixed_initializer",
        "bootstrap_resamples": BOOTSTRAPS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "independent_training_replicates": len(players),
        "uncertainty_covers_population_of_training_initializers": False,
        "one_sampled_trajectory_per_player_seed": True,
        "failure_floor_and_win_value": 0,
        "confirmation_rule": RULE,
        "auxiliary_progress_confirmed": confirmed,
        "terminal_victory_primary": True,
        "checkpoint_promoted": False,
        "base_readiness_passed": False,
        "adaptive_controller_allowed": False,
        "automatic_training_follows": False,
    }
