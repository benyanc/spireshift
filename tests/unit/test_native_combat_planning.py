from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_combat_planning_policy import fight, reward
from test_native_turn_teacher_policy import chooser, next_round
from test_native_turn_teacher_policy import root as source_root

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_planning import run
from spireshift.native_combat_planning_config import load
from spireshift.native_combat_planning_data import SAMPLES, SEARCH_CALL_CPU_CAP, SEARCH_CPU_CAP
from spireshift.native_combat_planning_policy import CONTRACT, MAX_BYTES, MAX_STEPS, RANKING
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_cache import cached_model


def fixture(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    from spireshift import native_combat_planning_config as config

    src, entry = tmp / "src/spireshift/dummy.py", tmp / "scripts/dummy.py"
    src.parent.mkdir(parents=True)
    entry.parent.mkdir()
    src.write_text("frozen implementation")
    entry.write_text("frozen wrapper")
    monkeypatch.setattr(config, "SOURCES", (src.name,))
    monkeypatch.setattr(config, "ENTRIES", (entry.name,))
    monkeypatch.setattr(config, "worker_helpers", lambda *a: {"helper": "sha"})
    parent: dict[str, Any] = {
        "stage": "finite_teacher_pilot",
        "workspace": "artifacts/old",
        "qualification": "qual.json",
        "qualification_id": "qual",
        "native_inputs": {"path": "inputs.json", "id": manifest_identifier({})},
        "node": str(tmp / "node"),
        "helpers_sha256": {"helper": "sha"},
        "temperature": 0.8,
    }
    roots, groups = [], []
    for ri in range(2):
        r = {
            **source_root(),
            "root_id": f"root-{ri}",
            "numerical_seed": ri + 2,
            "native_seed": f"WORLD{ri}",
            "source_seed_id": ri,
            "continuation_model_id": cached_model(model()).model_id,
        }
        roots.append(r)
        candidates = []
        for action in (0, 2):
            c = chooser(r, first_action=action)
            c(r["public_input"])
            c(next_round(r["public_input"]))
            assert c.plan is not None
            path = tmp / f"artifacts/old/r{ri}-a{action}.json"
            atomic_json(path, c.plan)
            candidates.append(
                {
                    "plan_id": c.plan["plan_id"],
                    "path": str(path.relative_to(tmp)),
                    "reference": action == 0,
                    "proposal_keys": [f"proposal-{ri}-{action}"],
                }
            )
        groups.append({"root_id": r["root_id"], "blocked": False, "candidates": candidates})
    corpus = {"training_spec": {"path": "score.json"}, "models": []}
    monkeypatch.setattr(config, "load_turn", lambda *a: (parent, corpus, roots, {}))
    frozen = {"config_id": manifest_identifier(parent), "roots": groups}
    atomic_json(
        tmp / parent["workspace"] / "candidate-set.json",
        {**frozen, "report_id": manifest_identifier(frozen)},
    )
    body = {
        "config_id": manifest_identifier(parent),
        "status": "native_complete_turn_teacher_complete",
        "failed_branches": 0,
        "skipped_branches": 0,
        "all_candidates_frozen_before_scored_branches": True,
        "sources": {},
        "cases": [
            {"candidate_plans": g["candidates"], "comparison_complete": True} for g in groups
        ],
    }
    prior = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp / "artifacts/old/report.json", prior)

    def old_baselines(
        root: Path,
        parent: dict[str, Any],
        corpus: dict[str, Any],
        roots: list[dict[str, Any]],
        frozen: dict[str, Any],
        items: list[dict[str, Any]],
        repeats: int,
        sources: dict[str, str],
    ) -> dict[str, dict[str, Any]]:
        return {
            f"{i['key']}-r{rep:02d}": {
                "status": "terminal",
                "root_reached": True,
                "turn_complete": True,
                "native_audit_valid": True,
                "training_return": 0.03,
                "maximum_floor": 8,
                "completed_acts": 0,
                "victory": False,
                "repeat": rep,
                "duplicate_control": False,
                "trace_id": f"baseline-{i['key']}-r{rep:02d}",
                "combat_exit": {"combat_survived": True},
            }
            for i in items
            for rep in range(repeats)
        }

    monkeypatch.setattr(config, "old_baselines", old_baselines)
    cfg = {
        **parent,
        "schema_version": "native-bounded-combat-planning-config-v1",
        "stage": "short_control",
        "workspace": "artifacts/planning",
        "policy_contract": CONTRACT,
        "information_scope": INFORMATION,
        "ordinary_PPO_eligible": False,
        "samples_per_initial_turn": SAMPLES,
        "ranking": RANKING,
        "repeats": 2,
        "maximum_combat_decisions": MAX_STEPS,
        "maximum_plan_bytes": MAX_BYTES,
        "search_cpu_cap": SEARCH_CPU_CAP,
        "search_call_cpu_cap": SEARCH_CALL_CPU_CAP,
        "proposal_temperature": 1.2,
        "implementation_sha256": {src.name: _sha_file(src)},
        "entry_sha256": {entry.name: _sha_file(entry)},
        "source_recipe": {"path": "parent.json", "id": manifest_identifier(parent)},
        "baseline_report": {"path": "artifacts/old/report.json", "id": prior["report_id"]},
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 2000000000,
        },
    }
    (tmp / "node").write_text("node")
    path = tmp / "recipe.json"
    path.write_text(json.dumps(cfg))
    return cfg, path


