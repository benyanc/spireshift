from __future__ import annotations

import math
import shutil
import subprocess
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
from spireshift.native_combat_intent_model import CombatIntentModel, copy_with_intents, encode, load
from spireshift.native_qualified_learning_inputs_v1 import plan
from spireshift.native_qualified_learning_session_v1 import development_report


def test_sustained_training_and_fresh_evaluation_are_disjoint() -> None:
    declared = plan()
    assert declared["rounds"] * declared["worlds_per_round"] * len(declared["initializers"]) == 2048
    phases = [set(declared[key]) for key in ("training", "development", "control", "reload")]
    assert sum(map(len, phases)) == len(set.union(*phases))
    assert declared["final_selection"] == "fixed_round_64"
    assert declared["replay_imitation_labels"] is False


def test_learning_worker_has_no_fixture_capability() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for worker capability checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-qualified-learning-worker-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_actor_critic_update_and_reload_preserve_current_input_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = copy_with_intents(extend(parent(), ("block", "damage")))
    before = original.document()
    rows, state = encode(menu(), original.model, score())
    logs = log_softmax(score_features(cast(Any, original.model.actor), rows), 0.8)
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
    updated, work = learning.fit(
        original, [], score(), {}, settings, 1, 123, math.inf, control_steps=2
    )
    assert work["optimizer_updates"] == 2
    assert isinstance(updated.model, CombatIntentModel)
    assert original.document() == before
    assert updated.model.actor.genome != original.model.actor.genome
    assert updated.model.value_weights != original.model.value_weights
    assert updated.actor_adam.steps == original.actor_adam.steps + 2
    assert updated.value_adam.steps == original.value_adam.steps + 2
    state_id = save(tmp_path / "copy.json", updated)
    restored, restored_id = load(tmp_path / "copy.json")
    assert (restored, restored_id) == (updated, state_id)
    assert encode(menu(), restored.model, score()) == encode(menu(), updated.model, score())


def test_zero_win_evaluation_stays_inconclusive_and_reports_act_progress() -> None:
    worlds = ["one", "two"]
    games = {
        (seed, p, arm): {
            "outcome": "loss",
            "completed_acts": int(arm == "fitted"),
            "maximum_floor": 20 if arm == "fitted" else 10,
        }
        for seed in worlds
        for p in (2, 3)
        for arm in ("original", "fitted")
    }
    report = development_report(worlds, games)
    assert report["comparison"] == "inconclusive"
    assert report["by_initializer"]["2"]["arms"]["fitted"]["act1_clears"] == 2
    assert report["by_initializer"]["3"]["arms"]["original"]["act1_clears"] == 0
    assert report["by_initializer"]["2"]["arms"]["fitted"]["win"] == 0


def test_failed_and_missing_evaluation_cells_keep_the_planned_denominator() -> None:
    report = development_report(["one", "two"], {("one", 2, "fitted"): {"outcome": "failed"}})
    info = report["by_initializer"]["2"]
    assert info["planned_worlds_per_arm"] == 2
    assert info["arms"]["fitted"]["failed"] == 1
    assert info["arms"]["fitted"]["unattempted"] == 1
    assert report["seed_clustered_bootstrap_95"] is None
