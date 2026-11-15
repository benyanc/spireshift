from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_turn_teacher_policy import chooser, next_round
from test_native_turn_teacher_policy import root as source_root

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_cache import cached_model
from spireshift.native_turn_teacher import run
from spireshift.native_turn_teacher_config import GENERATION, load
from spireshift.native_turn_teacher_policy import CONTRACT, MAX_PLAN_BYTES, MAX_STEPS


def fixture(tmp: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    from spireshift import native_turn_teacher_config as config

    src, entry = tmp / "src/spireshift/dummy.py", tmp / "scripts/dummy.py"
    src.parent.mkdir(parents=True)
    entry.parent.mkdir()
    src.write_text("frozen source")
    entry.write_text("frozen entry")
    monkeypatch.setattr(config, "SOURCES", (src.name,))
    monkeypatch.setattr(config, "ENTRIES", (entry.name,))
    monkeypatch.setattr(config, "worker_helpers", lambda *args: {"helper": "sha"})
    parent = {
        "stage": "finite_teacher_pilot",
        "roots_report": {"path": "roots.json", "id": "roots"},
        "qualification": "qual.json",
        "qualification_id": "qual",
        "node": str(tmp / "node"),
        "native_inputs": {"path": "inputs.json", "id": manifest_identifier({})},
        "temperature": 0.8,
        "helpers_sha256": {"helper": "sha"},
    }
    corpus = {"training_spec": {"path": "score.json"}, "models": []}
    roots = [
        {
            **source_root(),
            "root_id": f"root-{i}",
            "native_seed": f"WORLD{i}",
            "numerical_seed": 2 + i // 4,
            "continuation_model_id": cached_model(model()).model_id,
        }
        for i in range(8)
    ]
    monkeypatch.setattr(config, "load_later", lambda *args: (parent, corpus, roots, {}))
    cfg = {
        **parent,
        "schema_version": "native-complete-turn-teacher-config-v1",
        "stage": "short_control",
        "workspace": "artifacts/turns",
        "policy_contract": CONTRACT,
        "information_scope": INFORMATION,
        "ordinary_PPO_eligible": False,
        "proposal_generation": GENERATION,
        "proposal_temperature": 1.2,
        "maximum_turn_decisions": MAX_STEPS,
        "maximum_plan_bytes": MAX_PLAN_BYTES,
        "repeats": 2,
        "source_recipe": {"path": "parent.json", "id": manifest_identifier(parent)},
        "implementation_sha256": {src.name: _sha_file(src)},
        "entry_sha256": {entry.name: _sha_file(entry)},
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 2000000000,
        },
    }
    path = tmp / "recipe.json"
    path.write_text(json.dumps(cfg))
    (tmp / "node").write_text("node")
    return cfg, path


def test_plan_and_saved_result_reuse_cannot_start_a_native_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_turn_teacher as module

    cfg, path = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_running_games", lambda: pytest.fail("No native host"))
    planned = run(tmp_path, path, Path("not-used"), status_only=True)
    assert planned["planned_proposals"] == 8 and planned["native_branch_upper_bound"] == 26
    assert not (tmp_path / cfg["workspace"]).exists()
    body = {
        "status": "native_complete_turn_teacher_complete",
        "config_id": manifest_identifier(cfg),
        "sources": {},
    }
    saved = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp_path / cfg["workspace"] / "report.json", saved)
    assert run(tmp_path, path, Path("not-used")) == saved


@pytest.mark.parametrize(
    "fault", ["source", "scope", "stream", "generation", "caps", "target", "parent"]
)
def test_changed_sources_targets_and_information_scope_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    cfg, path = fixture(tmp_path, monkeypatch)
    if fault == "source":
        (tmp_path / "src/spireshift/dummy.py").write_text("changed")
    elif fault == "scope":
        cfg["ordinary_PPO_eligible"] = True
    elif fault == "stream":
        cfg["repeats"] = 16
    elif fault == "generation":
        cfg["proposal_generation"] = "choose_by_final_return"
    elif fault == "caps":
        cfg["maximum_turn_decisions"] = 9999
    elif fault == "target":
        cfg["temperature"] = 0.5
    else:
        cfg["source_recipe"]["id"] = "changed"
    path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        load(tmp_path, path)


def mock_native(
    tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], Path, list[str]]:
    from spireshift import native_turn_teacher as module

    cfg, path = fixture(tmp, monkeypatch)
    _, corpus, roots, _ = load(tmp, path)
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
    monkeypatch.setattr(module, "_shared_snapshot", lambda *a: {"untouched": "bytes"})
    monkeypatch.setattr(module, "immutable_checks", lambda *a: {"shared_unchanged": True})
    assert len(roots) == 2 and corpus["models"] == []
    return cfg, path, []


