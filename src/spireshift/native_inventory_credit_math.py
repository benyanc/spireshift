"""Whole-game inventory-information probes and exact chosen-logit credit diagnostics.

These fixed-penalty probes are not selected production predictors. They cannot
identify correct actions, estimate counterfactual outcomes or update a player.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from spireshift.native_matched_value import ValuePartition
from spireshift.native_public_value import paired_errors
from spireshift.native_residual_value import correction_path
from spireshift.native_value_credit import (
    ValueRun,
    fit_baseline,
    fold_assignment,
    prediction_metrics,
)
from spireshift.neural_combat import _numpy

METHODS = ("current", "deck", "relic", "deck_relic")
PENALTY = 1.0
SALT = "native-whole-run-value-crossfit-v1"


def runs(data: dict[str, Any], round: int) -> list[ValueRun]:
    np = _numpy()
    result = []
    for seed in sorted(set(int(i) for i in data["world"])):
        mask = data["world"] == seed
        targets = np.unique(data["target"][mask])
        if len(targets) != 1:
            raise ValueError("One complete training game must have one return")
        result.append(
            ValueRun(
                seed,
                round,
                float(targets[0]),
                tuple(tuple(float(x) for x in row) for row in data["coarse"][mask]),
                tuple(float(x) for x in data["potential"][mask]),
                tuple(float(x) for x in data["behavior_value"][mask]),
                tuple(int(x) for x in data["choices"][mask]),
            )
        )
    return result


def forecasts(
    data: dict[str, Any],
    names: list[str],
    round: int,
    directory: Path,
    deadline: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replay the exact existing folds; fit only typed, independently shrunk extras.

    The cache may index held-only names, but only fitting-observed columns enter
    each fold's model or normalization. No held target selects columns or lambda.
    """
    np = _numpy()
    source = runs(data, round)
    owners = fold_assignment(source, 4, SALT)
    predictions = {k: np.full(len(data["world"]), np.nan) for k in (*METHODS, "constant")}
    fold_rows, coarse_reports = [], []
    for fold in range(4):
        fitting = [r for r in source if owners[r.seed] != fold]
        held = [r for r in source if owners[r.seed] == fold]
        baseline = fit_baseline(fitting, "public_residual_ridge", 0.001)
        constant = fit_baseline(fitting, "constant", 1.0)
        train = np.asarray([owners[int(s)] != fold for s in data["world"]])
        for run in held:
            mask = data["world"] == run.seed
            predictions["current"][mask] = baseline.predict(run)
            predictions["constant"][mask] = constant.predict(run)
        coarse_reports.append(
            {**baseline.as_dict(), "fold": fold, "predicted_runs": [r.seed for r in held]}
        )
        variants = {}
        for method in METHODS[1:]:
            categories = ("deck/", "relic/") if method == "deck_relic" else (method + "/",)
            allowed = np.asarray([n.startswith(categories) for n in names])
            observed = np.any(data["inventory_present"][train], axis=0)
            indices = np.flatnonzero(allowed & observed)
            # A constant zero column lets the unchanged correction solver represent
            # genuinely empty fitting vocabularies without admitting a held-only name.
            extra = data["inventory"][:, indices] if len(indices) else np.zeros((len(train), 1))
            inputs = np.column_stack((data["coarse"], extra))
            selected = train & (data["choices"] > 1)
            partition = ValuePartition(
                inputs[selected],
                data["target"][selected],
                data["potential"][selected],
                tuple(int(i) for i in data["world"][selected]),
            )
            models, fitted = correction_path(partition, (PENALTY,), deadline)
            model = models[1]
            if model.baseline.as_dict() != baseline.as_dict():
                raise ValueError("Inventory fitting changed the original coarse baseline")
            raw = model.forecast(inputs, data["potential"])
            prediction = np.clip(raw, 0, 1)
            predictions[method][~train] = prediction[~train]
            path = directory / f"fold-{fold}-{method}.npz"
            with path.open("xb") as handle:
                np.savez_compressed(handle, indices=indices, **model.arrays())
            novel = allowed & ~observed
            variants[method] = {
                **fitted[1],
                "fitting_columns": len(indices),
                "held_only_columns": int(
                    np.any(data["inventory_present"][~train][:, novel], axis=0).sum()
                ),
                "held_rows_with_unfamiliar_features": int(
                    np.any(data["inventory_present"][~train][:, novel], axis=1).sum()
                ),
                "held_worlds_with_unfamiliar_features": sorted(
                    set(
                        int(g)
                        for g in data["world"][~train][
                            np.any(data["inventory_present"][~train][:, novel], axis=1)
                        ]
                    )
                ),
            }
        fold_rows.append(
            {
                "fold": fold,
                "fitting_worlds": baseline.fitting_runs,
                "held_worlds": [r.seed for r in held],
                "variants": variants,
            }
        )
    if any(not np.isfinite(p).all() for p in predictions.values()):
        raise ValueError("Missing out-of-fold predictions")
    choice = data["choices"] > 1
    report = {
        "coarse_folds": coarse_reports,
        "folds": fold_rows,
        "prediction": paired_errors(
            [int(i) for i in data["world"][choice]],
            data["target"][choice],
            {k: p[choice] for k, p in predictions.items()},
        ),
        "current_prediction_metrics": prediction_metrics(
            source,
            {
                r.seed: tuple(float(v) for v in predictions["current"][data["world"] == r.seed])
                for r in source
            },
        ),
        "fixed_inventory_penalty": PENALTY,
        "hyperparameters_selected_on_held_games": False,
        "coarse_coefficients_and_regularization_preserved": True,
        "state_only_predictions_not_action_rankings": True,
        "production_candidate_selected": False,
    }
    return predictions, report


