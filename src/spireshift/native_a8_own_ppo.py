"""PPO on delivered native decisions, including one ratio per ordered answer."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

from spireshift.full_run_policy import score_features, score_gradient
from spireshift.full_run_ppo_math import Adam, log_softmax, sigmoid
from spireshift.native_context_cache import CachedContextModel
from spireshift.neural_combat import _numpy


@dataclass(frozen=True, slots=True)
class Factor:
    rows: tuple[dict[int, float], ...]
    action: int


@dataclass(frozen=True, slots=True)
class Decision:
    factors: tuple[Factor, ...]
    state: tuple[float, ...]
    old_log_probability: float
    target: float
    advantage: float


def loss_gradient(
    model: CachedContextModel, decisions: Sequence[Decision], settings: dict[str, Any]
) -> tuple[float, tuple[float, ...], dict[str, float]]:
    np = _numpy()
    count = len(decisions)
    if not count:
        raise ValueError("PPO requires a nonempty minibatch")
    clip, temperature = settings["clip"], settings["temperature"]
    entropy_rate, value_rate = settings["entropy_coefficient"], settings["value_coefficient"]
    actor = cast(Any, model.actor)
    rows = tuple(
        row for decision in decisions for factor in decision.factors for row in factor.rows
    )
    logits = score_features(actor, rows)
    dz = np.zeros(len(rows), dtype=np.float64)
    policy_loss = entropy = kl = clipped = 0.0
    offset = 0
    for decision in decisions:
        if (
            not decision.factors
            or not math.isfinite(decision.old_log_probability)
            or decision.old_log_probability > 0
            or not math.isfinite(decision.advantage)
            or not 0 <= decision.target <= 1
        ):
            raise ValueError("Invalid on-policy native decision")
        conditional = []
        for factor in decision.factors:
            if not 0 <= factor.action < len(factor.rows):
                raise ValueError("Action is outside its conditional menu")
            end = offset + len(factor.rows)
            logs = log_softmax(logits[offset:end], temperature)
            conditional.append((slice(offset, end), factor.action, logs))
            offset = end

        # Prefix decisions are conditional probabilities inside one native action.
        log_ratio = math.fsum(logs[action] for _, action, logs in conditional)
        log_ratio -= decision.old_log_probability
        ratio = math.exp(log_ratio)
        bounded = min(1 + clip, max(1 - clip, ratio))
        advantage = decision.advantage
        policy_loss -= min(ratio * advantage, bounded * advantage)
        active = not ((advantage > 0 and ratio > 1 + clip) or (advantage < 0 and ratio < 1 - clip))
        scale = -advantage * ratio if active else 0.0
        kl += math.expm1(log_ratio) - log_ratio
        clipped += float(not active)

        # Average conditional entropy on the sampled prefixes. The policy ratio
        # and critic each get one term regardless of the number of factors.
        weight = 1.0 / len(conditional)
        for positions, action, logs in conditional:
            logp = np.asarray(logs)
            p = np.exp(logp)
            h = -float(p @ logp)
            gradient = -scale * p
            gradient[action] += scale
            gradient += entropy_rate * weight * p * (logp + h)
            dz[positions] = gradient / temperature / count
            entropy += weight * h

    states = np.asarray([d.state for d in decisions], dtype=np.float64)
    if states.shape != (count, len(model.value_weights)) or not np.isfinite(states).all():
        raise ValueError("Invalid public value features")
    values = sigmoid(states @ np.asarray(model.value_weights))
    difference = values - np.asarray([d.target for d in decisions])
    value_loss = float(np.mean(difference**2)) / 2
    dv = value_rate * (difference * values * (1 - values)) @ states / count
    gradient_values = (*score_gradient(actor, rows, dz), *(float(v) for v in dv))
    loss = (policy_loss - entropy_rate * entropy) / count + value_rate * value_loss
    if not math.isfinite(loss) or not all(math.isfinite(v) for v in gradient_values):
        raise ValueError("Nonfinite native PPO update")
    return (
        loss,
        gradient_values,
        {
            "policy_loss": policy_loss / count,
            "value_loss": value_loss,
            "conditional_entropy": entropy / count,
            "approximate_joint_kl": kl / count,
            "clipped_fraction": clipped / count,
        },
    )


def update(
    model: CachedContextModel,
    adam: Adam,
    decisions: list[Decision],
    settings: dict[str, Any],
    shuffle_seed: int,
) -> tuple[CachedContextModel, Adam, dict[str, Any]]:
    if not decisions or any(not math.isfinite(d.advantage) for d in decisions):
        raise ValueError("Training requires finite verified whole-run advantages")
    mean = math.fsum(d.advantage for d in decisions) / len(decisions)
    std = math.sqrt(math.fsum((d.advantage - mean) ** 2 for d in decisions) / len(decisions))
    if std <= 1e-8:
        return model, adam, {"optimizer_steps": 0, "stop_reason": "no_centered_policy_credit"}
    prepared = [replace(d, advantage=(d.advantage - mean) / std) for d in decisions]
    initial_steps, minibatch = adam.steps, settings["minibatch_decisions"]
    rng = random.Random(shuffle_seed)
    slices = range(0, len(prepared), minibatch)
    reason = "epoch_limit"
    kl = 0.0
    epochs = 0
    for _ in range(settings["epochs"]):
        rng.shuffle(prepared)
        for start in slices:
            _, gradient, _ = loss_gradient(model, prepared[start : start + minibatch], settings)
            updated, adam, _ = adam.update(
                cast(Any, model),
                gradient,
                actor_rate=settings["actor_learning_rate"],
                value_rate=settings["value_learning_rate"],
                maximum_norm=settings["gradient_clip"],
            )
            if not isinstance(updated, CachedContextModel):
                raise ValueError("PPO update lost the identity-compatible public model")
            model = updated
        epoch_kl = []
        for start in slices:
            batch = prepared[start : start + minibatch]
            _, _, diagnostic = loss_gradient(model, batch, settings)
            epoch_kl.append(len(batch) * diagnostic["approximate_joint_kl"])
        kl = math.fsum(epoch_kl) / len(prepared)
        epochs += 1
        if kl > settings["target_kl"]:
            reason = "round_behavior_kl_limit"
            break
    return (
        model,
        adam,
        {
            "optimizer_steps": adam.steps - initial_steps,
            "epochs_completed": epochs,
            "stop_reason": reason,
            "raw_advantage_mean": mean,
            "raw_advantage_std": std,
            "final_behavior_joint_kl": kl,
        },
    )
