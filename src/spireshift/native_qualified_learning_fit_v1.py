"""Shared actor/critic PPO from verified, model-owned complete normal starts."""

from __future__ import annotations

import math
import random
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.native_a8_head_policy import HeadState, OwnedDecision
from spireshift.native_a8_head_training import gradient, step, training_examples
from spireshift.native_combat_intent_model import (
    CombatIntentModel,
    CombatIntentState,
    using_intent_encoder,
)
from spireshift.training_objective import TrainingScoreSpec


def fit(
    state: HeadState,
    games: list[tuple[Path, dict[str, Any]]],
    score: TrainingScoreSpec,
    credit: dict[str, Any],
    settings: dict[str, Any],
    round_index: int,
    seed: int,
    deadline: float,
    *,
    control_steps: int | None = None,
) -> tuple[HeadState, dict[str, Any]]:
    if not isinstance(state.model, CombatIntentModel) or state.model.arm != "shared":
        raise ValueError("Require the shared actor with the qualified card/intent encoder")
    with using_intent_encoder():
        examples, evidence = training_examples(games, state, score, credit, round_index)
    if not examples:
        raise ValueError("A PPO round requires verified model-owned decisions")
    mean = math.fsum(row.decision.advantage for row in examples) / len(examples)
    std = math.sqrt(
        math.fsum((row.decision.advantage - mean) ** 2 for row in examples) / len(examples)
    )
    if not math.isfinite(std):
        raise ValueError("Require finite objective credit")
    prepared = [
        replace(
            row,
            decision=replace(
                row.decision, advantage=(row.decision.advantage - mean) / max(std, 1e-8)
            ),
        )
        for row in examples
    ]
    current = state
    work: dict[str, Any] = {
        **evidence,
        "raw_advantage_std": std,
        "optimizer_updates": 0,
        "actor_and_critic_learned": True,
        "epochs_completed": 0,
        "stop_reason": "epoch_limit",
    }
    indices = list(range(len(prepared)))
    rng = random.Random(seed)
    batch_size = settings["minibatch_decisions"]
    for epoch in range(1, settings["epochs"] + 1):
        rng.shuffle(indices)
        for offset in range(0, len(indices), batch_size):
            if time.monotonic() >= deadline:
                raise TimeoutError("Preserve the incomplete PPO fit at its deadline")
            batch: list[OwnedDecision] = [
                prepared[i] for i in indices[offset : offset + batch_size]
            ]
            updated = step(current, gradient(current, batch, settings), settings)
            if not isinstance(updated.model, CombatIntentModel):
                raise ValueError("A PPO step dropped its public input contract")
            current = CombatIntentState(updated.model, updated.actor_adam, None, updated.value_adam)
            work["optimizer_updates"] += 1
            if control_steps is not None and work["optimizer_updates"] >= control_steps:
                work["stop_reason"] = "short_control_step_limit"
                break
        work["epochs_completed"] = epoch
        if work["stop_reason"] == "short_control_step_limit":
            break
        kl = math.fsum(
            len(batch) * gradient(current, batch, settings).kl / len(prepared)
            for offset in range(0, len(prepared), batch_size)
            if (batch := prepared[offset : offset + batch_size])
        )
        work["joint_behavior_kl"] = kl
        if kl > settings["target_kl"]:
            work["stop_reason"] = "behavior_kl_limit"
            break
    updates = work["optimizer_updates"]
    if (
        current.actor_adam.steps - state.actor_adam.steps != updates
        or current.value_adam.steps - state.value_adam.steps != updates
    ):
        raise ValueError("Actor and critic did not receive their exact declared PPO work")
    work["game_partitions"] = dict(Counter(row["task"]["partition"] for _, row in games))
    return current, work
