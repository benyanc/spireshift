"""Differentiate the actual mixed behavior, including its PPO ratio and entropy.

At epsilon=0 this calls the original numerical kernel exactly. The 20% rest-only
arm uses q(a|s)=(1-epsilon)*pi(a|s)+epsilon/N, not off-policy softmax labels.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from spireshift.full_run_policy import dense_features, score_gradient
from spireshift.full_run_ppo_math import ActorCritic, Adam, log_softmax, sigmoid
from spireshift.full_run_ppo_math import loss_gradient as original_gradient
from spireshift.native_rest_exploration import Sample, mixed_logs
from spireshift.neural_combat import _numpy


def loss_gradient(
    model: ActorCritic,
    samples: Sequence[Sample],
    *,
    clip: float,
    entropy_coefficient: float,
    value_coefficient: float,
    temperature: float,
) -> tuple[float, tuple[float, ...], dict[str, float]]:
    if not samples:
        raise ValueError("PPO cannot optimize an empty minibatch")
    if all(s.epsilon == 0 for s in samples):
        return original_gradient(
            model,
            samples,
            clip=clip,
            entropy_coefficient=entropy_coefficient,
            value_coefficient=value_coefficient,
            temperature=temperature,
        )
    np = _numpy()
    rows = tuple(row for s in samples for row in s.rows)
    x = dense_features(rows, model.actor.dimension)
    w, b, out, linear = model.actor.unpack()
    logits = np.tanh(x @ w.T + b) @ out + x @ linear
    dz = np.zeros(len(rows), dtype=np.float64)
    policy_loss = entropy = kl = clipped = 0.0
    offset = 0
    for s in samples:
        if (
            not 0 <= s.action < len(s.rows)
            or not all(math.isfinite(v) for v in (s.old_log_probability, s.target, s.advantage))
            or not 0 <= s.target <= 1
        ):
            raise ValueError("Invalid mixed on-policy sample")
        pi_logs = log_softmax(logits[offset : offset + len(s.rows)], temperature)
        logp = np.asarray(mixed_logs(pi_logs, s.epsilon))
        pi = np.exp(pi_logs)
        q = np.exp(logp)
        log_ratio = float(logp[s.action]) - s.old_log_probability
        ratio = math.exp(log_ratio)
        bounded = min(1 + clip, max(1 - clip, ratio))
        policy_loss -= min(ratio * s.advantage, bounded * s.advantage)
        active = not (s.advantage > 0 and ratio > 1 + clip or s.advantage < 0 and ratio < 1 - clip)
        onehot = np.zeros(len(pi))
        onehot[s.action] = 1
        responsibility = (1 - s.epsilon) * pi[s.action] / q[s.action]
        gradient = (
            -s.advantage * ratio * responsibility * (onehot - pi) if active else np.zeros(len(pi))
        )
        gradient += entropy_coefficient * (1 - s.epsilon) * pi * (logp - float(pi @ logp))
        dz[offset : offset + len(pi)] = gradient / temperature / len(samples)
        entropy -= float(q @ logp)
        kl += ratio - 1 - log_ratio
        clipped += float(not active)
        offset += len(pi)
    states = np.asarray([s.state for s in samples], dtype=np.float64)
    if states.shape != (len(samples), len(model.value_weights)) or not np.isfinite(states).all():
        raise ValueError("Invalid public value features")
    values = sigmoid(states @ np.asarray(model.value_weights))
    difference = values - np.asarray([s.target for s in samples])
    value_loss = float(np.mean(difference * difference)) / 2
    dv = value_coefficient * (difference * values * (1 - values)) @ states / len(samples)
    gradient = (*score_gradient(model.actor, rows, dz), *(float(v) for v in dv))
    total_loss = (policy_loss - entropy_coefficient * entropy) / len(
        samples
    ) + value_coefficient * value_loss
    if not math.isfinite(total_loss) or not all(math.isfinite(v) for v in gradient):
        raise ValueError("Nonfinite mixed PPO loss or gradient")
    return (
        total_loss,
        gradient,
        {
            "policy_loss": policy_loss / len(samples),
            "value_loss": value_loss,
            "entropy": entropy / len(samples),
            "approximate_kl": kl / len(samples),
            "clipped_fraction": clipped / len(samples),
        },
    )


def fit_round(
    model: ActorCritic,
    optimizer: Adam,
    samples: Sequence[Sample],
    settings: dict[str, Any],
    shuffle_seed: int,
) -> tuple[ActorCritic, Adam, dict[str, Any]]:
    """One finite update from exactly one behavior checkpoint; no environment calls."""
    np = _numpy()
    if not samples:
        raise ValueError("No sampled decisions available for PPO")
    advantages = np.asarray([s.advantage for s in samples])
    mean, std = float(advantages.mean()), float(advantages.std())
    normalized = (advantages - mean) / max(std, 1e-8)
    prepared = [replace(s, advantage=float(a)) for s, a in zip(samples, normalized, strict=True)]
    indices = list(range(len(samples)))
    rng = random.Random(shuffle_seed)
    initial_steps, stats, epochs, stop = optimizer.steps, [], 0, "epoch_limit"
    for _ in range(settings["epochs"]):
        rng.shuffle(indices)
        for start in range(0, len(indices), settings["minibatch_decisions"]):
            batch = [prepared[i] for i in indices[start : start + settings["minibatch_decisions"]]]
            loss, gradient, diagnostic = loss_gradient(
                model,
                batch,
                clip=settings["clip"],
                entropy_coefficient=settings["entropy_coefficient"],
                value_coefficient=settings["value_coefficient"],
                temperature=settings["temperature"],
            )
            model, optimizer, norm = optimizer.update(
                model,
                gradient,
                actor_rate=settings["actor_learning_rate"],
                value_rate=settings["value_learning_rate"],
                maximum_norm=settings["gradient_clip"],
            )
            stats.append({**diagnostic, "loss": loss, "gradient_norm": norm})
        epochs += 1
        # Only constrain one reuse of this round's experience. The next round
        # collects fresh behavior, allowing arbitrarily large cumulative change.
        # Bound memory even if some runs approach the full decision cap.
        final_kl = 0.0
        for start in range(0, len(prepared), settings["minibatch_decisions"]):
            check = prepared[start : start + settings["minibatch_decisions"]]
            _, _, diagnostic = loss_gradient(
                model,
                check,
                clip=settings["clip"],
                entropy_coefficient=settings["entropy_coefficient"],
                value_coefficient=settings["value_coefficient"],
                temperature=settings["temperature"],
            )
            final_kl += diagnostic["approximate_kl"] * len(check) / len(prepared)
        if final_kl > settings["target_kl"]:
            stop = "round_behavior_kl_limit"
            break
    return (
        model,
        optimizer,
        {
            "sampled_decisions": len(samples),
            "optimizer_steps": optimizer.steps - initial_steps,
            "epochs_completed": epochs,
            "stop_reason": stop,
            "raw_advantage_mean": mean,
            "raw_advantage_std": std,
            "diagnostics": {k: math.fsum(d[k] for d in stats) / len(stats) for k in stats[0]},
            "final_behavior_kl": final_kl,
            "all_actor_layers_and_decision_types_mutable": True,
            "baseline_proximity_penalty": 0,
        },
    )
