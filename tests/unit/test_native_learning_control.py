from __future__ import annotations

import copy
import json
import math
import time
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import initial_actor, initialize_native_critic
from spireshift.native_input_normalization import QUARTER
from spireshift.native_learning_control import (
    TASKS,
    collect_round,
    evaluate,
    learn_task,
    load_config,
    policy_logs,
    public_input,
    run_control,
)
from spireshift.training_objective import load_training_score_spec

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path("configs/native-controls/ppo-known-tasks-v1.json")


def settings() -> dict[str, Any]:
    recipe: dict[str, Any] = json.loads(
        (ROOT / "configs/native-learning/sts2-v0.111.0-a8-input-normalized-v1.json").read_text()
    )
    result: dict[str, Any] = recipe["learning"]["ppo"]
    return result


def score() -> Any:
    return load_training_score_spec(
        ROOT / "configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v8.json"
    )


def model() -> Any:
    return initialize_native_critic(
        initial_actor("sha256:" + "f" * 64, input_normalization=QUARTER)
    )


def test_task_solution_is_terminal_only_and_risk_depends_on_public_context() -> None:
    immediate, delayed, contextual = TASKS
    assert immediate.delay_steps == 0 and delayed.delay_steps == contextual.delay_steps == 5
    for task in (immediate, delayed):
        for high in (False, True):
            assert task.probability(high, 1) == 1 and task.probability(high, 0) == 0
    assert contextual.probability(False, 0) < contextual.probability(False, 1)
    assert contextual.probability(True, 0) > contextual.probability(True, 1)
    assert sum(max(row) for row in contextual.terminal_probabilities) / 2 == 0.7
    assert all(t.as_dict()["intermediate_rewards"] == 0 for t in TASKS)
    with pytest.raises(ValueError):
        contextual.probability(False, -1)
    with pytest.raises(ValueError):
        public_input(delayed, False, 6)


@pytest.mark.parametrize("task", TASKS)
def test_menu_permutation_preserves_action_meaning_without_seed_or_solution_inputs(
    task: Any,
) -> None:
    m, cfg = model(), settings()
    p = public_input(task, False)
    rows, state, logs = policy_logs(m, p, cfg["temperature"])
    swapped, same, reverse = policy_logs(
        m, public_input(task, False, reverse=True), cfg["temperature"]
    )
    assert swapped == tuple(reversed(rows)) and state == same
    assert reverse == pytest.approx(tuple(reversed(logs)))
    text = json.dumps(p)
    for forbidden in ("terminal_probabilities", "optimal", "victory", "seed", "outcome"):
        assert forbidden not in text
    if task.delay_steps:
        wait, _, wait_logs = policy_logs(m, public_input(task, False, 1), cfg["temperature"])
        assert len(wait) == 1 and wait_logs == (0.0,)


def test_exact_evaluation_and_missing_context_control_do_not_sample_or_fit() -> None:
    m, task = model(), TASKS[2]
    source = m.as_dict()
    measured = evaluate(m, task, 0.8)
    assert measured["optimal_expected_victory"] == 0.7
    assert measured["synthetic_episodes_sampled"] == 0
    assert measured == evaluate(m, task, 0.8) and m.as_dict() == source
    blind = evaluate(m, task, 0.8, hide_hp=True)
    assert blind["expected_victory"] <= 0.55
    assert blind["greedy_accuracy"] == 0.5
    assert public_input(task, True, hide_hp=True) == public_input(task, False, hide_hp=True)


def test_collection_uses_sampled_terminal_outcomes_and_keeps_all_wait_steps() -> None:
    m, cfg, task = model(), settings(), TASKS[1]
    samples, report = collect_round(m, task, score(), cfg, 0, 1, 64)
    assert len(samples) == 64 * 6 and report["choice_bearing_decisions"] == 64
    assert report["forced_continuations"] == 64 * 5
    assert report["intermediate_rewards"] == report["supervised_action_labels"] == 0
    assert report["no_self_outcome_fitting"]
    for fold in report["folds"]:
        assert set(fold["fitting_runs"]).isdisjoint(fold["predicted_runs"])
    for episode, row in enumerate(report["outcomes"]):
        block = samples[episode * 6 : (episode + 1) * 6]
        assert row["victory"] == (row["action"] == 1)
        assert all(s.target == float(row["victory"]) for s in block)
        assert len(block[0].rows) == 2 and all(len(s.rows) == 1 for s in block[1:])
        assert all(s.old_log_probability == 0.0 for s in block[1:])
        assert all(math.isfinite(s.advantage) for s in block)
    repeated, same = collect_round(m, task, score(), cfg, 0, 1, 64)
    assert repeated == samples and same == report
    _, fresh = collect_round(m, task, score(), cfg, 0, 2, 64)
    assert fresh["outcomes"] != report["outcomes"]


