from __future__ import annotations

import time

import numpy as np
import pytest
from test_native_linear_value import partitions

from spireshift.native_linear_value import REGULARIZATION, SALT, subset, whole_game_folds
from spireshift.native_matched_value import ValuePartition, parameter_digest
from spireshift.native_public_value import game_weights
from spireshift.native_residual_value import (
    METHOD,
    CorrectedValue,
    coarse_fit,
    correction_path,
    nested_correction,
    select_correction,
)
from spireshift.native_value_credit import ValueRun, fit_baseline


def deadline() -> float:
    return time.monotonic() + 20


def test_off_reuses_the_exact_current_algorithm_and_separate_rich_penalty() -> None:
    fitting, held = partitions()
    owners = np.asarray(fitting.owners)
    runs = []
    for game in dict.fromkeys(fitting.owners):
        mask = owners == game
        runs.append(
            ValueRun(
                game,
                4,
                float(fitting.targets[mask][0]),
                tuple(tuple(float(x) for x in row) for row in fitting.inputs[mask, :20]),
                tuple(float(x) for x in fitting.base[mask]),
                (0.0,) * int(mask.sum()),
                (2,) * int(mask.sum()),
            )
        )
    original = fit_baseline(runs, "public_residual_ridge", 0.001)
    models, points = correction_path(fitting, (0.0001, 100.0), deadline())
    expected = held.base + held.inputs[:, :20] @ np.asarray(original.weights)
    assert np.array_equal(models[0].predict(held), expected)
    for model, point in zip(models, points, strict=True):
        assert model.baseline.as_dict() == original.as_dict()
        assert point["regularized_correction_loss"] == pytest.approx(
            point["fitting_mse"] + point["correction_penalty"]
        )
        restored = CorrectedValue.restore(model.arrays())
        assert np.array_equal(restored.predict(held), model.predict(held))
        assert parameter_digest(restored.arrays()) == point["parameter_digest"]
    weak, strong = models[1].correction, models[2].correction
    assert weak is not None and strong is not None
    assert not np.array_equal(weak.coefficients, strong.coefficients)
    # Disabling rich fitting must not even calculate a rich eigensystem.
    assert len(correction_path(fitting, (), deadline())[0]) == 1


def test_correction_matches_direct_ridge_on_residuals_and_uses_rich_only_columns() -> None:
    fitting, _ = partitions()
    models, reports = correction_path(fitting, (0.01,), deadline())
    rich = models[1].correction
    assert rich is not None and rich.intercept == 0.0
    weights = np.asarray(game_weights(list(fitting.owners)))
    z = np.clip((fitting.inputs[:, 20:] - rich.mean) / rich.scale, -4, 4) - rich.center
    residual = fitting.targets - models[0].forecast(fitting.inputs, fitting.base)
    direct = np.linalg.solve(
        z.T @ (weights[:, None] * z) + np.eye(z.shape[1]) * 0.01, z.T @ (weights * residual)
    )
    np.testing.assert_allclose(rich.coefficients, direct, atol=1e-12)
    assert len(rich.coefficients) == fitting.inputs.shape[1] - 20
    assert reports[1]["correction_penalty"] == pytest.approx(0.01 * float(direct @ direct))
    np.testing.assert_allclose(rich.mean, weights @ fitting.inputs[:, 20:])


def test_nested_whole_games_can_learn_a_useful_rich_signal() -> None:
    fitting, held = partitions()
    # Only the rich feature has the planted return signal; coarse input is constant.
    fitting.inputs[:, 1:20] = 0
    held.inputs[:, 1:20] = 0
    model, _, report = nested_correction(fitting, held, REGULARIZATION, 3, SALT, deadline())
    assert model.correction is not None
    assert report["held"]["clipped"]["mse"][METHOD] < (
        report["held"]["clipped"]["mse"]["current_ridge"] / 10
    )
    assignment = whole_game_folds(fitting.owners, 3, SALT)
    validations = []
    for inner in report["inner"]:
        mask = np.asarray([assignment[g] != inner["fold"] for g in fitting.owners])
        own_fit = subset(fitting, mask)
        assert inner["baseline"] == coarse_fit(own_fit).as_dict()
        assert len(inner["fitting_games"]) == 16 and len(inner["validation_games"]) == 8
        assert not set(inner["fitting_games"]) & set(inner["validation_games"])
        assert not set(inner["baseline"]["fitting_runs"]) & set(held.owners)
        validations.extend(inner["validation_games"])
    assert sorted(validations) == sorted(set(fitting.owners))
    assert not report["fitted_outer_baseline_used_in_inner_folds"]


