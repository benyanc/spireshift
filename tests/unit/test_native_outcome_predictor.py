from __future__ import annotations

import copy
import time
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from test_native_action_context import model, score
from test_native_consequence_math import split, state

from spireshift.native_action_context import ActionContextModel, policy
from spireshift.native_conditional_control import TASK
from spireshift.native_context_cache import cached_model
from spireshift.native_learning_control import public_input
from spireshift.native_outcome_predictor import (
    OutcomePredictor,
    PlayerWithPredictions,
    fit_predictor,
    gradient,
)


def fit(epochs: int = 3) -> tuple[Any, Any, Any]:
    f, h = split()
    return fit_predictor(
        cached_model(model()), f, h, 20261022, time.monotonic() + 15, epochs=epochs
    )


def test_fitting_changes_own_network_not_parent_weights_or_any_PPO_Adam_moment() -> None:
    m, adam = state()
    before, moments = m.as_dict(), adam.as_dict()
    f, h = split()
    p, optimizer, report = fit_predictor(m, f, h, 20261022, time.monotonic() + 15, epochs=3)
    assert m.as_dict() == before and adam.as_dict() == moments
    assert optimizer["steps"] == 3 and len(optimizer["first"]) == p.parameter_count
    assert len(optimizer["second"]) == p.parameter_count
    assert optimizer["scope"] == "new_prediction_parameters_only_not_parent_PPO_Adam"
    assert not report["parent_policy_changed"] and report["parent_PPO_Adam_updates"] == 0
    assert not report["used_for_action_selection"] and not report["ordinary_PPO_eligible"]
    assert p.parameter_count == 16647


def test_actions_probabilities_and_stateful_chooser_are_exact_after_prediction_fit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = cached_model(model())
    p, _, _ = fit()
    separate = PlayerWithPredictions(m, p)

    def forbidden(*_: Any, **__: Any) -> Any:
        raise AssertionError("Predictor was consulted during action selection")

    monkeypatch.setattr(OutcomePredictor, "predictions", forbidden)
    original = separate.chooser(score(), "FROZEN-NUMERIC-CONTROL", "greedy")
    from spireshift.native_combat_behavior_policy import Chooser

    reference = Chooser(m, score(), "FROZEN-NUMERIC-CONTROL", "greedy")
    for high in (False, True, False):
        public = public_input(TASK, high)
        public["context"]["persistent"]["run"]["act_definition_id"] = "UNDERDOCKS"
        assert separate.action_policy(public, score(), 0.8) == policy(public, m, score(), 0.8)
        assert original(public) == reference(public)


def test_large_prediction_changes_never_change_policy_outputs() -> None:
    m = cached_model(model())
    p, _, _ = fit()
    changed = replace(p, parameters=(500.0,) * p.parameter_count)
    a, b = PlayerWithPredictions(m, p), PlayerWithPredictions(m, changed)
    public = public_input(TASK, False)
    assert a.predict(public, score()) != b.predict(public, score())
    assert a.action_policy(public, score(), 0.8) == b.action_policy(public, score(), 0.8)


@pytest.mark.parametrize(
    "field",
    [
        "native_seed",
        "source_seed_id",
        "run_seed",
        "plan_id",
        "label_endpoints",
        "target_mask",
        "return_samples",
        "training_return",
        "private_final_identity",
    ],
)
def test_predictor_uses_current_public_candidates_and_rejects_hidden_fields(field: str) -> None:
    m = cached_model(model())
    p, _, _ = fit()
    separate = PlayerWithPredictions(m, p)
    public = public_input(TASK, False)
    predicted = separate.predict(public, score())
    assert (
        len(predicted["predictions"]) == len(public["candidates"])
        and not predicted["used_for_action_selection"]
    )
    public["context"][field] = "NOT-A-PUBLIC-FEATURE"
    with pytest.raises(ValueError):
        separate.predict(public, score())


def test_predictor_checkpoint_cannot_be_loaded_as_policy_and_tampering_rejected() -> None:
    p, _, _ = fit()
    data = p.as_dict()
    assert OutcomePredictor.from_mapping(data) == p
    bad = copy.deepcopy(data)
    bad["parameters"][0] += 1
    with pytest.raises(ValueError, match="seal"):
        OutcomePredictor.from_mapping(bad)
    with pytest.raises((ValueError, KeyError)):
        ActionContextModel.from_mapping(data)
    with pytest.raises(ValueError, match="schemas"):
        OutcomePredictor.from_mapping(model().as_dict())
    with pytest.raises(ValueError, match="exact original"):
        PlayerWithPredictions(cached_model(model(seed=1)), p)


