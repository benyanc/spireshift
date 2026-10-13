"""Normal shipped new-run entry against saved native starting facts; fixed app, fresh profile."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.engine_connector import (
    _probe_connector_private,
    _validate_benchmark_fixture_scope,
    _verify_toolchain,
    load_connector_qualification_config,
)
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_profile import load_profile_policy, verify_benchmark_progress
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_working_app import (
    load_working_app_policy,
    preflight_working_app,
    verify_working_app_receipt,
)
from spireshift.full_run_experience import atomic_json

HELPERS = {
    "engine-new-run-shipped-probe-v1.mjs",
    "engine-new-run-contract-v1.mjs",
    "engine-menu-probe.mjs",
    "engine-journey-contract-v2.mjs",
}


def _script_closure(root: Path, entries: set[str]) -> set[str]:
    """Pin indirect local imports too; module exports share their initialization code."""
    found: set[str] = set()
    pending = list(entries)
    while pending:
        name = pending.pop()
        if name in found:
            continue
        found.add(name)
        for imported in re.findall(r'from ["\']\./([^"\']+\.mjs)["\']', (root / name).read_text()):
            if Path(imported).name != imported:
                raise ValueError("Helper import outside the pinned scripts directory")
            pending.append(imported)
    return found


def compare_new_run(
    qualification: EngineQualificationConfig,
    recipe_path: Path,
    *,
    node: Path,
    preflight: bool = False,
) -> dict[str, Any]:
    recipe = json.loads(recipe_path.read_text())
    natural = recipe.get("natural_run") is True
    revision = recipe.get("shipped_ui_revision")
    if natural and revision not in {None, "natural_v2", "natural_v3"}:
        raise ValueError("Unknown natural shipped-run implementation")
    expected_helpers = HELPERS | (
        {
            "engine-natural-shipped-run-v3.mjs"
            if revision == "natural_v3"
            else "engine-natural-shipped-run-v2.mjs"
            if revision
            else "engine-natural-shipped-run-v1.mjs",
            "engine-run-contract-v1.mjs",
            "engine-journey-tutorial-v4.mjs",
            "engine-natural-tutorial-v1.mjs" if revision else "engine-combat-shuffle-v1.mjs",
        }
        if natural
        else set()
    )
    if revision == "natural_v3":
        expected_helpers = _script_closure(qualification.root / "scripts", expected_helpers)
    if (
        recipe.get("schema_version") != "engine-new-run-config-v1"
        or recipe.get("qualification_config_id") != qualification.config_id
        or recipe.get("training_allowed") is not False
        or recipe.get("checkpoint_imported") is not False
        or set(recipe.get("helpers_sha256", {})) != expected_helpers
        or any(
            _sha_file(qualification.root / "scripts" / name) != digest
            for name, digest in recipe["helpers_sha256"].items()
        )
    ):
        raise ValueError("Expected a pinned fresh-menu A8 startup comparison")
    objective = load_objective(qualification.root / "configs/default.toml")
    if revision == "natural_v3" and (
        recipe.get("objective_config") != "configs/default.toml"
        or recipe.get("objective_sha256") != _sha_file(qualification.root / "configs/default.toml")
        or "natural_run_limits" not in recipe
    ):
        raise ValueError("The full natural-run recipe must pin its objective and finite caps")
    native_path = _private_path(qualification.root, recipe["native_report"])
    native = json.loads(native_path.read_text())
    body = {key: value for key, value in native.items() if key != "report_id"}
    if (
        native.get("report_id") != manifest_identifier(body)
        or native.get("report_id") != recipe["native_report_id"]
        or native.get("seed") != recipe["seed"]
        or native.get("qualification_config_id") != qualification.config_id
        or native.get("privileged_fixture") is not False
        or native.get("training_allowed") is not False
        or objective.as_dict() != native.get("objective")
    ):
        raise ValueError("Starting reference must be a bound natural native run")
    journal = native_path.parent / "public-run.jsonl"
    if _sha_file(journal) != native["files"]["public-run.jsonl"]:
        raise ValueError("Saved native starting observation changed")
    first = json.loads(journal.read_text().splitlines()[0])
    if (
        first["stage"] != "observation"
        or first["snapshot"]["interaction"]["kind"] != "event_option"
    ):
        raise ValueError("Native run did not start at the initial ancient")
    connector_path = qualification.root / recipe["connector_config"]
    connector = load_connector_qualification_config(connector_path, qualification)
    if connector.config_id != recipe["connector_config_id"]:
        raise ValueError("New-run connector changed")
    working_app = load_working_app_policy(
        qualification.root / recipe["working_app_config"], qualification
    )
    if working_app.config_id != recipe["working_app_config_id"]:
        raise ValueError("New-run working app policy changed")
    policy = load_profile_policy(qualification.root / recipe["profile_policy"], qualification)
    if manifest_identifier(policy) != recipe["profile_policy_id"]:
        raise ValueError("New-run benchmark profile changed")
    progress = _private_path(qualification.root, recipe["benchmark_progress"])
    verify_benchmark_progress(progress, policy)
    workspace = _private_path(qualification.root, recipe["workspace"])
    fixture = {
        "comparison_mode": "new_run_v1",
        "natural_run": natural,
        "shipped_ui_revision": revision,
        "workspace": str(workspace.relative_to(qualification.root) / "shipped"),
        "seed": recipe["seed"],
        "native_observation": str(workspace / "native-start.json"),
        "benchmark_progress": recipe["benchmark_progress"],
        "profile_policy": recipe["profile_policy"],
        "profile_policy_id": recipe["profile_policy_id"],
        "objective": objective.as_dict(),
        **(
            {"natural_run_limits": recipe["natural_run_limits"]}
            if "natural_run_limits" in recipe
            else {}
        ),
    }
    _validate_benchmark_fixture_scope(fixture)
    if preflight:
        if not node.is_file() or _running_games():
            raise ValueError("Use the local Node runtime and close any running game")
        tools = _verify_toolchain(connector)
        pool = preflight_working_app(working_app)
        return {
            "schema_version": "engine-new-run-preflight-v1",
            "config_id": manifest_identifier(recipe),
            "ready_for_diagnostic": not workspace.exists(),
            "workspace": str(workspace),
            "toolchain_report_id": tools["report_id"],
            "working_app_pool_bytes": pool["logical_bytes"],
            "games_launched": 0,
            "training_allowed": False,
        }
    if workspace.exists():
        raise FileExistsError("Preserve the saved new-run comparison; no automatic retry")
    workspace.mkdir(parents=True)
    atomic_json(workspace / "in-progress.json", {"config_id": manifest_identifier(recipe)})
    sources = workspace / "source-at-launch"
    sources.mkdir()
    atomic_json(sources / "recipe.json", recipe)
    for name in expected_helpers:
        (sources / name).write_bytes((qualification.root / "scripts" / name).read_bytes())
    observation = workspace / "native-start.json"
    atomic_json(observation, first)
    result = _probe_connector_private(
        connector,
        node=node,
        fixture=fixture,
        working_app=working_app,
        retain_working_game=False,
    )
    reset = result.get("working_app")
    if reset is None:
        raise ValueError("New-run comparison has no shared-app reset receipt")
    verify_working_app_receipt(
        working_app, reset, attempt=Path(reset["attempt"]), archive_id=result["archive_id"]
    )
    report = {
        "schema_version": "engine-new-run-report-v1",
        "config_id": manifest_identifier(recipe),
        "qualification_config_id": qualification.config_id,
        "seed": recipe["seed"],
        "objective": objective.as_dict(),
        "native_report_id": native["report_id"],
        "status": ("natural_shipped_run_pass" if natural else "normal_start_comparison_pass")
        if result["verdict"]["status"] == "shipped_checkpoint_input_pass"
        else (
            "natural_shipped_run_incomplete" if natural else "normal_start_comparison_incomplete"
        ),
        "shipped_report": result,
        "natural_run": natural,
        "benchmark_denominator": 1,
        "full_run_attempts": result["full_run_attempts"],
        "gameplay": result.get("probe", {}).get("gameplay"),
        "games_launched": result["games_launched"],
        "checkpoint_imported": False,
        "optimizer_steps": 0,
        "training_allowed": False,
        "claim_scope": "natural_shipped_Ironclad_A8_diagnostic_ending_only"
        if natural
        else "natural_Ironclad_A8_lobby_embark_initial_state_only",
    }
    completed = {**report, "report_id": manifest_identifier(report)}
    atomic_json(workspace / "summary.json", completed)
    return completed


def verify_new_run(
    qualification: EngineQualificationConfig, recipe_path: Path, *, node: Path
) -> dict[str, Any]:
    """Verify original receipts and public facts; no games, repairs or retries."""
    recipe = json.loads(recipe_path.read_text())
    workspace = _private_path(qualification.root, recipe["workspace"])
    path = workspace / "summary.json"
    report = json.loads(path.read_text())
    shipped = report["shipped_report"]
    for body in (report, shipped):
        if body["report_id"] != manifest_identifier(
            {k: v for k, v in body.items() if k not in {"report_id", "report_path"}}
        ):
            raise ValueError("Saved new-run report changed")
    if (
        report["config_id"] != manifest_identifier(recipe)
        or report["qualification_config_id"] != qualification.config_id
        or report["seed"] != recipe["seed"]
        or report["checkpoint_imported"] is not False
        or report["training_allowed"] is not False
        or report["optimizer_steps"] != 0
        or report["native_report_id"] != recipe["native_report_id"]
        or report["gameplay"] != shipped["probe"].get("gameplay")
    ):
        raise ValueError("Saved new-run scope, outcome or provenance changed")
    sources = workspace / "source-at-launch"
    if json.loads((sources / "recipe.json").read_text()) != recipe:
        raise ValueError("Saved new-run recipe changed")
    for name, digest in recipe["helpers_sha256"].items():
        if Path(name).name != name or _sha_file(sources / name) != digest:
            raise ValueError("Saved new-run helper changed")
    attempt = _private_path(
        qualification.root,
        str(Path(shipped["working_app"]["attempt"]).relative_to(qualification.root)),
    )
    if json.loads((attempt / "checkpoint-control.json").read_text()) != shipped["probe"]:
        raise ValueError("Saved original shipped observations or delivery receipts changed")
    policy = load_working_app_policy(
        qualification.root / recipe["working_app_config"], qualification
    )
    verify_working_app_receipt(
        policy, shipped["working_app"], attempt=attempt, archive_id=shipped["archive_id"]
    )
    native_path = _private_path(qualification.root, recipe["native_report"])
    native = json.loads(native_path.read_text())
    journal = native_path.parent / "public-run.jsonl"
    if (
        native["report_id"] != recipe["native_report_id"]
        or native["report_id"]
        != manifest_identifier({k: v for k, v in native.items() if k != "report_id"})
        or _sha_file(journal) != native["files"]["public-run.jsonl"]
        or json.loads(journal.read_text().splitlines()[0])
        != json.loads((workspace / "native-start.json").read_text())
    ):
        raise ValueError("Saved native starting reference changed")
    checked = subprocess.run(
        [str(node), str(qualification.root / "scripts/verify-engine-new-run-v1.mjs")],
        input=json.dumps(
            {
                "report": str(path),
                "sources": str(sources),
                "reference": str(workspace / "native-start.json"),
                "seed": recipe["seed"],
            }
        ),
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if checked.returncode != 0:
        raise ValueError(f"Saved public-action audit failed: {checked.stderr[-2000:]}")
    return {
        **json.loads(checked.stdout),
        "report_id": report["report_id"],
        "status": report["status"],
        "source_inputs_reaudited": False,
        "fixed_app_reset_verified": True,
        "error": shipped["probe"].get("error"),
        "wall_seconds": shipped["process"]["wall_seconds"],
    }
