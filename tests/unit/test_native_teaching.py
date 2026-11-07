from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_coordinated_teacher import root_entry, trace

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_natural_data import resources
from spireshift.native_teaching_data import ARMS, LEARNING, VARIANTS, lessons, public_step
from spireshift.native_teaching_execute import execute
from spireshift.native_teaching_inputs import validate, worlds
from spireshift.native_teaching_learning import diagnostics
from spireshift.native_teaching_plan import schedule, summary


def fixture_bank() -> dict[str, Any]:
    roots = [root_entry(f"root-{i}") for i in range(3)]
    labels = []
    for i, root in enumerate(roots):
        root.update(partition="fit" if i < 2 else "heldout", seed_id=i)
        if i == 2:
            continue
        steps = [public_step(s) for s in trace()["steps"][:3]]
        teacher = [{**s, "action_index": 1} for s in steps]
        label = {
            "root_id": root["root_id"],
            "world": root["world"],
            "partition": "fit",
            "plans": {
                a: {"root_id": root["root_id"], "world": root["world"], "steps": ss}
                for a, ss in zip(ARMS, (steps, teacher), strict=True)
            },
            "changed_choices": {
                "root_id": root["root_id"],
                "world": root["world"],
                "steps": teacher[:1],
            },
        }
        labels.append(label)
    return {"bank_id": "bank", "lessons": labels, "roots": roots}


def config() -> dict[str, Any]:
    return {
        "schema_version": "native-plan-teaching-config-v1",
        "contract": "native_verified_plan_student_transfer_v1",
        "arms": list(ARMS),
        "stage": "short_control",
        "workspace": "artifacts/native-teaching/sts2-v0.111.0-a8-control-v1",
        "learning": {**LEARNING, "epochs": 1},
        "maximum_decisions": 4096,
        "episode_wall_seconds": 120,
        "technical_failure_allowance": 2,
        "evaluation_seeds": [{"id": 100, "seed": "FRESH", "partition": "development"}],
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        },
    }


def test_public_labels_have_exact_menus_and_no_debug_or_return_fields() -> None:
    step = {**trace()["steps"][0], "DEBUG_hidden_world": {"future": True}, "return": 999}
    clean = public_step(step)
    assert set(clean) == {"public_input", "public_input_id", "action_index"}
    step["action_index"] = 999
    with pytest.raises(ValueError, match="exact public"):
        public_step(step)
    step["action_index"], step["public_input_id"] = 0, "wrong"
    with pytest.raises(ValueError, match="exact public"):
        public_step(step)


def test_fitting_selection_combines_methods_without_reading_heldout_or_old_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.native_teaching_data as module

    roots = fixture_bank()["roots"]
    plans, cells, saved = {}, [], {}
    for i, r in enumerate(roots):
        if r["partition"] == "heldout":
            continue
        ref = {
            **trace(),
            "root_id": r["root_id"],
            "resources": {**resources(r["public_input"]), "hp": 0 if i == 0 else 20},
            "outcome": "loss" if i == 0 else "win",
            "fight_id": f"ref-{i}",
        }
        plans[ref["fight_id"]] = ref
        saved[f"reference-{i}"] = {"kind": "fight", "fight_id": ref["fight_id"]}
        for arm in ("single_change", "coordinated"):
            v = copy.deepcopy(ref)
            v.update(
                fight_id=f"{i}-{arm}",
                native_audit={"valid": True},
                outcome="win",
                resources={
                    **ref["resources"],
                    "hp": (40 if arm == "single_change" else 30)
                    if i == 0
                    else (30 if arm == "single_change" else 40),
                },
            )
            v["steps"][0]["action_index"] = 1
            v["edits"] = [
                {"decision": 0, "action": 1, "public_input_id": v["steps"][0]["public_input_id"]}
            ]
            plans[v["fight_id"]] = v
            saved[f"plan-{i}-{arm}"] = {"kind": "fight", "fight_id": v["fight_id"]}
            saved[f"root-{i:02d}-early-confirm-{arm.replace('_', '-')}"] = {
                "kind": "fight",
                "fight_id": v["fight_id"],
            }
            cells.append(
                {
                    "root_id": r["root_id"],
                    "partition": "fit",
                    "entry": "early",
                    "arm": arm,
                    "verified": True,
                    "reference_fight_id": ref["fight_id"],
                    "selected_fight_id": v["fight_id"],
                }
            )
    teacher = {"cells": cells, "fights": saved, "old_gate": {"passed": False}}
    monkeypatch.setattr(module, "read_fight", lambda _, row: plans[row["fight_id"]])
    before = copy.deepcopy(teacher)
    chosen = lessons(Path("."), roots, teacher)
    assert [r["chosen_search_arm"] for r in chosen] == ["single_change", "coordinated"]
    assert {r["world"] for r in chosen} == {r["world"] for r in roots[:2]}
    assert teacher == before
    cells[0]["partition"] = "heldout"
    with pytest.raises(ValueError, match="fitting cells"):
        lessons(Path("."), roots, teacher)


