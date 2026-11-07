from __future__ import annotations

import copy
import json
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score, settings
from test_native_context_trial import case

import spireshift.native_context_resume as runner
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.engine_experience_stream import compact_case
from spireshift.engine_learning import summarize
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam, fit_round
from spireshift.native_action_context import CROSSED, MODES, ORIGINAL
from spireshift.native_action_context_study import catalog, collect
from spireshift.native_conditional_control import TASK
from spireshift.native_context_cache import CachedContextModel, cached_model
from spireshift.native_context_game import predict, verified_samples
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_learning_control import public_input


@pytest.mark.parametrize("mode", MODES)
def test_cache_preserves_identity_inputs_draws_probabilities_and_serialization(mode: str) -> None:
    original, spec = model(mode), score()
    fast = cached_model(original)
    assert fast.model_id == original.model_id and fast.as_dict() == original.as_dict()
    for high in (False, True):
        for reverse in (False, True):
            p = public_input(TASK, high, reverse=reverse)
            assert predict(original, spec, p, random.Random(1), 0.8) == predict(
                fast, spec, p, random.Random(1), 0.8
            )
    with pytest.raises(FrozenInstanceError):
        fast.mode = ORIGINAL  # type: ignore[misc]
    assert CachedContextModel.from_mapping(fast.as_dict()).as_dict() == original.as_dict()


def test_identity_hash_is_cached_once_and_new_weights_get_a_new_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = model()
    expected = original.model_id
    calls: list[Any] = []

    def identifier(value: dict[str, Any]) -> str:
        calls.append(value)
        return manifest_identifier(value)

    monkeypatch.setattr("spireshift.native_action_context.manifest_identifier", identifier)
    fast = cached_model(original)
    assert calls and len(calls) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda _: fast.model_id, range(100))) == [expected] * 100
    assert len(calls) == 1
    weights = list(fast.weights())
    weights[-1] += 0.01
    changed = fast.with_weights(weights)
    assert isinstance(changed, CachedContextModel) and changed.model_id != expected
    assert fast.model_id == expected and len(calls) == 2


def test_optimizer_state_survives_restart_and_continuation_is_numerically_identical(
    tmp_path: Path,
) -> None:
    spec, cfg = score(), settings()
    initial = cached_model(model(CROSSED))
    samples, _, _ = collect(initial, catalog(initial, spec), cfg, 0, 1, 8)
    fitted, opt, _ = fit_round(
        cast(Any, initial), Adam.zero(initial.parameter_count), samples, cfg, 1
    )
    assert isinstance(fitted, CachedContextModel)
    p = tmp_path / "checkpoint.json"
    save_state(p, fitted, opt)
    restored, restored_opt, _ = load_state(p)
    assert restored.as_dict() == fitted.as_dict() and restored_opt == opt
    assert restored_opt.steps > 0 and any(restored_opt.first) and any(restored_opt.second)
    second, _, _ = collect(restored, catalog(restored, spec), cfg, 0, 2, 8)
    a, ao, _ = fit_round(cast(Any, fitted), opt, second, cfg, 2)
    b, bo, _ = fit_round(cast(Any, restored), restored_opt, second, cfg, 2)
    assert a.as_dict() == b.as_dict() and ao == bo
    with pytest.raises(FileExistsError):
        save_state(p, restored, restored_opt)
    changed = json.loads(p.read_text())
    changed["optimizer"]["steps"] = 0
    p.write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        load_state(p)


def test_chunk_receipt_skips_completed_work_and_guards_predecessor_and_source_bytes(
    tmp_path: Path,
) -> None:
    recipe = {"workspace": "artifacts/chunk-test", "setting": 1}
    journal = ChunkJournal(tmp_path, recipe)
    request = {"kind": "fit", "before_state": "immutable", "seeds": [1, 2]}
    assert journal.completed("round-1", request) is None
    with journal.lock():
        target = journal.begin("round-1", request)
        (target / "data.json").write_text("preserved")
        receipt = journal.commit("round-1", request, {"steps": 3})
    reloaded = ChunkJournal(tmp_path, recipe)
    assert reloaded.completed("round-1", request) == receipt
    with pytest.raises(ValueError, match="predecessor"):
        reloaded.completed("round-1", {**request, "before_state": "different"})
    (target / "data.json").write_text("modified")
    with pytest.raises(ValueError, match="evidence changed"):
        reloaded.completed("round-1", request)
    with (
        pytest.raises(ValueError, match="recipe changed"),
        ChunkJournal(tmp_path, {**recipe, "setting": 2}).lock(),
    ):
        pytest.fail("Changed recipe acquired the comparison")


