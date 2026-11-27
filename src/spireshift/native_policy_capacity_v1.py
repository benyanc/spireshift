"""Add scoring units while preserving initial choices and all inherited Adam entries."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import replace

from spireshift.engine_neural import NativeActor, NativeActorCritic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_combat_intent_model import CombatIntentModel, CombatIntentState


def retained(values: Sequence[float], dimension: int, before: int, after: int) -> tuple[float, ...]:
    if not 0 < before < after or len(values) != dimension * after + 2 * after + dimension:
        raise ValueError("The wider actor/Adam layout differs")
    n = dimension * after
    return (
        *values[: dimension * before],
        *values[n : n + before],
        *values[n + after : n + after + before],
        *values[n + 2 * after :],
    )


def expand(state: HeadState, hidden_units: int, seed: int) -> CombatIntentState:
    model, actor = state.model, state.model.actor
    if not isinstance(model, CombatIntentModel) or model.arm != "shared":
        raise ValueError("Expand only the qualified single-head model on a new copy")
    before, dimension = actor.hidden_units, actor.dimension
    if not before < hidden_units <= 128:
        raise ValueError("Choose a strictly wider supported actor")
    extra = hidden_units - before
    rng = random.Random(seed)
    scale = math.sqrt(6 / (dimension + hidden_units))

    def layout(values: Sequence[float], new_inputs: Sequence[float]) -> tuple[float, ...]:
        n = dimension * before
        if len(values) != actor.parameter_count or len(new_inputs) != dimension * extra:
            raise ValueError("The source actor or complete Adam layout differs")
        return (
            *values[:n],
            *new_inputs,
            *values[n : n + before],
            *([0.0] * extra),
            *values[n + before : n + 2 * before],
            *([0.0] * extra),
            *values[n + 2 * before :],
        )

    # New hidden features can learn immediately through their output weights.
    # Their initial zero output coefficients preserve the entire old policy.
    genome = layout(actor.genome, [rng.uniform(-scale, scale) for _ in range(dimension * extra)])
    wider = NativeActor(
        actor.environment_id, dimension, hidden_units, genome, actor.input_normalization
    )
    adam = Adam(
        state.actor_adam.steps,
        layout(state.actor_adam.first, [0.0] * (dimension * extra)),
        layout(state.actor_adam.second, [0.0] * (dimension * extra)),
    )
    for original, changed in (
        (actor.genome, wider.genome),
        (state.actor_adam.first, adam.first),
        (state.actor_adam.second, adam.second),
    ):
        if retained(changed, dimension, before, hidden_units) != tuple(original):
            raise ValueError("An inherited weight or complete Adam moment changed")
    updated = replace(model, native=NativeActorCritic(wider, model.value_weights))
    return CombatIntentState(updated, adam, None, state.value_adam)