def test_status_and_cached_reuse_never_start_a_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_combat_planning as module

    cfg, path = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_running_games", lambda: pytest.fail("No native host"))
    plan = run(tmp_path, path, Path("not-used"), status_only=True)
    assert plan["initial_turns"] == 4 and plan["reused_baseline_branches"] == 8
    assert plan["search_attempts"] == 16 and plan["native_attempt_upper_bound"] == 28
    assert not (tmp_path / cfg["workspace"]).exists()
    body = {
        "status": "native_bounded_combat_comparison_complete",
        "config_id": manifest_identifier(cfg),
        "sources": {},
    }
    saved = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp_path / cfg["workspace"] / "report.json", saved)
    assert run(tmp_path, path, Path("not-used")) == saved


@pytest.mark.parametrize(
    "fault", ["code", "scope", "ranking", "cost", "sampling", "parent", "baseline", "cap"]
)
def test_recipe_rejects_changed_sources_scope_and_optimization(
    fault: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = fixture(tmp_path, monkeypatch)
    if fault == "code":
        (tmp_path / "src/spireshift/dummy.py").write_text("changed")
    elif fault == "scope":
        cfg["ordinary_PPO_eligible"] = True
    elif fault == "ranking":
        cfg["ranking"] = "best_final_floor"
    elif fault == "cost":
        cfg["search_cpu_cap"] = 128
    elif fault == "sampling":
        cfg["samples_per_initial_turn"] = 40
    elif fault == "parent":
        cfg["source_recipe"]["id"] = "changed"
    elif fault == "baseline":
        cfg["baseline_report"]["id"] = "changed"
    else:
        cfg["maximum_combat_decisions"] = 999999
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        load(tmp_path, path)


def mock_native(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    from spireshift import native_combat_planning as module

    cfg, path = fixture(tmp, monkeypatch)
    monkeypatch.setattr(module, "_running_games", lambda: [])
    monkeypatch.setattr(
        module,
        "load_engine_qualification_config",
        lambda *a: SimpleNamespace(root=tmp, config_id="qual"),
    )
    monkeypatch.setattr(
        module,
        "_run_inputs",
        lambda *a: {"recipe": {}, "objective": score().evaluation_objective.as_dict()},
    )
    monkeypatch.setattr(module, "load_training_score_spec", lambda *a: score())
    monkeypatch.setattr(
        module, "load_models", lambda *a: {2: cached_model(model()), 3: cached_model(model())}
    )
    monkeypatch.setattr(module, "_shared_snapshot", lambda *a: {"unchanged": "profile"})
    monkeypatch.setattr(module, "immutable_checks", lambda *a: {"unchanged": True})
    return cfg, path


@pytest.mark.parametrize("failed", [False, True])
def test_search_freezes_before_replay_failed_item_isolated_and_all_costs_charged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    from spireshift import native_combat_planning as module

    cfg, path = mock_native(tmp_path, monkeypatch)
    calls = []
    initial = copy.deepcopy(cached_model(model()).as_dict())

    def branch(
        q: Any,
        cfg: dict[str, Any],
        inputs: dict[str, Any],
        target: Path,
        node: Path,
        r: dict[str, Any],
        item: dict[str, Any],
        task: dict[str, Any],
        model: Any,
        score: Any,
        deadline: float,
    ) -> dict[str, Any]:
        calls.append(task)
        base = {
            "stage": task["stage"],
            "item_key": item["key"],
            "root_id": r["root_id"],
            "sample": task["sample"],
            "repeat": task["repeat"],
            "duplicate": task["duplicate"],
            "root_reached": True,
            "status": "terminal",
            "combat_complete": True,
            "native_audit_valid": True,
            "error": None,
            "victory": False,
            "training_return": 0.03,
            "maximum_floor": 8,
            "completed_acts": 0,
            "execution_cpu_seconds": 1.0,
            "cpu_seconds": 1.0 + task.get("planning_cpu_seconds", 0.0),
            "planning_cpu_seconds": task.get("planning_cpu_seconds", 0.0),
        }
        if (
            failed
            and task["stage"] == "search"
            and item["key"] == "r000-p000"
            and task["sample"] == 1
        ):
            return {**base, "status": "failed", "combat_complete": False}
        if task["stage"] == "evaluation":
            assert (tmp_path / cfg["workspace"] / "selection.json").exists()
            plan = identified(tmp_path / task["selected"]["path"], "plan_id")
            assert task["planning_cpu_seconds"] == 4.0 and task["cpu_allowance"] == 124.0
            return {
                **base,
                "plan_id": plan["plan_id"],
                "plan_path": task["selected"]["path"],
                "exit": plan["exit"],
                "trace_id": f"selected-{item['key']}-r{task['repeat']:02d}",
            }
        turn = identified(tmp_path / item["turn_plan_path"], "plan_id")
        c = fight(r, turn, sample=task["sample"])
        c(r["public_input"])
        c(next_round(r["public_input"]))
        c(reward(r["public_input"], 30 + task["sample"]))
        assert c.plan is not None
        dest = target / "fight-plan.json"
        atomic_json(dest, c.plan)
        return {
            **base,
            "plan_id": c.plan["plan_id"],
            "plan_path": str(dest.relative_to(tmp_path)),
            "exit": c.plan["exit"],
            "trace_id": f"baseline-{item['key']}-r{task['repeat']:02d}",
        }

    monkeypatch.setattr(module, "branch", branch)
    result = run(tmp_path, path, tmp_path / "node")
    assert result["status"] == "native_bounded_combat_comparison_complete"
    assert result["production_optimizer_steps"] == 0 and cached_model(model()).as_dict() == initial
    first_eval = next(i for i, t in enumerate(calls) if t["stage"] == "evaluation")
    assert all(t["stage"] == "search" for t in calls[:first_eval])
    if failed:
        assert result["failed_branches"] == 1 and result["blocked_initial_turns"] == 1
        assert (
            result["summary"]["denominator"] == 8
            and result["summary"]["failed_or_unattempted"] == 2
        )
        assert result["summary"]["completed"] == 6
    else:
        assert result["completed_units"] == 28 and result["baseline_control_traces_match"]
        assert result["duplicate_selected_traces_match"] and result["summary"]["completed"] == 8
    monkeypatch.setattr(module, "branch", lambda *a: pytest.fail("Completed work never reruns"))
    assert run(tmp_path, path, tmp_path / "node") == result


def test_uncommitted_search_is_preserved_without_a_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_combat_planning as module

    cfg, path = mock_native(tmp_path, monkeypatch)
    target = tmp_path / cfg["workspace"] / "chunks/search-r000-p000-s00"
    target.mkdir(parents=True)
    (target / "active.json").write_text("uncertain delivery")
    monkeypatch.setattr(module, "branch", lambda *a: pytest.fail("No new attempt"))
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, path, tmp_path / "node")
    assert (target / "active.json").read_text() == "uncertain delivery"


@pytest.mark.parametrize(
    "fault", [None, "cost", "audit", "probability", "duplicates", "baseline", "denominator"]
)
def test_main_requires_matching_native_and_saved_behavior_control(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    from spireshift import native_combat_planning_config as config

    cfg, path = fixture(tmp_path, monkeypatch)
    auditor = tmp_path / "src/spireshift/native_combat_planning_audit.py"
    auditor.write_text("frozen saved auditor")
    monkeypatch.setattr(config, "SOURCES", ("dummy.py", auditor.name))
    cfg["implementation_sha256"][auditor.name] = _sha_file(auditor)
    (tmp_path / "control-recipe.json").write_text(json.dumps(cfg))
    body = {
        "recipe_path": "control-recipe.json",
        "config_id": manifest_identifier(cfg),
        "status": "native_bounded_combat_comparison_complete",
        "failed_branches": 0,
        "skipped_branches": 0,
        "blocked_initial_turns": 0,
        "completed_units": 27 if fault == "denominator" else 28,
        "baseline_control_traces_match": fault != "baseline",
        "duplicate_selected_traces_match": fault != "duplicates",
        "sources": {},
    }
    passed = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp_path / "control.json", passed)
    body = {
        "source_report_id": passed["report_id"],
        "auditor_sha256": "other" if fault == "audit" else _sha_file(auditor),
        "branch_receipts_verified": 28,
        "all_choices_reconstructed": fault != "probability",
        "combat_plans_and_selection_reconstructed": True,
        "planning_cost_charged_without_amortization": fault != "cost",
        "full_states_unchanged": True,
    }
    checked = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp_path / "audit.json", checked)
    cfg.update(
        stage="finite_comparison",
        repeats=8,
        workspace="artifacts/pilot",
        control_report={"path": "control.json", "id": passed["report_id"]},
        control_audit={"path": "audit.json", "id": checked["report_id"]},
    )
    cfg["session_limits"].update(wall_seconds=900, cpu_seconds=1800, storage_bytes=4000000000)
    path.write_text(json.dumps(cfg))
    if fault is None:
        assert len(load(tmp_path, path)[3]) == 4
    else:
        with pytest.raises(ValueError):
            load(tmp_path, path)
