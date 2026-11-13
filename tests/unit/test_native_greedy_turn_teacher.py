from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_greedy_turn_policy import plan, seed
from test_native_turn_teacher_policy import public

from spireshift import native_greedy_turn_config as admission
from spireshift import native_greedy_turn_teacher as module
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_cache import cached_model
from spireshift.native_greedy_turn_policy import CONTRACT, ROOT_SELECTION, SourceChooser


def sealed(root: Path, name: str, body: dict[str, Any], key: str = "report_id") -> dict[str, str]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {**body, key: manifest_identifier(body)}
    path.write_text(json.dumps(value))
    return {"path": name, "id": value[key]}


def recipe(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    code = root / "src/spireshift/native_greedy_turn_audit.py"
    entry = root / "scripts/entry.py"
    code.parent.mkdir(parents=True)
    entry.parent.mkdir()
    code.write_text("source")
    entry.write_text("entry")
    monkeypatch.setattr(admission, "SOURCES", (code.name,))
    monkeypatch.setattr(admission, "ENTRIES", (entry.name,))
    m, spec = cached_model(model()), score()
    old = sealed(root, "history.json", {"seeds": [{"id": 1, "seed": "OLD"}]}, "manifest_id")
    base = {
        "stage": "fresh_game_comparison",
        "qualification": "q.json",
        "qualification_id": "q",
        "native_inputs": {"path": "native.json", "id": "native"},
        "node": "frozen-node",
        "helpers_sha256": {"helper": "frozen"},
        "historical_seed_manifests": [old],
        "excluded_seed_manifests": [],
        "seed_manifest": old,
    }
    base_path = root / "behavior.json"
    base_path.write_text(json.dumps(base))
    monkeypatch.setattr(admission, "load_behavior", lambda *_: (base, [], {2: m, 3: m}, spec, {}))
    passed = sealed(
        root,
        "behavior-report.json",
        {
            "config_id": manifest_identifier(base),
            "status": "native_combat_behavior_complete",
            "failed_games": 0,
            "completed_units": 256,
            "noncombat_matching": {"valid": True},
            "full_states_unchanged": True,
            "checks": {"account": True},
            "sources": {},
        },
    )
    fresh = sealed(
        root,
        "fresh.json",
        {
            "schema_version": "native-greedy-turn-seeds-v1",
            "environment_id": m.actor.environment_id,
            "partition": "control",
            "seeds": [seed(2), seed(3)],
        },
        "manifest_id",
    )
    cfg = {
        **{
            k: base[k]
            for k in (
                "qualification",
                "qualification_id",
                "native_inputs",
                "node",
                "helpers_sha256",
            )
        },
        "schema_version": "native-greedy-turn-teacher-config-v1",
        "stage": "short_control",
        "workspace": "artifacts/control",
        "policy_contract": CONTRACT,
        "root_selection": ROOT_SELECTION,
        "temperature": 0.8,
        "proposal_temperature": 1.2,
        "maximum_decisions": 4096,
        "episode_wall_seconds": 120,
        "repeats": 2,
        "information_scope": "public_student_inputs_original_fixed_hidden_world_teacher",
        "ordinary_PPO_eligible": False,
        "proposal_cpu_cap": 64.0,
        "proposal_call_cpu_cap": 32.0,
        "candidate_selection": "all_first_moves_exact_trace_dedup_no_outcome_filter",
        "cost_accounting": (
            "all_proposal_episode_CPU_to_each_alternative_reference_zero_no_amortization"
        ),
        "implementation_sha256": {code.name: _sha_file(code)},
        "entry_sha256": {entry.name: _sha_file(entry)},
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        },
        "behavior_recipe": {"path": base_path.name, "sha256": _sha_file(base_path)},
        "behavior_report": passed,
        "seed_manifest": fresh,
        "freshness_exclusions": [old],
        "excluded_seed_manifests": [],
    }
    path = root / "control.json"
    path.write_text(json.dumps(cfg))
    return cfg, path


