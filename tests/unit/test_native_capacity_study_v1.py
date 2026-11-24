from __future__ import annotations

import gzip
import json
import math
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_a8_card_display_model import menu, parent
from test_native_action_context import score

from spireshift import native_qualified_learning_fit_v1 as learning
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_card_display_model import extend
from spireshift.native_a8_head_policy import OwnedDecision, save
from spireshift.native_a8_own_ppo import Decision, Factor
from spireshift.native_capacity_control_v1 import same_initial_games
from spireshift.native_capacity_inputs_v1 import EVALUATION, METHODS, plan
from spireshift.native_capacity_session_v1 import comparison_report
from spireshift.native_combat_intent_model import copy_with_intents, encode, load
from spireshift.native_policy_capacity_v1 import expand


def test_training_depth_world_ownership_and_frozen_candidate_selection() -> None:
    declared = plan()
    assert declared["rounds"] * declared["worlds_per_round"] * 2 * len(METHODS) == 4096
    assert declared["development_worlds"] * 2 * len(EVALUATION) == 768
    sets = [set(declared[k]) for k in ("training", "development", "control", "reload")]
    assert sum(map(len, sets)) == len(set.union(*sets))
    assert declared["final_selection"] == "fixed_round_64_for_each_method_before_development"
    assert declared["replay_imitation_labels"] is False
    assert declared["matched_optimizer_work_claimed"] is False


def test_new_hidden_units_really_learn_and_the_full_copied_Adam_reloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = copy_with_intents(extend(parent(), ("block", "damage")))
    wide = expand(original, original.model.actor.hidden_units * 2, 42)
    before = wide.document()
    rows, state = encode(menu(), wide.model, score())
    logs = log_softmax(score_features(cast(Any, wide.model.actor), rows), 0.8)
    examples = [
        OwnedDecision(True, Decision((Factor(rows, i),), state, logs[i], target, advantage))
        for i, target, advantage in ((0, 0.3, 0.1), (1, 0.7, -0.2))
    ]
    monkeypatch.setattr(
        learning,
        "training_examples",
        lambda *args: (examples, {"native_families": {"combat_turn": 2}}),
    )
    settings: dict[str, Any] = {
        "actor_learning_rate": 0.001,
        "value_learning_rate": 0.003,
        "clip": 0.2,
        "temperature": 0.8,
        "entropy_coefficient": 0.015,
        "value_coefficient": 0.5,
        "gradient_clip": 1.0,
        "minibatch_decisions": 1,
        "epochs": 2,
        "target_kl": 0.03,
    }
    updated, work = learning.fit(wide, [], score(), {}, settings, 1, 123, math.inf, control_steps=2)
    assert work["optimizer_updates"] == 2
    assert updated.actor_adam.steps == wide.actor_adam.steps + 2
    assert updated.value_adam.steps == wide.value_adam.steps + 2
    _, _, out, _ = updated.model.actor.unpack()
    assert any(abs(v) > 0 for v in out[original.model.actor.hidden_units :])
    assert wide.document() == before
    state_id = save(tmp_path / "trained-wide.json", updated)
    assert load(tmp_path / "trained-wide.json") == (updated, state_id)


def test_three_method_comparison_preserves_unknown_denominators() -> None:
    result = comparison_report(["one", "two"], {("one", 2, "expanded"): {"outcome": "failed"}})
    contrast = result["expanded_versus_standard"]
    assert contrast["by_initializer"]["2"]["arms"]["fitted"]["failed"] == 1
    assert contrast["by_initializer"]["2"]["arms"]["fitted"]["unattempted"] == 1
    assert contrast["by_initializer"]["2"]["arms"]["original"]["unattempted"] == 2
    assert contrast["comparison"] == "inconclusive"
    assert len(result) == 3


def test_native_initial_equivalence_requires_exact_states_and_choices(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    rows: list[dict[str, Any]] = [
        {"kind": "policy_input", "frame": {"public_input": {"all_current_choices": [0, 1]}}},
        {
            "kind": "policy_choice",
            "choice": {"action_index": 1, "draw_key": "same", "draw": 0.7, "log_probability": -0.3},
        },
        {"kind": "final_observation", "frame": {"public_input": {"terminal": True}}},
    ]

    def save_rows(folder: Path) -> None:
        with gzip.open(folder / "shared-public.jsonl.gz", "wt") as handle:
            for row in rows:
                handle.write(json.dumps(row) + "\n")

    save_rows(a)
    save_rows(b)
    assert same_initial_games(a, b) == {"matching_public_states": 2, "matching_model_choices": 1}
    rows[1]["choice"]["action_index"] = 0
    save_rows(b)
    with pytest.raises(ValueError, match="different model-owned choices"):
        same_initial_games(a, b)
