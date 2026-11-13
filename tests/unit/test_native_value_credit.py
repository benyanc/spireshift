from __future__ import annotations

import copy
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_value_credit import (
    FEATURES,
    ValueRun,
    action_advantages,
    cross_fitted_predictions,
    fit_baseline,
    fold_assignment,
    prediction_metrics,
    public_value_features,
    redistribute_terminal_return,
    value_run,
)
from spireshift.training_objective import load_training_score_spec


def run(seed: int, target: float) -> ValueRun:
    x = (1.0, seed / 20, *([0.0] * (len(FEATURES) - 2)))
    return ValueRun(seed, 1, target, (x, x), (0.01, 0.02), (0.02, 0.02), (2, 1))


def public() -> dict[str, Any]:
    return {
        "schema_version": "actual-engine-public-entity-graph-v1",
        "context": {
            "persistent": {
                "run": {"act": 1, "floor": 5},
                "player": {
                    "hp": 40,
                    "max_hp": 80,
                    "gold": 100,
                    "relics": [],
                    "potions": [],
                },
            },
            "interaction": {"kind": "rest_site"},
            "reads": [{"kind": "run_deck", "content": {"card_count": 12}}],
        },
        "candidates": [{"verb": "skip"}, {"verb": "select"}],
    }


def score() -> Any:
    return load_training_score_spec(
        Path("configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v8.json")
    )


def test_value_features_use_only_public_state_and_are_bounded() -> None:
    p = public()
    values, phi = public_value_features(p, score())
    assert len(values) == len(FEATURES) and all(0 <= v <= 1 for v in values)
    assert phi == pytest.approx(0.25 * (5 / 21) / 4)
    p["candidates"] = [{"verb": "any_other_legal_action"}]
    assert public_value_features(p, score()) == (values, phi)
    p["context"]["seed"] = "private"
    with pytest.raises(ValueError):
        public_value_features(p, score())


def test_normalization_preserves_hp_and_later_act_progress() -> None:
    p = public()
    first, phi = public_value_features(p, score())
    p["context"]["persistent"]["player"]["hp"] = 1
    p["context"]["persistent"]["run"]["act"] = 2
    second, later = public_value_features(p, score())
    assert second[FEATURES.index("hp_fraction")] < first[FEATURES.index("hp_fraction")]
    assert later > phi
    p["context"]["persistent"]["player"]["max_hp"] = 0
    with pytest.raises(ValueError):
        public_value_features(p, score())


@pytest.mark.parametrize("target", [0.0, 0.03, 1.0])
def test_redistribution_and_full_trace_preserve_loss_or_victory_objective(target: float) -> None:
    # Includes repeated/skipped menus, a return loop and an act transition.
    phi = (0.003, 0.003, 0.01, 0.003, 0.08, 0.09)
    values = (0.02, 0.023, 0.04, 0.01, 0.1, 0.2)
    rewards = redistribute_terminal_return(target, phi)
    assert rewards[0] == 0 and math.fsum(rewards[1:3]) == pytest.approx(0)
    assert math.fsum(rewards) == pytest.approx(target - phi[0])
    assert action_advantages(target, phi, values, 1.0) == pytest.approx(
        tuple(target - v for v in values)
    )
    # Shaping cancels from TD credit as well when values use matching coordinates.
    assert action_advantages(target, phi, values, 0.95) == pytest.approx(
        action_advantages(target, (0.0,) * len(phi), values, 0.95)
    )


def test_td_credit_changes_earlier_credit_but_does_not_bootstrap_terminal_value() -> None:
    assert action_advantages(1, (0, 0), (0.2, 0.4), 0) == pytest.approx((0.2, 0.6))
    for args in [
        (1, (), (), 1),
        (1, (0,), (), 1),
        (1, (0,), (0,), float("nan")),
        (1, (float("nan"),), (0,), 1),
    ]:
        with pytest.raises(ValueError):
            action_advantages(*args)


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "failed"),
        ("recovered", True),
        ("privileged_fixture", True),
        ("native_ending_evidence_agrees", False),
    ],
)
def test_partial_failed_recovered_or_privileged_runs_cannot_supply_credit(
    key: str, value: Any
) -> None:
    case = {
        "status": "terminal",
        "recovered": False,
        "privileged_fixture": False,
        "native_ending_evidence_agrees": True,
    }
    case[key] = value
    with pytest.raises(ValueError):
        value_run(case, 1, 1, score())


def test_cross_fitting_never_uses_a_runs_own_outcome_or_length() -> None:
    runs = [run(i, i / 100) for i in range(1, 9)]
    predictions, folds = cross_fitted_predictions(runs, "public_residual_ridge", 0.01, 4, "fixed")
    for fold in folds:
        assert set(fold["fitting_runs"]).isdisjoint(fold["predicted_runs"])
        assert len(fold["fitting_runs"]) == 6
    owners = fold_assignment(runs, 4, "fixed")
    changed = [replace(r, target=1) if owners[r.seed] == owners[1] else r for r in runs]
    again, _ = cross_fitted_predictions(changed, "public_residual_ridge", 0.01, 4, "fixed")
    assert predictions[1] == again[1]
    assert fold_assignment(list(reversed(runs)), 4, "fixed") == owners
    assert prediction_metrics(runs, predictions)["independent_runs"] == 8


def test_equal_game_weighting_does_not_count_repeated_decisions_as_more_outcomes() -> None:
    a, b = run(1, 0.1), run(2, 0.9)
    duplicated = replace(
        a,
        features=a.features * 20,
        potentials=a.potentials * 20,
        behavior_values=a.behavior_values * 20,
        choices=a.choices * 20,
    )
    baseline = fit_baseline([a, b], "constant", 0.01)
    assert baseline.weights == pytest.approx((0.5,))
    first = fit_baseline([a, b], "public_residual_ridge", 0.01)
    second = fit_baseline([duplicated, b], "public_residual_ridge", 0.01)
    assert first.weights == pytest.approx(second.weights)
    with pytest.raises(ValueError):
        baseline.predict(a)
    with pytest.raises(ValueError):
        fold_assignment([a, copy.copy(a)], 2, "fixed")
