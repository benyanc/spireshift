from __future__ import annotations

import copy
import time
from dataclasses import replace
from typing import Any

import pytest
from test_native_action_context import model, score, settings
from test_native_rest_exploration import rest, samples

from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_feedback_audit import decision, training_binding
from spireshift.native_feedback_checks import input_checks, teaching_check
from spireshift.native_feedback_metrics import movement, value_quality


def test_input_probes_preserve_menu_order_and_distinguish_health_and_current_cost() -> None:
    m = cached_model(model())
    public = rest()
    public["candidates"][0]["subject"] = {
        "role": "card",
        "properties": {"cost": 0, "stats": {"damage": 6, "block": 5}},
    }
    original = copy.deepcopy(public)
    r = input_checks(public, m, score())
    assert r["candidate_order_equivariant"] and r["all_exercised_facts_distinguished"]
    assert {p["fact"] for p in r["probes"]} == {
        "current_health",
        "current_card_cost",
        "current_card_damage",
        "current_card_block",
    }
    assert public == original  # Mutations belong only to encoder controls.
    assert all(p["relative_row_change"] > 0 for p in r["probes"])


def test_synthetic_teaching_uses_a_disposable_full_Adam_copy_and_has_no_native_labels() -> None:
    m = cached_model(model())
    optimizer = Adam(9, (0.0001,) * m.parameter_count, (0.001,) * m.parameter_count)
    before_model, before_adam = m.as_dict(), optimizer.as_dict()
    r = teaching_check(rest(), m, optimizer, score(), settings(), steps=3)
    assert r["ending_optimizer_steps"] == 12
    assert r["production_optimizer_steps"] == 0 and r["synthetic_optimizer_steps"] == 3
    assert r["label_probability_after"] > r["label_probability_before"]
    assert not r["native_action_quality_label"] and not r["model_saved_or_promoted"]
    assert m.as_dict() == before_model and optimizer.as_dict() == before_adam
    with pytest.raises(ValueError, match="64"):
        teaching_check(rest(), m, optimizer, score(), settings(), steps=65)


def test_mixture_feedback_checks_actual_probabilities_and_reports_weak_responsibility() -> None:
    m, ss = samples()
    m = cached_model(m)
    metadata = [
        {
            "family": "rest_site",
            "seed_id": i,
            "chosen_label": "Smith",
            "hp_fraction": 0.8,
            "opportunities": {"rest_option_SMITH": [1]},
            "hp_band": "high",
        }
        for i in range(len(ss))
    ]
    r = movement(m, m, ss, metadata, 0.8, time.monotonic() + 10)
    assert r["all_learner_likelihoods_reconstructed"]
    rest_result = r["rest_choices"]["Smith"]
    assert rest_result["credit_aligned_probability_change"]["maximum"] == 0
    assert rest_result["responsibility_at_behavior"]["minimum"] < 1
    assert r["observed_opportunities"]["rest_option_SMITH"]["opportunities"] == 2
    broken = [replace(ss[0], old_log_probability=1), *ss[1:]]
    with pytest.raises(ValueError, match="probability"):
        movement(m, m, broken, metadata, 0.8, time.monotonic() + 10)
    with pytest.raises(TimeoutError):
        movement(m, m, ss, metadata, 0.8, 0)


def test_value_references_use_other_whole_games_and_equal_game_weights() -> None:
    _, ss = samples()
    values = [replace(ss[0], target=0.2, advantage=0.1)] * 9 + [
        replace(ss[0], target=0.8, advantage=0.2)
    ]
    metadata = [
        {"seed_id": 1 if i < 9 else 2, "behavior_value": 0.0, "progress_potential": 0.0}
        for i in range(10)
    ]
    folds = [
        {"fitting_runs": [1], "predicted_runs": [2]},
        {"fitting_runs": [2], "predicted_runs": [1]},
    ]
    r = value_quality(values, metadata, folds)
    assert r["mse"]["credit_baseline"] == pytest.approx((0.1**2 + 0.2**2) / 2)
    assert r["mse"]["other_fold_constant"] == pytest.approx(0.6**2)
    folds[0]["fitting_runs"] = [1, 2]
    with pytest.raises(ValueError, match="own outcome"):
        value_quality(values, metadata, folds)


def test_low_smith_use_is_not_a_failure_or_an_optimal_action_label() -> None:
    def result(passed: bool) -> dict[str, Any]:
        return {
            "input_checks": [
                {"candidate_order_equivariant": True, "all_exercised_facts_distinguished": True}
            ],
            "synthetic_teaching_check": {"memorization_criterion_passed": passed},
            "value_quality": {"credit_baseline_beats_other_fold_constant": True},
        }

    r = decision([result(True)])
    assert r["low_Smith_frequency_is_not_a_failure_criterion"]
    assert r["next_step"] == "qualify_native_counterfactual_combat_lessons_before_larger_training"
    assert not r["native_action_quality_established"]
    assert not r["automatic_training_follows"]
    assert "optimization" in decision([result(False)])["next_step"]


@pytest.mark.parametrize(
    "fault", ["partition", "panel", "seed", "initializer", "config", "manifest"]
)
def test_reserved_or_differently_owned_games_are_rejected(fault: str) -> None:
    binding = {
        "native_seed": "train001",
        "partition": "train",
        "panel_purpose": "training",
        "config_id": "config",
        "seed_manifest_id": "manifest",
    }
    owner = {"partition": "train", "seed": "train001", "numerical_seed": 2}
    training_binding(binding, owner, {"numerical_seed": 2}, "config", "manifest")
    if fault == "partition":
        owner["partition"] = "holdout"
    elif fault == "panel":
        binding["panel_purpose"] = "evaluation"
    elif fault == "seed":
        binding["native_seed"] = "reserved002"
    elif fault == "initializer":
        owner["numerical_seed"] = 3
    elif fault == "config":
        binding["config_id"] = "other"
    else:
        binding["seed_manifest_id"] = "other"
    with pytest.raises(ValueError, match="TRAIN"):
        training_binding(binding, owner, {"numerical_seed": 2}, "config", "manifest")


def test_current_native_string_costs_are_exercised() -> None:
    p = rest()
    p["candidates"][0]["subject"] = {"role": "card", "properties": {"cost": "1"}}
    r = input_checks(p, cached_model(model()), score())
    cost = next(v for v in r["probes"] if v["fact"] == "current_card_cost")
    assert cost["maximum_row_change"] > 0
    assert p["candidates"][0]["subject"]["properties"]["cost"] == "1"
