from __future__ import annotations

import copy
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_native_action_context import model, score

import spireshift.native_final_canary_session as module
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_curriculum_config import plan
from spireshift.native_curriculum_store import journal
from spireshift.native_fitting_session import LAUNCH as FITTING_LAUNCH
from spireshift.native_structured_state import load, save


def inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    cases = plan()["canary_cases"]
    launch: dict[str, Any] = {
        "config_id": "study",
        "cases": cases,
        "frozen_finals_id": "frozen",
        "finals": {},
        "short_check": None,
    }
    ctx: dict[str, Any] = {
        "config_id": "study",
        "environment": {"manifest_id": "env"},
        "guard_receipt": {"report_id": "guard"},
        "qualification": SimpleNamespace(root=root),
        "config": {"workspace": "artifacts/native-varied-teaching/derived-study", "plan": plan()},
        "canary_launch": launch,
        "canary_launch_path": root / "launch.json",
    }
    (root / "launch.json").write_text("{}\n")
    assessed = {
        "status": "all_256_updates_full_Adam_and_fixed_finals_independently_reconstructed",
        "config_id": "study",
        "source_report_id": "fitted",
        "frozen_finals_id": "frozen",
        "bank_id": "bank",
        "environment_id": "env",
        "guard_receipt_id": "guard",
        "sealed_units_verified": 67,
        "unique_checkpoint_recorded_regressions_verified": 66,
        "registered_main_optimizer_updates": 256,
        "separate_numerical_reconstruction_steps": 256,
        "all_original_weights_and_full_Adam_unchanged": True,
        "no_evaluation_used_for_final_selection": True,
        "new_checkpoint_live_delivery_qualified": False,
    }
    fitted = {
        "status": "diagnostic_finals_frozen",
        "config_id": "study",
        "report_id": "fitted",
        "frozen_finals_id": "frozen",
        "bank_id": "bank",
        "optimizer_updates": 256,
        "new_checkpoint_live_delivery_qualified": False,
    }
    return ctx, launch, assessed, fitted


@pytest.mark.parametrize(
    "field",
    ["source_report_id", "frozen_finals_id", "bank_id", "registered_main_optimizer_updates"],
)
def test_wrong_assessed_finals_cannot_reuse_live_attempt_scope(tmp_path: Path, field: str) -> None:
    ctx, launch, assessed, fitted = inputs(tmp_path)
    module.require_assessed_finals(ctx, launch, assessed, fitted)
    assessed[field] = "other-valid-receipt"
    with pytest.raises(ValueError, match="assessed"):
        module.require_assessed_finals(ctx, launch, assessed, fitted)


@pytest.mark.parametrize("field", ["seed", "variant", "player"])
def test_predeclared_worlds_and_policy_modes_cannot_be_swapped(tmp_path: Path, field: str) -> None:
    ctx, launch, assessed, fitted = inputs(tmp_path)
    launch["cases"] = copy.deepcopy(launch["cases"])
    launch["cases"][0][field] = "different"
    with pytest.raises(ValueError, match="prospectively"):
        module.require_assessed_finals(ctx, launch, assessed, fitted)


def test_full_Adam_swap_rejected_even_when_replacement_file_is_valid(tmp_path: Path) -> None:
    ctx, launch, _, fitted = inputs(tmp_path)
    m = cached_model(model())
    ctx.update(models={2: m, 3: m}, adams={}, score=score())
    fitted["finals"] = {}
    for p, step in [(2, 5658), (3, 6045)]:
        initial = Adam(step, (0.01,) * m.parameter_count, (0.02,) * m.parameter_count)
        ctx["adams"][p] = initial
        for arm in ["original", "reference", "teacher"]:
            path = tmp_path / f"p{p}-{arm}.json"
            adam = Adam(step + (0 if arm == "original" else 64), initial.first, initial.second)
            value = save(path, m, adam)
            slot = f"p{p}-{arm}"
            row = {
                "state_id": value["state_id"],
                "model_id": m.model_id,
                "optimizer_id": manifest_identifier(adam.as_dict()),
                "optimizer_steps": adam.steps,
            }
            launch["finals"][slot] = {**row, "path": path.name, "sha256": _sha_file(path)}
            fitted["finals"][slot] = {**row, "state_path": path.name}
    module.verify_final_files(ctx, launch, fitted)
    original = tmp_path / launch["finals"]["p2-teacher"]["path"]
    restored, adam, _ = load(original)
    changed = Adam(adam.steps, (adam.first[0] + 0.1, *adam.first[1:]), adam.second)
    replacement = tmp_path / "replacement.json"
    value = save(replacement, restored, changed)
    launch["finals"]["p2-teacher"].update(
        path=replacement.name,
        sha256=_sha_file(replacement),
        state_id=value["state_id"],
        optimizer_id=manifest_identifier(changed.as_dict()),
    )
    with pytest.raises(ValueError, match="substituted"):
        module.verify_final_files(ctx, launch, fitted)


def result(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "trained_policy_canaries_verified",
        "config_id": ctx["config_id"],
        "frozen_finals_id": ctx["canary_launch"]["frozen_finals_id"],
        "cases": [
            {"case": c, "status": "matching_genuine_endings"} for c in ctx["canary_launch"]["cases"]
        ],
        "all_current_policy_modes_live_qualified": True,
        "promotion_allowed": False,
        "broader_live_admission": False,
        "optimizer_updates": 0,
    }


