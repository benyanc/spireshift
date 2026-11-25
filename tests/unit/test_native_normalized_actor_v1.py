from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_a8_card_display_model import menu, parent
from test_native_action_context import score

from spireshift import full_run_policy, native_a8_own_ppo, native_structured_policy
from spireshift import native_qualified_learning_fit_v1 as learning
from spireshift.engine_neural import initial_actor
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_card_display_model import extend
from spireshift.native_a8_head_policy import OwnedDecision, save
from spireshift.native_a8_own_ppo import Decision, Factor
from spireshift.native_combat_intent_model import copy_with_intents, encode
from spireshift.native_normalized_actor_v1 import (
    METHODS,
    CorrectionActor,
    initialize,
    load,
    score_features,
    score_gradient,
    using_correction_scoring,
)
from spireshift.native_policy_updates import SETTINGS


def actor(method: str) -> CorrectionActor:
    base = initial_actor("sha256:" + "a" * 64, 128, 4, 123)
    return CorrectionActor(
        base.environment_id,
        base.dimension,
        base.hidden_units,
        base.genome,
        base.input_normalization,
        reference=base,
        correction_normalization=method,
    )


@pytest.mark.parametrize("method", METHODS)
def test_entire_manual_derivative_matches_finite_differences(method: str) -> None:
    model = actor(method)
    rows = ({0: 1.0, 1: 2.0}, {0: 1.0, 3: -0.75}, {7: 0.2, 1: 0.4})
    derivative = (0.3, -0.5, 0.2)
    analytic = score_gradient(model, rows, derivative)
    epsilon = 1e-6
    for j in range(model.parameter_count):
        plus, minus = list(model.genome), list(model.genome)
        plus[j] += epsilon
        minus[j] -= epsilon
        hi = score_features(model.with_genome(plus), rows)
        lo = score_features(model.with_genome(minus), rows)
        finite = math.fsum(d * (a - b) for d, a, b in zip(derivative, hi, lo, strict=True))
        finite /= 2 * epsilon
        assert analytic[j] == pytest.approx(finite, rel=2e-5, abs=2e-8)


def test_normalization_never_reads_sibling_choices_or_other_states() -> None:
    model = actor("normalized")
    rows = ({0: 1.0, 2: 3.0}, {1: 2.0, 7: -1.0}, {0: -5.0})
    values = score_features(model, rows)
    assert score_features(model, rows[::-1]) == pytest.approx(values[::-1], abs=1e-14)
    for row, value in zip(rows, values, strict=True):
        assert score_features(model, (row,))[0] == pytest.approx(value, abs=1e-14)
    equal = replace(model, genome=(0.0,) * model.parameter_count)
    assert all(math.isfinite(v) for v in score_features(equal, rows))
    assert all(math.isfinite(v) for v in score_gradient(equal, rows, (1.0, -1.0, 0.0)))
    with pytest.raises(ValueError, match="derivative"):
        score_gradient(model, rows, (float("nan"), 0.0, 0.0))


@pytest.mark.parametrize("method", METHODS)
def test_qualified_PPO_updates_only_correction_and_critic_and_reloads_all_Adam(
    method: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = copy_with_intents(extend(parent(), ("block", "damage")))
    before = original.document()
    state = initialize(original, method, 678)
    other = initialize(original, "normalized" if method == "raw" else "raw", 678)
    assert state.model.actor.genome == other.model.actor.genome
    assert state.model.value_weights == original.model.value_weights
    assert state.value_adam == original.value_adam
    assert state.actor_adam.steps == 0 and not any(state.actor_adam.first)
    assert not any(state.actor_adam.second)
    rows, value = encode(menu(), state.model, score())
    baseline = full_run_policy.score_features(cast(Any, original.model.actor), rows)
    assert score_features(state.model.actor, rows) == baseline
    logs = log_softmax(baseline, 0.8)
    examples = [
        OwnedDecision(True, Decision((Factor(rows, i),), value, logs[i], target, advantage))
        for i, target, advantage in ((0, 0.3, 0.1), (1, 0.7, -0.2))
    ]
    monkeypatch.setattr(learning, "training_examples", lambda *args: (examples, {}))
    with using_correction_scoring():
        assert native_structured_policy.__dict__["score_features"] is score_features
        assert native_a8_own_ppo.__dict__["score_gradient"] is score_gradient
        updated, work = learning.fit(
            state,
            [],
            score(),
            {},
            {**SETTINGS, "minibatch_decisions": 1, "epochs": 2},
            1,
            123,
            math.inf,
            control_steps=2,
        )
        identifier = save(tmp_path / "trained.json", updated)
        assert load(tmp_path / "trained.json") == (updated, identifier)
    assert work["optimizer_updates"] == 2
    assert updated.actor_adam.steps == 2
    assert updated.value_adam.steps == original.value_adam.steps + 2
    assert isinstance(updated.model.actor, CorrectionActor)
    assert updated.model.actor.reference == original.model.actor
    assert updated.model.actor.genome != state.model.actor.genome
    assert score_features(updated.model.actor, rows) != baseline
    assert original.document() == before


def test_unqualified_kernels_fail_closed_and_nested_dispatch_restores_after_error() -> None:
    model = actor("normalized")
    before = full_run_policy.score_features
    rows = ({0: 1.0}, {1: -1.0})
    with pytest.raises(ValueError, match="qualified scoring"):
        before(cast(Any, model), rows)
    with pytest.raises(RuntimeError, match="exit"), using_correction_scoring():
        with using_correction_scoring():
            assert full_run_policy.score_features(cast(Any, model), rows) == score_features(
                model, rows
            )
        assert full_run_policy.score_features is score_features
        raise RuntimeError("exit")
    assert full_run_policy.score_features is before
    invalid: dict[str, Any] = {**model.as_dict(), "normalization_epsilon": 1.0}
    with pytest.raises(ValueError, match="architecture"):
        CorrectionActor.from_mapping(invalid)