def test_interrupted_chunk_and_concurrent_launches_never_replay_or_erase_work(
    tmp_path: Path,
) -> None:
    journal = ChunkJournal(tmp_path, {"workspace": "artifacts/interrupted"})
    with journal.lock():
        target = journal.begin("chunk-1", {"kind": "collect", "seeds": [1, 2]})
        marker = target / "native-active.json"
        marker.write_text("preserve")
        with (
            pytest.raises(ValueError, match="Another process"),
            ChunkJournal(tmp_path, journal.recipe).lock(),
        ):
            pytest.fail("Concurrent writer was admitted")
    with pytest.raises(FileExistsError, match="uncommitted"):
        journal.completed("chunk-1", {"kind": "collect", "seeds": [1, 2]})
    assert marker.read_text() == "preserve"
    with journal.lock(), pytest.raises(FileExistsError):
        journal.begin("chunk-1", {"kind": "collect", "seeds": [1, 2]})
    assert marker.read_text() == "preserve"


def test_cached_model_does_not_weaken_saved_behavior_verification() -> None:
    m, spec = cached_model(model()), score()
    p = public_input(TASK, False)
    case: dict[str, Any] = {
        "status": "terminal",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": [{"public_input": p, "choice": predict(m, spec, p, random.Random(0), 0.8)}],
    }
    assert len(verified_samples(case, m, spec, 0.01, 0.8)) == 1
    broken = copy.deepcopy(case)
    broken["decisions"][0]["choice"]["model_id"] = "wrong"
    with pytest.raises(ValueError, match="stale"):
        verified_samples(broken, m, spec, 0.01, 0.8)


