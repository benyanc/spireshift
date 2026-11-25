from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from test_native_a8_card_display_model import menu, parent
from test_native_action_context import score

from spireshift import native_qualified_learning_fit_v1 as unchanged
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_card_display_model import extend
from spireshift.native_a8_head_policy import OwnedDecision
from spireshift.native_a8_own_ppo import Decision, Factor
from spireshift.native_capacity_inputs_v1 import plan as old_plan
from spireshift.native_combat_intent_model import copy_with_intents, encode
from spireshift.native_normalization_fit_v1 import fit, geometry
from spireshift.native_normalization_inputs_v1 import EVALUATION, initialization, plan
from spireshift.native_normalization_session_v1 import comparison_report
from spireshift.native_normalized_actor_v1 import METHODS, initialize, score_features
from spireshift.native_policy_updates import SETTINGS


def test_fixed_training_depth_and_fresh_unseen_development() -> None:
    cfg = plan()
    assert cfg["rounds"] * cfg["worlds_per_round"] * 2 * len(METHODS) == 4096
    assert cfg["development_worlds"] * 2 * len(EVALUATION) == 768
    sets = [set(cfg[k]) for k in ("training", "development", "control", "reload")]
    assert len(set.union(*sets)) == sum(map(len, sets))
    previous = set.union(
        *(set(old_plan()[k]) for k in ("training", "development", "control", "reload"))
    )
    assert previous.isdisjoint(set.union(*sets))
    assert cfg["final_selection"] == "fixed_round_64_for_each_method_before_development"
    assert not cfg["replay_imitation_labels"] and cfg["inherited_training_units"] == 0
    assert initialization()["reference_actor_trainable"] is False
    assert initialization()["action_families"] == "all_legal_actions_model_owned"
    assert initialization()["objective_credit_and_PPO"] == "unchanged"


def test_failed_and_unattempted_games_remain_in_all_three_contrasts() -> None:
    result = comparison_report(["one", "two"], {("one", 2, "normalized"): {"outcome": "failed"}})
    assert set(result) == {
        "raw_versus_reference",
        "normalized_versus_reference",
        "normalized_versus_raw",
    }
    row = result["normalized_versus_raw"]["by_initializer"]["2"]["arms"]
    assert row["fitted"]["failed"] == 1 and row["fitted"]["unattempted"] == 1
    assert row["original"]["unattempted"] == 2


@pytest.mark.parametrize("method", METHODS)
def test_geometry_and_fitting_preserve_grouped_choice_weight_and_original_learning_kernel(
    method: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = copy_with_intents(extend(parent(), ("block", "damage")))
    state = initialize(original, method, 123)
    rows, value = encode(menu(), state.model, score())
    logs = log_softmax(score_features(state.model.actor, rows), 0.8)
    one = OwnedDecision(True, Decision((Factor(rows, 0),), value, logs[0], 0.2, 0.1))
    compound = replace(one, decision=replace(one.decision, factors=one.decision.factors * 2))
    a, b = geometry(state, [one], 0.8), geometry(state, [compound], 0.8)
    assert a["correction_logit_range"] == 0.0
    for key in a:
        if key != "sampled_policy_factors":
            assert b[key] == a[key]
    assert b["sampled_policy_factors"] == 2
    calls = []

    def unchanged_fit(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
        calls.append((args, kwargs))
        unchanged.__dict__["training_examples"](*args[:2])
        return state, {"optimizer_updates": 0}

    monkeypatch.setattr(unchanged, "fit", unchanged_fit)
    monkeypatch.setattr(
        "spireshift.native_normalization_fit_v1.training_examples", lambda *args: ([one], {})
    )
    games: list[Any] = [(None, {"native_decisions": 1, "task": {"seed": "A"}})]
    after, work = fit(state, games, score(), {}, SETTINGS, 4, 12, 100.0, control_steps=2)
    assert after is state and work["reference_actor_unchanged"]
    assert work["correction_geometry_before"] == work["correction_geometry_after"]
    assert calls[0][0] == (state, games, score(), {}, SETTINGS, 4, 12, 100.0)
    assert calls[0][1] == {"control_steps": 2}
