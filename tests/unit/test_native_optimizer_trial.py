from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score, settings
from test_native_context_trial import case

import spireshift.native_optimizer_trial as trial
from spireshift.engine_experience import save_native_episode
from spireshift.engine_experience_stream import compact_case
from spireshift.engine_learning import summarize
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_game import predict
from spireshift.native_context_journal import ChunkJournal, load_state
from spireshift.native_context_resume import request_for


def plan(short: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg: dict[str, Any] = {
        "stage": "short_bridge_control" if short else "bounded_optimizer_learning_curve",
        "training_seeds": [2] if short else [2, 3],
        "arms": list(trial.ARMS),
        "games_per_player": 2 if short else 512,
        "evaluation_games": 2 if short else 16,
        "milestones": [2] if short else [128, 256, 384, 512],
        "chunk_games": 2 if short else 8,
    }
    rows = [
        {"id": i, "seed": f"TRAIN{i}", "partition": "control" if short else "train"}
        for i in range(len(cfg["training_seeds"]) * cfg["games_per_player"])
    ]
    rows.extend(
        {
            "id": 10000 + i,
            "seed": f"EVAL{i}",
            "partition": "control_eval" if short else "development",
        }
        for i in range(len(cfg["training_seeds"]) * cfg["evaluation_games"])
    )
    return cfg, {"seeds": rows}


def test_fixed_plan_matches_game_budgets_stages_and_allows_all_training_decisions() -> None:
    cfg, seeds = plan(False)
    tasks = trial.plan(cfg, seeds)
    assert len(tasks) == 340 and len({t["key"] for t in tasks}) == len(tasks)
    assert sum(len(t.get("seeds", [])) for t in tasks) == 2368
    for n in (2, 3):
        trainsets = []
        for arm, size in (("standard", 32), ("larger-batch", 128)):
            selected = [t for t in tasks if t["numerical_seed"] == n and t["arm"]["name"] == arm]
            training = [t for t in selected if t["kind"] == "collect" and t["training"]]
            ids = [s["id"] for t in training for s in t["seeds"]]
            trainsets.append(set(ids))
            assert len(ids) == len(set(ids)) == 512
            fits = [t for t in selected if t["kind"] == "fit"]
            assert len(fits) == 512 // size and all(len(t["round_seed_ids"]) == size for t in fits)
            evals = [t for t in selected if t["kind"] == "collect" and not t["training"]]
            assert len(evals) == 10 and not set(ids) & {s["id"] for t in evals for s in t["seeds"]}
            assert {t["panel"] for t in training} == {
                "train"
            }  # Same per-seed random salt across batch sizes.
        assert trainsets[0] == trainsets[1]
    assert not {
        s["id"] for t in tasks if t.get("training") and t["numerical_seed"] == 2 for s in t["seeds"]
    } & {
        s["id"] for t in tasks if t.get("training") and t["numerical_seed"] == 3 for s in t["seeds"]
    }


def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    cfg, seeds = plan(True)
    cfg.update(
        row_storage="readonly_sparse_uint16_float64_v1",
        workspace="artifacts/optimizer-test",
        session_limits={"wall_seconds": 180},
        implementation_sha256={},
        seed_manifest={"path": "seeds.json"},
    )
    atomic_json(tmp_path / "seeds.json", seeds)
    cfg["probe_config"] = {"path": "probe.json"}
    atomic_json(tmp_path / "probe.json", {"unit": True})
    cfg["compact_check"] = {"path": "compact.json"}
    atomic_json(tmp_path / "compact.json", {"unit": True})
    parent = {
        "environment_manifest": {"id": model().actor.environment_id},
        "training_spec": {"path": "unused"},
        "learning": {
            "ppo": settings(),
            "credit_assignment": {
                "baseline": "public_residual_ridge",
                "regularization": 0.001,
                "folds": 4,
                "fold_salt": "native-whole-run-value-crossfit-v1",
            },
        },
    }
    path = tmp_path / "recipe.json"
    atomic_json(path, cfg)
    node = tmp_path / "node"
    node.touch()
    launched = []

    def collect(*args: Any) -> tuple[Any, ...]:
        rows, out, m = args[4], args[6], args[7]
        out.mkdir()
        paths = []
        outcomes = []
        for s in rows:
            launched.append((str(out), s["id"]))
            c = case(
                s["seed"], lambda p, seed=s["id"]: predict(m, score(), p, random.Random(seed), 0.8)
            )
            c["worker_workspace"] = "fake"
            p = out / f"case-{s['id']}.json"
            save_native_episode(
                p,
                c,
                {
                    "partition": s["partition"],
                    "panel_purpose": "training" if args[11] else "frozen_policy_evaluation",
                    "model_id": m.model_id,
                    "seed_id": s["id"],
                    "environment_id": m.actor.environment_id,
                    "training_spec_id": score().spec_id,
                },
            )
            paths.append(p)
            outcomes.append({**compact_case(c), "seed_id": s["id"], "training_return": 0.01})
        summary = {
            **summarize(
                [{**o, "decisions": range(o["decision_count"])} for o in outcomes], len(rows)
            ),
            "outcomes": outcomes,
        }
        return paths, summary, {}

    monkeypatch.setattr(trial, "load_trial", lambda *_: (cfg, parent, seeds))
    monkeypatch.setattr(trial, "load_training_score_spec", lambda *_: score())
    monkeypatch.setattr(trial, "initialize", lambda e, s, n, mode: model(mode, n))
    monkeypatch.setattr(trial, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(trial, "_running_games", lambda: False)
    monkeypatch.setattr(trial, "launch_inputs", lambda *_: {})
    monkeypatch.setattr(trial, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(trial, "immutable_checks", lambda *_: {"unchanged": True})
    monkeypatch.setattr(trial, "collect_panel", collect)
    return (
        EngineQualificationConfig(document={}, root=tmp_path),
        cfg,
        seeds,
        parent,
        path,
        node,
        launched,
    )


def test_pause_restore_identical_initializers_and_complete_final_only_curve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, _, _, path, node, launched = fake(tmp_path, monkeypatch)
    first = trial.session(q, path, node, maximum_steps=4)
    assert first["completed_units"] == 4 and first["games_recorded"] == 2
    workspace = q.root / cfg["workspace"]
    a = load_state(workspace / "chunks/seed-2-standard-initial/state.json")[0]
    b = load_state(workspace / "chunks/seed-2-larger-batch-initial/state.json")[0]
    assert a.model_id == b.model_id
    before = (workspace / "chunks/seed-2-standard-batch-001-fit/state.json").read_bytes()
    result = trial.session(q, path, node)
    assert result["status"] == "native_optimizer_control_pass" and result["games_recorded"] == 8
    assert len(launched) == 8 and len(result["learning_curves"]) == 2
    assert (workspace / "chunks/seed-2-standard-batch-001-fit/state.json").read_bytes() == before
    assert (
        result["candidate_changes_batch_size_and_reuse_together"]
        and not result["checkpoint_promoted"]
    )
    assert trial.session(q, path, node) == result and len(launched) == 8


def test_read_only_status_and_running_game_guard_preserve_finished_units(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, _, _, path, node, launched = fake(tmp_path, monkeypatch)
    r = trial.session(q, path, node, status_only=True)
    assert r["completed_units"] == 0 and not (q.root / cfg["workspace"]).exists()
    trial.session(q, path, node, maximum_steps=2)
    monkeypatch.setattr(trial, "_running_games", lambda: True)
    with pytest.raises(ValueError, match="Close the game"):
        trial.session(q, path, node)
    assert (
        not launched and len(list((q.root / cfg["workspace"] / "chunks").glob("*/done.json"))) == 2
    )


def test_failure_allowance_is_shared_across_the_whole_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, seeds, parent, path, node, _ = fake(tmp_path, monkeypatch)
    trial.session(q, path, node, maximum_steps=2)
    store = ChunkJournal(q.root, cfg)
    completed: dict[str, dict[str, Any]] = {}
    tasks = trial.plan(cfg, seeds)
    for t in tasks[:2]:
        r = store.completed(t["key"], request_for(t, completed))
        assert r is not None
        completed[t["key"]] = r
    task = tasks[2]
    completed["earlier"] = {
        "result": {"failure_group": task["failure_group"], "summary": {"failed_games": 2}}
    }
    original = trial.__dict__["collect_panel"]

    def failed(*args: Any) -> tuple[Any, ...]:
        paths, summary, sources = original(*args)
        summary["failed_games"] = 1
        return paths, summary, sources

    monkeypatch.setattr(trial, "collect_panel", failed)
    with store.lock(), pytest.raises(ValueError, match="Aggregate"):
        trial.execute(
            q,
            cfg,
            parent,
            score(),
            node,
            store,
            task,
            request_for(task, completed),
            completed,
            1e12,
        )
    with pytest.raises(FileExistsError, match="uncommitted"):
        store.completed(task["key"], request_for(task, completed))


def test_final_comparison_retains_failed_evaluation_games_and_paired_seed_ownership() -> None:
    cfg, _ = plan(False)
    evaluations = []
    for n in cfg["training_seeds"]:
        for arm in cfg["arms"]:
            for milestone in (0, 512):
                outcomes = [
                    {
                        "seed_id": i,
                        "maximum_floor": 7 if milestone == 0 else 9,
                        "status": "terminal",
                        "victory": False,
                        "decisions": range(1),
                        "completed_acts": 0,
                        "cpu_seconds": 0.1,
                        "seed": str(i),
                        "worker_workspace": "fake",
                    }
                    for i in range(16)
                ]
                if milestone == 512 and arm["name"] == "larger-batch":
                    outcomes[0]["status"] = "failed"
                summary = summarize(outcomes, 16)
                evaluations.append(
                    {
                        "numerical_seed": n,
                        "arm": arm["name"],
                        "training_games": milestone,
                        "outcomes": outcomes,
                        "summary": summary,
                    }
                )
    result = trial.compare_final(cfg, evaluations)
    assert all(m["denominator"] == 32 and m["wins"] == 0 for m in result["methods"])
    assert result["methods"][1]["failed_games"] == 2 and not result["automatic_promotion"]
    evaluations[-1]["outcomes"].pop()
    with pytest.raises(ValueError, match="paired evaluation"):
        trial.compare_final(cfg, evaluations)
