from __future__ import annotations

import copy
import time
from typing import Any

import numpy as np
import pytest
from test_native_action_context import model

from spireshift.full_run_ppo_math import Adam
from spireshift.native_consequence_data import TARGETS
from spireshift.native_consequence_math import SETTINGS, fit, mathematical_controls, validate_arrays
from spireshift.native_context_cache import cached_model


def arrays() -> dict[str, Any]:
    rng = np.random.default_rng(5)
    x = rng.normal(0, 0.1, (12, 512))
    y = rng.normal(0, 0.1, (12, len(TARGETS)))
    y[:, 0] = np.linspace(0.01, 0.04, 12)
    y[:, 5] = np.asarray([0, 1] * 6)
    return {
        "inputs": x,
        "action_blind": x * 0.9,
        "targets": y,
        "mask": np.ones(y.shape, dtype=np.bool_),
        "owners": np.repeat([1, 2, 3, 4], 3),
        "plans": np.asarray(["a", "b", "b"] * 4),
        "potential": np.full(12, 0.01),
    }


def split() -> tuple[dict[str, Any], dict[str, Any]]:
    a = arrays()
    held = a["owners"] == 4
    return {k: v[~held] for k, v in a.items()}, {k: v[held] for k, v in a.items()}


def state() -> tuple[Any, Adam]:
    m = cached_model(model())
    return m, Adam(31, (0.0001,) * m.parameter_count, (0.001,) * m.parameter_count)


def run(arm: str, f: dict[str, Any], h: dict[str, Any], **extra: Any) -> tuple[Any, Any, Any, Any]:
    m, adam = state()
    return fit(
        m,
        adam,
        f,
        h,
        arm,
        20261022,
        time.monotonic() + 10,
        settings={**SETTINGS, "epochs": 3},
        **extra,
    )


def test_finite_difference_and_exact_encoder_stop_gradient_controls_pass() -> None:
    m, adam = state()
    proof = mathematical_controls(m, adam)
    assert proof["passed"] and proof["maximum_absolute_gradient_error"] < 1e-6
    assert proof["return_only_encoder_equals_return_loss_gradient"]
    assert proof["auxiliary_heads_identically_fitted_in_both_arms"]
    assert proof["auxiliary_gradient_reaches_hidden_encoder_only"]


@pytest.mark.parametrize("arm", ["return_only", "consequence", "action_blind"])
def test_forks_use_every_original_adam_moment_without_mutating_parents(arm: str) -> None:
    m, adam = state()
    original, original_adam = m.as_dict(), adam.as_dict()
    f, h = split()
    after, trained_adam, heads, report = fit(
        m,
        adam,
        f,
        h,
        arm,
        20261022,
        time.monotonic() + 10,
        settings={**SETTINGS, "epochs": 3},
    )
    assert m.as_dict() == original and adam.as_dict() == original_adam
    assert trained_adam.steps == 34 and report["initial_PPO_Adam_steps"] == 31
    assert after.model_id != m.model_id and report["original_PPO_Adam_moments_used_without_reset"]
    assert after.value_weights == m.value_weights and len(heads["head_first_bias"]) == 6
    assert heads["head_steps"].tolist() == [3]
    assert report["fitting_worlds"] == [1, 2, 3] and report["held_worlds"] == [4]
    assert not report["ordinary_PPO_eligible"] and not report["checkpoint_promoted"]


def test_held_labels_cannot_change_parameters_optimizer_normalization_or_fitting_curve() -> None:
    f, h = split()
    changed = copy.deepcopy(h)
    changed["targets"][:, 0] = 0.99
    changed["targets"][:, 1] = 50
    a, aa, ah, ar = run("consequence", f, h)
    b, ba, bh, br = run("consequence", f, changed)
    assert a.as_dict() == b.as_dict() and aa.as_dict() == ba.as_dict()
    assert all(np.array_equal(ah[k], bh[k]) for k in ah)
    assert [v["fitting"] for v in ar["curves"]] == [v["fitting"] for v in br["curves"]]
    assert ar["curves"][-1]["held"] != br["curves"][-1]["held"]


def test_zero_auxiliary_weight_is_an_exact_matched_optimizer_control() -> None:
    m, adam = state()
    f, h = split()
    result = [
        fit(
            m,
            adam,
            f,
            h,
            arm,
            20261022,
            time.monotonic() + 10,
            settings={**SETTINGS, "epochs": 3, "auxiliary_weight": 0.0},
        )
        for arm in ("return_only", "consequence")
    ]
    assert result[0][0].as_dict() == result[1][0].as_dict()
    assert result[0][1].as_dict() == result[1][1].as_dict()
    assert all(np.array_equal(result[0][2][k], result[1][2][k]) for k in result[0][2])


def test_source_game_leakage_is_rejected_even_for_different_plan_rows() -> None:
    f, h = split()
    h["owners"][:] = 1
    with pytest.raises(ValueError, match="source game"):
        run("consequence", f, h)


def test_missing_or_constant_fitting_heads_do_not_create_fabricated_feedback() -> None:
    f, h = split()
    f["mask"][:, 2] = False
    f["targets"][:, 6] = 0.0
    _, _, heads, report = run("consequence", f, h)
    assert heads["coefficients"][2] == heads["coefficients"][6] == 0
    assert "next_public_enemy_hp_sum_delta" not in report["active_auxiliary_heads"]
    assert "next_public_potion_count_delta" not in report["active_auxiliary_heads"]


@pytest.mark.parametrize("fault", ["nonfinite", "mask", "shape", "return", "alive"])
def test_bad_target_arrays_never_reach_optimizer(fault: str) -> None:
    a = arrays()
    if fault == "nonfinite":
        a["targets"][0, 1] = np.nan
    elif fault == "mask":
        a["mask"][0, 0] = False
    elif fault == "shape":
        a["inputs"] = a["inputs"][:, :10]
    elif fault == "return":
        a["targets"][0, 0] = 2
    else:
        a["targets"][0, 5] = 0.5
    with pytest.raises(ValueError, match="Invalid"):
        validate_arrays(a, 512)


def test_final_all_train_fork_has_no_held_outcome_selection() -> None:
    a = arrays()
    empty = {k: v[:0] for k, v in a.items()}
    _, _, _, report = run("consequence", a, empty, allow_no_held=True)
    assert not report["held_worlds"]
    assert not report["held_outcomes_used_for_fitting_or_epoch_selection"]
    assert report["curves"][-1]["held"][TARGETS[0]]["mse"] is None
    with pytest.raises(ValueError, match="unseen"):
        run("consequence", a, empty)


def test_finite_deadline_stops_without_mutating_original_optimizer_or_weights() -> None:
    m, adam = state()
    f, h = split()
    before, moments = m.as_dict(), adam.as_dict()
    with pytest.raises(TimeoutError):
        fit(m, adam, f, h, "consequence", 20261022, time.monotonic() - 1)
    assert m.as_dict() == before and adam.as_dict() == moments
