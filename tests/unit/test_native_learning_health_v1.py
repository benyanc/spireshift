from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import initial_actor, initialize_native_critic
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, log_softmax
from spireshift.native_a8_head_policy import HeadModel, HeadState, OwnedDecision
from spireshift.native_a8_own_ppo import Decision, Factor
from spireshift.native_action_context import ORIGINAL
from spireshift.native_input_normalization import QUARTER
from spireshift.native_learning_health_math_v1 import (
    explained_variance,
    geometry,
    kernel_probe,
    optimizer_probes,
)
from spireshift.native_learning_health_v1 import selected_examples
from spireshift.native_policy_updates import SETTINGS


def fixture() -> tuple[HeadState, OwnedDecision]:
    actor = initial_actor("sha256:" + "a" * 64, 128, 8, 4, input_normalization=QUARTER)
    model = HeadModel(initialize_native_critic(actor), ORIGINAL, "sha256:" + "b" * 64)
    state = HeadState(
        model,
        Adam(13, (0.0,) * actor.parameter_count, (0.0,) * actor.parameter_count),
        None,
        Adam(13, (0.0,) * 129, (0.0,) * 129),
    )
    rows = ({0: 1.0, 1: 1.0}, {0: 1.0, 2: 1.0}, {0: 1.0, 3: 1.0})
    logs = log_softmax(score_features(actor, rows), SETTINGS["temperature"])  # type: ignore[arg-type]
    sample = Decision((Factor(rows, 0),), (*([0.0] * 128), 1.0), logs[0], 0.2, 1.0)
    return state, OwnedDecision(True, sample)


def test_directional_probes_check_both_signs_without_mutating_source() -> None:
    state, sample = fixture()
    before = manifest_identifier(state.document())
    report = kernel_probe(state, sample, SETTINGS)
    assert report["responsive"]
    assert report["maximum_relative_directional_error"] < 1e-5
    assert all(row["correct_direction"] for row in report["advantage_signs"].values())
    assert manifest_identifier(state.document()) == before


def test_disposable_warm_and_reset_steps_leave_original_full_Adam_untouched() -> None:
    state, sample = fixture()
    before = manifest_identifier(state.document())
    result = optimizer_probes(state, [sample], SETTINGS)
    assert set(result["one_step_probes"]) == {"inherited_Adam", "reset_Adam"}
    assert all(row["copy_updates"] == 1 for row in result["one_step_probes"].values())
    assert result["checkpoints_saved"] == 0 and not result["strength_improvement_established"]
    assert manifest_identifier(state.document()) == before


def test_compound_answers_keep_one_weight_in_geometry() -> None:
    state, sample = fixture()
    one = geometry(state, [sample], 0.8)
    compound = replace(
        sample, decision=replace(sample.decision, factors=sample.decision.factors * 2)
    )
    two = geometry(state, [compound], 0.8)
    assert two["native_decisions"] == 1 and two["policy_factors"] == 2
    for name in one:
        if name not in {"native_decisions", "policy_factors"}:
            assert two[name] == pytest.approx(one[name])


def test_explained_variance_retains_degenerate_targets() -> None:
    assert explained_variance([1.0, 1.0], [0.0, 1.0]) is None
    assert explained_variance([0.0, 1.0], [0.0, 1.0]) == 1.0
    poor = explained_variance([0.0, 1.0], [1.0, 0.0])
    assert poor is not None and poor < 0
    with pytest.raises(ValueError, match="aligned"):
        explained_variance([1.0], [])


def test_probe_sampling_keeps_worlds_balanced_and_rejects_count_drift() -> None:
    _, sample = fixture()
    examples = [sample] * 9
    games: list[tuple[Any, dict[str, Any]]] = [
        (None, {"native_decisions": 3, "task": {"seed": "A"}}),
        (None, {"native_decisions": 6, "task": {"seed": "B"}}),
    ]
    assert len(selected_examples(examples, games, 2)) == 4
    with pytest.raises(ValueError, match="ownership"):
        selected_examples(examples[:-1], games, 2)
