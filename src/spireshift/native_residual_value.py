"""Keep the existing coarse ridge intact; validate an independently penalized rich residual.

Every nesting level refits its own original baseline. No outer-fit offset may
enter an inner fit or validation. Off is a real candidate and wins exact ties.
These are offline auxiliary-return forecasts, never actor/Adam updates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from spireshift.native_linear_value import LinearValue, _deadline, subset, whole_game_folds
from spireshift.native_matched_value import ValuePartition, errors, parameter_digest
from spireshift.native_public_value import game_weights, paired_errors
from spireshift.native_value_credit import FEATURES, ValueBaseline, ValueRun, fit_baseline
from spireshift.neural_combat import _numpy

BASELINE_REGULARIZATION = 0.001
METHOD = "baseline_plus_rich_correction"


def coarse_fit(fitting: ValuePartition) -> ValueBaseline:
    """Call the unchanged 20-column fitter, preserving original game and row order."""
    np = _numpy()
    fitting.validate()
    if fitting.inputs.shape[1] <= len(FEATURES) or not np.all(fitting.inputs[:, 0] == 1):
        raise ValueError("Require the original coarse bias/prefix and additional rich columns")
    owners = np.asarray(fitting.owners)
    runs = []
    for game in dict.fromkeys(fitting.owners):
        mask = owners == game
        n = int(mask.sum())
        runs.append(
            ValueRun(
                game,
                0,
                float(fitting.targets[mask][0]),
                tuple(tuple(float(x) for x in row) for row in fitting.inputs[mask, :20]),
                tuple(float(x) for x in fitting.base[mask]),
                (0.0,) * n,
                (2,) * n,  # The sealed cache contains only choice-bearing states.
            )
        )
    return fit_baseline(runs, "public_residual_ridge", BASELINE_REGULARIZATION)


@dataclass(frozen=True)
class CorrectedValue:
    baseline: ValueBaseline
    correction: LinearValue | None
    input_dimension: int

    def arrays(self) -> dict[str, Any]:
        np = _numpy()
        result = {
            "baseline_weights": np.asarray(self.baseline.weights),
            "baseline_regularization": np.asarray([self.baseline.regularization]),
            "fitting_games": np.asarray(self.baseline.fitting_runs),
            "input_dimension": np.asarray([self.input_dimension]),
            "correction_enabled": np.asarray([self.correction is not None]),
        }
        if self.correction is not None:
            result.update({"rich_" + k: v for k, v in self.correction.arrays().items()})
        return result

    @classmethod
    def restore(cls, arrays: dict[str, Any]) -> CorrectedValue:
        baseline = ValueBaseline(
            "public_residual_ridge",
            float(arrays["baseline_regularization"][0]),
            tuple(float(x) for x in arrays["baseline_weights"]),
            tuple(int(x) for x in arrays["fitting_games"]),
        )
        rich = None
        if bool(arrays["correction_enabled"][0]):
            rich = LinearValue(
                arrays["rich_mean"],
                arrays["rich_scale"],
                arrays["rich_center"],
                arrays["rich_coefficients"],
                float(arrays["rich_intercept"][0]),
                float(arrays["rich_regularization"][0]),
                tuple(int(x) for x in arrays["rich_fitting_games"]),
            )
        model = cls(baseline, rich, int(arrays["input_dimension"][0]))
        if (
            baseline.regularization != BASELINE_REGULARIZATION
            or len(baseline.weights) != 20
            or model.input_dimension <= 20
            or (rich is not None and rich.fitting_games != baseline.fitting_runs)
            or parameter_digest(model.arrays()) != parameter_digest(arrays)
        ):
            raise ValueError("Saved correction schema or baseline differs")
        return model

    def forecast(self, inputs: Any, potential: Any) -> Any:
        np = _numpy()
        if (
            inputs.ndim != 2
            or inputs.shape[1] != self.input_dimension
            or potential.shape != (len(inputs),)
            or not np.isfinite(inputs).all()
            or not np.isfinite(potential).all()
        ):
            raise ValueError("Incomplete or nonfinite correction inputs")
        # Identical raw forecast convention to the sealed comparator; clip for scoring.
        baseline = potential + inputs[:, :20] @ np.asarray(self.baseline.weights)
        if self.correction is None:
            return baseline
        return self.correction.forecast(inputs[:, 20:], baseline)

    def predict(self, held: ValuePartition) -> Any:
        held.validate()
        if set(held.owners) & set(self.baseline.fitting_runs):
            raise ValueError("Whole fitting games cannot supply their own value credit")
        return self.forecast(held.inputs, held.base)


def correction_path(
    fitting: ValuePartition, grid: tuple[float, ...], deadline: float
) -> tuple[list[CorrectedValue], list[dict[str, Any]]]:
    """Fixed coarse lambda; centered rich slopes have their own positive lambda.

    Fit residuals on the current fitting games only. There is no extra intercept:
    the original coarse fit already has an unpenalized intercept. Only rich slopes
    vary across this path. All errors give equal total mass to each complete game.
    """
    np = _numpy()
    _deadline(deadline)
    if tuple(sorted(set(grid))) != grid or any(not math.isfinite(v) or v <= 0 for v in grid):
        raise ValueError("Require a fixed positive correction ridge grid")
    baseline = coarse_fit(fitting)
    off = CorrectedValue(baseline, None, fitting.inputs.shape[1])
    offset = off.forecast(fitting.inputs, fitting.base)
    off_errors = errors(offset, fitting)
    off_report = {
        "regularization": None,
        "correction_enabled": False,
        "fitting_mse": off_errors["mse"],
        "fitting_clipped_mse": off_errors["clipped_mse"],
        "correction_penalty": 0.0,
        "regularized_correction_loss": off_errors["mse"],
        "normal_equation_relative_residual": 0.0,
        "parameter_digest": parameter_digest(off.arrays()),
    }
    if not grid:  # A selected off candidate refits only the coarse predictor.
        return [off], [off_report]
    weights = np.asarray(game_weights(list(fitting.owners)))
    extra = fitting.inputs[:, 20:]
    mean = weights @ extra
    scale = np.maximum(0.25, np.sqrt(weights @ np.square(extra - mean)))
    standardized = np.clip((extra - mean) / scale, -4, 4)
    center = weights @ standardized
    z = standardized - center
    gram = z.T @ (weights[:, None] * z)
    rhs = z.T @ (weights * (fitting.targets - offset))
    values, vectors = np.linalg.eigh(gram)
    _deadline(deadline)
    if float(values[0]) < -1e-9 * max(1.0, float(values[-1])):
        raise ValueError("Correction Gram matrix is not positive semidefinite")
    values = np.maximum(values, 0)
    projected = vectors.T @ rhs
    models = [off]
    reports: list[dict[str, Any]] = []
    for regularization in grid:
        _deadline(deadline)
        slopes = vectors @ (projected / (values + regularization))
        relative = float(np.linalg.norm(gram @ slopes + regularization * slopes - rhs)) / max(
            float(np.linalg.norm(rhs)), 1e-15
        )
        if not np.isfinite(slopes).all() or relative > 1e-7:
            raise ValueError("Correction failed its normal-equation check")
        models.append(
            CorrectedValue(
                baseline,
                LinearValue(
                    mean, scale, center, slopes, 0.0, regularization, baseline.fitting_runs
                ),
                fitting.inputs.shape[1],
            )
        )
        reports.append({"normal_equation_relative_residual": relative})
    reports.insert(0, {"normal_equation_relative_residual": 0.0})
    for model, report in zip(models, reports, strict=True):
        err = errors(model.forecast(fitting.inputs, fitting.base), fitting)
        rich = model.correction
        penalty = (
            0.0
            if rich is None
            else rich.regularization * float(rich.coefficients @ rich.coefficients)
        )
        report.update(
            regularization=None if rich is None else rich.regularization,
            correction_enabled=rich is not None,
            fitting_mse=err["mse"],
            fitting_clipped_mse=err["clipped_mse"],
            correction_penalty=penalty,
            regularized_correction_loss=err["mse"] + penalty,
            parameter_digest=parameter_digest(model.arrays()),
        )
    return models, reports


def select_correction(rows: list[dict[str, Any]], grid: tuple[float, ...]) -> int:
    candidates = (None, *grid)
    if not rows or any(tuple(p["regularization"] for p in r["path"]) != candidates for r in rows):
        raise ValueError("Incomplete whole-game correction grid")
    games = [game for r in rows for game in r["validation_games"]]
    if len(games) != len(set(games)) or not games:
        raise ValueError("Duplicate or missing whole validation games")
    scores = [
        math.fsum(len(r["validation_games"]) * r["path"][i]["validation_clipped_mse"] for r in rows)
        / len(games)
        for i in range(len(candidates))
    ]
    if any(not math.isfinite(v) for v in scores):
        raise ValueError("Nonfinite inner correction score")
    return min(
        range(len(candidates)),
        key=lambda i: (scores[i], 0 if i == 0 else 1, -(candidates[i] or 0)),
    )


def nested_correction(
    fitting: ValuePartition,
    held: ValuePartition,
    grid: tuple[float, ...],
    folds: int,
    salt: str,
    deadline: float,
) -> tuple[CorrectedValue, dict[str, Any], dict[str, Any]]:
    np = _numpy()
    if not grid:
        raise ValueError("Nested selection requires a positive correction grid plus off")
    fitting.validate()
    held.validate()
    if set(fitting.owners) & set(held.owners) or fitting.inputs.shape[1] != held.inputs.shape[1]:
        raise ValueError("Correction needs disjoint complete outer games and matched columns")
    assignment = whole_game_folds(fitting.owners, folds, salt)
    inner = []
    for fold in range(folds):
        mask = np.asarray([assignment[g] != fold for g in fitting.owners])
        train, validation = subset(fitting, mask), subset(fitting, ~mask)
        models, path = correction_path(train, grid, deadline)
        for model, point in zip(models, path, strict=True):
            err = errors(model.predict(validation), validation)
            point.update(validation_mse=err["mse"], validation_clipped_mse=err["clipped_mse"])
        inner.append(
            {
                "fold": fold,
                "fitting_games": sorted(set(train.owners)),
                "validation_games": sorted(set(validation.owners)),
                "baseline": models[0].baseline.as_dict(),
                "path": path,
            }
        )
    selected_index = select_correction(inner, grid)
    selected_lambda = (None, *grid)[selected_index]
    # Selection is frozen before any outer-held predictions. Only refit the chosen lambda.
    refit_grid = () if selected_lambda is None else (selected_lambda,)
    outer, reports = correction_path(fitting, refit_grid, deadline)
    model = outer[0 if selected_lambda is None else 1]
    selected = reports[0 if selected_lambda is None else 1]
    predictions = {"current_ridge": outer[0].predict(held), METHOD: model.predict(held)}
    report = {
        "fitting_games": sorted(set(fitting.owners)),
        "held_games": sorted(set(held.owners)),
        "inner": inner,
        "selected": selected,
        "baseline": model.baseline.as_dict(),
        "held": {
            "unclipped": paired_errors(list(held.owners), held.targets, predictions),
            "clipped": paired_errors(
                list(held.owners),
                held.targets,
                {k: np.clip(v, 0, 1) for k, v in predictions.items()},
            ),
        },
        "selection_metric": "inner_equal_whole_game_clipped_mse",
        "exact_tie_rule": "no_correction_first_then_stronger_rich_shrinkage",
        "coarse_regularization": BASELINE_REGULARIZATION,
        "coarse_weights_never_optimized_by_rich_fit": True,
        "correction_columns": "rich_only_after_original_20_columns",
        "correction_intercept": 0.0,
        "inner_baseline_refitted_without_validation_returns": True,
        "fitted_outer_baseline_used_in_inner_folds": False,
        "outer_held_used_for_selection": False,
        "dictionary_scope": "frozen_prior_outer_fitting_inputs_not_inner_refitted",
        "residual_labels": "current_fitting_game_return_minus_in_sample_coarse_forecast",
    }
    return model, predictions, report