@pytest.mark.parametrize("failure", ["incomplete", "different-final", "different-world", "updates"])
def test_capped_or_mismatched_panel_cannot_qualify(tmp_path: Path, failure: str) -> None:
    ctx, _, _, _ = inputs(tmp_path)
    r = result(ctx)
    module.require_result(ctx, r)
    r = copy.deepcopy(r)
    if failure == "incomplete":
        r["cases"][0]["status"] = "prefix_limit"
    elif failure == "different-final":
        r["frozen_finals_id"] = "other-valid-state"
    elif failure == "different-world":
        r["cases"][0]["case"]["seed"] = "other-world"
    else:
        r["optimizer_updates"] = 1
    with pytest.raises(ValueError):
        module.require_result(ctx, r)


def test_clean_prefix_resumes_but_unfinished_case_preserves_and_blocks(tmp_path: Path) -> None:
    ctx, launch, _, _ = inputs(tmp_path)
    declared = tmp_path / ctx["config"]["workspace"] / "canary-launch/scope.json"
    declared.parent.mkdir(parents=True)
    declared.write_text(json.dumps(module.scope(ctx)))
    store = journal(ctx, "canaries")
    a, b = launch["cases"][:2]

    def request(case: dict[str, Any]) -> dict[str, Any]:
        return {"case": case, "frozen_finals_id": "frozen", "guard_id": "guard"}

    with store.lock():
        store.begin(a["key"], request(a))
        store.commit(
            a["key"],
            request(a),
            {"case": a, "status": "matching_genuine_endings", "clean_reset": True},
            {"launch.json": _sha_file(tmp_path / "launch.json")},
        )
    assert module.verify_resume(ctx) == 1
    first = (store.path(a["key"]) / "done.json").read_bytes()
    with store.lock():
        pending = store.begin(b["key"], request(b))
    active = (pending / "active.json").read_bytes()
    with pytest.raises(FileExistsError, match="uncommitted"):
        module.verify_resume(ctx)
    assert (pending / "active.json").read_bytes() == active
    assert (store.path(a["key"]) / "done.json").read_bytes() == first
    assert not store.path(launch["cases"][2]["key"]).exists()


def test_preflight_never_launches_a_host_or_writes_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx, _, _, _ = inputs(tmp_path)
    monkeypatch.setattr(sys, "argv", ["canaries", str(tmp_path / "launch.json"), "--preflight"])
    monkeypatch.setattr(module, "prepare", lambda *a: ctx)
    monkeypatch.setattr(module, "frozen_checks", lambda c: {"exact": True})
    monkeypatch.setattr(module, "canary", lambda *a, **kw: pytest.fail("preflight started games"))
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["new_games"] == 0
    assert not (tmp_path / ctx["config"]["workspace"]).exists()


def test_owner_session_only_dispatches_canaries_and_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, _, _, _ = inputs(tmp_path)
    target = tmp_path / "scope"
    target.mkdir()
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["canaries", str(tmp_path / "launch.json")])
    monkeypatch.setattr(module, "prepare", lambda *a: ctx)
    monkeypatch.setattr(module, "snapshot", lambda c: target)

    def checks(c: Any) -> dict[str, bool]:
        calls.append("check")
        return {"exact": True}

    def run(c: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append("canary")
        assert kwargs["deadline"] - time.monotonic() > 4000
        return result(ctx)

    monkeypatch.setattr(module, "frozen_checks", checks)
    monkeypatch.setattr(module, "canary", run)
    assert module.main() == 0
    assert calls == ["check", "canary", "check"]
    receipt = json.loads((target / "session-1.json").read_text())
    assert receipt["optimizer_updates"] == 0 and receipt["automatic_follow_up"] is False


@pytest.mark.parametrize("field", ["live_qualification_granted", "planned_canary_worlds_used"])
def test_saved_control_cannot_claim_live_qualification(tmp_path: Path, field: str) -> None:
    _, launch, _, _ = inputs(tmp_path)
    report = {
        "status": "all_six_exact_modes_saved_inputs_verified",
        "launch_binding_id": module.binding(launch),
        "saved_mode_menu_comparisons": 1752,
        "new_games": 0,
        "optimizer_updates": 0,
        "planned_canary_worlds_used": False,
        "live_qualification_granted": False,
        "checks": {"exact": True},
    }
    module.require_short_check(report, launch)
    report[field] = True
    with pytest.raises(ValueError, match="short check"):
        module.require_short_check(report, launch)


def test_resource_accounting_uses_recipe_workspace_and_whole_panel_cap(tmp_path: Path) -> None:
    for name in module.FILES:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("pinned\n")
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps({"workspace": "artifacts/native-varied-teaching/derived"}))
    fit = tmp_path / FITTING_LAUNCH
    fit.parent.mkdir(parents=True, exist_ok=True)
    fit.write_text(json.dumps({"recipe": {"path": recipe.name, "sha256": _sha_file(recipe)}}))
    launch: dict[str, Any] = {
        "schema_version": module.SCHEMA,
        "operation": module.OPERATION,
        "budget": module.BUDGET,
        "session_limits": dict(module.LIMITS),
        "implementation": module.implementation(tmp_path),
        "fitting_launch": {"path": FITTING_LAUNCH, "sha256": _sha_file(fit)},
        "automatic_follow_up": False,
    }
    path = tmp_path / module.LAUNCH
    path.write_text(json.dumps(launch))
    command = module.resource_command(tmp_path, path, 1)
    roots = [command[i + 1] for i, x in enumerate(command) if x == "--artifact-root"]
    assert roots == [
        "artifacts/native-varied-teaching/derived/canaries",
        "artifacts/native-varied-teaching/derived/canary-launch",
    ]
    assert command[command.index("--max-wall-seconds") + 1] == "4200"
    assert command[-2:] == ["spireshift.native_final_canary_session", module.LAUNCH]
    assert not {"fit", "evaluate", "collect"}.intersection(command)
    launch["session_limits"]["wall_seconds"] = 14400
    path.write_text(json.dumps(launch))
    with pytest.raises(ValueError):
        module.resource_command(tmp_path, path, 1)
