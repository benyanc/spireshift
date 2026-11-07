from __future__ import annotations

import time
from typing import Any

import numpy as np
import pytest

from spireshift.native_linear_value import (
    ARMS,
    REGULARIZATION,
    fit_path,
    nested_pair,
    select_regularization,
    subset,
    whole_game_folds,
)
from spireshift.native_matched_value import ValuePartition
from spireshift.native_public_value import game_weights


def data() -> ValuePartition:
    rng = np.random.default_rng(123)
    owners = np.repeat(np.arange(32), 4)
    x = rng.normal(0, 0.05, (len(owners), 24))
    x[:, 0] = 1
    x[:, 20] = np.repeat(np.linspace(-1, 1, 32), 4)
    y = 0.4 + 0.2 * x[:, 20]
    return ValuePartition(x, y, np.full(len(y), 0.01), tuple(int(i) for i in owners))


def deadline() -> float:
    return time.monotonic() + 20


def partitions() -> tuple[ValuePartition, ValuePartition]:
    d = data()
    mask = np.asarray([i % 4 != 0 for i in d.owners])
    return subset(d, mask), subset(d, ~mask)


def test_ridge_matches_direct_weighted_normal_equations_and_separate_loss() -> None:
    fitting, held = partitions()
    models, report = fit_path(fitting, (0.01,), "rich_linear", deadline())
    model = models[0]
    weights = np.asarray(game_weights(list(fitting.owners)))
    z = np.clip((fitting.inputs - model.mean) / model.scale, -4, 4) - model.center
    design = np.column_stack((np.ones(len(z)), z))
    penalty = np.diag([0] + [0.01] * z.shape[1])
    direct = np.linalg.solve(
        design.T @ (weights[:, None] * design) + penalty,
        design.T @ (weights * (fitting.targets - fitting.base)),
    )
    np.testing.assert_allclose(model.coefficients, direct[1:], atol=1e-12)
    assert model.intercept == pytest.approx(direct[0], abs=1e-12)
    fitting_error = float(weights @ np.square(design @ direct + fitting.base - fitting.targets))
    assert report[0]["fitting_mse"] == pytest.approx(fitting_error)
    assert report[0]["regularized_fitting_loss"] == pytest.approx(
        fitting_error + 0.01 * float(direct[1:] @ direct[1:])
    )
    assert report[0]["normal_equation_relative_residual"] < 1e-10
    assert model.predict(held).shape == held.targets.shape
    with pytest.raises(ValueError, match="own value credit"):
        model.predict(fitting)


def test_inner_folds_hold_whole_games_and_rich_identity_signal_can_generalize() -> None:
    fitting, held = partitions()
    models, _, report = nested_pair(fitting, held, REGULARIZATION, 3, "frozen", deadline())
    assert report["held"]["clipped"]["mse"]["rich_linear"] < 0.001
    assert (
        report["held"]["clipped"]["mse"]["rich_linear"]
        < report["held"]["clipped"]["mse"]["coarse_linear"]
    )
    for arm in ARMS:
        seen = []
        for fold in report["inner"][arm]:
            assert not set(fold["fitting_games"]) & set(fold["validation_games"])
            assert not (set(fold["fitting_games"]) | set(fold["validation_games"])) & set(
                held.owners
            )
            assert len(fold["fitting_games"]) == 16 and len(fold["validation_games"]) == 8
            seen.extend(fold["validation_games"])
        assert sorted(seen) == sorted(set(fitting.owners))
        assert models[arm].regularization in REGULARIZATION
    assert not report["fitted_outer_baseline_used_in_inner_folds"]


def test_outer_targets_and_inputs_never_change_selection_or_fitted_arrays() -> None:
    fitting, held = partitions()
    first, _, report = nested_pair(fitting, held, REGULARIZATION, 3, "frozen", deadline())
    changed = ValuePartition(held.inputs * 20, 1 - held.targets, held.base + 0.1, held.owners)
    second, _, other = nested_pair(fitting, changed, REGULARIZATION, 3, "frozen", deadline())
    assert report["inner"] == other["inner"]
    assert report["selected"] == other["selected"]
    for arm in ARMS:
        for name, value in first[arm].arrays().items():
            assert np.array_equal(value, second[arm].arrays()[name])


