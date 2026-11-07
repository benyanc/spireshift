"""Fixed complete-game tasks and seed-clustered, paired evaluation summaries."""

from __future__ import annotations

import random
import statistics
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_combat_behavior_policy import ARMS

BOOTSTRAP_SEED = 20261020
RESAMPLES = 10000


def tasks(seeds: list[dict[str, Any]], control: bool) -> list[dict[str, Any]]:
    result = []
    for index, seed in enumerate(seeds):
        for player in (2, 3):
            # Counterbalance order without selecting on outcomes or machine timing.
            for arm in ARMS if (index + player) % 2 == 0 else tuple(reversed(ARMS)):
                result.append(
                    {
                        "key": f"game-{seed['id']}-p{player}-{arm}",
                        "seed": seed,
                        "numerical_seed": player,
                        "arm": arm,
                        "duplicate_of": None,
                    }
                )
    if control:
        result.extend(
            {**t, "key": f"duplicate-p{t['numerical_seed']}-{t['arm']}", "duplicate_of": t["key"]}
            for t in result[:4]
        )
    return result


def intervals(differences: list[list[float]]) -> list[list[float]]:
    if not differences or any(len(row) != 4 for row in differences):
        raise ValueError("Keep four paired outcomes for every original complete-game seed")
    rng = random.Random(BOOTSTRAP_SEED)
    samples: list[list[float]] = [[] for _ in range(4)]
    for _ in range(RESAMPLES):
        selected = [rng.randrange(len(differences)) for _ in differences]
        for column in range(4):
            samples[column].append(statistics.fmean(differences[i][column] for i in selected))
    result = []
    for values in samples:
        values.sort()
        result.append([values[int(0.025 * (RESAMPLES - 1))], values[int(0.975 * (RESAMPLES - 1))]])
    return result


def summarize(
    seeds: list[dict[str, Any]], completed: dict[str, dict[str, Any]], *, control: bool
) -> dict[str, Any]:
    planned = tasks(seeds, control)
    if not set(completed).issubset({t["key"] for t in planned}):
        raise ValueError("Comparison includes an unplanned or replacement game")
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    players: list[dict[str, Any]] = []
    diffs: dict[int, list[list[float]]] = {}
    for player in (2, 3):
        arms, outcomes = {}, {}
        for arm in ARMS:
            values = []
            for seed in seeds:
                value = completed.get(f"game-{seed['id']}-p{player}-{arm}")
                clean = value is not None and value["status"] == "terminal"
                if value is not None and (
                    value["numerical_seed"] != player
                    or value["arm"] != arm
                    or value["seed_id"] != seed["id"]
                ):
                    raise ValueError("Saved game is bound to a different paired cell")
                values.append([float(value[k]) if clean and value else 0.0 for k in columns])
            outcomes[arm] = values
            rows = [
                completed[t["key"]]
                for t in planned
                if t["key"] in completed
                and t["numerical_seed"] == player
                and t["arm"] == arm
                and not t["duplicate_of"]
            ]
            terminal = [v for v in rows if v["status"] == "terminal"]
            arms[arm] = {
                "denominator": len(seeds),
                "completed_games": len(terminal),
                "failed_games": len(rows) - len(terminal),
                "not_attempted_games": len(seeds) - len(rows),
                "wins": int(sum(v[0] for v in values)),
                "mean_completed_acts": statistics.fmean(v[1] for v in values),
                "mean_floor": statistics.fmean(v[2] for v in values),
                "mean_bootstrap_return": statistics.fmean(v[3] for v in values),
                "best_floor": max((v["maximum_floor"] for v in terminal), default=0),
                "cpu_seconds": sum(v["cpu_seconds"] for v in rows),
            }
        diff = [
            [g - s for g, s in zip(greedy, sampled, strict=True)]
            for greedy, sampled in zip(outcomes["greedy"], outcomes["sampled"], strict=True)
        ]
        diffs[player] = diff
        ci = intervals(diff)
        players.append(
            {
                "numerical_seed": player,
                "arms": arms,
                "greedy_minus_sampled": {
                    k: {"mean": statistics.fmean(v[i] for v in diff), "interval95": ci[i]}
                    for i, k in enumerate(columns)
                },
            }
        )
    pooled = [
        [statistics.fmean((diffs[2][i][j], diffs[3][i][j])) for j in range(4)]
        for i in range(len(seeds))
    ]
    ci = intervals(pooled)
    body = {
        "schema_version": "native-combat-behavior-summary-v1",
        "players": players,
        "pooled_greedy_minus_sampled": {
            k: {"mean": statistics.fmean(v[i] for v in pooled), "interval95": ci[i]}
            for i, k in enumerate(columns)
        },
        "independent_game_seeds": len(seeds),
        "fixed_players": 2,
        "denominator": 4 * len(seeds),
        "completed_games": sum(a["completed_games"] for p in players for a in p["arms"].values()),
        "failed_games": sum(a["failed_games"] for p in players for a in p["arms"].values()),
        "not_attempted_games": sum(
            a["not_attempted_games"] for p in players for a in p["arms"].values()
        ),
        "failure_and_unattempted_evaluation_value": 0,
        "interval_method": (
            "percentile_bootstrap_complete_game_seed_jointly_across_both_fixed_players"
        ),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_resamples": RESAMPLES,
        "uncertainty_covers_population_of_training_initializers": False,
        "one_behavior_stream_per_arm_player_game_seed": True,
        "short_control_not_strength_evidence": control,
        "terminal_victory_primary": True,
        "base_readiness_passed": False,
        "checkpoint_promoted": False,
    }
    return {**body, "report_id": manifest_identifier(body)}