def test_schedule_matches_work_and_freezes_every_final_before_all_evaluations() -> None:
    cfg = {
        **config(),
        "stage": "bounded_teaching_test",
        "learning": LEARNING,
        "evaluation_seeds": [{"id": i} for i in range(32)],
    }
    bank = fixture_bank()
    bank["roots"] = bank["roots"][:2] + [
        {**bank["roots"][2], "root_id": f"held-{i}"} for i in range(4)
    ]
    tasks = schedule(cfg, bank)
    barrier = next(i for i, t in enumerate(tasks) if t["kind"] == "freeze")
    assert all(t["kind"] in {"import", "fit"} for t in tasks[:barrier])
    assert all(t["kind"] in {"fight", "fresh"} for t in tasks[barrier + 1 :])
    assert len(tasks[barrier]["states"]) == 6
    assert sum(t["kind"] == "fresh" for t in tasks) == 192
    assert sum(t["kind"] == "fight" for t in tasks) == 36
    for p in (2, 3):
        for arm in ARMS:
            rows = [t for t in tasks if t["kind"] == "fit" and t["player"] == p and t["arm"] == arm]
            assert [r["epoch"] for r in rows] == list(range(1, 17))
            assert len(rows) * LEARNING["steps_per_epoch"] == 64
    assert len({t["key"] for t in tasks}) == len(tasks)


def test_failed_and_missing_games_keep_original_denominators() -> None:
    cfg = config()
    done = {}
    for p in (2, 3):
        for a in VARIANTS:
            done[f"{p}-{a}"] = {
                "kind": "fresh",
                "player": p,
                "arm": a,
                "seed_id": 100,
                "status": "failed" if p == 2 and a == "teacher_clone" else "terminal",
                "victory": False,
                "maximum_floor": 10,
                "completed_acts": 0,
                "training_return": 0.01,
            }
    value = summary(cfg, done)
    assert value["players"][0]["arms"]["teacher_clone"]["failed_games"] == 1
    assert value["pooled_paired"]["teacher_clone_minus_initial"]["maximum_floor"]["mean"] == -5
    del done["3-teacher_clone"]
    assert not summary(cfg, done)["complete"]
    assert summary(cfg, done)["pooled_paired"] == {}
    done["extra"] = {**next(iter(done.values())), "seed_id": 999}
    with pytest.raises(ValueError, match="unplanned"):
        summary(cfg, done)


def test_seed_validation_rejects_canonical_aliases_and_heldout_world_reuse(tmp_path: Path) -> None:
    cfg = config()
    bank = {
        **fixture_bank(),
        "runtime": {
            "environment_manifest": {"id": "env"},
            "freshness_exclusions": [],
            "seed_manifest": {"path": "old.json"},
        },
    }
    atomic_json(tmp_path / "old.json", {"seeds": [{"id": 1, "seed": "USED"}]})
    cfg["freshness_exclusions"] = [{"path": "old.json", "sha256": _sha_file(tmp_path / "old.json")}]

    def save_manifest() -> None:
        body = {
            "schema_version": "native-plan-teaching-seeds-v1",
            "environment_id": "env",
            "seeds": cfg["evaluation_seeds"],
        }
        value = {**body, "manifest_id": manifest_identifier(body)}
        name = f"fresh-{value['manifest_id'].split(':')[1]}.json"
        atomic_json(tmp_path / name, value)
        cfg["seed_manifest"] = {"path": name, "id": value["manifest_id"]}

    save_manifest()
    assert worlds(tmp_path, cfg, bank)
    cfg["evaluation_seeds"][0]["seed"] = "ILLEGAL"
    save_manifest()
    with pytest.raises(ValueError, match="canonical"):
        worlds(tmp_path, cfg, bank)
    cfg["evaluation_seeds"][0]["seed"] = "USED"
    save_manifest()
    with pytest.raises(ValueError, match="reuse"):
        worlds(tmp_path, cfg, bank)


@pytest.mark.parametrize("field", ["learning", "workspace", "technical_failure_allowance"])
def test_frozen_work_and_workspace_cannot_be_silently_changed(field: str) -> None:
    cfg = config()
    validate(cfg)
    cfg[field] = {} if field == "learning" else "changed"
    with pytest.raises(ValueError, match="fixed"):
        validate(cfg)


def test_changed_choice_metrics_are_public_fitting_only_and_do_not_update_weights() -> None:
    m = cached_model(model())
    before = m.as_dict()
    d = diagnostics(m, fixture_bank(), score())
    assert d["heldout_inputs_or_outcomes_used"] is False
    assert len(d["per_world_changed_choices"]) == 2
    assert 0 < d["changed_choices"]["root_equal_label_probability"] < 1
    assert m.as_dict() == before