def fake_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    q = EngineQualificationConfig(document={}, root=tmp_path)
    cfg: dict[str, Any] = {
        "stage": "short_bridge_control",
        "modes": [ORIGINAL, CROSSED],
        "training_seed": 0,
        "rounds": 1,
        "games_per_round": 2,
        "chunk_games": 2,
        "evaluation_games": 2,
        "session_limits": {"wall_seconds": 180},
        "workspace": "artifacts/chunks",
        "implementation_sha256": {},
        "seed_manifest": {"id": "fake"},
    }
    seeds = {
        "seeds": [
            {"id": i, "seed": f"TRAIN{i}", "partition": "control" if i <= 2 else "control_eval"}
            for i in range(1, 5)
        ]
    }
    parent = {
        "environment_manifest": {"id": score().scope.ruleset_manifest_id},
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
    path, node = tmp_path / "recipe.json", tmp_path / "node"
    atomic_json(path, cfg)
    node.touch()
    launched: list[tuple[str, int]] = []

    def collect(*args: Any) -> tuple[list[Path], dict[str, Any], dict[str, str]]:
        rows, out, m = args[4], args[6], args[7]
        out.mkdir()
        paths, outcomes = [], []
        for s in rows:
            launched.append((m.mode, s["id"]))
            c = case(
                s["seed"], lambda p, seed=s["id"]: predict(m, score(), p, random.Random(seed), 0.8)
            )
            c["worker_workspace"] = "fake-worker"
            p = out / f"case-{s['id']}.json"
            save_native_episode(
                p,
                c,
                {
                    "partition": s["partition"],
                    "panel_purpose": "training" if args[11] else "frozen_policy_evaluation",
                    "model_id": m.model_id,
                    "seed_id": s["id"],
                },
            )
            paths.append(p)
            outcomes.append({**compact_case(c), "seed_id": s["id"], "training_return": 0.01})
        summary = {
            **summarize(
                [{**c, "decisions": range(c["decision_count"])} for c in outcomes], len(rows)
            ),
            "outcomes": outcomes,
            "model_id": m.model_id,
        }
        return paths, summary, {}

    monkeypatch.setattr(runner, "load_resume", lambda *_: (cfg, parent, seeds))
    monkeypatch.setattr(runner, "load_training_score_spec", lambda *_: score())
    monkeypatch.setattr(runner, "initialize", lambda e, s, n, mode: model(mode))
    monkeypatch.setattr(runner, "launch_inputs", lambda *_: {})
    monkeypatch.setattr(runner, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(runner, "_running_games", lambda: False)
    monkeypatch.setattr(runner, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(runner, "immutable_checks", lambda *_: {"unchanged": True})
    monkeypatch.setattr(runner, "collect_panel", collect)
    return q, cfg, path, node, launched


def test_session_restores_committed_fit_and_never_recollects_or_refits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, path, node, launched = fake_session(tmp_path, monkeypatch)
    first = runner.session(q, path, node, maximum_steps=3)
    assert first["completed_chunks"] == 3 and first["new_games_this_session"] == 2
    state_path = q.root / cfg["workspace"] / "chunks/base-round-001-fit/state.json"
    before = state_path.read_bytes()
    _, opt, state_id = load_state(state_path)
    assert opt.steps > 0
    second = runner.session(q, path, node)
    assert second["status"] == "chunked_native_control_pass" and second["games_recorded"] == 8
    assert second["new_games_this_session"] == 6
    assert len(set(launched)) == len(launched) == 8
    assert state_path.read_bytes() == before and load_state(state_path)[2] == state_id
    again = runner.session(q, path, node)
    assert again == second
    assert len(launched) == 8 and again["report_id"] == second["report_id"]


def test_status_is_read_only_and_preflight_does_not_leave_uncertain_chunk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q, cfg, path, node, launched = fake_session(tmp_path, monkeypatch)
    status = runner.session(q, path, node, status_only=True)
    assert status["completed_chunks"] == 0 and not (q.root / cfg["workspace"]).exists()
    runner.session(q, path, node, maximum_steps=1)
    monkeypatch.setattr(runner, "_running_games", lambda: True)
    with pytest.raises(ValueError, match="Close the game"):
        runner.session(q, path, node)
    assert not launched
    assert not (q.root / cfg["workspace"] / "chunks/base-round-001-collect-00").exists()


def test_chunked_collection_keeps_historical_whole_round_lane_order(tmp_path: Path) -> None:
    paths = []
    # Two separate four-game chunks return each lane's games contiguously.
    for seed in (1, 3, 2, 4, 5, 7, 6, 8):
        p = tmp_path / f"{seed}.json"
        atomic_json(p, {"binding": {"seed_id": seed}})
        paths.append(p)
    ordered = runner.ordered_paths(paths, list(range(1, 9)))
    assert [int(p.stem) for p in ordered] == [1, 3, 5, 7, 2, 4, 6, 8]
    with pytest.raises(ValueError):
        runner.ordered_paths(paths[:-1], list(range(1, 9)))
    with pytest.raises(ValueError):
        runner.ordered_paths([*paths, paths[0]], list(range(1, 9)))


def test_evaluation_keeps_failed_games_in_original_denominator() -> None:
    initial = [
        {"seed_id": i, "maximum_floor": 6, "status": "terminal", "victory": False}
        for i in range(16)
    ]
    final = [
        {
            **c,
            "maximum_floor": 8,
            "status": "failed" if c["seed_id"] == 0 else "terminal",
            "victory": c["seed_id"] == 0,
        }
        for c in initial
    ]
    result = runner.evaluation_change(CROSSED, 1, initial, final, "test")
    assert result["final_failed_games"] == 1 and result["planned_evaluation_games"] == 16
    assert result["mean_floor_change"] == 2 and result["wins_change"] == 0
    with pytest.raises(ValueError):
        runner.evaluation_change(CROSSED, 1, initial, final[1:], "test")


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "modes",
        "training_seed",
        "chunk_games",
        "session_limits",
        "recovery",
        "old_seed",
        "duplicate",
    ],
)
def test_versioned_loader_rejects_protocol_changes_or_seed_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    q, cfg, path, _, _ = fake_session(tmp_path, monkeypatch)
    # Exercise the actual loader, while keeping historical/native admission outside this unit.
    monkeypatch.undo()
    old: dict[str, Any] = {"fixed_legacy_rules": True}
    parent = {"environment_manifest": {"id": "environment"}}
    old_seeds = {"seeds": [{"id": 90, "seed": "OLD", "partition": "train"}]}
    monkeypatch.setattr(runner, "load_trial", lambda *_: (old, parent, old_seeds))
    rows = [
        {"id": i, "seed": f"FRESH{i}", "partition": "control" if i <= 2 else "control_eval"}
        for i in range(1, 5)
    ]
    if fault == "old_seed":
        rows[0]["seed"] = "OLD"
    elif fault == "duplicate":
        rows[1]["seed"] = rows[0]["seed"]
    body = {"environment_id": "environment", "seeds": rows}
    atomic_json(tmp_path / "seeds.json", {**body, "manifest_id": manifest_identifier(body)})
    hashes = {}
    for name in runner.SOURCES:
        p = tmp_path / "src/spireshift" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("pinned")
        hashes[name] = _sha_file(p)
    cfg.update(
        schema_version="native-context-chunked-comparison-config-v2",
        cache="immutable_identity_compatible_model_id_v1",
        legacy_recipe={"path": "legacy.json", "id": manifest_identifier(old)},
        checkpoint_selection="final_only",
        recovery="control_only",
        implementation_sha256=hashes,
        seed_manifest={"path": "seeds.json", "id": manifest_identifier(body)},
        session_limits={
            "wall_seconds": 180,
            "cpu_seconds": 360,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000,
        },
    )
    if fault is not None and fault in cfg:
        cfg[fault] = None
    atomic_json(tmp_path / "actual.json", cfg)
    if fault:
        with pytest.raises(ValueError):
            runner.load_resume(q, tmp_path / "actual.json")
    else:
        loaded, _, _ = runner.load_resume(q, tmp_path / "actual.json")
        assert loaded == cfg


def test_completed_chunk_rejects_new_unexpected_files(tmp_path: Path) -> None:
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/chunks"})
    with store.lock():
        target = store.begin("one", {"test": 1})
        store.commit("one", {"test": 1}, {"done": True})
    (target / "unexpected-active.json").write_text("preserve for inspection")
    with pytest.raises(ValueError, match="unexpected"):
        store.completed("one", {"test": 1})
