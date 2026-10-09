from __future__ import annotations

import math

import pytest
from test_full_run_public_policy import CATALOG, MenuRun, environment

from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import (
    ActorCritic,
    Adam,
    Sample,
    fit_round,
    initialize_critic,
    log_softmax,
    loss_gradient,
)
from spireshift.full_run_public_policy import initial_public_full_run_model


def model() -> ActorCritic:
    env = environment(MenuRun())
    actor = initial_public_full_run_model(
        env.ruleset, CATALOG, "a" * 64, dimension=128, hidden_units=4
    )
    return initialize_critic(actor)


def samples(source: ActorCritic) -> list[Sample]:
    rows = ({0: 1.0, 1: 0.4, 62: 0.7}, {0: 1.0, 2: 0.5, 66: -0.3})
    logs = log_softmax(score_features(source.actor, rows), 0.7)
    state = (1.0, *([0.0] * 127), 1.0)
    return [Sample(rows, state, 0, logs[0], 1.0, 0.8), Sample(rows, state, 1, logs[1], 0.0, -0.6)]


def loss(
    source: ActorCritic, rows: list[Sample]
) -> tuple[float, tuple[float, ...], dict[str, float]]:
    return loss_gradient(
        source, rows, clip=0.2, entropy_coefficient=0.013, value_coefficient=0.5, temperature=0.7
    )


def test_actor_and_critic_backprop_matches_numerical_derivatives() -> None:
    source, epsilon = model(), 1e-5
    data = samples(source)
    _, analytic, _ = loss(source, data)
    n, h = source.actor.dimension, source.actor.hidden_units
    coordinates = [
        1,
        62,
        n + 2,
        n * h,
        n * h + h,
        n * h + 2 * h + 2,
        source.actor.parameter_count,
        source.parameter_count - 1,
    ]
    for index in coordinates:
        plus, minus = list(source.weights()), list(source.weights())
        plus[index] += epsilon
        minus[index] -= epsilon
        numeric = (
            loss(source.with_weights(plus), data)[0] - loss(source.with_weights(minus), data)[0]
        ) / (2 * epsilon)
        assert analytic[index] == pytest.approx(numeric, rel=1e-5, abs=1e-8)


@pytest.mark.parametrize("advantage,ratio", [(1.0, 1.5), (-1.0, 0.5)])
def test_ppo_clipped_branch_stops_policy_gradient(advantage: float, ratio: float) -> None:
    source = model()
    s = samples(source)[0]
    clipped = Sample(
        s.rows, s.state, s.action, s.old_log_probability - math.log(ratio), s.target, advantage
    )
    _, gradient, diagnostic = loss_gradient(
        source, [clipped], clip=0.2, entropy_coefficient=0, value_coefficient=0, temperature=0.7
    )
    assert all(v == 0 for v in gradient)
    assert diagnostic["clipped_fraction"] == 1


def test_sampled_return_changes_every_actor_layer_and_value_then_resumes_exactly() -> None:
    source = model()
    settings = {
        "epochs": 2,
        "minibatch_decisions": 2,
        "clip": 0.2,
        "entropy_coefficient": 0.005,
        "value_coefficient": 0.5,
        "temperature": 0.7,
        "actor_learning_rate": 0.001,
        "value_learning_rate": 0.005,
        "gradient_clip": 5.0,
        "target_kl": 0.2,
    }
    initial_probability = math.exp(
        log_softmax(score_features(source.actor, samples(source)[0].rows), 0.7)[0]
    )
    updated, optimizer, report = fit_round(
        source, Adam.zero(source.parameter_count), samples(source), settings, 0
    )
    final_probability = math.exp(
        log_softmax(score_features(updated.actor, samples(source)[0].rows), 0.7)[0]
    )
    assert final_probability > initial_probability
    n, h = source.actor.dimension, source.actor.hidden_units
    cuts = (
        0,
        n * h,
        n * h + h,
        n * h + 2 * h,
        source.actor.parameter_count,
        source.parameter_count,
    )
    assert all(
        any(a != b for a, b in zip(source.weights()[i:j], updated.weights()[i:j], strict=True))
        for i, j in zip(cuts[:-1], cuts[1:], strict=True)
    )
    assert report["baseline_proximity_penalty"] == 0
    assert report["optimizer_steps"] == optimizer.steps == 2
    decoded = ActorCritic.from_mapping(updated.as_dict())
    restored = Adam.from_mapping(optimizer.as_dict(), updated.parameter_count)
    first = fit_round(updated, optimizer, samples(updated), settings, 1)
    resumed = fit_round(decoded, restored, samples(decoded), settings, 1)
    assert first == resumed


def test_nonfinite_and_mismatched_models_or_optimizer_are_rejected() -> None:
    source = model()
    d = source.as_dict()
    d["value_weights"][0] = float("nan")
    with pytest.raises(ValueError):
        ActorCritic.from_mapping(d)
    with pytest.raises(ValueError):
        Adam.from_mapping({"steps": 0, "first": [0], "second": [-1]}, 1)
    with pytest.raises(ValueError):
        log_softmax([float("inf"), 0])
