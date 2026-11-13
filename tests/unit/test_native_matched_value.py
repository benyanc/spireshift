from __future__ import annotations

import dataclasses
import time

import numpy as np
import pytest

from spireshift.native_matched_value import (
    ARMS,
    SETTINGS,
    ValuePartition,
    errors,
    fit_pair,
    standardized,
)


def examples(start: int) -> ValuePartition:
    identity = np.asarray([-1, 1] * 8, dtype=float)
    x = np.column_stack((np.ones(16), identity, identity * 0.3))
    return ValuePartition(
        x, 0.2 + identity * 0.05, np.full(16, 0.2), tuple(range(start, start + 16))
    )


def test_same_network_learns_rich_signal_with_identical_coarse_measurements() -> None:
    models, predictions, result = fit_pair(
        examples(0), examples(20), 1, SETTINGS, (0, 24, 96), 9, time.monotonic() + 10
    )
    a, b = (result["arms"][name] for name in ARMS)
    assert a["parameter_count"] == b["parameter_count"]
    assert a["initial_parameter_sha256"] == b["initial_parameter_sha256"]
    assert a["input_dimension"] == b["input_dimension"] == 3
    assert np.array_equal(predictions["coarse_masked_step_0"], predictions["rich_step_0"])
    assert b["curve"][-1]["held_mse"] < a["curve"][-1]["held_mse"] / 10
    assert models["coarse_masked"]["input_mask"].tolist() == [1, 0, 0]
    assert models["rich"]["input_mask"].tolist() == [1, 1, 1]
    assert result["actor_optimizer_steps"] == 0 and not result["best_step_selected"]


def test_zero_extras_make_both_arms_identical_through_every_update() -> None:
    fitting, held = examples(0), examples(20)
    fitting.inputs[:, 1:] = 0
    held.inputs[:, 1:] = 0
    models, predictions, result = fit_pair(
        fitting, held, 1, {**SETTINGS, "epochs": 4}, (0, 1, 4), 5, time.monotonic() + 10
    )
    assert result["arms"]["coarse_masked"]["curve"] == result["arms"]["rich"]["curve"]
    for key in ("input", "output", "bias", "intercept", "adam_mean_input", "adam_square_output"):
        assert np.array_equal(models["coarse_masked"][key], models["rich"][key])
    for step in (0, 1, 4):
        assert np.array_equal(
            predictions[f"coarse_masked_step_{step}"], predictions[f"rich_step_{step}"]
        )


def test_curves_separate_prediction_error_penalty_and_clipping() -> None:
    _, _, result = fit_pair(
        examples(0), examples(20), 1, {**SETTINGS, "epochs": 4}, (0, 1, 4), 5, time.monotonic() + 10
    )
    for name in ARMS:
        assert [p["step"] for p in result["arms"][name]["curve"]] == [0, 1, 4]
        for row in result["arms"][name]["curve"]:
            assert row["regularized_fitting_loss"] == pytest.approx(
                row["fitting_mse"] + row["weight_penalty"]
            )
            assert row["fitting_clipped_mse"] <= row["fitting_mse"] + 1e-15
            assert row["held_clipped_mse"] <= row["held_mse"] + 1e-15
    part = ValuePartition(np.ones((2, 2)), np.asarray([0.0, 1.0]), np.zeros(2), (0, 1))
    measured = errors(np.asarray([-2.0, 3.0]), part)
    assert measured == {"mse": 4.0, "clipped_mse": 0.0}


def test_held_targets_never_influence_weights_normalization_or_fitting_curves() -> None:
    fitting, held = examples(0), examples(20)
    changed = dataclasses.replace(held, targets=1 - held.targets)
    a, _, ra = fit_pair(
        fitting, held, 1, {**SETTINGS, "epochs": 4}, (0, 4), 5, time.monotonic() + 10
    )
    b, _, rb = fit_pair(
        fitting, changed, 1, {**SETTINGS, "epochs": 4}, (0, 4), 5, time.monotonic() + 10
    )
    for arm in ARMS:
        for key in a[arm]:
            assert np.array_equal(a[arm][key], b[arm][key])
        for pa, pb in zip(ra["arms"][arm]["curve"], rb["arms"][arm]["curve"], strict=True):
            assert pa["fitting_mse"] == pb["fitting_mse"]
            assert pa["held_mse"] != pb["held_mse"]
    extreme = dataclasses.replace(held, inputs=held.inputs * 1e6)
    *_, ma, sa = standardized(fitting, held, 1)
    *_, mb, sb = standardized(fitting, extreme, 1)
    assert np.array_equal(ma, mb) and np.array_equal(sa, sb)


def test_game_mass_and_whole_game_boundaries() -> None:
    p = ValuePartition(np.zeros((10, 2)), np.zeros(10), np.zeros(10), (1,) * 9 + (2,))
    assert errors(np.asarray([0.1] * 9 + [0.9]), p)["mse"] == pytest.approx((0.1**2 + 0.9**2) / 2)
    with pytest.raises(ValueError, match="disjoint"):
        standardized(examples(0), examples(0), 1)
    with pytest.raises(ValueError, match="one observed return"):
        dataclasses.replace(examples(0), owners=(0, 0) + tuple(range(2, 16))).validate()
    with pytest.raises(ValueError, match="finite"):
        dataclasses.replace(examples(0), targets=np.full(16, np.nan)).validate()
    with pytest.raises(TimeoutError):
        fit_pair(examples(0), examples(20), 1, SETTINGS, (0, 24, 96), 9, 0)


@pytest.mark.parametrize("points", [(1, 4), (0, 4, 1), (0, 1, 1, 4), (0, 3)])
def test_invalid_snapshot_schedules_are_refused(points: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="fixed"):
        fit_pair(examples(0), examples(20), 1, {**SETTINGS, "epochs": 4}, points, 1, 0)
