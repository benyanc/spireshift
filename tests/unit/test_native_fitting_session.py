from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import spireshift.native_fitting_session as module
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file


def inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    context = {
        "config_id": "fixed-study",
        "guard_receipt": {"report_id": "guard"},
        "environment": {"manifest_id": "frozen-engine"},
        "config": {
            "plan": {
                "worlds": [
                    {"seed": "fit", "partition": "fit"},
                    {"seed": "held", "partition": "heldout"},
                ]
            }
        },
    }
    assessment = {
        "status": "finite_curriculum_independently_verified_ready_for_declared_copy_fitting",
        "config_id": "fixed-study",
        "source_report_id": "collected",
        "bank_id": "bank",
        "guard_receipt_id": "guard",
        "environment_id": "frozen-engine",
        "actual_selection_and_complete_lesson_bank_reconstructed": True,
        "original_weights_and_complete_Adam_unchanged": True,
        "capped_proposals_supply_no_labels": True,
    }
    collection = {
        "status": "curriculum_qualified",
        "config_id": "fixed-study",
        "bank_id": "bank",
        "report_id": "collected",
        "all_natural_sources_clean": True,
        "all_prospective_withheld_worlds_have_public_roots": True,
        "fitting_started": False,
        "optimizer_updates": 0,
    }
    bank = {
        "bank_id": "bank",
        "control_only": False,
        "heldout_labels_or_outcomes_used": False,
        "student_inputs_public_only": True,
        "quality": {"passed": True},
        "lessons": [{"world": "fit", "partition": "fit"}],
    }
    return context, assessment, collection, bank


@pytest.mark.parametrize("field", ["config_id", "bank_id", "source_report_id", "guard_receipt_id"])
def test_stale_assessment_cannot_authorize_fitting(field: str) -> None:
    context, assessment, collection, bank = inputs()
    module.require_assessed_bank(context, assessment, collection, bank)
    assessment[field] = "different-valid-receipt"
    with pytest.raises(ValueError, match="assessed"):
        module.require_assessed_bank(context, assessment, collection, bank)


def test_withheld_world_cannot_be_relabeled_even_if_receipt_ids_agree() -> None:
    context, assessment, collection, bank = inputs()
    bank["lessons"][0]["world"] = "held"
    # Self-consistent replacement identities alone cannot authorize held-out labels.
    for value in [assessment, collection, bank]:
        value["bank_id"] = "valid-replacement-bank"
    with pytest.raises(ValueError, match="withheld"):
        module.require_assessed_bank(context, assessment, collection, bank)


def launch_fixture(root: Path) -> tuple[Path, dict[str, Any]]:
    for name in module.FILES:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("frozen source\n")
    cfg = {
        "stage": "bounded_study",
        "workspace": "artifacts/native-varied-teaching/derived-study",
        "session_limits": {
            "wall_seconds": 1800,
            "cpu_seconds": 3600,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        },
        "plan": {"learning": {"epochs": 16, "steps_per_epoch": 4, "batch_choices": 32}},
    }
    recipe = root / module.RECIPE
    recipe.parent.mkdir(parents=True, exist_ok=True)
    recipe.write_text(json.dumps(cfg))
    launch = {
        "schema_version": module.SCHEMA,
        "phase": "fit_only",
        "work": dict(module.WORK),
        "recipe": {"path": module.RECIPE, "sha256": _sha_file(recipe)},
        "config_id": manifest_identifier(cfg),
        "implementation": module.implementation(root),
        "session_limits": cfg["session_limits"],
        "automatic_follow_up": False,
        "short_check": None,
    }
    path = root / module.LAUNCH
    path.write_text(json.dumps(launch))
    return path, launch


