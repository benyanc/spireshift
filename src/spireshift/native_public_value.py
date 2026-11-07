"""Offline nonlinear return predictor, separate from every saved actor/Adam state.

Targets are observed complete-game bootstrap returns. This is value supervision,
not optimal-action labeling, fresh PPO experience or win-probability training.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any

from spireshift.neural_combat import _numpy


def game_weights(owners: list[int]) -> tuple[float, ...]:
    if not owners:
        raise ValueError("Value fitting needs complete games")
    counts = {i: owners.count(i) for i in set(owners)}
    return tuple(1 / len(counts) / counts[i] for i in owners)


def initialize(dimension: int, hidden: int, seed: int) -> dict[str, Any]:
    np = _numpy()
    if not 1 <= dimension <= 8212 or not 1 <= hidden <= 64:
        raise ValueError("Experimental critic exceeds its declared small architecture")
    rng = np.random.default_rng(seed)
    return {
        "input": rng.normal(0, 1 / math.sqrt(dimension), (dimension, hidden)),
        "bias": np.zeros(hidden),
        "output": np.zeros(hidden),
        "intercept": np.zeros(1),
    }


def forward(parameters: dict[str, Any], x: Any) -> Any:
    np = _numpy()
    return (
        np.tanh(x @ parameters["input"] + parameters["bias"]) @ parameters["output"]
        + parameters["intercept"][0]
    )


def loss_gradient(
    parameters: dict[str, Any], x: Any, target: Any, weights: Any, regularization: float
) -> tuple[float, dict[str, Any]]:
    np = _numpy()
    hidden = np.tanh(x @ parameters["input"] + parameters["bias"])
    error = hidden @ parameters["output"] + parameters["intercept"][0] - target
    delta = 2 * weights * error
    back = delta[:, None] * parameters["output"] * (1 - hidden * hidden)
    gradients = {
        "input": x.T @ back + 2 * regularization * parameters["input"],
        "bias": back.sum(axis=0),
        "output": hidden.T @ delta + 2 * regularization * parameters["output"],
        "intercept": np.asarray([delta.sum()]),
    }
    loss = float(weights @ (error * error)) + regularization * sum(
        float(np.square(parameters[k]).sum()) for k in ("input", "output")
    )
    return loss, gradients


@dataclass
class PublicValue:
    parameters: dict[str, Any]
    mean: Any
    scale: Any
    base_weights: Any
    fitting_games: tuple[int, ...]
    updates: int

    def predict(self, x: Any, coarse: Any, potential: Any, owners: list[int]) -> Any:
        np = _numpy()
        if set(owners) & set(self.fitting_games):
            raise ValueError("A value predictor cannot score its own fitting game")
        z = np.clip((x - self.mean) / self.scale, -4, 4)
        result = np.clip(potential + coarse @ self.base_weights + forward(self.parameters, z), 0, 1)
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite held-game value prediction")
        return result

    def arrays(self) -> dict[str, Any]:
        return {
            **self.parameters,
            "mean": self.mean,
            "scale": self.scale,
            "base_weights": self.base_weights,
        }


def fit_value(
    x: Any,
    coarse: Any,
    potential: Any,
    target: Any,
    owners: list[int],
    base_weights: tuple[float, ...],
    settings: dict[str, Any],
    seed: int,
    deadline: float,
) -> tuple[PublicValue, dict[str, Any]]:
    """Fixed epochs, equal mass per game and per choice within it; no test selection."""
    np = _numpy()
    if (
        len(x) != len(owners)
        or len(coarse) != len(x)
        or len(potential) != len(x)
        or len(target) != len(x)
        or not np.isfinite(x).all()
        or not np.isfinite(target).all()
        or not np.isfinite(coarse).all()
        or not np.isfinite(potential).all()
        or not np.isfinite(base_weights).all()
        or np.any(target < 0)
        or np.any(target > 1)
    ):
        raise ValueError("Invalid complete-game critic fitting arrays")
    weights = np.asarray(game_weights(owners))
    mean = weights @ x
    scale = np.maximum(0.25, np.sqrt(weights @ np.square(x - mean)))
    z = np.clip((x - mean) / scale, -4, 4)
    residual = target - potential - coarse @ np.asarray(base_weights)
    parameters = initialize(x.shape[1], settings["hidden"], seed)
    first = loss_gradient(parameters, z, residual, weights, settings["l2"])[0]
    moments = {k: np.zeros_like(v) for k, v in parameters.items()}
    variances = {k: np.zeros_like(v) for k, v in parameters.items()}
    for step in range(1, settings["epochs"] + 1):
        if time.monotonic() >= deadline:
            raise TimeoutError("Offline value fit reached its finite cap")
        _, gradient = loss_gradient(parameters, z, residual, weights, settings["l2"])
        norm = math.sqrt(sum(float(np.square(g).sum()) for g in gradient.values()))
        factor = min(1.0, settings["gradient_clip"] / max(norm, 1e-30))
        for key in parameters:
            g = gradient[key] * factor
            moments[key] = 0.9 * moments[key] + 0.1 * g
            variances[key] = 0.999 * variances[key] + 0.001 * g * g
            parameters[key] -= (
                settings["learning_rate"]
                * (moments[key] / (1 - 0.9**step))
                / (np.sqrt(variances[key] / (1 - 0.999**step)) + 1e-8)
            )
        if any(not np.isfinite(p).all() for p in parameters.values()):
            raise ValueError("Nonfinite experimental critic update")
    final = loss_gradient(parameters, z, residual, weights, settings["l2"])[0]
    model = PublicValue(
        parameters,
        mean,
        scale,
        np.asarray(base_weights),
        tuple(sorted(set(owners))),
        settings["epochs"],
    )
    return model, {
        "fitting_games": list(model.fitting_games),
        "choice_states": len(x),
        "input_dimension": x.shape[1],
        "hidden": settings["hidden"],
        "optimizer_steps": model.updates,
        "initial_regularized_fit_loss": first,
        "final_regularized_fit_loss": final,
        "parameter_count": sum(p.size for p in parameters.values()),
        "weighting": "equal_complete_game_then_equal_choice_bearing_state",
        "held_game_targets_used_for_fitting_or_selection": False,
    }


def paired_errors(owners: list[int], target: Any, predictions: dict[str, Any]) -> dict[str, Any]:
    np = _numpy()
    if len(target) != len(owners) or any(len(p) != len(owners) for p in predictions.values()):
        raise ValueError("Held-game value denominator changed")
    weights = np.asarray(game_weights(owners))
    if any(not np.isfinite(p).all() for p in predictions.values()):
        raise ValueError("Nonfinite held-game predictions")
    per_game = []
    for game in sorted(set(owners)):
        mask = np.asarray(owners) == game
        per_game.append(
            {
                "game": game,
                "states": int(mask.sum()),
                "mse": {
                    name: float(np.square(target[mask] - pred[mask]).mean())
                    for name, pred in predictions.items()
                },
            }
        )
    return {
        "games": len(per_game),
        "choice_states": len(owners),
        "per_game": per_game,
        "mse": {
            name: float(weights @ np.square(target - pred)) for name, pred in predictions.items()
        },
    }
