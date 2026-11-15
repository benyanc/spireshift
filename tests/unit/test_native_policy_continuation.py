from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_optimizer_trial import fake as legacy_fake

import spireshift.native_policy_continuation as continuation
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Adam, fit_round
from spireshift.native_compact_training import prepare_compact
from spireshift.native_context_cache import cached_model
from spireshift.native_context_journal import load_state, save_state
from spireshift.native_context_resume import ordered_paths
from spireshift.native_continuation_plan import (
    STOP_RULE,
    decide,
    final_plan,
    training_plan,
    validate,
)
from spireshift.native_policy_confirmation import COMPLETE as CONFIRMATION_COMPLETE

LOAD = continuation.load_continuation


def recipe(short: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg: dict[str, Any] = {
        "schema_version": "native-policy-continuation-config-v1",
        "stage": "short_bridge_control" if short else "bounded_standard_continuation",
        "training_seeds": [2, 3],
        "starting_training_games": 512,
        "starting_round": 16,
        "additional_games_per_player": 2 if short else 1024,
        "batch_games": 2 if short else 32,
        "chunk_games": 2 if short else 8,
        "evaluation_games": 2 if short else 32,
        "holdout_games": 0 if short else 64,
        "milestones": [514] if short else [768, 1024, 1280, 1536],
        "stopping_rule": STOP_RULE,
        "checkpoint_selection": "both_current_stopping_states_not_best_seen",
        "invocation_wall_seconds": 240 if short else 14400,
        "session_limits": {
            "wall_seconds": 240 if short else 900,
            "cpu_seconds": 480 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 8000000000,
        },
        "workspace": "artifacts/continuation-test",
        "players": [{"numerical_seed": n} for n in (2, 3)],
    }
    rows: list[dict[str, Any]] = []
    for n in (2, 3):
        for part, size in [
            ("control" if short else "train", cfg["additional_games_per_player"]),
            ("control_eval" if short else "development", cfg["evaluation_games"]),
            ("holdout", cfg["holdout_games"]),
        ]:
            for i in range(size):
                rows.append(
                    {
                        "id": len(rows) + 100,
                        "seed": f"CONTINUE{n}{part}{i}",
                        "partition": part,
                        "numerical_seed": n,
                    }
                )
    return cfg, {"seeds": rows}


def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    q, _, _, parent, path, node, launched = legacy_fake(tmp_path, monkeypatch)
    cfg, seeds = recipe()
    cfg["players"] = []
    cfg["seed_manifest"] = {"path": "unused", "id": "seed-manifest"}
    for n in (2, 3):
        m = cached_model(model(seed=n))
        # Nonzero, asymmetric moments make a silent Adam reset observable.
        optimizer = Adam(
            1353 if n == 2 else 1413,
            tuple(0.001 * (i % 3) for i in range(m.parameter_count)),
            (0.01,) * m.parameter_count,
        )
        p = tmp_path / f"source-{n}.json"
        save_state(p, m, optimizer)
        state_id = load_state(p)[2]
        cfg["players"].append(
            {
                "numerical_seed": n,
                "version": "trained",
                "path": p.name,
                "state_id": state_id,
                "model_id": m.model_id,
                "sha256": _sha_file(p),
            }
        )
    path.write_text(json.dumps(cfg))
    sources = {p["path"]: p["sha256"] for p in cfg["players"]}
    monkeypatch.setattr(
        continuation, "load_continuation", lambda *_: (cfg, parent, seeds, dict(sources))
    )
    monkeypatch.setattr(continuation, "load_training_score_spec", lambda *_: score())
    return q, cfg, parent, seeds, path, node, launched


def test_finite_full_plan_preserves_round_17_and_disjoint_seed_ownership() -> None:
    cfg, seeds = recipe(False)
    validate(cfg, seeds)
    tasks = continuation.maximum_plan(cfg, seeds)
    assert len(tasks) == 398 and sum(len(t.get("seeds", [])) for t in tasks) == 2624
    fits = [t for t in tasks if t["kind"] == "fit"]
    assert len(fits) == 64
    for n in (2, 3):
        own_fits = [t for t in fits if t["numerical_seed"] == n]
        assert [t["round"] for t in own_fits] == list(range(17, 49))
        assert own_fits[0]["state"] == f"seed-{n}-restore"
        assert all(len(t["round_seed_ids"]) == 32 for t in own_fits)
    train = [s["id"] for t in tasks if t.get("training") for s in t["seeds"]]
    dev = {
        s["id"] for t in tasks if t.get("panel", "").startswith("development") for s in t["seeds"]
    }
    holdout = {
        s["id"] for t in tasks if t.get("panel", "").startswith("holdout") for s in t["seeds"]
    }
    assert len(train) == len(set(train)) == 2048
    assert len(dev) == 64 and len(holdout) == 128
    assert not set(train) & (dev | holdout) and not dev & holdout
    assert not any("holdout" in str(t) for t in training_plan(cfg, seeds))
    assert all(t["milestone"] == 512 for t in tasks if t.get("panel") == "holdout-initial")


@pytest.mark.parametrize(
    "fault", ["seed_id", "native_seed", "partition", "round_reset", "horizon", "selection", "caps"]
)
def test_plan_rejects_reset_leakage_or_unbounded_extension(fault: str) -> None:
    cfg, seeds = recipe(False)
    if fault == "seed_id":
        seeds["seeds"][1]["id"] = seeds["seeds"][0]["id"]
    elif fault == "native_seed":
        seeds["seeds"][1]["seed"] = seeds["seeds"][0]["seed"]
    elif fault == "partition":
        seeds["seeds"][0]["partition"] = "holdout"
    elif fault == "round_reset":
        cfg["starting_round"] = 0
    elif fault == "horizon":
        cfg["additional_games_per_player"] = 1000000
    elif fault == "selection":
        cfg["checkpoint_selection"] = "best_seen"
    else:
        cfg["session_limits"]["wall_seconds"] = 1000000
    with pytest.raises(ValueError):
        validate(cfg, seeds)


def test_restoration_resumption_is_numerically_identical_to_uninterrupted_nonzero_Adam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, parent, seeds, path, node, launched = setup(tmp_path, monkeypatch)
    protected = {p["path"]: (q.root / p["path"]).read_bytes() for p in cfg["players"]}
    assert continuation.session(q, path, node, status_only=True)["completed_units"] == 0
    assert not (q.root / cfg["workspace"]).exists()
    first = continuation.session(q, path, node, maximum_steps=6)
    assert first["fit_rounds"] == [17] and first["starting_optimizer_steps"] == {
        "2": 1353,
        "3": 1413,
    }
    tasks = training_plan(cfg, seeds)
    fit = next(t for t in tasks if t["kind"] == "fit")
    base = q.root / cfg["workspace"] / "chunks"
    paths = [
        q.root / p
        for k in fit["collections"]
        for p in json.loads((base / k / "done.json").read_text())["result"]["paths"]
    ]
    paths = ordered_paths(paths, fit["round_seed_ids"])
    m, original_adam, _ = load_state(q.root / cfg["players"][0]["path"])
    samples, _ = prepare_compact(
        paths, m, score(), parent["learning"]["ppo"], parent["learning"]["credit_assignment"], 17
    )
    expected, expected_adam, _ = fit_round(
        cast(Any, m), original_adam, samples, parent["learning"]["ppo"], 17
    )
    saved_path = base / fit["key"] / "state.json"
    actual, actual_adam, _ = load_state(saved_path)
    assert actual.model_id == expected.model_id and actual_adam == expected_adam
    assert actual_adam.steps > original_adam.steps and any(actual_adam.first)
    before = saved_path.read_bytes()
    final = continuation.session(q, path, node)
    assert final["status"] == continuation.CONTROL and final["games_recorded"] == 12
    assert final["fit_rounds"] == [17, 17] and len(launched) == 12
    assert (
        final["ending_optimizer_steps"]["2"] > 1353 and final["ending_optimizer_steps"]["3"] > 1413
    )
    assert saved_path.read_bytes() == before
    assert all((q.root / p).read_bytes() == data for p, data in protected.items())
    assert continuation.session(q, path, node, status_only=True) == final
    assert continuation.session(q, path, node) == final and len(launched) == 12


def test_plateau_rule_uses_wins_first_and_keeps_current_states_without_holdout_peeking() -> None:
    cfg, seeds = recipe(False)
    tasks = training_plan(cfg, seeds)
    decisions = [t for t in tasks if t["kind"] == "decide"]
    completed: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if task["kind"] == "collect" and not task["training"]:
            floor = 9 if task["milestone"] == 512 else 10
            completed[task["key"]] = {
                "result": {
                    "summary": {
                        "outcomes": [
                            {"status": "terminal", "maximum_floor": floor, "victory": False}
                            for _ in task["seeds"]
                        ]
                    }
                }
            }
    # Holdout contents are neither a dependency nor an input of this rule.
    completed["hostile-holdout"] = {
        "result": {"summary": {"outcomes": [{"victory": True, "maximum_floor": 999}]}}
    }
    for task in decisions[:3]:
        completed[task["key"]] = {"result": decide(cfg, task, completed)}
    end = completed[decisions[2]["key"]]["result"]
    assert end["stop"] and end["reason"] == "development_plateau" and end["milestone"] == 1280
    assert end["states"] == decisions[2]["states"] != decisions[0]["states"]
    assert not end["holdout_consulted"] and end["stale_checks"] == 2
    tests = final_plan(cfg, seeds, end)
    assert len(tests) == 32 and all(
        t["state"] in {f"seed-{n}-restore" for n in (2, 3)} | set(end["states"].values())
        for t in tests
    )
    # A victory increase wins over even a large floor decrease.
    victory = copy.deepcopy(completed)
    row = victory[decisions[0]["evaluations"][0]]["result"]["summary"]["outcomes"][0]
    row.update(victory=True, maximum_floor=1)
    d = decide(cfg, decisions[0], victory)
    assert d["improved_over_previous_best"] and d["stale_checks"] == 0


def test_final_holdout_opens_after_stop_and_never_supplies_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, parent, seeds, path, node, launched = setup(tmp_path, monkeypatch)
    cfg.update(stage="bounded_standard_continuation", holdout_games=2)
    cfg["session_limits"]["wall_seconds"] = 900
    for s in seeds["seeds"]:
        s["partition"] = "train" if s["partition"] == "control" else "development"
    for n in (2, 3):
        seeds["seeds"].extend(
            {
                "id": 1000 + n * 10 + i,
                "seed": f"HOLDOUT{n}{i}",
                "partition": "holdout",
                "numerical_seed": n,
            }
            for i in range(2)
        )
    path.write_text(json.dumps(cfg))
    prefix = continuation.session(q, path, node, maximum_steps=10)
    assert prefix["ending"] is None and not prefix["holdout"] and len(launched) == 12
    done = continuation.session(q, path, node)
    assert done["status"] == continuation.COMPLETE and done["games_recorded"] == 20
    assert done["maximum_planned_games"] == done["scheduled_games_at_stop"] == 20
    assert (
        len(done["holdout"]) == 4
        and done["final_holdout_comparison"]["aggregate"]["trained"]["denominator"] == 4
    )
    assert not done["checkpoint_promoted"] and not done["automatic_extension_follows"]
    p = next(
        (q.root / cfg["workspace"] / "chunks/seed-2-holdout-initial-00/games").glob("case-*.json")
    )
    m = load_state(q.root / cfg["players"][0]["path"])[0]
    with pytest.raises(ValueError, match="current-behavior training"):
        prepare_compact(
            [p], m, score(), parent["learning"]["ppo"], parent["learning"]["credit_assignment"], 18
        )


def test_uncertain_chunk_and_corrupted_optimizer_never_auto_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, _, _, path, node, launched = setup(tmp_path, monkeypatch)
    continuation.session(q, path, node, maximum_steps=2)
    import spireshift.native_optimizer_trial as qualified

    original = qualified.__dict__["collect_panel"]

    def interrupted(*args: Any) -> Any:
        original(*args)
        raise TimeoutError("Uncertain delivery")

    monkeypatch.setattr(qualified, "collect_panel", interrupted)
    with pytest.raises(TimeoutError):
        continuation.session(q, path, node)
    count = len(launched)
    with pytest.raises(FileExistsError, match="uncommitted"):
        continuation.session(q, path, node)
    assert len(launched) == count


def test_corrupt_restored_optimizer_is_rejected_before_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, _, _, path, node, launched = setup(tmp_path, monkeypatch)
    continuation.session(q, path, node, maximum_steps=2)
    p = q.root / cfg["workspace"] / "chunks/seed-2-restore/state.json"
    d = json.loads(p.read_text())
    d["optimizer"]["steps"] = 0
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="evidence changed"):
        continuation.session(q, path, node)
    assert not launched


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "player_selection",
        "reset_round",
        "overlap_id",
        "overlap_native",
        "unfinished_confirmation",
        "source_change",
    ],
)
def test_loader_requires_confirmed_players_full_states_and_fresh_partitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    from spireshift.full_run_experience import atomic_json

    q, cfg, parent, seeds, path, _, _ = setup(tmp_path, monkeypatch)
    trusted = {
        "players": cfg["players"],
        "workspace": "artifacts/confirmed",
        "seed_manifest": {"path": "old-seeds.json"},
        "excluded_seed_manifests": [],
    }
    p = q.root / "confirmation.json"
    atomic_json(p, trusted)
    monkeypatch.setattr(continuation, "load_confirmation", lambda *_: (trusted, parent, {}, {}))
    protected = {r["path"]: r["sha256"] for r in cfg["players"]}
    report = {
        "status": CONFIRMATION_COMPLETE,
        "config_id": manifest_identifier(trusted),
        "games_recorded": 256,
        "completed_units": 32,
        "comparison": {"auxiliary_progress_confirmed": fault != "unfinished_confirmation"},
        "optimizer_steps": 0,
        "sources": protected,
    }
    rp = q.root / trusted["workspace"] / "report.json"
    atomic_json(rp, {**report, "report_id": manifest_identifier(report)})
    cfg["confirmation_config"] = {"path": p.name, "id": manifest_identifier(trusted)}
    cfg["confirmation_report"] = {
        "path": str(rp.relative_to(q.root)),
        "id": manifest_identifier(report),
    }
    monkeypatch.setattr(continuation, "SOURCES", ())
    cfg["implementation_sha256"] = {}
    (q.root / "scripts").mkdir()
    entry = q.root / "scripts/policy-continuation-v1.py"
    entry.write_text("frozen entry")
    cfg["entry_sha256"] = _sha_file(entry)
    previous = {"seeds": [{"id": 1, "seed": "OLD"}]}
    if fault == "overlap_id":
        previous["seeds"][0]["id"] = seeds["seeds"][0]["id"]
    if fault == "overlap_native":
        previous["seeds"][0]["seed"] = seeds["seeds"][0]["seed"]
    atomic_json(
        q.root / "old-seeds.json", {**previous, "manifest_id": manifest_identifier(previous)}
    )
    cfg["excluded_seed_manifests"] = [
        {"path": "old-seeds.json", "id": manifest_identifier(previous)}
    ]
    seeds["environment_id"] = parent["environment_manifest"]["id"]
    sp = q.root / "continuation-seeds.json"
    atomic_json(sp, {**seeds, "manifest_id": manifest_identifier(seeds)})
    cfg["seed_manifest"] = {"path": sp.name, "id": manifest_identifier(seeds)}
    if fault == "player_selection":
        cfg["players"] = cfg["players"][:1]
    elif fault == "reset_round":
        cfg["starting_round"] = 0
    elif fault == "source_change":
        (q.root / cfg["players"][0]["path"]).write_text("changed source")
    path.write_text(json.dumps(cfg))
    if fault is None:
        actual, actual_parent, actual_seeds, sources = LOAD(q, path)
        assert actual == cfg and actual_parent == parent and actual_seeds["seeds"] == seeds["seeds"]
        assert set(protected) <= sources.keys()
    else:
        with pytest.raises(ValueError):
            LOAD(q, path)