def _moments(values: Any) -> dict[str, Any]:
    np = _numpy()
    if not len(values):
        return {"rows": 0, "mean": None, "std": None, "positive_fraction": None}
    return {
        "rows": len(values),
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "positive_fraction": float(np.mean(values > 0)),
    }


def credit_diagnostics(data: dict[str, Any], predictions: dict[str, Any]) -> dict[str, Any]:
    """Exact derivative w.r.t. the selected logit at the behavior policy, data loss only.

    This is NOT a full parameter gradient, entropy/Adam update, importance ratio
    after fitting, or an assessment of which chosen actions were actually correct.
    """
    np = _numpy()
    choice = data["choices"] > 1
    probability = np.exp(data["log_probability"])
    if np.any(probability <= 0) or np.any(probability > 1 + 1e-12):
        raise ValueError("Invalid sealed sampled probability")
    raw, normalized, coefficients = {}, {}, {}
    for method in METHODS:
        a = data["target"] - predictions[method]
        mean = math.fsum(float(v) for v in a) / len(a)
        std = math.sqrt(math.fsum((float(v) - mean) ** 2 for v in a) / len(a))
        z = (a - mean) / max(std, 1e-8) if std > 1e-8 else np.zeros_like(a)
        raw[method], normalized[method] = a, z
        coefficients[method] = np.where(choice, z * (1 - probability) / 0.8, 0.0)

    def group(mask: Any) -> dict[str, Any]:
        return {
            "decisions": int(mask.sum()),
            "choice_decisions": int((mask & choice).sum()),
            "methods": {
                m: {
                    "raw_credit": _moments(raw[m][mask & choice]),
                    "normalized_credit": _moments(normalized[m][mask & choice]),
                    "chosen_logit_ascent_coefficient": _moments(coefficients[m][mask & choice]),
                    "normalized_credit_sign_flip_vs_current": (
                        float(
                            np.mean(
                                np.sign(normalized[m][mask & choice])
                                != np.sign(normalized["current"][mask & choice])
                            )
                        )
                        if np.any(mask & choice)
                        else None
                    ),
                }
                for m in METHODS
            },
        }

    return {
        "whole_batch": group(np.ones(len(choice), dtype=bool)),
        "families": {str(f): group(data["family"] == f) for f in sorted(set(data["family"]))},
        "production_raw_advantage_mean": math.fsum(float(v) for v in raw["current"]) / len(choice),
        "production_raw_advantage_std": float(np.std(raw["current"])),
        "normalization": "same_entire_non_navigation_training_batch_as_production",
        "coefficient_definition": (
            "normalized_advantage_times_one_minus_selected_probability_divided_by_temperature"
        ),
        "temperature": 0.8,
        "chosen_logit_coefficients_are_unaveraged_per_decision": True,
        "parameter_gradients_or_optimizer_updates_computed": False,
        "counterfactual_action_returns_available": False,
        "better_action_credit_not_established_by_sign_changes": True,
    }
