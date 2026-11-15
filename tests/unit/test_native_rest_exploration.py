from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_shop_policy import action, shop

from spireshift.full_run_ppo_math import (
    Adam,
)
from spireshift.full_run_ppo_math import (
    fit_round as original_fit,
)
from spireshift.full_run_ppo_math import (
    loss_gradient as original_gradient,
)
from spireshift.native_action_context import policy
from spireshift.native_conditional_control import TASK
from spireshift.native_exploration_math import fit_round, loss_gradient
from spireshift.native_learning_control import public_input
from spireshift.native_rest_exploration import Sample, choose, mixed_logs, verified_samples
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_shop_policy import choose as original_choose


def rest() -> dict[str, Any]:
    p = public_input(TASK, False)
    p["context"]["interaction"]["kind"] = "rest_site"
    p["candidates"] = [action("Rest"), action("Smith"), action("Leave rest site", "close")]
    return p


def test_uniform_floor_preserves_every_legal_option_even_under_extreme_logits() -> None:
    q = mixed_logs((0.0, -1000.0, -1000.0), 0.2)
    assert sum(math.exp(x) for x in q) == pytest.approx(1.0)
    assert all(math.exp(x) >= 0.2 / 3 - 1e-15 for x in q)
    assert mixed_logs((0.0, -1000.0), 0) == (0.0, -1000.0)


@pytest.mark.parametrize("surface", [rest(), public_input(TASK, False), shop(False, False)])
def test_standard_actions_reproduce_original_and_only_rest_mixes(surface: dict[str, Any]) -> None:
    m = model()
    s = score()
    for seed in range(12):
        old = original_choose(m, s, surface, ShopNavigation(), random.Random(seed), 0.8)
        ordinary = choose(m, s, surface, ShopNavigation(), random.Random(seed), 0.8, 0.0)
        assert old["action_index"] == ordinary["action_index"]
        assert old["log_probability"] == ordinary["log_probability"]
        mixed = choose(m, s, surface, ShopNavigation(), random.Random(seed), 0.8, 0.2)
        assert mixed["exploration_epsilon"] == (
            0.2 if surface["context"]["interaction"]["kind"] == "rest_site" else 0.0
        )
        assert 0 <= mixed["action_index"] < len(surface["candidates"])


@pytest.mark.parametrize("fault", [None, "epsilon", "probability", "partial", "contract"])
def test_behavior_reconstruction_rejects_stale_or_invented_mixture(fault: str | None) -> None:
    p = rest()
    m = model()
    s = score()
    c = choose(m, s, p, ShopNavigation(), random.Random(9), 0.8, 0.2)
    case = {
        "status": "terminal",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": [{"public_input": p, "choice": c}],
    }
    if fault == "epsilon":
        c["exploration_epsilon"] = 0.0
    if fault == "probability":
        c["log_probability"] += 0.1
    if fault == "partial":
        case["status"] = "failed"
    if fault == "contract":
        c["policy_contract"] = "wrong"
    if fault:
        with pytest.raises(ValueError):
            verified_samples(case, m, s, 0.03, 0.8, 0.2)
    else:
        samples, _ = verified_samples(case, m, s, 0.03, 0.8, 0.2)
        assert samples[0].epsilon == 0.2
        with pytest.raises(ValueError):
            verified_samples(case, m, s, 0.03, 0.8, 0.0)


def samples() -> tuple[Any, list[Sample]]:
    m = model()
    s = score()
    rows, state, logs = policy(rest(), m, s, 0.8)
    return m, [
        Sample(rows, state, 1, mixed_logs(logs, 0.2)[1], 0.1, 0.04, 0.2),
        Sample(rows, state, 0, logs[0], 0.02, -0.03, 0.0),
    ]


def test_mixed_PPO_and_entropy_derivatives_match_finite_differences() -> None:
    m, ss = samples()
    settings = {
        "clip": 0.2,
        "entropy_coefficient": 0.015,
        "value_coefficient": 0.5,
        "temperature": 0.8,
    }
    _, g, _ = loss_gradient(m, ss, **settings)
    weights = list(m.weights())
    # Include hidden, linear, output and critic parameters, including nonzero derivatives.
    chosen = sorted(
        set(
            [
                0,
                len(weights) - 1,
                *sorted(range(len(g)), key=lambda i: abs(g[i]), reverse=True)[:12],
            ]
        )
    )
    for i in chosen:
        plus = weights.copy()
        minus = weights.copy()
        plus[i] += 1e-5
        minus[i] -= 1e-5
        numeric = (
            loss_gradient(m.with_weights(plus), ss, **settings)[0]
            - loss_gradient(m.with_weights(minus), ss, **settings)[0]
        ) / 2e-5
        assert g[i] == pytest.approx(numeric, rel=1e-4, abs=1e-7)


def test_zero_mixture_kernel_and_fitted_weights_equal_original_exactly() -> None:
    m, ss = samples()
    zero = [replace(s, epsilon=0.0) for s in ss]
    _, _, logs = policy(rest(), m, score(), 0.8)
    zero = [replace(s, old_log_probability=logs[s.action]) for s in zero]
    kw = {"clip": 0.2, "entropy_coefficient": 0.015, "value_coefficient": 0.5, "temperature": 0.8}
    assert loss_gradient(m, zero, **kw) == original_gradient(m, zero, **kw)
    settings = {
        **kw,
        "epochs": 2,
        "minibatch_decisions": 2,
        "actor_learning_rate": 0.001,
        "value_learning_rate": 0.001,
        "gradient_clip": 5.0,
        "target_kl": 0.02,
    }
    initial = Adam(5, tuple([0.01] * m.parameter_count), tuple([0.1] * m.parameter_count))
    ours, adam, _ = fit_round(m, initial, zero, settings, 57)
    original, old_adam, _ = original_fit(m, initial, zero, settings, 57)
    assert ours.as_dict() == original.as_dict() and adam == old_adam
    assert adam.steps > initial.steps and initial.steps == 5
