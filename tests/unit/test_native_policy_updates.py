from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, cast

import pytest
from test_native_consequence_math import state

from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax
from spireshift.native_policy_updates import SETTINGS, gradient, qualify, update


def examples(m: Any) -> list[Sample]:
    rows = ({0: 1.0, 1: 1.0}, {0: 1.0, 2: 1.0})
    logs = log_softmax(score_features(m.actor, rows), 0.8)
    value = (1.0, *([0.0] * (len(m.value_weights) - 1)))
    return [Sample(rows, value, 0, logs[0], 0.03, 1), Sample(rows, value, 1, logs[1], 0.01, -1)]


def test_signed_gradient_derivatives_and_separation_checks_pass_without_mutation() -> None:
    m, adam = state()
    before = m.as_dict(), adam.as_dict()
    q = qualify(m, adam)
    assert q["passed"] and all(q["checks"].values())
    assert q["maximum_derivative_absolute_error"] < 1e-7
    assert q["production_optimizer_updates"] == 0
    assert q["signed_log_probability_changes"]["1"] > 0
    assert q["signed_log_probability_changes"]["-1"] < 0
    assert (m.as_dict(), adam.as_dict()) == before


@pytest.mark.parametrize("advantage", [0.0, 0.00001, 1.0, -1.0])
def test_constant_centered_credit_does_not_advance_warm_momentum(advantage: float) -> None:
    m, adam = state()
    samples = [replace(s, advantage=advantage) for s in examples(m)]
    after, ao, report = update(m, adam, samples, 0)
    assert after is m and ao is adam and report["optimizer_steps"] == 0
    # Without the explicit skip, Adam can move parameters despite a zero new gradient.
    moved, _, _ = adam.update(
        cast(Any, m), [0.0] * m.parameter_count, actor_rate=0.001, value_rate=0, maximum_norm=1
    )
    assert moved.actor.as_dict() != m.actor.as_dict()


def test_real_policy_update_keeps_original_and_every_old_Adam_moment_read_only() -> None:
    m, adam = state()
    before = m.as_dict(), adam.as_dict()
    after, ao, work = update(m, adam, examples(m), 0)
    assert after.model_id != m.model_id
    assert ao.steps == adam.steps + work["optimizer_steps"] and work["optimizer_steps"] > 0
    assert (m.as_dict(), adam.as_dict()) == before
    assert not work["actor_scores_regressed_onto_return_labels"]
    assert not work["independent_action_conditional_predictor_used_as_baseline"]
    assert work["all_actor_layers_and_decision_types_mutable"]
    # Continuation is reproducible from the same complete saved state.
    repeated, repeated_Adam, _ = update(
        m, Adam.from_mapping(adam.as_dict(), m.parameter_count), examples(m), 0
    )
    assert repeated.as_dict() == after.as_dict() and repeated_Adam == ao


@pytest.mark.parametrize("target", [0.0, 0.3, 1.0])
def test_outcome_target_does_not_become_an_absolute_action_score_target(target: float) -> None:
    m, _ = state()
    s = examples(m)[0]
    a = gradient(m, [s], value=0.5)[1]
    b = gradient(m, [replace(s, target=target)], value=0.5)[1]
    assert a[: m.actor.parameter_count] == b[: m.actor.parameter_count]
    assert all(
        v == 0
        for v in gradient(m, [replace(s, advantage=0)], value=0.5)[1][: m.actor.parameter_count]
    )


@pytest.mark.parametrize(
    "ratio,sign,clipped", [(1.5, 1, True), (0.5, -1, True), (0.5, 1, False), (1.5, -1, False)]
)
def test_clipping_stops_only_the_disallowed_policy_direction(
    ratio: float, sign: int, clipped: bool
) -> None:
    m, _ = state()
    s = examples(m)[0]
    s = replace(s, old_log_probability=s.old_log_probability - math.log(ratio), advantage=sign)
    _, g, report = gradient(m, [s])
    assert (report["clipped_fraction"] == 1) is clipped
    assert all(v == 0 for v in g) is clipped


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_credit_is_never_a_silent_no_update(bad: float) -> None:
    m, adam = state()
    with pytest.raises(ValueError, match="finite"):
        update(m, adam, [replace(examples(m)[0], advantage=bad)], 0)


def test_the_frozen_trial_does_not_add_proximity_or_actor_return_regression_loss() -> None:
    assert SETTINGS["epochs"] == 3 and SETTINGS["temperature"] == 0.8
    assert SETTINGS["value_coefficient"] == 0.5
    assert not {"l2", "auxiliary_weight", "baseline_proximity"} & SETTINGS.keys()