def test_admission_binds_exact_prior_behavior_and_fresh_training_source_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = recipe(tmp_path, monkeypatch)
    _, seeds, models, _, sources = admission.load(tmp_path, path)
    assert seeds == [seed(2), seed(3)] and set(models) == {2, 3}
    assert sources[path.name] == _sha_file(path)
    assert cfg["behavior_recipe"]["path"] in sources or cfg["behavior_report"]["path"] in sources


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "base",
        "helper",
        "objective",
        "PPO",
        "temperature",
        "history",
        "seed_id",
        "seed_case",
        "player",
        "scope",
        "budget",
    ],
)
def test_admission_refuses_changed_inputs_reused_worlds_and_learning_relabeling(
    fault: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = recipe(tmp_path, monkeypatch)
    if fault == "source":
        (tmp_path / "src/spireshift/native_greedy_turn_audit.py").write_text("changed")
    elif fault == "base":
        (tmp_path / "behavior.json").write_text("changed")
    elif fault == "helper":
        cfg["helpers_sha256"] = {"helper": "other"}
    elif fault == "objective":
        cfg["cost_accounting"] = "ignore_search_cost"
    elif fault == "PPO":
        cfg["ordinary_PPO_eligible"] = True
    elif fault == "temperature":
        cfg["temperature"] = 1.2
    elif fault == "history":
        cfg["freshness_exclusions"] = []
    elif fault == "scope":
        cfg["information_scope"] = "public_belief"
    elif fault == "budget":
        cfg["session_limits"]["wall_seconds"] = 7200
    else:
        fresh = json.loads((tmp_path / "fresh.json").read_text())
        fresh.pop("manifest_id")
        if fault == "seed_id":
            fresh["seeds"][0]["id"] = 1
        elif fault == "seed_case":
            fresh["seeds"][0]["seed"] = "old"
        else:
            fresh["seeds"][0]["numerical_seed"] = 3
        cfg["seed_manifest"] = sealed(tmp_path, "fresh.json", fresh, "manifest_id")
    path.write_text(json.dumps(cfg))
    with pytest.raises((ValueError, KeyError)):
        admission.load(tmp_path, path)


def test_long_teacher_requires_matching_control_and_saved_choice_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path = recipe(tmp_path, monkeypatch)
    control_seeds = copy.deepcopy(cfg["seed_manifest"])
    passed = sealed(
        tmp_path,
        "control-report.json",
        {
            "recipe_path": path.name,
            "status": module.COMPLETE,
            "failed_branches": 0,
            "unavailable_source_worlds": 0,
            "blocked_source_roots": 0,
            "completed_units": 16,
            "completed_source_comparisons": 2,
            "duplicate_public_traces_identical": True,
            "noncombat_matching": {"valid": True},
            "sources": {},
        },
    )
    audit = sealed(
        tmp_path,
        "audit.json",
        {
            "source_report_id": passed["id"],
            "auditor_sha256": cfg["implementation_sha256"]["native_greedy_turn_audit.py"],
            "branch_receipts_verified": 16,
            "all_choices_and_root_selection_reconstructed": True,
        },
    )
    manifest = json.loads((tmp_path / "fresh.json").read_text())
    manifest.pop("manifest_id")
    manifest.update(
        partition="train",
        seeds=[{"id": 100 + i, "seed": f"NEW{i}", "numerical_seed": 2 + i % 2} for i in range(8)],
    )
    cfg = {
        **cfg,
        "stage": "fresh_train_teacher",
        "repeats": 8,
        "workspace": "artifacts/pilot",
        "seed_manifest": sealed(tmp_path, "main-seeds.json", manifest, "manifest_id"),
        "excluded_seed_manifests": [control_seeds],
        "control_report": passed,
        "control_audit": audit,
        "session_limits": {
            "wall_seconds": 900,
            "cpu_seconds": 1800,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 4000000000,
        },
    }
    path = tmp_path / "main.json"
    path.write_text(json.dumps(cfg))
    assert len(admission.load(tmp_path, path)[1]) == 8
    cfg["control_audit"]["id"] = "not-the-passed-audit"
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="reference"):
        admission.load(tmp_path, path)


