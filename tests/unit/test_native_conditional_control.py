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
from spireshift.full_run_ppo_math import Adam
from spireshift.native_conditional_control import (
    TASK,
    load_config,
    output_path,
    paired_seed,
    run_comparison,
    teach_round,
    teaching_examples,
    teaching_gradient,
)
from spireshift.native_input_normalization import QUARTER
from spireshift.native_learning_control import collect_round, learn_task, public_input
from spireshift.training_objective import load_training_score_spec

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/native-controls/conditional-teaching-v1.json"


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


def test_oracle_binds_hp_and_menu_order_not_the_sampled_action_or_reward() -> None:
    m, cfg = model(), settings()
    samples, collection = collect_round(m, TASK, score(), cfg, 0, 1, 64)
    examples, labels = teaching_examples(m, samples, collection)
    assert examples == samples
    for index, outcome in enumerate(collection["outcomes"]):
        first = samples[index * 6]
        reverse = first.rows[0].get(4) == 1.0  # Direct Skip feature; Commit has Play.
        optimal = 0 if outcome["high_hp"] else 1
        assert labels[index * 6] == (1 - optimal if reverse else optimal)
        assert labels[index * 6 + 1 : index * 6 + 6] == [0] * 5
    changed = {
        **collection,
        "outcomes": [
            {**r, "action": 1 - r["action"], "victory": not r["victory"]}
            for r in collection["outcomes"]
        ],
    }
    assert teaching_examples(m, samples, changed)[1] == labels
    for high in (False, True):
        text = json.dumps(public_input(TASK, high))
        for forbidden in ("optimal", "terminal_probabilities", "victory", "outcome", "seed"):
            assert forbidden not in text


def test_masked_teaching_keeps_labels_but_hp_context_is_gone() -> None:
    m, cfg = model(), settings()
    samples, collection = collect_round(m, TASK, score(), cfg, 0, 1, 64)
    own, labels = teaching_examples(m, samples, collection, hide_hp=True)
    assert labels == teaching_examples(m, samples, collection)[1]
    assert own != samples
    # In each menu order, opposite HP labels share identical actor AND critic inputs.
    groups: dict[str, set[int]] = {}
    for index in range(0, len(own), 6):
        key = json.dumps({"rows": own[index].rows, "state": own[index].state}, sort_keys=True)
        groups.setdefault(key, set()).add(labels[index])
    assert len(groups) == 2 and all(g == {0, 1} for g in groups.values())
    broken = list(samples)
    broken[1] = samples[0]
    with pytest.raises(ValueError, match="ordered public inputs"):
        teaching_examples(m, broken, collection)
    with pytest.raises(ValueError, match="lost an episode"):
        teaching_examples(m, samples[:-1], collection)


def test_teacher_derivative_matches_finite_differences_for_actor_and_critic() -> None:
    m, cfg = model(), settings()
    data, collection = collect_round(m, TASK, score(), cfg, 0, 1, 8)
    samples, labels = teaching_examples(m, data, collection)
    samples, labels = samples[:12], labels[:12]
    loss, gradient, _ = teaching_gradient(m, samples, labels, cfg)
    assert math.isfinite(loss) and len(gradient) == m.parameter_count
    weights = list(m.weights())
    # Hidden weights/bias/output, action-linear coordinates and diagnostic value weights.
    indices = [
        0,
        73,
        512 * 32,
        512 * 32 + 32,
        m.actor.parameter_count - 512 + 1,
        m.actor.parameter_count - 512 + 4,
        m.actor.parameter_count,
        len(weights) - 1,
    ]
    for i in indices:
        plus, minus = list(weights), list(weights)
        plus[i] += 1e-5
        minus[i] -= 1e-5
        numeric = (
            teaching_gradient(m.with_weights(plus), samples, labels, cfg)[0]
            - teaching_gradient(m.with_weights(minus), samples, labels, cfg)[0]
        ) / 2e-5
        assert gradient[i] == pytest.approx(numeric, abs=2e-9)
    with pytest.raises(ValueError, match="legal menu"):
        teaching_gradient(m, samples, [5, *labels[1:]], cfg)
    with pytest.raises(ValueError):
        teaching_gradient(m, samples, labels[:-1], cfg)