def test_frozen_actor_is_a_real_optimizer_control_not_an_unexecuted_comparison() -> None:
    result = learn_task(
        TASKS[1],
        score(),
        settings(),
        seed=0,
        rounds=1,
        episodes=8,
        deadline=time.monotonic() + 20,
        frozen_actor=True,
    )
    assert result["synthetic_optimizer_steps"] > 0
    assert result["actor_unchanged"]
    assert result["initial_model_id"] != result["final_model_id"]  # Diagnostic critic still fits.
    assert result["final"] == result["learning_curve"][0]["evaluation"]
    assert result["complete_synthetic_episodes"] == 8
    assert result["final_only_no_checkpoint_selection"]


def test_task_loop_obeys_short_deadline() -> None:
    with pytest.raises(TimeoutError):
        learn_task(
            TASKS[0],
            score(),
            settings(),
            seed=0,
            rounds=1,
            episodes=8,
            deadline=time.monotonic() - 1,
        )


def test_config_binds_production_settings_without_opening_a_native_checkpoint() -> None:
    cfg, ppo, feature_score = load_config(ROOT, ROOT / CONFIG)
    assert ppo == settings()
    assert feature_score.evaluation_objective.primary == "terminal_victory"
    assert cfg["rounds"] == 32 and cfg["training_seeds"] == [0, 1, 2]
    assert cfg["resource_limits"]["wall_seconds"] < 300
    assert cfg["workspace"].startswith("artifacts/synthetic-learning/")


@pytest.mark.parametrize("change", ["rounds", "objective", "source", "criteria"])
def test_changed_experiment_contract_is_rejected_before_output(tmp_path: Path, change: str) -> None:
    cfg = copy.deepcopy(json.loads((ROOT / CONFIG).read_text()))
    if change == "rounds":
        cfg["rounds"] += 1
    elif change == "objective":
        cfg["objective"]["primary"] = "maximum_floor"
    elif change == "source":
        cfg["implementation_sha256"]["full_run_ppo_math.py"] = "0" * 64
    else:
        cfg["acceptance"]["minimum_exact_victory_gain"] = 0
    path = tmp_path / "config.json"
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        load_config(ROOT, path)


def test_cached_report_returns_without_training_and_tampering_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {"workspace": "artifacts/synthetic-learning/cached-v1"}
    body = {"config_id": manifest_identifier(cfg), "status": "complete", "games_launched": 0}
    doc = {**body, "report_id": manifest_identifier(body)}
    output = tmp_path / cfg["workspace"]
    output.mkdir(parents=True)
    path = output / "report.json"
    path.write_text(json.dumps(doc))
    monkeypatch.setattr(
        "spireshift.native_learning_control.load_config", lambda *_: (cfg, settings(), score())
    )
    monkeypatch.setattr(
        "spireshift.native_learning_control.learn_task",
        lambda *_a, **_kw: pytest.fail("Cached report unexpectedly starts fitting"),
    )
    assert run_control(tmp_path, tmp_path / "config.json") == doc
    doc["status"] = "changed"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="changed"):
        run_control(tmp_path, tmp_path / "config.json")


def test_interrupted_directory_is_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {"workspace": "artifacts/synthetic-learning/unfinished-v1"}
    output = tmp_path / cfg["workspace"]
    output.mkdir(parents=True)
    marker = output / "do-not-delete.txt"
    marker.write_text("preserved")
    monkeypatch.setattr(
        "spireshift.native_learning_control.load_config", lambda *_: (cfg, {}, score())
    )
    with pytest.raises(FileExistsError, match="Preserve"):
        run_control(tmp_path, tmp_path / "config.json")
    assert marker.read_text() == "preserved"