def test_every_inner_scaler_is_fitted_without_validation_games() -> None:
    fitting, _ = partitions()
    assignment = whole_game_folds(fitting.owners, 3, "frozen")
    mask = np.asarray([assignment[i] != 0 for i in fitting.owners])
    train, validation = subset(fitting, mask), subset(fitting, ~mask)
    model = fit_path(train, (0.1,), "rich_linear", deadline())[0][0]
    weights = np.asarray(game_weights(list(train.owners)))
    np.testing.assert_allclose(model.mean, weights @ train.inputs)
    assert not set(model.fitting_games) & set(validation.owners)
    assert not np.allclose(
        model.mean, np.asarray(game_weights(list(fitting.owners))) @ fitting.inputs
    )


def test_equal_game_mass_is_invariant_to_repeating_one_games_rows() -> None:
    fitting, _ = partitions()
    index = np.concatenate((np.arange(len(fitting.owners)), np.repeat(np.arange(4), 20)))
    repeated = subset(fitting, index)
    for arm in ARMS:
        original = fit_path(fitting, (0.1,), arm, deadline())[0][0]
        enlarged = fit_path(repeated, (0.1,), arm, deadline())[0][0]
        np.testing.assert_allclose(original.mean, enlarged.mean, atol=1e-12)
        np.testing.assert_allclose(original.coefficients, enlarged.coefficients, atol=1e-12)
        assert original.intercept == pytest.approx(enlarged.intercept, abs=1e-12)


def test_coarse_arm_masks_extra_columns_and_intercept_is_unpenalized() -> None:
    fitting, _ = partitions()
    constant = ValuePartition(
        fitting.inputs, np.full(len(fitting.owners), 0.6), fitting.base, fitting.owners
    )
    for arm in ARMS:
        model = fit_path(constant, (100.0,), arm, deadline())[0][0]
        assert model.intercept == pytest.approx(0.59)
        np.testing.assert_allclose(model.coefficients, 0, atol=1e-14)
    model = fit_path(fitting, (0.001,), "coarse_linear", deadline())[0][0]
    assert not np.any(model.coefficients[20:])


def test_lambda_selection_weights_games_and_breaks_exact_ties_toward_shrinkage() -> None:
    def row(games: list[int], errors: list[float]) -> dict[str, Any]:
        return {
            "validation_games": games,
            "path": [
                {"regularization": v, "validation_clipped_mse": e}
                for v, e in zip((0.1, 1.0), errors, strict=True)
            ],
        }

    assert select_regularization([row([1, 2], [0.1, 0.1])], (0.1, 1.0)) == 1.0
    assert (
        select_regularization([row([1, 2], [0.0, 0.3]), row([3, 4, 5, 6], [0.4, 0.1])], (0.1, 1.0))
        == 1.0
    )
    with pytest.raises(ValueError, match="Incomplete"):
        select_regularization([], (0.1, 1.0))


def test_rejects_leaking_owners_nonfinite_inputs_and_missed_deadline() -> None:
    fitting, held = partitions()
    with pytest.raises(ValueError, match="disjoint complete"):
        nested_pair(fitting, fitting, REGULARIZATION, 3, "x", deadline())
    with pytest.raises(TimeoutError):
        fit_path(fitting, REGULARIZATION, "rich_linear", 0)
    invalid = fitting.inputs.copy()
    invalid[0, 0] = np.nan
    with pytest.raises(ValueError, match="finite complete"):
        fit_path(
            ValuePartition(invalid, fitting.targets, fitting.base, fitting.owners),
            REGULARIZATION,
            "rich_linear",
            deadline(),
        )
    with pytest.raises(ValueError, match="positive ridge grid"):
        fit_path(fitting, (0.0,), "rich_linear", deadline())
    with pytest.raises(ValueError, match="two complete games"):
        whole_game_folds(held.owners, 5, "x")