def test_forced_menu_has_no_actor_derivative_and_frozen_teacher_still_updates_critic() -> None:
    m, cfg = model(), settings()
    data, collection = collect_round(m, TASK, score(), cfg, 0, 1, 8)
    samples, labels = teaching_examples(m, data, collection)
    _, gradient, _ = teaching_gradient(m, [samples[1]], [0], cfg)
    assert all(g == 0 for g in gradient[: m.actor.parameter_count])
    work = {"epochs_completed": 1, "optimizer_steps": 1, "sampled_decisions": len(samples)}
    updated, optimizer, _ = teach_round(
        m, Adam.zero(m.parameter_count), samples, labels, cfg, 1, work, frozen_actor=True
    )
    assert updated.actor.genome == m.actor.genome and optimizer.steps == 1
    assert updated.value_weights != m.value_weights
    with pytest.raises(ValueError, match="actual complete epoch"):
        teach_round(m, optimizer, samples, labels, cfg, 1, {**work, "optimizer_steps": 2})


def test_pair_replays_PPO_early_stopping_work_and_exact_historical_PPO_result() -> None:
    cfg, ppo = (
        {
            "rounds": 1,
            "episodes_per_round": 8,
            "frozen_actor_rounds": 1,
            "acceptance": {
                "minimum_optimal_action_probability": 0.75,
                "minimum_exact_victory_gain": 0.1,
            },
        },
        settings(),
    )
    ppo = {**ppo, "target_kl": 0.0}  # PPO stops after one complete epoch.
    pair = paired_seed(cfg, ppo, score(), 0, time.monotonic() + 20)
    methods = {m["name"]: m for m in pair["methods"]}
    assert pair["paired_actual_work_equal"]
    assert methods["ppo"]["work"] == methods["direct_teaching"]["work"]
    assert methods["ppo"]["work"]["optimizer_steps"] == 1
    assert methods["ppo"]["work"]["sample_decision_presentations"] == 48
    assert methods["ppo"]["work"]["choice_presentations"] == 8
    old = learn_task(
        TASK, score(), ppo, seed=0, rounds=1, episodes=8, deadline=time.monotonic() + 20
    )
    assert old["final_model_id"] == methods["ppo"]["final_model_id"]
    assert old["final"] == methods["ppo"]["final"]
    assert methods["hp_removed"]["final"]["greedy_accuracy"] == 0.5
    assert methods["frozen_actor"]["actor_unchanged"]
    with pytest.raises(TimeoutError):
        paired_seed(cfg, ppo, score(), 0, time.monotonic() - 1)


@pytest.mark.parametrize(
    "change", ["source", "rounds", "information", "objective", "schedule", "caps", "reference"]
)
def test_comparison_pins_sources_objective_labels_work_and_budget(
    tmp_path: Path, change: str
) -> None:
    cfg = copy.deepcopy(json.loads(CONFIG.read_text()))
    if change == "source":
        cfg["implementation_sha256"]["native_conditional_control.py"] = "0" * 64
    elif change == "rounds":
        cfg["rounds"] += 1
    elif change == "information":
        cfg["ppo_receives_optimal_action_labels"] = True
    elif change == "objective":
        cfg["objective"]["primary"] = "maximum_floor"
    elif change == "schedule":
        cfg["teaching_schedule"] = "extra_steps_until_success"
    elif change == "caps":
        cfg["resource_limits"]["wall_seconds"] = 600
    else:
        cfg["reference_control"]["id"] = "sha256:" + "0" * 64
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        load_config(ROOT, path)