def fake_native(
    root: Path, monkeypatch: pytest.MonkeyPatch, control: bool = True
) -> tuple[dict[str, Any], Path, list[str]]:
    spec, m = score(), cached_model(model())
    seeds = [seed(2), seed(3)]
    cfg = {
        "stage": "short_control" if control else "fresh_train_teacher",
        "repeats": 2 if control else 8,
        "workspace": "artifacts/teacher",
        "node": str(root / "node"),
        "qualification": "q.json",
        "qualification_id": "q",
        "native_inputs": {"path": "native.json", "id": manifest_identifier({})},
        "session_limits": {"wall_seconds": 240},
    }
    (root / "node").write_text("node")
    path = root / "recipe.json"
    path.write_text(json.dumps(cfg))
    monkeypatch.setattr(module, "load", lambda *_: (cfg, seeds, {2: m, 3: m}, spec, {}))
    monkeypatch.setattr(
        module, "load_engine_qualification_config", lambda *_: SimpleNamespace(config_id="q")
    )
    monkeypatch.setattr(
        module,
        "_run_inputs",
        lambda *_: {"recipe": {}, "objective": spec.evaluation_objective.as_dict()},
    )
    monkeypatch.setattr(module, "_running_games", lambda: [])
    monkeypatch.setattr(module, "_shared_snapshot", lambda *_: {})
    monkeypatch.setattr(module, "immutable_checks", lambda *_: {"shared": True})
    calls: list[str] = []

    def branch(
        _q: Any,
        _cfg: Any,
        _inputs: Any,
        target: Path,
        _node: Any,
        task: dict[str, Any],
        _model: Any,
        _score: Any,
        r: dict[str, Any] | None,
        _deadline: float,
    ) -> dict[str, Any]:
        calls.append(task["key"])
        source = task["stage"] == "source"
        p = None
        if source:
            c = SourceChooser(task["seed"], m, spec)
            c(public())
            r = c.root
            assert r is not None
            atomic_json(target / "root.json", r)
        else:
            assert r is not None
            p = (
                plan(r, task["first_action"])
                if task["stage"] == "proposal"
                else identified(root / task["plan_path"], "plan_id")
            )
            if task["stage"] == "proposal":
                atomic_json(target / "turn-plan.json", p)
        assert r is not None
        body = {
            "noncombat": [
                {
                    "draw_key": f"{r['root_id']}-{task.get('repeat')}",
                    "draw": 0.5,
                    "effective_input_id": "same",
                    "action_index": 0,
                    "policy_log_probability": 0.0,
                }
            ]
        }
        rng = {**body, "report_id": manifest_identifier(body)}
        atomic_json(target / "rng-receipt.json", rng)
        return {
            "stage": task["stage"],
            "status": "terminal",
            "victory": False,
            "maximum_floor": 10,
            "completed_acts": 0,
            "cpu_seconds": 1.0 + task["planning_cpu_seconds"],
            "execution_cpu_seconds": 1.0,
            "planning_cpu_seconds": task["planning_cpu_seconds"],
            "seed_id": task["seed"]["id"],
            "numerical_seed": task["seed"]["numerical_seed"],
            "root_id": r["root_id"],
            "root_path": str((target / "root.json").relative_to(root)) if source else None,
            "root_reached": True,
            "turn_complete": True,
            "native_audit_valid": True,
            "inference_audit_valid": True,
            "plan_id": p["plan_id"] if p else None,
            "plan_path": str((target / "turn-plan.json").relative_to(root))
            if task["stage"] == "proposal"
            else task.get("plan_path"),
            "trace_id": f"{r['root_id']}-{p['plan_id'] if p else None}-{task.get('repeat')}",
            "repeat": task.get("repeat"),
            "duplicate_control": task.get("duplicate_control", False),
            "reference": task.get("reference", False),
            "training_return": 0.01,
            "rng_receipt_path": str((target / "rng-receipt.json").relative_to(root)),
            "rng_receipt_id": rng["report_id"],
        }

    monkeypatch.setattr(module, "branch", branch)
    return cfg, path, calls