def install_fakes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import spireshift.native_teaching_execute as module

    calls: list[str] = []
    monkeypatch.setattr(module, "_running_games", lambda: [])
    monkeypatch.setattr(module, "_shared_snapshot", lambda _: {})
    monkeypatch.setattr(module, "immutable_checks", lambda *args: {"unchanged": True})
    monkeypatch.setattr(module, "snapshot", lambda *args: {})

    def fight(*args: Any) -> dict[str, Any]:
        target = args[7]
        assert (target.parents[1] / "chunks/frozen-finals/done.json").exists()
        calls.append("fight")
        return {
            "status": "complete",
            "outcome": "win",
            "resources": {"hp": 30},
            "fight_id": "fight",
            "error": None,
        }

    def game(*args: Any) -> dict[str, Any]:
        target, seed, m = args[3:6]
        assert (target.parents[1] / "chunks/frozen-finals/done.json").exists()
        calls.append("fresh")
        return {
            "status": "terminal",
            "victory": False,
            "maximum_floor": 8,
            "completed_acts": 0,
            "training_return": 0.01,
            "seed_id": seed["id"],
            "model_id": m.model_id,
        }

    monkeypatch.setattr(module, "branch", fight)
    monkeypatch.setattr(module, "game", game)
    return calls


def context() -> dict[str, Any]:
    models = {p: cached_model(model(seed=p)) for p in (2, 3)}
    adams = {
        p: replace(
            Adam.zero(m.parameter_count),
            steps=7,
            first=(0.001,) * m.parameter_count,
            second=(0.01,) * m.parameter_count,
        )
        for p, m in models.items()
    }
    return {
        "config": config(),
        "bank": fixture_bank(),
        "models": models,
        "adams": adams,
        "score": score(),
        "sources": {},
    }


def test_real_imitation_resumes_exactly_and_never_overwrites_originals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_fakes(monkeypatch)
    ctx = context()
    originals = {p: (m.as_dict(), ctx["adams"][p].as_dict()) for p, m in ctx["models"].items()}
    first = execute(tmp_path, ctx, (None, None), max_units=5)
    assert first["status"] == "native_teaching_clean_pause" and not calls
    value = execute(tmp_path, ctx, (None, None))
    assert value["control_checks_passed"]
    assert value["optimizer_steps_on_copies"] == 16
    assert calls.count("fight") == 3 and calls.count("fresh") == 6
    assert all(r["optimizer_steps"] == 11 for r in value["states"].values() if r["kind"] == "fit")
    assert {
        p: (m.as_dict(), ctx["adams"][p].as_dict()) for p, m in ctx["models"].items()
    } == originals
    uninterrupted = execute(tmp_path / "other", context(), (None, None))
    assert value["frozen_finals"] == uninterrupted["frozen_finals"]
    count = len(calls)
    assert execute(tmp_path, ctx, (None, None)) == value
    assert len(calls) == count


def test_uncommitted_or_changed_chunk_stops_without_replaying_a_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_fakes(monkeypatch)
    ctx = context()
    p = tmp_path / ctx["config"]["workspace"] / "chunks/initial-p2"
    p.mkdir(parents=True)
    atomic_json(p / "active.json", {"uncertain": True})
    with pytest.raises(FileExistsError, match="uncommitted"):
        execute(tmp_path, ctx, (None, None))
    assert not calls and json.loads((p / "active.json").read_text()) == {"uncertain": True}


def test_open_game_refuses_before_creating_an_evaluation_chunk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.native_teaching_execute as module

    calls = install_fakes(monkeypatch)
    ctx = context()
    monkeypatch.setattr(module, "_running_games", lambda: ["steam-game"])
    with pytest.raises(ValueError, match="Close STS2"):
        execute(tmp_path, ctx, (None, None))
    w = tmp_path / ctx["config"]["workspace"]
    assert (w / "chunks/frozen-finals/done.json").exists()
    assert not list((w / "chunks").glob("fight-*/active.json")) and not calls


def test_one_failed_game_is_sealed_not_retried_and_keeps_its_denominator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spireshift.native_teaching_execute as module

    calls = install_fakes(monkeypatch)
    original_game = cast(Any, module).game
    attempts = 0

    def failing_first(*args: Any) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        value: dict[str, Any] = original_game(*args)
        if attempts == 1:
            value["status"] = "failed"
        return value

    monkeypatch.setattr(module, "game", failing_first)
    ctx = context()
    report = execute(tmp_path, ctx, (None, None))
    assert report["status"] == "native_teaching_complete" and not report["control_checks_passed"]
    assert report["fresh_games"]["players"][0]["arms"]["teacher_clone"]["failed_games"] == 1
    assert report["fresh_games"]["players"][0]["arms"]["teacher_clone"]["denominator"] == 1
    assert attempts == 6 and calls.count("fresh") == 6
    assert execute(tmp_path, ctx, (None, None)) == report and attempts == 6


def test_changed_sealed_state_cannot_be_resumed_or_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = install_fakes(monkeypatch)
    ctx = context()
    execute(tmp_path, ctx, (None, None), max_units=2)
    path = tmp_path / ctx["config"]["workspace"] / "chunks/initial-p2/state.json"
    path.write_text(path.read_text() + "\n")
    with pytest.raises(ValueError, match="evidence changed"):
        execute(tmp_path, ctx, (None, None))
    assert not calls