def test_pinned_real_config_loads_and_old_native_and_toy_recipes_still_match() -> None:
    cfg, ppo, feature_score = load_config(ROOT, CONFIG)
    assert ppo == settings() and cfg["resource_limits"]["wall_seconds"] < 300
    assert feature_score.evaluation_objective.primary == "terminal_victory"


@pytest.mark.parametrize(
    "workspace",
    [
        "/tmp/elsewhere",
        "artifacts/../elsewhere",
        "artifacts/native-learning/native-conditional-teaching-v1",
        "artifacts/synthetic-learning/child/deeper",
    ],
)
def test_workspace_cannot_alias_production_or_escape(tmp_path: Path, workspace: str) -> None:
    with pytest.raises(ValueError):
        output_path(tmp_path, {"workspace": workspace})


def test_cached_files_are_rechecked_without_any_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {"workspace": "artifacts/synthetic-learning/cached"}
    output = output_path(tmp_path, cfg)
    output.mkdir(parents=True)
    (output / "config-at-launch.json").write_text(json.dumps(cfg))
    f = output / "seed-0.json"
    f.write_text("original")
    from spireshift.engine_qualification import _sha_file

    body = {
        "config_id": manifest_identifier(cfg),
        "status": "complete",
        "files": [{"path": f.name, "sha256": _sha_file(f)}],
    }
    report = {**body, "report_id": manifest_identifier(body)}
    (output / "report.json").write_text(json.dumps(report))
    monkeypatch.setattr(
        "spireshift.native_conditional_control.load_config", lambda *_: (cfg, settings(), score())
    )
    monkeypatch.setattr(
        "spireshift.native_conditional_control.paired_seed",
        lambda *_: pytest.fail("Unexpected fitting"),
    )
    assert run_comparison(tmp_path, Path("unused")) == report
    f.write_text("tampered")
    with pytest.raises(ValueError, match="evidence changed"):
        run_comparison(tmp_path, Path("unused"))
    (output / "report.json").unlink()
    with pytest.raises(FileExistsError, match="Preserve interrupted"):
        run_comparison(tmp_path, Path("unused"))
    assert f.read_text() == "tampered"


def test_interrupted_pair_keeps_its_sealed_prefix_and_failed_pair_in_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = {
        "workspace": "artifacts/synthetic-learning/interrupted",
        "training_seeds": [0, 1, 2],
        "resource_limits": {"wall_seconds": 180},
        "objective": {"primary": "terminal_victory"},
    }
    monkeypatch.setattr(
        "spireshift.native_conditional_control.load_config", lambda *_: (cfg, {}, None)
    )

    def fail_after_round(*args: Any) -> Any:
        output: Path = args[-1]
        body = {
            "training_seed": 0,
            "round": 1,
            "collection": {"complete_synthetic_episodes": 8},
            "optimizer": {
                "ppo": {"optimizer_steps": 1},
                "direct_teaching": {"optimizer_steps": 1},
            },
        }
        (output / "seed-0-round-01.json").write_text(
            json.dumps({**body, "report_id": manifest_identifier(body)})
        )
        raise TimeoutError("simulated cap after a sealed round")

    monkeypatch.setattr("spireshift.native_conditional_control.paired_seed", fail_after_round)
    r = run_comparison(tmp_path, Path("unused"))
    assert r["status"] == "incomplete" and not r["comparison_integrity_pass"]
    assert r["planned_training_pairs"] == 3 and r["completed_training_pairs"] == 0
    assert r["failed_training_pairs"] == 1 and r["not_attempted_training_pairs"] == 2
    assert r["sealed_rounds"] == 1 and r["sampled_synthetic_episodes"] == 8
    assert r["synthetic_optimizer_steps"] == 2 and r["unsealed_partial_work_unknown"]
    monkeypatch.setattr(
        "spireshift.native_conditional_control.paired_seed",
        lambda *_: pytest.fail("Interrupted study unexpectedly restarted"),
    )
    assert run_comparison(tmp_path, Path("unused")) == r
