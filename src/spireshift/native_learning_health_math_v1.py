"""Measure existing learner inputs and updates without creating gameplay labels."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import dense_features, score_features
from spireshift.full_run_ppo_math import Adam, log_softmax
from spireshift.native_a8_head_policy import HeadState, OwnedDecision
from spireshift.native_a8_head_training import gradient, step
from spireshift.native_a8_own_ppo import loss_gradient
from spireshift.neural_combat import _numpy


def explained_variance(targets: list[float], predictions: list[float]) -> float | None:
    np = _numpy()
    if len(targets) != len(predictions) or not targets:
        raise ValueError("Require aligned nonempty target and prediction vectors")
    y, p = np.asarray(targets), np.asarray(predictions)
    if not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError("Require finite learner diagnostics")
    variance = float(np.var(y))
    return None if variance <= 1e-16 else 1.0 - float(np.var(y - p)) / variance


def geometry(state: HeadState, examples: list[OwnedDecision], temperature: float) -> dict[str, Any]:
    np = _numpy()
    actor = state.model.actor
    w, b, _, _ = actor.unpack()
    saturation = ranges = entropy = relative_difference = 0.0
    decisions = factors = 0
    for example in examples:
        if not example.decision.factors:
            raise ValueError("A native decision has no policy factors")
        values = []
        for factor in example.decision.factors:
            x = dense_features(factor.rows, actor.dimension)
            h = np.tanh(x @ w.T + b)
            logs = np.asarray(
                log_softmax(score_features(cast(Any, actor), factor.rows), temperature)
            )
            p = np.exp(logs)
            centered = x - np.mean(x, axis=0)
            values.append(
                (
                    float(np.mean(np.abs(h) > 0.95)),
                    float(np.mean(np.ptp(h, axis=0))),
                    -float(p @ logs) / math.log(len(p)) if len(p) > 1 else 0.0,
                    float(np.linalg.norm(centered)) / max(1e-12, float(np.linalg.norm(x))),
                )
            )
            factors += 1
        # Each delivered native decision has weight one, including compound answers.
        averages = [math.fsum(v[i] for v in values) / len(values) for i in range(4)]
        saturation += averages[0]
        ranges += averages[1]
        entropy += averages[2]
        relative_difference += averages[3]
        decisions += 1
    if not decisions:
        raise ValueError("Require sampled native decisions for model geometry")
    return {
        "native_decisions": decisions,
        "policy_factors": factors,
        "hidden_units": actor.hidden_units,
        "input_dimensions": actor.dimension,
        "mean_hidden_saturation_above_abs_0_95": saturation / decisions,
        "mean_hidden_range_across_legal_actions": ranges / decisions,
        "mean_entropy_fraction_of_uniform": entropy / decisions,
        "mean_action_varying_input_fraction": relative_difference / decisions,
    }


def kernel_probe(
    state: HeadState, example: OwnedDecision, settings: dict[str, Any]
) -> dict[str, Any]:
    """Synthetic advantage signs check mathematics, never teach an action preference."""
    np = _numpy()
    before = manifest_identifier(state.document())
    isolated = {**settings, "entropy_coefficient": 0.0, "value_coefficient": 0.0}
    rows = example.decision.factors
    if not any(len(f.rows) > 1 for f in rows):
        raise ValueError("Gradient direction needs at least two legal alternatives")
    signs = {}
    finite_errors = []
    for sign in (1.0, -1.0):
        sample = replace(example.decision, advantage=sign)
        _, g, _ = loss_gradient(state.model, [sample], isolated)
        norm = math.sqrt(math.fsum(v * v for v in g))
        if norm <= 1e-12:
            return {"responsive": False, "gradient_norm": norm, "source_unchanged": True}
        direction = tuple(v / norm for v in g)
        weights = state.model.weights()
        epsilon = 1e-5
        plus = state.model.with_weights(
            tuple(w + epsilon * d for w, d in zip(weights, direction, strict=True))
        )
        minus = state.model.with_weights(
            tuple(w - epsilon * d for w, d in zip(weights, direction, strict=True))
        )
        hi = loss_gradient(cast(Any, plus), [sample], isolated)[0]
        lo = loss_gradient(cast(Any, minus), [sample], isolated)[0]
        finite_errors.append(abs((hi - lo) / (2 * epsilon) - norm) / max(1.0, norm))

        def log_probability(model: Any) -> float:
            return math.fsum(
                log_softmax(score_features(model.actor, f.rows), settings["temperature"])[f.action]
                for f in rows
            )

        change = log_probability(minus) - log_probability(state.model)
        signs[str(int(sign))] = {
            "selected_log_probability_change": change,
            "correct_direction": sign * change > 0,
        }
    if manifest_identifier(state.document()) != before:
        raise ValueError("A numerical probe changed the source state or Adam")
    if not np.isfinite(finite_errors).all():
        raise ValueError("Nonfinite finite-difference probe")
    return {
        "responsive": True,
        "maximum_relative_directional_error": max(finite_errors),
        "advantage_signs": signs,
        "source_unchanged": True,
        "synthetic_advantages_used_as_training_labels": False,
    }


def optimizer_probes(
    state: HeadState, batch: list[OwnedDecision], settings: dict[str, Any]
) -> dict[str, Any]:
    """Compare one disposable warm/reset Adam step on an identical saved minibatch."""
    before = manifest_identifier(state.document())
    original = state.model
    decisions = [row.decision for row in batch]
    initial_loss, _, initial_stats = loss_gradient(original, decisions, settings)
    grads = gradient(state, batch, settings)
    policy_grads = gradient(
        state, batch, {**settings, "entropy_coefficient": 0.0, "value_coefficient": 0.0}
    )
    policy_norm = math.sqrt(math.fsum(v * v for v in (policy_grads.actor or ())))
    entropy_norm = math.sqrt(
        math.fsum(
            (a - b) ** 2 for a, b in zip(grads.actor or (), policy_grads.actor or (), strict=True)
        )
    )
    zero_actor = (0.0,) * original.actor.parameter_count
    zero_value = (0.0,) * len(original.value_weights)
    reset = replace(
        state,
        actor_adam=Adam(0, zero_actor, zero_actor),
        value_adam=Adam(0, zero_value, zero_value),
    )
    results = {}
    for name, source in (("inherited_Adam", state), ("reset_Adam", reset)):
        updated = step(source, grads, settings)
        after, _, stats = loss_gradient(updated.model, decisions, settings)
        if (
            updated.actor_adam.steps != source.actor_adam.steps + 1
            or updated.value_adam.steps != source.value_adam.steps + 1
        ):
            raise ValueError("A disposable probe advanced the wrong optimizer clocks")
        results[name] = {
            "loss_change": after - initial_loss,
            "policy_loss_change": stats["policy_loss"] - initial_stats["policy_loss"],
            "value_loss_change": stats["value_loss"] - initial_stats["value_loss"],
            "joint_behavior_kl": stats["approximate_joint_kl"],
            "clipped_fraction": stats["clipped_fraction"],
            "copy_updates": 1,
        }
    if manifest_identifier(state.document()) != before:
        raise ValueError("A disposable Adam probe changed the source model or optimizer")
    return {
        "batch_native_decisions": len(batch),
        "policy_gradient_norm": policy_norm,
        "entropy_gradient_norm": entropy_norm,
        "one_step_probes": results,
        "source_unchanged": True,
        "checkpoints_saved": 0,
        "strength_improvement_established": False,
    }
