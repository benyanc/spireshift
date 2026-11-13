"""Whole-run actor credit from independent full-menu policy samples."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from statistics import fmean
from typing import Any

from spireshift.native_a8_mix_fit import behavior_kl
from spireshift.native_a8_own_experience import samples
from spireshift.native_a8_own_policy import OwnPolicy
from spireshift.native_a8_own_ppo import Decision, update
from spireshift.native_a8_own_training import State, save_checkpoint
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_policy_updates import SETTINGS as BASE_SETTINGS
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.training_objective import (
    RunStatus,
    TrainingOutcome,
    TrainingScoreSpec,
    score_training_outcome,
)

DRAWS = 3
FITTED = ("pooled", "within_world")
ARMS = ("original", *FITTED)
SETTINGS = {**BASE_SETTINGS, "epochs": 1, "actor_learning_rate": 0.0006}


def sampler_seed(world: str, draw: int) -> str:
    if type(draw) is not int or not 0 <= draw < DRAWS:
        raise ValueError("Require a predeclared independent policy draw")
    return f"{world}/a8-world-credit-v1/{draw}"


def policy(
    ctx: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
) -> AnswerPolicy:
    task = start["scenario"]
    if (
        variant != "own_policy"
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or task["partition"] not in {"train", "control"}
        or start["seed"] != task["seed"]
    ):
        raise ValueError("Require independent model samples on fresh training worlds")
    return AnswerPolicy(OwnPolicy(model, ctx["score"], sampler_seed(start["seed"], task["draw"])))


def run_return(row: dict[str, Any], score: TrainingScoreSpec) -> float:
    if row["outcome"] not in {"win", "loss"}:
        raise ValueError("Incomplete games cannot supply a learning return")
    result = score_training_outcome(
        score,
        TrainingOutcome(
            row["task"]["seed_id"],
            RunStatus.VICTORY if row["outcome"] == "win" else RunStatus.LOSS,
            row["completed_acts"],
            row["maximum_floor"],
            row["native_decisions"],
            row["native_cpu_seconds"],
        ),
    )
    if not result["completed"]:
        raise ValueError("Over-budget games cannot supply a learning return")
    return float(result["training_return"])


def advantages(
    returns: dict[str, list[float]],
) -> dict[str, dict[str, list[float]]]:
    """Use other sampled episodes as baselines, excluding the credited run."""
    if len(returns) < 2 or any(
        len(rows) != DRAWS or any(not math.isfinite(r) or not 0 <= r <= 1 for r in rows)
        for rows in returns.values()
    ):
        raise ValueError("Require complete independent draws on at least two worlds")
    pooled, within = {}, {}
    for world, rows in returns.items():
        other = fmean(r for key, batch in returns.items() if key != world for r in batch)
        pooled[world] = [r - other for r in rows]
        within[world] = [
            r - fmean(peer for j, peer in enumerate(rows) if i != j) for i, r in enumerate(rows)
        ]
    return {"pooled": pooled, "within_world": within}


def fit(
    store: ChunkJournal,
    target: Path,
    original: State,
    games: list[dict[str, Any]],
    score: TrainingScoreSpec,
    player: int,
) -> dict[str, Any]:
    model, adam, original_id = original
    returns: dict[str, list[float]] = {}
    batches: dict[str, list[list[Decision]]] = {}
    for game in games:
        task = game["task"]
        seed = task["seed"]
        rows = batches.setdefault(seed, [])
        if task["player"] != player or task["draw"] != len(rows):
            raise ValueError("Training samples must preserve their declared world and draw order")
        decisions, run, _ = samples(
            store.path(task["key"]), game, model, score, task["partition"], 1
        )
        if run.target != run_return(game, score):
            raise ValueError("Full-run targets do not match the native outcome")
        rows.append(decisions)
        returns.setdefault(seed, []).append(run.target)
    credit = advantages(returns)
    original_rows = [d for rows in batches.values() for batch in rows for d in batch]
    behavior = behavior_kl(model, original_rows, SETTINGS)
    if behavior > 1e-12:
        raise ValueError("The original model must reconstruct every behavior probability")
    reports, fitted = {}, {}
    for arm in FITTED:
        training = [
            replace(d, advantage=value)
            for seed, groups in batches.items()
            for group, value in zip(groups, credit[arm][seed], strict=True)
            for d in group
        ]
        learned, next_adam, work = update(model, adam, training, SETTINGS, 97100 + player)
        if (
            work["stop_reason"] != "epoch_limit"
            or work["optimizer_steps"] < 1
            or learned.actor.genome == model.actor.genome
        ):
            raise ValueError(f"The {arm} fit has no usable bounded update: {work}")
        fitted[arm] = learned, next_adam, original_id
        reports[arm] = work
    if (
        reports["pooled"]["optimizer_steps"] != reports["within_world"]["optimizer_steps"]
        or fitted["pooled"][0].actor.genome == fitted["within_world"][0].actor.genome
    ):
        raise ValueError("Require distinct actors with the same optimizer work")
    checkpoints = {}
    for arm, state in fitted.items():
        directory = target / arm
        directory.mkdir()
        checkpoints[arm] = save_checkpoint(directory, state)
    return {
        "player": player,
        "predecessor_state_id": original_id,
        "training_returns": returns,
        "varied_worlds": sum(len(set(rows)) > 1 for rows in returns.values()),
        "training_games": len(games),
        "native_decisions": len(original_rows),
        "initial_behavior_kl": behavior,
        "optimizer_updates_per_copy": reports["pooled"]["optimizer_steps"],
        "work": reports,
        "critics_exactly_matched": fitted["pooled"][0].value_weights
        == fitted["within_world"][0].value_weights,
        "checkpoints": checkpoints,
    }