def test_owner_command_uses_derived_fitting_outputs_and_never_evaluates(tmp_path: Path) -> None:
    path, _ = launch_fixture(tmp_path)
    command = module.resource_command(tmp_path, path, 7)
    roots = [command[i + 1] for i, arg in enumerate(command) if arg == "--artifact-root"]
    assert roots == [
        "artifacts/native-varied-teaching/derived-study/fitting",
        "artifacts/native-varied-teaching/derived-study/fitting-launch",
    ]
    assert command[-2:] == ["spireshift.native_fitting_session", module.LAUNCH]
    assert not {"collect", "canary", "evaluate", "--max-units"}.intersection(command)
    assert command[command.index("--max-wall-seconds") + 1] == "1800"
    assert command[command.index("--max-cpu-seconds") + 1] == "3600"


@pytest.mark.parametrize("mutation", ["evaluation", "larger-budget", "source-drift"])
def test_launcher_rejects_phase_budget_or_implementation_drift(
    tmp_path: Path, mutation: str
) -> None:
    path, launch = launch_fixture(tmp_path)
    if mutation == "evaluation":
        launch["phase"] = "fit_then_evaluate"
    elif mutation == "larger-budget":
        launch["session_limits"]["wall_seconds"] = 7200
    else:
        (tmp_path / module.FILES[0]).write_text("changed\n")
    path.write_text(json.dumps(launch))
    with pytest.raises(ValueError):
        module.resource_command(tmp_path, path, 1)


@pytest.mark.parametrize("mutation", ["other-source", "main-started", "wrong-work"])
def test_wrong_short_control_never_admits_main(mutation: str) -> None:
    launch = {"work": module.WORK, "short_check": None}
    report = {
        "status": "assessed_bank_fitting_control_pass",
        "launch_binding_id": module.binding(launch),
        "matched_copy_optimizer_updates": 16,
        "resume_fork_optimizer_updates": 4,
        "separate_numerical_reconstruction_steps": 4,
        "main_fitting_started": False,
        "control_finals_enter_main": False,
        "checks": {"all": True},
    }
    module.require_short_check(report, launch)
    if mutation == "other-source":
        report["launch_binding_id"] = "other-source"
    elif mutation == "main-started":
        report["main_fitting_started"] = True
    else:
        report["matched_copy_optimizer_updates"] = 256
    with pytest.raises(ValueError, match="control"):
        module.require_short_check(report, launch)


def test_preflight_runs_guard_checks_without_fitting_or_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["fit", str(tmp_path / "launch.json"), "--preflight"])
    monkeypatch.setattr(module, "prepare", lambda *args: {"fitting_bank": {"bank_id": "bank"}})

    def checks(ctx: Any) -> dict[str, bool]:
        calls.append("check")
        return {"exact": True}

    monkeypatch.setattr(module, "frozen_checks", checks)
    monkeypatch.setattr(
        module, "fit", lambda *args, **kwargs: pytest.fail("preflight performed updates")
    )
    assert module.main() == 0 and calls == ["check"]
    assert json.loads(capsys.readouterr().out)["optimizer_updates"] == 0
    assert not list(tmp_path.iterdir())


def test_actual_session_stops_after_frozen_finals_and_postflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    target = tmp_path / "launch-evidence"
    target.mkdir()
    context = {"fitting_launch": {"session_limits": {"wall_seconds": 1800}}, "config_id": "fixed"}
    monkeypatch.setattr(sys, "argv", ["fit", str(tmp_path / "launch.json")])
    monkeypatch.setattr(module, "prepare", lambda *args: copy.deepcopy(context))

    def checks(ctx: Any) -> dict[str, bool]:
        calls.append("check")
        return {"exact": True}

    monkeypatch.setattr(module, "frozen_checks", checks)
    monkeypatch.setattr(module, "snapshot_launch", lambda ctx: target)

    def fit_once(ctx: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append("fit")
        return {"status": "diagnostic_finals_frozen", "report_id": "frozen"}

    monkeypatch.setattr(module, "fit", fit_once)
    assert module.main() == 0
    assert calls == ["check", "fit", "check"]
    receipt = json.loads((target / "session-1.json").read_text())
    assert receipt["fitting_report_id"] == "frozen" and receipt["new_games"] == 0
    assert receipt["automatic_follow_up"] is False