def test_no_rich_signal_selects_off_and_ties_keep_the_baseline() -> None:
    fitting, held = partitions()
    x, y = fitting.inputs.copy(), held.inputs.copy()
    x[:, 20:], y[:, 20:] = 1, 1
    train = ValuePartition(x, fitting.targets, fitting.base, fitting.owners)
    validation = ValuePartition(y, held.targets, held.base, held.owners)
    model, predictions, report = nested_correction(
        train, validation, REGULARIZATION, 3, SALT, deadline()
    )
    assert model.correction is None and report["selected"]["regularization"] is None
    assert np.array_equal(predictions[METHOD], predictions["current_ridge"])
    assert report["selected"]["correction_penalty"] == 0
    paths = [{"regularization": v, "validation_clipped_mse": 0.1} for v in (None, 0.1, 1.0)]
    rows = [{"validation_games": [1, 2], "path": paths}]
    assert select_correction(rows, (0.1, 1.0)) == 0
    paths[0]["validation_clipped_mse"] = 0.2
    assert select_correction(rows, (0.1, 1.0)) == 2
    with pytest.raises(ValueError, match="Duplicate"):
        select_correction(rows * 2, (0.1, 1.0))


def test_held_inputs_and_answers_cannot_change_inner_fits_or_outer_parameters() -> None:
    fitting, held = partitions()
    first, _, report = nested_correction(fitting, held, REGULARIZATION, 3, SALT, deadline())
    x = held.inputs.copy()
    x[:, 1:] *= 50
    changed = ValuePartition(x, 1 - held.targets, held.base + 0.1, held.owners)
    second, _, other = nested_correction(fitting, changed, REGULARIZATION, 3, SALT, deadline())
    assert report["inner"] == other["inner"] and report["selected"] == other["selected"]
    assert parameter_digest(first.arrays()) == parameter_digest(second.arrays())


def test_one_longer_game_does_not_receive_more_training_weight() -> None:
    fitting, _ = partitions()
    expanded = subset(
        fitting, np.concatenate((np.arange(len(fitting.owners)), np.tile(np.arange(4), 20)))
    )
    original = correction_path(fitting, (0.1,), deadline())[0][1]
    repeated = correction_path(expanded, (0.1,), deadline())[0][1]
    assert original.correction is not None and repeated.correction is not None
    np.testing.assert_allclose(original.baseline.weights, repeated.baseline.weights, atol=1e-12)
    np.testing.assert_allclose(
        original.correction.coefficients, repeated.correction.coefficients, atol=1e-12
    )


def test_incomplete_nonfinite_overlapping_and_late_inputs_are_refused() -> None:
    fitting, held = partitions()
    with pytest.raises(ValueError, match="own value credit"):
        correction_path(fitting, (0.1,), deadline())[0][0].predict(fitting)
    with pytest.raises(ValueError, match="disjoint"):
        nested_correction(fitting, fitting, REGULARIZATION, 3, SALT, deadline())
    with pytest.raises(TimeoutError):
        correction_path(fitting, REGULARIZATION, 0)
    with pytest.raises(ValueError, match="positive"):
        correction_path(fitting, (0.0,), deadline())
    with pytest.raises(ValueError, match="positive"):
        nested_correction(fitting, held, (), 3, SALT, deadline())
    x = fitting.inputs.copy()
    x[:, 0] = 0
    with pytest.raises(ValueError, match="bias"):
        coarse_fit(ValuePartition(x, fitting.targets, fitting.base, fitting.owners))
    x[:, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        coarse_fit(ValuePartition(x, fitting.targets, fitting.base, fitting.owners))
