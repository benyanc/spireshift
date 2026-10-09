"""Small, transparent PPO learner for the complete public-action neural player.

Monte Carlo returns use the declared whole-episode training score. The critic
estimates that bootstrap return, never terminal victory probability. Clipping
compares with this round's sampled player, not a permanent baseline anchor.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_features import _tokens
from spireshift.full_run_policy import dense_features, score_gradient
from spireshift.full_run_public_policy import PublicFullRunModel
from spireshift.models import _exact_keys, _mapping
from spireshift.neural_combat import _numpy

SCHEMA = "public-full-run-actor-critic-v1"
VALUE_ENCODER = "public-context-bootstrap-value-v1"


def finite_vector(value: object, size: int, label: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(f"{label} length differs")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in value):
        raise ValueError(f"{label} must contain finite numbers")
    return tuple(float(v) for v in value)


def state_features(context: dict[str, Any], dimension: int) -> tuple[float, ...]:
    """Only the already validated public context; no candidate/seed/engine state."""
    tokens: dict[str, float] = {}
    _tokens(context, "state", tokens)
    values = [0.0] * dimension
    for token, amount in sorted(tokens.items()):
        digest = hashlib.sha256(f"{VALUE_ENCODER}|{token}".encode()).digest()
        index = int.from_bytes(digest[:8], "big") % dimension
        values[index] += (1 if digest[8] & 1 else -1) * amount
    return (*[max(-5.0, min(5.0, v)) for v in values], 1.0)


def sigmoid(value: Any) -> Any:
    np = _numpy()
    # tanh is stable for either sign without an overflowing exp.
    return (np.tanh(value / 2) + 1) / 2


@dataclass(frozen=True, slots=True)
class ActorCritic:
    actor: PublicFullRunModel
    value_weights: tuple[float, ...]

    def __post_init__(self) -> None:
        finite_vector(self.value_weights, self.actor.dimension + 1, "critic")

    @property
    def parameter_count(self) -> int:
        return self.actor.parameter_count + len(self.value_weights)

    @property
    def model_id(self) -> str:
        return manifest_identifier(self.body_dict())

    def body_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA,
            "actor": self.actor.as_dict(),
            "value_encoder_id": VALUE_ENCODER,
            "value_weights": list(self.value_weights),
            "value_target": "declared_undiscounted_whole_episode_bootstrap_return",
            "terminal_victory_probability_available": False,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.body_dict(), "model_id": self.model_id}

    @classmethod
    def from_mapping(cls, value: object) -> ActorCritic:
        d = _mapping(value, "actor critic")
        _exact_keys(
            d,
            {
                "schema_version",
                "actor",
                "value_encoder_id",
                "value_weights",
                "value_target",
                "terminal_victory_probability_available",
                "model_id",
            },
            "actor critic",
        )
        if (
            d["schema_version"] != SCHEMA
            or d["value_encoder_id"] != VALUE_ENCODER
            or d["value_target"] != "declared_undiscounted_whole_episode_bootstrap_return"
            or d["terminal_victory_probability_available"] is not False
            or d["model_id"] != manifest_identifier({k: v for k, v in d.items() if k != "model_id"})
        ):
            raise ValueError("Actor critic identity or target differs")
        actor = PublicFullRunModel.from_mapping(d["actor"])
        return cls(actor, finite_vector(d["value_weights"], actor.dimension + 1, "critic"))

    def weights(self) -> tuple[float, ...]:
        return (*self.actor.genome, *self.value_weights)

    def with_weights(self, values: Sequence[float]) -> ActorCritic:
        weights = finite_vector(tuple(values), self.parameter_count, "learner weights")
        n = self.actor.parameter_count
        return ActorCritic(self.actor.with_genome(weights[:n]), weights[n:])

    def value(self, row: Sequence[float]) -> float:
        if len(row) != len(self.value_weights):
            raise ValueError("Value feature dimension differs")
        return float(
            sigmoid(math.fsum(a * b for a, b in zip(row, self.value_weights, strict=True)))
        )


def initialize_critic(actor: PublicFullRunModel) -> ActorCritic:
    return ActorCritic(actor, (*([0.0] * actor.dimension), math.log(0.02 / 0.98)))


def log_softmax(logits: Sequence[float], temperature: float = 1.0) -> tuple[float, ...]:
    if len(logits) == 0 or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("Invalid policy logits or temperature")
    scaled = [v / temperature for v in logits]
    if not all(math.isfinite(v) for v in scaled):
        raise ValueError("Nonfinite policy logits")
    maximum = max(scaled)
    normalizer = maximum + math.log(math.fsum(math.exp(v - maximum) for v in scaled))
    return tuple(v - normalizer for v in scaled)


@dataclass(frozen=True, slots=True)
class Sample:
    rows: tuple[dict[int, float], ...]
    state: tuple[float, ...]
    action: int
    old_log_probability: float
    target: float
    advantage: float


def loss_gradient(
    model: ActorCritic,
    samples: Sequence[Sample],
    *,
    clip: float,
    entropy_coefficient: float,
    value_coefficient: float,
    temperature: float,
) -> tuple[float, tuple[float, ...], dict[str, float]]:
    """Vectorized variable-action minibatch; differentiate every actor and critic weight."""
    np = _numpy()
    if not samples:
        raise ValueError("PPO cannot optimize an empty minibatch")
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
            raise ValueError("Invalid on-policy sample")
        logp = np.asarray(log_softmax(logits[offset : offset + len(s.rows)], temperature))
        p = np.exp(logp)
        log_ratio = float(logp[s.action]) - s.old_log_probability
        ratio = math.exp(log_ratio)
        bounded = min(1 + clip, max(1 - clip, ratio))
        policy_loss -= min(ratio * s.advantage, bounded * s.advantage)
        active = not (
            (s.advantage > 0 and ratio > 1 + clip) or (s.advantage < 0 and ratio < 1 - clip)
        )
        onehot = np.zeros(len(p))
        onehot[s.action] = 1
        h = -float(p @ logp)
        gradient = -s.advantage * ratio * (onehot - p) if active else np.zeros(len(p))
        gradient += entropy_coefficient * p * (logp + h)
        dz[offset : offset + len(p)] = gradient / temperature / len(samples)
        entropy += h
        kl += ratio - 1 - log_ratio
        clipped += float(not active)
        offset += len(p)
    states = np.asarray([s.state for s in samples], dtype=np.float64)
    if states.shape != (len(samples), len(model.value_weights)) or not np.isfinite(states).all():
        raise ValueError("Invalid public value features")
    values = sigmoid(states @ np.asarray(model.value_weights))
    difference = values - np.asarray([s.target for s in samples])
    value_loss = float(np.mean(difference * difference)) / 2
    dv = value_coefficient * (difference * values * (1 - values)) @ states / len(samples)
    actor_gradient = score_gradient(model.actor, rows, dz)
    gradient = (*actor_gradient, *(float(v) for v in dv))
    total_loss = (policy_loss - entropy_coefficient * entropy) / len(samples)
    total_loss += value_coefficient * value_loss
    if not math.isfinite(total_loss) or not all(math.isfinite(v) for v in gradient):
        raise ValueError("Nonfinite PPO loss or gradient")
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


@dataclass(frozen=True, slots=True)
class Adam:
    steps: int
    first: tuple[float, ...]
    second: tuple[float, ...]

    @classmethod
    def zero(cls, size: int) -> Adam:
        return cls(0, (0.0,) * size, (0.0,) * size)

    def as_dict(self) -> dict[str, Any]:
        return {"steps": self.steps, "first": list(self.first), "second": list(self.second)}

    @classmethod
    def from_mapping(cls, value: object, size: int) -> Adam:
        d = _mapping(value, "Adam state")
        _exact_keys(d, {"steps", "first", "second"}, "Adam state")
        if type(d["steps"]) is not int or d["steps"] < 0:
            raise ValueError("Invalid optimizer step count")
        second = finite_vector(d["second"], size, "Adam second moment")
        if any(v < 0 for v in second):
            raise ValueError("Adam second moment is negative")
        return cls(d["steps"], finite_vector(d["first"], size, "Adam first moment"), second)

    def update(
        self,
        model: ActorCritic,
        gradient: Sequence[float],
        *,
        actor_rate: float,
        value_rate: float,
        maximum_norm: float,
    ) -> tuple[ActorCritic, Adam, float]:
        np = _numpy()
        g = np.asarray(finite_vector(tuple(gradient), model.parameter_count, "gradient"))
        norm = float(np.linalg.norm(g))
        g *= min(1.0, maximum_norm / max(norm, 1e-12))
        t = self.steps + 1
        m, v = (
            0.9 * np.asarray(self.first) + 0.1 * g,
            0.999 * np.asarray(self.second) + 0.001 * g * g,
        )
        rate = np.full(model.parameter_count, value_rate)
        rate[: model.actor.parameter_count] = actor_rate
        weights = np.asarray(model.weights()) - rate * (m / (1 - 0.9**t)) / (
            np.sqrt(v / (1 - 0.999**t)) + 1e-8
        )
        updated = model.with_weights(tuple(float(v) for v in weights))
        state = Adam(t, tuple(float(a) for a in m), tuple(float(a) for a in v))
        return updated, state, norm


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
    prepared = [
        Sample(s.rows, s.state, s.action, s.old_log_probability, s.target, float(a))
        for s, a in zip(samples, normalized, strict=True)
    ]
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