def test_held_outcome_poisoning_cannot_change_fit_parameters_scaling_or_Adam() -> None:
    m = cached_model(model())
    f, h = split()
    changed = copy.deepcopy(h)
    changed["targets"][:, 0] = 0.9
    changed["targets"][:, 1] = 30
    a, aa, ar = fit_predictor(m, f, h, 2, time.monotonic() + 15, epochs=3)
    b, ba, br = fit_predictor(m, f, changed, 2, time.monotonic() + 15, epochs=3)
    assert a == b and aa == ba
    assert [v["fitting"] for v in ar["curves"]] == [v["fitting"] for v in br["curves"]]
    assert ar["curves"][-1]["held"] != br["curves"][-1]["held"]


def test_entire_source_world_split_is_required() -> None:
    f, h = split()
    h["owners"][:] = 1
    with pytest.raises(ValueError, match="source world"):
        fit_predictor(cached_model(model()), f, h, 0, time.monotonic() + 15)
    empty = {k: v[:0] for k, v in h.items()}
    with pytest.raises(ValueError, match="source world"):
        fit_predictor(cached_model(model()), f, empty, 0, time.monotonic() + 15)
    _, _, r = fit_predictor(
        cached_model(model()), f, empty, 0, time.monotonic() + 15, epochs=1, allow_no_held=True
    )
    assert r["curves"][-1]["held"]["recorded_continuation_full_run_return"]["mse"] is None


def test_missing_and_constant_labels_do_not_create_gradient_targets() -> None:
    f, h = split()
    f["mask"][:, 2] = False
    f["targets"][:, 6] = 0
    p, _, r = fit_predictor(cached_model(model()), f, h, 0, time.monotonic() + 15, epochs=3)
    assert "next_public_enemy_hp_sum_delta" not in r["active_targets"]
    assert "next_public_potion_count_delta" not in r["active_targets"]
    out = p.predictions(h["inputs"])
    assert np.array_equal(out[:, 2], np.zeros(len(out))) and np.array_equal(
        out[:, 6], np.zeros(len(out))
    )


def test_new_prediction_network_derivatives_match_finite_differences() -> None:
    p, _, _ = fit(1)
    f, _ = split()
    rng = np.random.default_rng(20)
    x = f["inputs"]
    target = rng.normal(0, 0.2, (len(x), 7))
    weights = np.full(target.shape, 1 / len(x))
    coefficients = np.asarray([1.0, *([0.25 / 6] * 6)])
    _, g = gradient(p, x, target, weights, coefficients, 0.0001)
    for i in (0, 511, 16383, 16415, 16416, p.parameter_count - 1):
        losses = []
        for sign in (-1, 1):
            values = list(p.parameters)
            values[i] += sign * 1e-5
            losses.append(
                gradient(
                    replace(p, parameters=tuple(values)), x, target, weights, coefficients, 0.0001
                )[0]
            )
        assert (losses[1] - losses[0]) / 2e-5 == pytest.approx(g[i], abs=1e-7)


def test_deadline_and_nonfinite_inputs_fail_without_touching_parent() -> None:
    m = cached_model(model())
    before = m.as_dict()
    f, h = split()
    with pytest.raises(TimeoutError):
        fit_predictor(m, f, h, 0, time.monotonic() - 1)
    assert m.as_dict() == before
    p, _, _ = fit()
    with pytest.raises(ValueError):
        p.predictions(np.full((2, p.dimension), np.nan))
    with pytest.raises(ValueError):
        replace(p, scales=(0.0,) * 7)


@pytest.mark.parametrize("arm", ["greedy", "sampled"])
def test_nested_combat_and_noncombat_routers_never_consult_prediction(
    arm: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_native_combat_behavior_policy import noncombat
    from test_native_turn_teacher_policy import public, selection

    from spireshift.native_combat_behavior_policy import Chooser

    m = cached_model(model())
    p, _, _ = fit()
    player = PlayerWithPredictions(m, p)

    def forbidden(*_: Any, **__: Any) -> Any:
        raise AssertionError("Predictions entered gameplay routing")

    monkeypatch.setattr(OutcomePredictor, "predictions", forbidden)
    a = player.chooser(score(), "ROUTER-INVARIANCE", arm)
    b = Chooser(m, score(), "ROUTER-INVARIANCE", arm)
    for observation in (
        public(),
        selection(public()),
        noncombat("reward_claim"),
        noncombat("rest_site"),
        noncombat("map_navigation"),
    ):
        assert a(observation) == b(observation)
