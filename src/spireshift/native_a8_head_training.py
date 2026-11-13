"""Matched PPO updates over model-owned, verified native decisions."""

from __future__ import annotations

import math
import random
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from spireshift.engine_neural import NativeActorCritic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import ARMS, HeadState, OwnedDecision, owned_decisions
from spireshift.native_a8_own_experience import samples
from spireshift.native_a8_own_ppo import Decision, loss_gradient
from spireshift.native_value_credit import ValueRun, cross_fitted_predictions
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec


@dataclass(frozen=True, slots=True)
class ParameterBlock:
    """Use the existing Adam kernel for an independent actor or critic block."""

    values: tuple[float, ...]

    @property
    def parameter_count(self) -> int:
        return len(self.values)

    @property
    def actor(self) -> ParameterBlock:
        return self

    def weights(self) -> tuple[float, ...]:
        return self.values

    def with_weights(self, values: tuple[float, ...]) -> ParameterBlock:
        return ParameterBlock(values)


@dataclass(frozen=True, slots=True)
class Gradient:
    actor: tuple[float, ...] | None
    combat: tuple[float, ...] | None
    value: tuple[float, ...]
    kl: float


def gradient(
    state: HeadState, examples: Sequence[OwnedDecision], settings: dict[str, Any]
) -> Gradient:
    if not examples:
        raise ValueError("Require a nonempty verified PPO minibatch")
    split = state.model.combat_actor is not None
    groups: dict[bool, list[Decision]] = {False: [], True: []}
    for sample in examples:
        groups[split and sample.combat].append(sample.decision)
    actor_gradients: dict[bool, tuple[float, ...]] = {}
    value = _numpy().zeros(len(state.model.value_weights))
    kl = 0.0
    for combat, decisions in groups.items():
        if not decisions:
            continue
        view = state.model.view(combat)
        _, raw, stats = loss_gradient(view, decisions, settings)
        n = view.actor.parameter_count
        weight = len(decisions) / len(examples)
        actor_gradients[combat] = tuple(g * weight for g in raw[:n])
        value += _numpy().asarray(raw[n:]) * weight
        kl += stats["approximate_joint_kl"] * weight
    return Gradient(
        actor_gradients.get(False), actor_gradients.get(True), tuple(map(float, value)), kl
    )


def step(state: HeadState, grads: Gradient, settings: dict[str, Any]) -> HeadState:
    limit = settings["gradient_clip"]
    parts = (grads.actor or (), grads.combat or (), grads.value)
    norm = math.sqrt(math.fsum(g * g for part in parts for g in part))
    scale = min(1.0, limit / max(norm, 1e-12))

    def apply(
        values: tuple[float, ...], adam: Adam, g: tuple[float, ...], rate: float
    ) -> tuple[tuple[float, ...], Adam]:
        new, next_adam, _ = adam.update(
            cast(Any, ParameterBlock(values)),
            tuple(v * scale for v in g),
            actor_rate=rate,
            value_rate=rate,
            maximum_norm=limit,
        )
        return cast(ParameterBlock, new).values, next_adam

    model = state.model
    actor, combat = model.actor, model.combat_actor
    actor_adam, combat_adam = state.actor_adam, state.combat_adam
    if grads.actor is not None:
        weights, actor_adam = apply(
            actor.genome, actor_adam, grads.actor, settings["actor_learning_rate"]
        )
        actor = actor.with_genome(weights)
    if grads.combat is not None:
        if combat is None or combat_adam is None:
            raise ValueError("A shared actor cannot receive a separate combat gradient")
        weights, combat_adam = apply(
            combat.genome, combat_adam, grads.combat, settings["actor_learning_rate"]
        )
        combat = combat.with_genome(weights)
    weights, value_adam = apply(
        model.value_weights, state.value_adam, grads.value, settings["value_learning_rate"]
    )
    return HeadState(
        replace(model, native=NativeActorCritic(actor, weights), combat_actor=combat),
        actor_adam,
        combat_adam,
        value_adam,
    )