def test_status_and_cached_result_are_read_only_and_never_start_a_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, calls = fake_native(tmp_path, monkeypatch)
    monkeypatch.setattr(
        module, "_running_games", lambda: pytest.fail("status must not inspect hosts")
    )
    assert (
        module.run(tmp_path, path, Path("unused"), status_only=True)["native_attempt_upper_bound"]
        == 16
    )
    assert not (tmp_path / cfg["workspace"]).exists() and not calls
    value = {"status": module.COMPLETE, "config_id": manifest_identifier(cfg), "sources": {}}
    sealed(tmp_path, cfg["workspace"] + "/report.json", value)
    assert module.run(tmp_path, path, Path("unused"))["status"] == module.COMPLETE
    assert not calls


def test_complete_teacher_resumes_immutable_games_and_preserves_full_states(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, calls = fake_native(tmp_path, monkeypatch)
    result = module.run(tmp_path, path, Path(cfg["node"]))
    assert result["completed_units"] == 16 and len(calls) == 16
    assert (
        result["duplicate_public_traces_identical"] and result["completed_source_comparisons"] == 2
    )
    assert result["noncombat_matching"]["shared_noncombat_draw_keys"] == 4
    assert result["production_optimizer_steps"] == result["game_apps_created"] == 0
    assert module.run(tmp_path, path, Path("unused")) == result and len(calls) == 16


def test_clean_pause_resumes_only_unfinished_source_and_counterfactual_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, calls = fake_native(tmp_path, monkeypatch)
    original: Callable[..., dict[str, Any]] = vars(module)["branch"]
    clock = [0.0]
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])

    def branch(*args: Any) -> dict[str, Any]:
        result = original(*args)
        if len(calls) == 1:
            clock[0] = 100.0
        return result

    monkeypatch.setattr(module, "branch", branch)
    partial = module.run(tmp_path, path, Path(cfg["node"]))
    assert (
        partial["completed_units"] == 1
        and partial["status"] == "paused_between_greedy_teacher_attempts"
    )
    clock[0] = 0.0
    final = module.run(tmp_path, path, Path(cfg["node"]))
    assert (
        final["completed_units"] == 16
        and final["new_units_this_session"] == 15
        and len(calls) == 16
    )


def test_failed_proposal_blocks_only_its_root_and_preserves_source_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, _ = fake_native(tmp_path, monkeypatch, False)
    original: Callable[..., dict[str, Any]] = vars(module)["branch"]
    failed = [False]

    def branch(*args: Any) -> dict[str, Any]:
        result = original(*args)
        if result["stage"] == "proposal" and not failed[0]:
            result["status"], failed[0] = "failed", True
        return result

    monkeypatch.setattr(module, "branch", branch)
    result = module.run(tmp_path, path, Path(cfg["node"]))
    assert result["status"] == module.COMPLETE + "_with_gaps"
    assert result["failed_branches"] == 1 and result["blocked_source_roots"] == 1
    assert result["skipped_branches"] > 0 and result["completed_source_comparisons"] == 1
    assert result["planned_source_worlds"] == len(result["source_world_denominator"]) == 2


def test_uncertain_attempt_is_preserved_and_never_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, calls = fake_native(tmp_path, monkeypatch)
    p = tmp_path / cfg["workspace"] / f"chunks/source-{seed()['id']}"
    p.mkdir(parents=True)
    (p / "active.json").write_text("uncertain")
    with pytest.raises(FileExistsError, match="uncommitted"):
        module.run(tmp_path, path, Path(cfg["node"]))
    assert not calls and (p / "active.json").read_text() == "uncertain"
