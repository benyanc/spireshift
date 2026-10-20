"""Closed-form public-state ridge values with nested whole-game selection.

Only the declared progress potential is an offset. In particular, an outer-fit
ridge forecast must not enter an inner fold: it has seen inner-validation returns.
No actor, Adam state, game engine or hidden engine facts are used here.
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Any

from spireshift.native_matched_value import ValuePartition, errors, parameter_digest
from spireshift.native_public_value import game_weights, paired_errors
from spireshift.neural_combat import _numpy

ARMS = ("coarse_linear", "rich_linear")
REGULARIZATION = (0.000001, 0.00001, 0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
INNER_FOLDS = 3
SALT = "native-linear-value-whole-game-v1"


def _deadline(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("Linear value unit exceeded its bounded deadline; preserve evidence")


def subset(data: ValuePartition, selected: Any) -> ValuePartition:
    """Here `base` means the fixed progress potential, never a fitted forecast."""
    np = _numpy()
    return ValuePartition(
        data.inputs[selected],
        data.targets[selected],
        data.base[selected],
        tuple(int(i) for i in np.asarray(data.owners)[selected]),
    )


def whole_game_folds(owners: tuple[int, ...], folds: int, salt: str) -> dict[int, int]:
    games = sorted(set(owners))
    if type(folds) is not int or folds < 2 or len(games) < 2 * folds:
        raise ValueError("Each validation fold needs at least two complete games")
    games.sort(key=lambda game: hashlib.sha256(f"{salt}|{game}".encode()).digest())
    return {game: i % folds for i, game in enumerate(games)}


@dataclass(frozen=True)
class LinearValue:
    mean: Any
    scale: Any
    center: Any
    coefficients: Any
    intercept: float
    regularization: float
    fitting_games: tuple[int, ...]

    def arrays(self) -> dict[str, Any]:
        np = _numpy()
        return {
            "mean": self.mean,
            "scale": self.scale,
            "center": self.center,
            "coefficients": self.coefficients,
            "intercept": np.asarray([self.intercept]),
            "regularization": np.asarray([self.regularization]),
            "fitting_games": np.asarray(self.fitting_games),
        }

    def forecast(self, inputs: Any, potential: Any) -> Any:
        np = _numpy()
        if (
            inputs.ndim != 2
            or inputs.shape[1] != len(self.mean)
            or potential.shape != (len(inputs),)
            or not np.isfinite(inputs).all()
            or not np.isfinite(potential).all()
        ):
            raise ValueError("Incomplete or nonfinite linear value inputs")
        z = np.clip((inputs - self.mean) / self.scale, -4, 4) - self.center
        prediction = potential + (self.intercept + z @ self.coefficients)
        if not np.isfinite(prediction).all():
            raise ValueError("Nonfinite linear value forecast")
        return prediction

    def predict(self, held: ValuePartition) -> Any:
        held.validate()
        if set(held.owners) & set(self.fitting_games):
            raise ValueError("Whole fitting games cannot supply their own value credit")
        return self.forecast(held.inputs, held.base)


def fit_path(
    fitting: ValuePartition, grid: tuple[float, ...], arm: str, deadline: float
) -> tuple[list[LinearValue], list[dict[str, Any]]]:
    """Minimize equal-game MSE + lambda * squared slopes; intercept unpenalized.

    One eigensystem fits a fixed grid exactly, without initialization, Adam or epochs.
    Normalization and centering use only the fitting games at this level of nesting.
    """
    np = _numpy()
    fitting.validate()
    if (
        arm not in ARMS
        or fitting.inputs.shape[1] <= 20
        or not grid
        or tuple(sorted(set(grid))) != grid
        or any(not math.isfinite(v) or v <= 0 for v in grid)
    ):
        raise ValueError("Require coarse/rich arms and a fixed positive ridge grid")
    _deadline(deadline)
    weights = np.asarray(game_weights(list(fitting.owners)))
    mean = weights @ fitting.inputs
    scale = np.maximum(0.25, np.sqrt(weights @ np.square(fitting.inputs - mean)))
    standardized = np.clip((fitting.inputs - mean) / scale, -4, 4)
    center = weights @ standardized
    dimension = 20 if arm == "coarse_linear" else fitting.inputs.shape[1]
    z = standardized[:, :dimension] - center[:dimension]
    residual = fitting.targets - fitting.base
    intercept = float(weights @ residual)
    gram = z.T @ (weights[:, None] * z)
    rhs = z.T @ (weights * (residual - intercept))
    eigenvalues, vectors = np.linalg.eigh(gram)
    _deadline(deadline)
    if float(eigenvalues[0]) < -1e-9 * max(1.0, float(eigenvalues[-1])):
        raise ValueError("Ridge Gram matrix is not positive semidefinite")
    eigenvalues = np.maximum(eigenvalues, 0)
    projected = vectors.T @ rhs
    models, reports = [], []
    for regularization in grid:
        _deadline(deadline)
        slopes = vectors @ (projected / (eigenvalues + regularization))
        equation_error = float(np.linalg.norm(gram @ slopes + regularization * slopes - rhs))
        equation_relative = equation_error / max(float(np.linalg.norm(rhs)), 1e-15)
        if not np.isfinite(slopes).all() or equation_relative > 1e-7:
            raise ValueError("Closed-form ridge solve failed its normal-equation check")
        coefficients = np.zeros(fitting.inputs.shape[1])
        coefficients[:dimension] = slopes
        model = LinearValue(
            mean,
            scale,
            center,
            coefficients,
            intercept,
            regularization,
            tuple(sorted(set(fitting.owners))),
        )
        fit_errors = errors(model.forecast(fitting.inputs, fitting.base), fitting)
        penalty = regularization * float(coefficients @ coefficients)
        reports.append(
            {
                "regularization": regularization,
                "fitting_mse": fit_errors["mse"],
                "fitting_clipped_mse": fit_errors["clipped_mse"],
                "weight_penalty": penalty,
                "regularized_fitting_loss": fit_errors["mse"] + penalty,
                "normal_equation_relative_residual": equation_relative,
                "parameter_digest": parameter_digest(model.arrays()),
            }
        )
        models.append(model)
    return models, reports


def select_regularization(rows: list[dict[str, Any]], grid: tuple[float, ...]) -> float:
    """Equal mass per validation game, deterministic stronger-shrinkage exact ties."""
    if not rows or any(tuple(p["regularization"] for p in r["path"]) != grid for r in rows):
        raise ValueError("Incomplete whole-game regularization grid")
    denominator = sum(len(r["validation_games"]) for r in rows)
    scores = {
        value: sum(
            len(r["validation_games"]) * r["path"][i]["validation_clipped_mse"] for r in rows
        )
        / denominator
        for i, value in enumerate(grid)
    }
    if any(not math.isfinite(v) for v in scores.values()):
        raise ValueError("Nonfinite inner validation score")
    return min(grid, key=lambda value: (scores[value], -value))


def nested_pair(
    fitting: ValuePartition,
    held: ValuePartition,
    grid: tuple[float, ...],
    folds: int,
    salt: str,
    deadline: float,
) -> tuple[dict[str, LinearValue], dict[str, Any], dict[str, Any]]:
    """Select separately for each arm on inner whole games, then refit outer train.

    The inherited public dictionary is frozen from the prior outer-fitting inputs.
    It excludes outer-held games; inner validation is conditional on that dictionary.
    Outer-held inputs/targets never enter fitting, scaling or lambda selection.
    """
    np = _numpy()
    fitting.validate()
    held.validate()
    if set(fitting.owners) & set(held.owners) or fitting.inputs.shape[1] != held.inputs.shape[1]:
        raise ValueError("Linear study needs disjoint complete outer games and matched columns")
    assignment = whole_game_folds(fitting.owners, folds, salt)
    inner: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for fold in range(folds):
        mask = np.asarray([assignment[game] != fold for game in fitting.owners])
        train, validation = subset(fitting, mask), subset(fitting, ~mask)
        for arm in ARMS:
            path_models, path = fit_path(train, grid, arm, deadline)
            for model, point in zip(path_models, path, strict=True):
                result = errors(model.predict(validation), validation)
                point.update(
                    validation_mse=result["mse"], validation_clipped_mse=result["clipped_mse"]
                )
            inner[arm].append(
                {
                    "fold": fold,
                    "fitting_games": sorted(set(train.owners)),
                    "validation_games": sorted(set(validation.owners)),
                    "path": path,
                }
            )
    # Freeze both choices and refit before touching any outer-held error.
    models, selected_reports = {}, {}
    for arm in ARMS:
        value = select_regularization(inner[arm], grid)
        fitted, metrics = fit_path(fitting, (value,), arm, deadline)
        models[arm] = fitted[0]
        selected_reports[arm] = metrics[0]
    predictions = {arm: model.predict(held) for arm, model in models.items()}
    report = {
        "fitting_games": sorted(set(fitting.owners)),
        "held_games": sorted(set(held.owners)),
        "inner": inner,
        "selected": selected_reports,
        "held": {
            "unclipped": paired_errors(list(held.owners), held.targets, predictions),
            "clipped": paired_errors(
                list(held.owners),
                held.targets,
                {k: np.clip(v, 0, 1) for k, v in predictions.items()},
            ),
        },
        "selection_metric": "inner_equal_whole_game_clipped_mse",
        "intercept_penalized": False,
        "fitted_outer_baseline_used_in_inner_folds": False,
        "outer_held_used_for_selection": False,
        "inner_scaling_fitted_without_validation_games": True,
        "dictionary_scope": "frozen_prior_outer_fitting_inputs_not_inner_refitted",
        "potential_offset": "fixed_objective_progress_not_fitted_forecast",
    }
    return models, predictions, report