def training_examples(
    games: list[tuple[Path, dict[str, Any]]],
    state: HeadState,
    score: TrainingScoreSpec,
    credit: dict[str, Any],
    round_index: int,
) -> tuple[list[OwnedDecision], dict[str, Any]]:
    grouped: dict[int, list[OwnedDecision]] = {}
    runs: list[ValueRun] = []
    families: Counter[str] = Counter()
    for directory, game in games:
        decisions, run, counts = samples(
            directory, game, state.model, score, game["task"]["partition"], round_index
        )
        if run.seed in grouped:
            raise ValueError("A world may enter its on-policy batch once")
        grouped[run.seed] = list(owned_decisions(directory, state.model, decisions))
        families.update(counts)
        runs.append(run)
    predictions, _ = cross_fitted_predictions(
        runs,
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    result = [
        replace(example, decision=replace(example.decision, advantage=run.target - estimate))
        for run in runs
        for example, estimate in zip(grouped[run.seed], predictions[run.seed], strict=True)
    ]
    return result, {
        "native_families": dict(families),
        "returns_by_seed_id": {str(run.seed): run.target for run in runs},
        "candidate_decisions": len(result),
        "compound_decisions": sum(len(sample.decision.factors) > 1 for sample in result),
    }


def matched_update(
    states: dict[str, HeadState],
    examples: dict[str, list[OwnedDecision]],
    settings: dict[str, Any],
    shuffle_seed: int,
    *,
    deadline: float = math.inf,
) -> tuple[dict[str, HeadState], dict[str, Any]]:
    if set(states) != set(ARMS) or set(examples) != set(ARMS):
        raise ValueError("Require a complete matched pair of PPO cohorts")
    count = min(len(examples[arm]) for arm in ARMS)
    if not count:
        raise ValueError("Both arms require verified native decisions")
    minibatch = settings["minibatch_decisions"]
    prepared: dict[str, list[OwnedDecision]] = {}
    raw_std, used = {}, {}
    for arm in ARMS:
        # Same deterministic budget in both arms. Every paired terminal game
        # informed credit before the larger action stream is subsampled.
        indices = random.Random(shuffle_seed).sample(range(len(examples[arm])), count)
        batch = [examples[arm][i] for i in indices]
        advantages = [sample.decision.advantage for sample in batch]
        mean = math.fsum(advantages) / count
        std = math.sqrt(math.fsum((a - mean) ** 2 for a in advantages) / count)
        if not math.isfinite(std):
            raise ValueError("Require finite on-policy advantages")
        raw_std[arm] = std
        used[arm] = {
            "combat": sum(sample.combat for sample in batch),
            "strategy": sum(not sample.combat for sample in batch),
        }
        prepared[arm] = [
            replace(
                sample,
                decision=replace(
                    sample.decision, advantage=(sample.decision.advantage - mean) / max(std, 1e-8)
                ),
            )
            for sample in batch
        ]
    work: dict[str, Any] = {
        "selected_decisions_per_arm": count,
        "selected_decisions_by_owner": used,
        "raw_advantage_std": raw_std,
        "optimizer_steps_per_arm": 0,
        "epochs_completed": 0,
        "joint_kl": None,
        "stop_reason": "matched_no_centered_policy_credit",
    }
    if min(raw_std.values()) <= 1e-8:
        return states, work

    current = states.copy()
    rng = random.Random(shuffle_seed + 1)
    indices = list(range(count))
    for epoch in range(1, settings["epochs"] + 1):
        rng.shuffle(indices)
        for offset in range(0, count, minibatch):
            if time.monotonic() >= deadline:
                raise TimeoutError("Preserve a fit that reaches the session deadline")
            window = indices[offset : offset + minibatch]
            for arm in ARMS:
                batch = [prepared[arm][i] for i in window]
                current[arm] = step(current[arm], gradient(current[arm], batch, settings), settings)
            work["optimizer_steps_per_arm"] += 1
        kl = {}
        for arm in ARMS:
            kl[arm] = math.fsum(
                len(batch) * gradient(current[arm], batch, settings).kl / count
                for offset in range(0, count, minibatch)
                if (batch := prepared[arm][offset : offset + minibatch])
            )
        work.update(epochs_completed=epoch, joint_kl=kl, stop_reason="epoch_limit")
        if max(kl.values()) > settings["target_kl"]:
            work["stop_reason"] = "matched_round_behavior_kl_limit"
            break
    if any(
        current[arm].value_adam.steps - states[arm].value_adam.steps
        != work["optimizer_steps_per_arm"]
        for arm in ARMS
    ):
        raise ValueError("Both arms must receive the same number of PPO minibatch updates")
    return current, work
