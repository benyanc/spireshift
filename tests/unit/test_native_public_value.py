from __future__ import annotations

import time

import numpy as np
import pytest

from spireshift.native_public_value import (
    fit_value,
    game_weights,
    initialize,
    loss_gradient,
    paired_errors,
)
from spireshift.native_public_value_study import SETTINGS


def test_nonlinear_value_gradient_matches_finite_difference() -> None:
    p = initialize(3, 4, 8)
    p["output"][:] = [0.2, -0.1, 0.3, -0.2]
    x = np.asarray([[0.1, 0.3, -0.2], [0.3, 0.7, 0.8]])
    y, w = np.asarray([0.1, 0.8]), np.asarray([0.4, 0.6])
    _, g = loss_gradient(p, x, y, w, 0.002)
    for key, index in (("input", (2, 1)), ("bias", (2,)), ("output", (1,)), ("intercept", (0,))):
        delta = 1e-6
        p[key][index] += delta
        plus = loss_gradient(p, x, y, w, 0.002)[0]
        p[key][index] -= 2 * delta
        minus = loss_gradient(p, x, y, w, 0.002)[0]
        p[key][index] += delta
        assert g[key][index] == pytest.approx((plus - minus) / (2 * delta), abs=1e-8)


def test_whole_game_mass_does_not_grow_with_game_length() -> None:
    weights = game_weights([1] * 9 + [2])
    assert sum(weights[:9]) == pytest.approx(0.5) and weights[9] == 0.5
    errors = paired_errors(
        [1] * 9 + [2], np.zeros(10), {"predictor": np.asarray([0.1] * 9 + [0.9])}
    )
    assert errors["mse"]["predictor"] == pytest.approx((0.1**2 + 0.9**2) / 2)


def test_rich_features_can_learn_interaction_missing_from_coarse_counts() -> None:
    # Synthetic identity interaction, invented outcomes, never native action labels.
    x = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]] * 4, dtype=float)
    y = np.asarray([0.1, 0.3, 0.3, 0.1] * 4)
    c = np.ones((16, 1))
    model, result = fit_value(
        x,
        c,
        np.zeros(16),
        y,
        list(range(16)),
        (0.2,),
        {**SETTINGS, "epochs": 200, "learning_rate": 0.02, "l2": 0.000001},
        0,
        time.monotonic() + 10,
    )
    predictions = model.predict(x[:4], c[:4], np.zeros(4), [20, 21, 22, 23])
    assert np.square(predictions - y[:4]).mean() < 1e-5
    assert result["final_regularized_fit_loss"] < result["initial_regularized_fit_loss"]
    with pytest.raises(ValueError, match="own fitting game"):
        model.predict(x[:1], c[:1], np.zeros(1), [0])
    with pytest.raises(TimeoutError):
        fit_value(x, c, np.zeros(16), y, list(range(16)), (0.2,), SETTINGS, 0, 0)


def test_standardization_is_fitting_only_and_outputs_remain_bounded() -> None:
    x = np.asarray([[0.0], [1.0]])
    c = np.ones((2, 1))
    model, _ = fit_value(
        x,
        c,
        np.zeros(2),
        np.asarray([0.1, 0.2]),
        [1, 2],
        (0.15,),
        SETTINGS,
        0,
        time.monotonic() + 10,
    )
    mean = model.mean.copy()
    p = model.predict(np.asarray([[1e6], [-1e6]]), c, np.zeros(2), [3, 4])
    assert np.array_equal(mean, model.mean) and np.all((p >= 0) & (p <= 1))
