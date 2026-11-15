"""Matched offline value fits; never updates an actor or its optimizer.

Both arms have the same full input shape and exact initial arrays. The sole
treatment masks the extra standardized public inputs to zero in one arm.
Held outcomes are used for reporting fixed snapshots, never fitting/selection.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any

from spireshift.native_public_value import forward, game_weights, initialize, loss_gradient
from spireshift.neural_combat import _numpy

ARMS = ("coarse_masked", "rich")
SETTINGS = {"hidden": 32, "epochs": 96, "learning_rate": 0.003, "l2": 0.0001, "gradient_clip": 5.0}
CURVE_STEPS = (0, 1, 4, 8, 16, 24, 48, 96)
PRIMARY_STEP = 24
INITIALIZERS = (20261020, 20261021, 20261022)


@dataclass(frozen=True)
class ValuePartition:
    inputs: Any
    targets: Any
    base: Any
    owners: tuple[int, ...]

    def validate(self) -> None:
        np = _numpy()
        n = len(self.owners)
        if (
            not n
            or len(set(self.owners)) < 2
            or self.inputs.ndim != 2
            or self.inputs.shape[0] != n
            or self.targets.shape != (n,)
            or self.base.shape != (n,)
            or not 1 <= self.inputs.shape[1] <= 8212
            or any(type(i) is not int for i in self.owners)
            or any(not np.isfinite(a).all() for a in (self.inputs, self.targets, self.base))
            or np.any(self.targets < 0)
            or np.any(self.targets > 1)
        ):
            raise ValueError("Matched value fitting requires finite complete-game partitions")
        for game in set(self.owners):
            if len(np.unique(self.targets[np.asarray(self.owners) == game])) != 1:
                raise ValueError("One complete game must have one observed return")


def parameter_digest(parameters: dict[str, Any]) -> str:
    """Include names/shapes/dtypes as well as exact numerical bytes."""
    digest = hashlib.sha256()
    for key in sorted(parameters):
        a = parameters[key]
        digest.update(f"{key}|{a.shape}|{a.dtype.str}|".encode())
        digest.update(a.tobytes(order="C"))
    return digest.hexdigest()


def errors(prediction: Any, partition: ValuePartition) -> dict[str, float]:
    np = _numpy()
    if prediction.shape != partition.targets.shape or not np.isfinite(prediction).all():
        raise ValueError("Nonfinite or incomplete value forecasts")
    weights = np.asarray(game_weights(list(partition.owners)))
    return {
        "mse": float(weights @ np.square(prediction - partition.targets)),
        "clipped_mse": float(weights @ np.square(np.clip(prediction, 0, 1) - partition.targets)),
    }


def standardized(
    fitting: ValuePartition, held: ValuePartition, coarse_dimension: int
) -> tuple[Any, Any, Any, Any]:
    """One fitting-only mean/scale for both arms; mask only after this transform."""
    np = _numpy()
    fitting.validate()
    held.validate()
    if (
        set(fitting.owners) & set(held.owners)
        or held.inputs.shape[1] != fitting.inputs.shape[1]
        or type(coarse_dimension) is not int
        or not 1 <= coarse_dimension < fitting.inputs.shape[1]
    ):
        raise ValueError("Matched arms need extra inputs and disjoint whole-game owners")
    weights = np.asarray(game_weights(list(fitting.owners)))
    mean = weights @ fitting.inputs
    scale = np.maximum(0.25, np.sqrt(weights @ np.square(fitting.inputs - mean)))
    return (
        np.clip((fitting.inputs - mean) / scale, -4, 4),
        np.clip((held.inputs - mean) / scale, -4, 4),
        mean,
        scale,
    )


def fit_pair(
    fitting: ValuePartition,
    held: ValuePartition,
    coarse_dimension: int,
    settings: dict[str, Any],
    curve_steps: tuple[int, ...],
    seed: int,
    deadline: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Fixed updates, identical starting weights/moments, no held-data feedback."""
    np = _numpy()
    if (
        set(settings) != set(SETTINGS)
        or type(settings["epochs"]) is not int
        or not 1 <= settings["epochs"] <= 400
        or type(settings["hidden"]) is not int
        or not 1 <= settings["hidden"] <= 64
        or any(
            type(settings[k]) not in (int, float)
            or not math.isfinite(settings[k])
            or settings[k] <= 0
            for k in ("learning_rate", "gradient_clip")
        )
        or type(settings["l2"]) not in (int, float)
        or not math.isfinite(settings["l2"])
        or settings["l2"] < 0
        or not curve_steps
        or curve_steps[0] != 0
        or curve_steps[-1] != settings["epochs"]
        or any(type(s) is not int for s in curve_steps)
        or tuple(sorted(set(curve_steps))) != curve_steps
        or type(seed) is not int
        or seed < 0
    ):
        raise ValueError("Invalid fixed matched-value fitting schedule")
    z_fit, z_held, mean, scale = standardized(fitting, held, coarse_dimension)
    common = initialize(fitting.inputs.shape[1], settings["hidden"], seed)
    initial_digest = parameter_digest(common)
    weights = np.asarray(game_weights(list(fitting.owners)))
    residual = fitting.targets - fitting.base
    models, arms, predictions = {}, {}, {}
    for name in ARMS:
        parameters = {k: v.copy() for k, v in common.items()}
        moments = {k: np.zeros_like(v) for k, v in parameters.items()}
        variances = {k: np.zeros_like(v) for k, v in parameters.items()}
        if parameter_digest(parameters) != initial_digest:
            raise ValueError("Matched starting parameters differ")
        mask = np.ones(fitting.inputs.shape[1])
        if name == "coarse_masked":
            mask[coarse_dimension:] = 0
        x_fit, x_held = z_fit * mask, z_held * mask
        curve = []
        primary_arrays = {}
        for step in range(settings["epochs"] + 1):
            if time.monotonic() >= deadline:
                raise TimeoutError("Matched value fit reached its finite cap")
            if step in curve_steps:
                fit_prediction = fitting.base + forward(parameters, x_fit)
                held_prediction = held.base + forward(parameters, x_held)
                fit_error = errors(fit_prediction, fitting)
                held_error = errors(held_prediction, held)
                penalty = settings["l2"] * sum(
                    float(np.square(parameters[k]).sum()) for k in ("input", "output")
                )
                curve.append(
                    {
                        "step": step,
                        "fitting_mse": fit_error["mse"],
                        "fitting_clipped_mse": fit_error["clipped_mse"],
                        "held_mse": held_error["mse"],
                        "held_clipped_mse": held_error["clipped_mse"],
                        "weight_penalty": penalty,
                        "regularized_fitting_loss": fit_error["mse"] + penalty,
                        "parameter_sha256": parameter_digest(parameters),
                    }
                )
                predictions[f"{name}_step_{step}"] = held_prediction.copy()
                if step == PRIMARY_STEP:
                    primary_arrays = {
                        f"primary_{key}": value.copy() for key, value in parameters.items()
                    }
            if step == settings["epochs"]:
                break
            _, gradient = loss_gradient(parameters, x_fit, residual, weights, settings["l2"])
            norm = math.sqrt(sum(float(np.square(g).sum()) for g in gradient.values()))
            factor = min(1.0, settings["gradient_clip"] / max(norm, 1e-30))
            t = step + 1
            for key in parameters:
                g = gradient[key] * factor
                moments[key] = 0.9 * moments[key] + 0.1 * g
                variances[key] = 0.999 * variances[key] + 0.001 * g * g
                parameters[key] -= (
                    settings["learning_rate"]
                    * (moments[key] / (1 - 0.9**t))
                    / (np.sqrt(variances[key] / (1 - 0.999**t)) + 1e-8)
                )
            if any(not np.isfinite(p).all() for p in parameters.values()):
                raise ValueError("Nonfinite matched value update")
        models[name] = {
            **parameters,
            **primary_arrays,
            **{f"adam_mean_{k}": v for k, v in moments.items()},
            **{f"adam_square_{k}": v for k, v in variances.items()},
            "mean": mean,
            "scale": scale,
            "input_mask": mask,
            "fitting_games": np.asarray(sorted(set(fitting.owners))),
            "optimizer_steps": np.asarray([settings["epochs"]]),
        }
        arms[name] = {
            "initial_parameter_sha256": initial_digest,
            "final_parameter_sha256": parameter_digest(parameters),
            "initial_moments": "all_zero",
            "input_dimension": fitting.inputs.shape[1],
            "active_input_columns": int(mask.sum()),
            "parameter_count": sum(p.size for p in parameters.values()),
            "curve": curve,
        }
    # A zero correction must exactly reproduce the same ridge, including clipping.
    if not np.array_equal(predictions["coarse_masked_step_0"], predictions["rich_step_0"]):
        raise ValueError("Matched initial forecasts differ")
    return (
        models,
        predictions,
        {
            "network_initializer": seed,
            "arms": arms,
            "shared_normalization": "equal_game_fitting_only_then_mask_standardized_extras",
            "identical_initial_parameters_and_moments": True,
            "identical_initial_predictions": True,
            "fitting_games": sorted(set(fitting.owners)),
            "held_games": sorted(set(held.owners)),
            "fitting_choice_states": len(fitting.owners),
            "held_choice_states": len(held.owners),
            "held_outcomes_used_for_fitting_or_selection": False,
            "best_step_selected": False,
            "actor_optimizer_steps": 0,
        },
    )