@pytest.mark.parametrize("failed", [False, True])
def test_proposals_all_freeze_before_scoring_and_failed_root_does_not_halt_other_worlds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed: bool
) -> None:
    from spireshift import native_turn_teacher as module

    cfg, path, calls = mock_native(tmp_path, monkeypatch)
    start = copy.deepcopy(cached_model(model()).as_dict())

    def branch(*args: Any) -> dict[str, Any]:
        _, _, _, target, _, r, task, _, _, _ = args
        calls.append(task["key"])
        base = {
            "status": "terminal",
            "root_id": r["root_id"],
            "stage": task["stage"],
            "root_reached": True,
            "turn_complete": True,
            "native_audit_valid": True,
            "duplicate_control": task["duplicate_control"],
            "repeat": task["repeat"],
            "training_return": 0.03,
            "maximum_floor": 8,
            "completed_acts": 0,
            "victory": False,
            "turn_decisions": 1,
            "trace_id": f"trace-{r['root_id']}",
            "error": None,
        }
        if failed and r["numerical_seed"] == 2 and task["first_action"] == 1:
            return {**base, "status": "failed", "turn_complete": False}
        if task["stage"] == "proposal":
            c = chooser(r, first_action=task["first_action"])
            c(r["public_input"])
            c(next_round(r["public_input"]))
            assert c.plan is not None
            plan_path = target / "turn-plan.json"
            atomic_json(plan_path, c.plan)
            return {
                **base,
                "plan_id": c.plan["plan_id"],
                "plan_path": str(plan_path.relative_to(tmp_path)),
            }
        assert (tmp_path / cfg["workspace"] / "candidate-set.json").exists()
        assert sum(name.startswith("propose") for name in calls) == (7 if failed else 8)
        return {**base, "plan_id": task["plan_id"], "plan_path": task["plan_path"]}

    monkeypatch.setattr(module, "branch", branch)
    result = run(tmp_path, path, tmp_path / "node")
    assert result["status"] == "native_complete_turn_teacher_complete"
    assert result["original_full_states_unchanged"] and result["production_optimizer_steps"] == 0
    assert cached_model(model()).as_dict() == start
    if failed:
        assert result["failed_branches"] == 1 and result["skipped_branches"] == 1
        assert result["completed_source_comparisons"] == 1
        assert len(result["cases"]) == 2 and not result["cases"][0]["comparison_complete"]
    else:
        assert result["completed_source_comparisons"] == 2
        assert result["duplicate_public_traces_identical"]
    monkeypatch.setattr(module, "branch", lambda *a: pytest.fail("Saved branches never rerun"))
    assert run(tmp_path, path, tmp_path / "node") == result


def test_uncommitted_attempt_is_preserved_and_never_replayed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_turn_teacher as module

    cfg, path, _ = mock_native(tmp_path, monkeypatch)
    target = tmp_path / cfg["workspace"] / "chunks/propose-000-greedy"
    target.mkdir(parents=True)
    (target / "active.json").write_text("preserve uncertain delivery")
    monkeypatch.setattr(module, "branch", lambda *a: pytest.fail("No new attempt"))
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, path, tmp_path / "node")
    assert (target / "active.json").read_text() == "preserve uncertain delivery"


@pytest.mark.parametrize(
    "fault", [None, "boundary", "probability", "denominator", "auditor", "duplicates"]
)
def test_main_pilot_requires_matching_native_and_saved_behavior_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    from spireshift import native_turn_teacher_config as config

    cfg, path = fixture(tmp_path, monkeypatch)
    auditor = tmp_path / "src/spireshift/native_turn_teacher_audit.py"
    auditor.write_text("frozen saved auditor")
    monkeypatch.setattr(config, "SOURCES", ("dummy.py", auditor.name))
    cfg["implementation_sha256"][auditor.name] = _sha_file(auditor)
    (tmp_path / "control-recipe.json").write_text(json.dumps(cfg))
    body: dict[str, Any] = {
        "recipe_path": "control-recipe.json",
        "status": "native_complete_turn_teacher_complete",
        "failed_branches": 0,
        "skipped_branches": 0,
        "completed_units": 26,
        "duplicate_public_traces_identical": fault != "duplicates",
        "all_turn_boundaries_replayed_exactly": fault != "boundary",
        "cases": [{"comparison_complete": True}, {"comparison_complete": True}],
        "sources": {},
    }
    passed = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp_path / "control-report.json", passed)
    body = {
        "source_report_id": passed["report_id"],
        "auditor_sha256": "other" if fault == "auditor" else _sha_file(auditor),
        "branch_receipts_verified": 25 if fault == "denominator" else 26,
        "turn_boundaries_and_plans_reconstructed": True,
        "all_action_tables_exactly_reconstructed": True,
        "proposal_selection_outcome_blind": True,
        "continuation_probabilities_reconstructed": fault != "probability",
        "original_players_and_full_Adam_unchanged": True,
    }
    checked = {**body, "report_id": manifest_identifier(body)}
    atomic_json(tmp_path / "control-audit.json", checked)
    cfg.update(
        stage="finite_teacher_pilot",
        repeats=8,
        control_report={"path": "control-report.json", "id": passed["report_id"]},
        control_audit={"path": "control-audit.json", "id": checked["report_id"]},
    )
    cfg["session_limits"].update(wall_seconds=900, cpu_seconds=1800, storage_bytes=4000000000)
    path.write_text(json.dumps(cfg))
    if fault is None:
        assert len(load(tmp_path, path)[2]) == 8
    else:
        with pytest.raises(ValueError):
            load(tmp_path, path)
