"""Post-sweep random-prefix and same-build lifecycle checks.

The in-flight sweep is read-only. Its success is a required saved fact before
this entry point may launch any short checks; no training or app copy follows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_coverage import (
    _read_sealed,
    _saved_case,
    _sealed,
    coverage_implementation,
)
from spireshift.engine_native import _private_path
from spireshift.engine_progression import run_native_progression, verify_native_progression
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_sequence_checks import (
    load_sequence_config,
    run_legal_sequences,
    verify_legal_sequences,
)
from spireshift.full_run_experience import atomic_json

IMPLEMENTATION = (
    "engine_mechanics_followups.py",
    "engine_sequence_checks.py",
    "engine_progression.py",
)
REMAINING = ["out_of_combat_potion_use", "non_creature_potion_target"]


def followup_implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / "src/spireshift" / name) for name in IMPLEMENTATION}


def assert_completed_sweep(
    cfg: dict[str, Any], plan: dict[str, Any], report: dict[str, Any], rows: list[dict[str, Any]]
) -> None:
    if (
        report.get("config_id") != manifest_identifier(cfg)
        or report.get("plan_id") != plan["plan_id"]
        or report.get("inventory_complete") is not True
        or report.get("known_gaps") != []
        or report.get("not_attempted_cases") != 0
        or report.get("planned_cases") != len(plan["cases"])
        or report.get("completed_cases") != len(plan["cases"])
        or not rows
        or len(rows) != len(plan["cases"])
        or [r["spec"] for r in rows] != plan["cases"]
        or [r["report_id"] for r in rows] != report.get("case_reports")
        or any(
            r["status"] not in {"effect_exercised", "observed_prerequisite_blocked"} for r in rows
        )
    ):
        raise ValueError(
            "The full repaired sweep must finish with no unresolved case failures first"
        )


def followup_inputs(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    cfg = json.loads(path.read_text())
    if (
        cfg.get("schema_version") != "native-mechanics-followup-config-v1"
        or cfg.get("qualification_config_id") != q.config_id
        or cfg.get("training_allowed") is not False
        or cfg.get("game_apps_created") != 0
        or cfg.get("implementation_sha256") != followup_implementation(q.root)
    ):
        raise ValueError("Expected a frozen separate post-sweep mechanics recipe")
    sweep = json.loads((q.root / cfg["sweep_config"]).read_text())
    sequence = load_sequence_config(q.root / cfg["sequence_config"], q)
    progression = json.loads((q.root / cfg["progression_config"]).read_text())
    if (
        manifest_identifier(sweep) != cfg["sweep_config_id"]
        or sweep.get("implementation_sha256") != coverage_implementation(q.root)
        or manifest_identifier(sequence) != cfg["sequence_config_id"]
        or manifest_identifier(progression) != cfg["progression_config_id"]
        or sequence["run_config_id"] != sweep["run_config_id"]
    ):
        raise ValueError("Post-sweep diagnostics changed native, sweep or implementation identity")
    run = json.loads((q.root / sweep["run_config"]).read_text())
    inputs = json.loads((q.root / run["input_config"]).read_text())
    if (
        manifest_identifier(inputs) != run["input_config_id"]
        or progression["build_report_id"] != inputs["build_report_id"]
        or progression["build_config"] != inputs["build_config"]
    ):
        raise ValueError("Act/ending checks must use the exact same native build as the sweep")
    _private_path(q.root, cfg["workspace"])
    return {"cfg": cfg, "sweep": sweep, "sequence": sequence, "progression": progression}


def completed_sweep(q: EngineQualificationConfig, loaded: dict[str, Any]) -> dict[str, Any]:
    sweep = loaded["sweep"]
    workspace = _private_path(q.root, sweep["workspace"])
    path = workspace / "sweep-summary.json"
    if not path.is_file():
        raise ValueError(
            "Wait for the current full sweep to finish; no follow-up games were launched"
        )
    report = _read_sealed(path)
    plan = _read_sealed(workspace / "plan.json", "plan_id")
    if plan["plan_id"] != loaded["cfg"]["sweep_plan_id"]:
        raise ValueError("Post-sweep recipe belongs to another generated mechanics plan")
    rows = []
    for case in plan["cases"]:
        folder = workspace / "sweep" / f"case-{case['case_id']}"
        if not (folder / "result.json").is_file():
            folder = workspace / "smoke" / f"case-{case['case_id']}"
        rows.append(_saved_case(folder / "result.json", case, plan["plan_id"]))
    assert_completed_sweep(sweep, plan, report, rows)
    return report


def run_mechanics_followups(
    q: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    loaded = followup_inputs(q, path)
    cfg = loaded["cfg"]
    sweep = completed_sweep(q, loaded)
    workspace = _private_path(q.root, cfg["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    recipe = workspace / "recipe.json"
    if recipe.exists() and json.loads(recipe.read_text()) != cfg:
        raise ValueError("Follow-up workspace belongs to another recipe")
    if not recipe.exists():
        atomic_json(recipe, cfg)
    target = workspace / "summary.json"
    if target.exists():
        return verify_mechanics_followups(q, path)
    sequence = run_legal_sequences(q, q.root / cfg["sequence_config"], node=node)
    progression_path = _private_path(q.root, loaded["progression"]["workspace"])
    if (progression_path / "summary.json").exists():
        # Even a saved failed attempt is preserved. No implicit retry or overwrite.
        progression = _read_sealed(progression_path / "summary.json")
        if progression["status"] == "native_progression_pass":
            verify_native_progression(q, q.root / cfg["progression_config"])
    else:
        progression = run_native_progression(q, q.root / cfg["progression_config"])
    sequence_ok = sequence["status"] == "legal_sequence_panel_pass"
    progression_ok = progression["status"] == "native_progression_pass"
    if sequence_ok:
        verify_legal_sequences(q, q.root / cfg["sequence_config"])
    if progression_ok:
        verify_native_progression(q, q.root / cfg["progression_config"])
    result = _sealed(
        {
            "schema_version": "native-mechanics-followup-report-v1",
            "config_id": manifest_identifier(cfg),
            "sweep_report_id": sweep["report_id"],
            "sequence_report_id": sequence["report_id"],
            "progression_report_id": progression["report_id"],
            "status": "scoped_followups_pass"
            if sequence_ok and progression_ok
            else "followups_incomplete",
            "requirements": {
                "random_legal_action_sequences": "exercised_native_diagnostic"
                if sequence_ok
                else "unverified",
                "act_and_terminal_transitions": "exercised_native_diagnostic"
                if progression_ok
                else "unverified",
            },
            "unresolved_requirements": REMAINING,
            "all_mechanics_requirements_resolved": False,
            "training_allowed": False,
            "game_apps_created": 0,
            "optimizer_steps": 0,
            "player_victories_qualified": 0,
            "claim_scope": (
                "saved_full_sweep_plus_bounded_random_prefixes_and_privileged_native_lifecycle_only"
            ),
        }
    )
    atomic_json(target, result)
    return result


def verify_mechanics_followups(q: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    loaded = followup_inputs(q, path)
    cfg = loaded["cfg"]
    sweep = completed_sweep(q, loaded)
    workspace = _private_path(q.root, cfg["workspace"])
    saved = _read_sealed(workspace / "summary.json")
    sequence = verify_legal_sequences(q, q.root / cfg["sequence_config"])
    progression = verify_native_progression(q, q.root / cfg["progression_config"])
    if (
        json.loads((workspace / "recipe.json").read_text()) != cfg
        or saved["config_id"] != manifest_identifier(cfg)
        or saved["sweep_report_id"] != sweep["report_id"]
        or saved["sequence_report_id"] != sequence["report_id"]
        or saved["progression_report_id"] != progression["native_report_id"]
        or saved["status"] != "scoped_followups_pass"
        or saved["training_allowed"] is not False
        or saved["all_mechanics_requirements_resolved"] is not False
        or saved["unresolved_requirements"] != REMAINING
        or saved["player_victories_qualified"] != 0
    ):
        raise ValueError("Saved follow-up scope, engine or subordinate evidence changed")
    return {**saved, "verified_saved_evidence": True, "games_replayed": 0}
