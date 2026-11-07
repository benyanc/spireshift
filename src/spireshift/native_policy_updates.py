"""Qualify the existing PPO actor loss; never regress action logits onto returns."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, fit_round, log_softmax, loss_gradient
from spireshift.native_context_cache import CachedContextModel

SETTINGS = {
    "actor_learning_rate": 0.001,
    "clip": 0.2,
    "entropy_coefficient": 0.015,
    "epochs": 3,
    "gradient_clip": 1.0,
    "minibatch_decisions": 128,
    "target_kl": 0.03,
    "temperature": 0.8,
    "value_coefficient": 0.5,
    "value_learning_rate": 0.003,
}


def gradient(
    model: Any, samples: list[Sample], *, entropy: float = 0, value: float = 0
) -> tuple[float, tuple[float, ...], dict[str, float]]:
    return loss_gradient(
        model,
        samples,
        clip=SETTINGS["clip"],
        entropy_coefficient=entropy,
        value_coefficient=value,
        temperature=SETTINGS["temperature"],
    )


def qualify(model: CachedContextModel, adam: Adam) -> dict[str, Any]:
    """Hypothetical numerical checks only; no saved player/Adam is advanced."""
    before = manifest_identifier({"model": model.as_dict(), "Adam": adam.as_dict()})
    rows = ({0: 1.0, 1: 1.0}, {0: 1.0, 2: 1.0}, {0: 1.0, 3: 1.0})
    temperature = SETTINGS["temperature"]
    logs = log_softmax(score_features(cast(Any, model.actor), rows), temperature)
    sample = Sample(rows, (1.0, *([0.0] * (len(model.value_weights) - 1))), 0, logs[0], 0.2, 1)
    checks: dict[str, bool] = {}
    directions = {}
    for sign in (1, -1):
        s = replace(sample, advantage=sign)
        _, g, _ = gradient(model, [s])
        scale = 1e-4 / max(1, math.sqrt(math.fsum(v * v for v in g)))
        trial = model.with_weights(
            tuple(w - scale * v for w, v in zip(model.weights(), g, strict=True))
        )
        after = log_softmax(score_features(cast(Any, trial.actor), rows), temperature)[0]
        checks[f"advantage_{sign}_moves_log_probability_in_expected_direction"] = (
            sign * (after - logs[0]) > 0
        )
        directions[str(sign)] = after - logs[0]
    actor_size = model.actor.parameter_count
    a = gradient(model, [replace(sample, target=0)], value=0.5)[1]
    b = gradient(model, [replace(sample, target=1)], value=0.5)[1]
    checks["outcome_target_cannot_change_actor_gradient_when_advantage_fixed"] = (
        a[:actor_size] == b[:actor_size]
    )
    g = gradient(model, [replace(sample, advantage=0, target=1)], value=0.5)[1]
    checks["prediction_loss_has_zero_actor_gradient"] = all(v == 0 for v in g[:actor_size])
    for sign, ratio in ((1, 1.5), (-1, 0.5)):
        clipped = replace(sample, advantage=sign, old_log_probability=logs[0] - math.log(ratio))
        _, g, d = gradient(model, [clipped])
        checks[f"clipped_{sign}_branch_has_zero_policy_gradient"] = (
            all(v == 0 for v in g) and d["clipped_fraction"] == 1
        )
    shifted = log_softmax(
        [v + 13 for v in score_features(cast(Any, model.actor), rows)], temperature
    )
    checks["common_score_shift_preserves_probabilities"] = all(
        math.isclose(a, b, abs_tol=1e-12, rel_tol=0) for a, b in zip(logs, shifted, strict=True)
    )
    permutation = replace(sample, rows=rows[::-1], action=2)
    checks["candidate_permutation_preserves_actor_gradient"] = all(
        math.isclose(a, b, abs_tol=1e-12, rel_tol=0)
        for a, b in zip(
            gradient(model, [sample])[1], gradient(model, [permutation])[1], strict=True
        )
    )
    loss_args = {"entropy": 0.015, "value": 0.5}
    _, analytic, _ = gradient(model, [sample], **loss_args)
    n, h = model.actor.dimension, model.actor.hidden_units
    coordinates = (1, n + 2, n * h, n * h + h, actor_size - 1, actor_size)
    errors = []
    for i in coordinates:
        plus, minus = list(model.weights()), list(model.weights())
        plus[i] += 1e-5
        minus[i] -= 1e-5
        numeric = (
            gradient(model.with_weights(plus), [sample], **loss_args)[0]
            - gradient(model.with_weights(minus), [sample], **loss_args)[0]
        ) / 2e-5
        errors.append(abs(numeric - analytic[i]))
    checks["actor_and_critic_derivatives_match_finite_differences"] = max(errors) < 1e-7
    _, g, _ = gradient(model, [sample], **loss_args)
    _, continued, norm = adam.update(
        cast(Any, model), g, actor_rate=0, value_rate=0, maximum_norm=1
    )
    factor = min(1.0, 1.0 / max(norm, 1e-12))
    checks["copied_Adam_continues_all_prior_moments_and_counter"] = (
        continued.steps == adam.steps + 1
        and all(
            math.isclose(v, 0.9 * old + 0.1 * new * factor, abs_tol=1e-12, rel_tol=0)
            for v, old, new in zip(continued.first, adam.first, g, strict=True)
        )
        and all(
            math.isclose(v, 0.999 * old + 0.001 * (new * factor) ** 2, abs_tol=1e-12, rel_tol=0)
            for v, old, new in zip(continued.second, adam.second, g, strict=True)
        )
    )
    skipped_model, skipped_adam, work = update(model, adam, [replace(sample, advantage=0)], 0)
    checks["no_policy_signal_skips_warm_Adam_instead_of_momentum_only_drift"] = (
        skipped_model is model and skipped_adam is adam and work["optimizer_steps"] == 0
    )
    checks["full_original_model_and_Adam_unchanged"] = before == manifest_identifier(
        {"model": model.as_dict(), "Adam": adam.as_dict()}
    )
    result = {
        "checks": checks,
        "passed": all(checks.values()),
        "signed_log_probability_changes": directions,
        "maximum_derivative_absolute_error": max(errors),
        "original_model_id": model.model_id,
        "original_Adam_steps": adam.steps,
        "production_optimizer_updates": 0,
        "synthetic_advantages_are_not_gameplay_evidence": True,
        "prediction_only_fits_must_use_their_own_optimizer_not_warm_PPO_Adam": True,
    }
    if not result["passed"]:
        raise ValueError(f"PPO policy-update qualification failed: {checks}")
    return result


def update(
    model: CachedContextModel, adam: Adam, samples: list[Sample], shuffle_seed: int
) -> tuple[CachedContextModel, Adam, dict[str, Any]]:
    if not samples or any(not math.isfinite(s.advantage) for s in samples):
        raise ValueError("Policy learning requires finite qualified on-policy advantages")
    advantages = [s.advantage for s in samples]
    mean = math.fsum(advantages) / len(advantages)
    variance = math.fsum((a - mean) ** 2 for a in advantages) / len(advantages)
    if variance <= 1e-16:
        return (
            model,
            adam,
            {
                "optimizer_steps": 0,
                "sampled_decisions": len(samples),
                "stop_reason": "no_centered_policy_credit_skip_entire_update",
                "original_Adam_moments_and_steps_retained": True,
            },
        )
    result, optimizer, work = fit_round(
        cast(Any, model), adam, samples, dict(SETTINGS), shuffle_seed
    )
    if not isinstance(result, CachedContextModel):
        raise ValueError("PPO update lost the identity-compatible public policy")
    return (
        result,
        optimizer,
        {
            **work,
            "actor_loss": "clipped_on_policy_log_probability_ratio_times_advantage",
            "actor_scores_regressed_onto_return_labels": False,
            "outcome_critic_owns_separate_parameters": True,
            "independent_action_conditional_predictor_used_as_baseline": False,
        },
    )
