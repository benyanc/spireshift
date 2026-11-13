"""Bind the Trial repair and derive the next continuation of the frozen plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_win5_inputs import RECIPE as PARENT_RECIPE
from spireshift.native_win5_inputs import completed
from spireshift.native_win5_inputs import frozen_checks as frozen_checks
from spireshift.native_win5_inputs import load as parent_load
from spireshift.native_win6_build import CHANGED_FILE
from spireshift.native_win6_recovery import COMPLETED_CASES, REUSABLE_SEALS, continuation_plan

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v6.json"


def implementation(root: Path) -> dict[str, str]:
    files = sorted((root / "src/spireshift").glob("native_win6_*.py"))
    files.extend(sorted((root / "backend-patches/headless-trial-portrait-v1").iterdir()))
    files.append(root / "scripts/continue-win-curriculum-v6.sh")
    return {str(path.relative_to(root)): _sha_file(path) for path in files}


def support_context(root: Path, parent: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    if (
        report["schema_version"] != "native-headless-trial-build-v59"
        or report["status"] != "trial_portrait_bridge_built"
        or report["parent_environment_id"] != parent["environment"]["manifest_id"]
        or report["changed_production_source_files"] != [CHANGED_FILE]
    ):
        raise ValueError("The support build must bind the exact prior native environment")
    check_sources(root, report["sources"])
    check_sources(root, report["evidence"])
    build = report["builds"][0]
    old = parent["native"]
    if any(build[key] != old["build"][key] for key in ("runtime_sts2_sha256", "godot_stub_sha256")):
        raise ValueError("Frozen game or Godot support DLL changed")
    execution = {
        "schema_version": "native-curriculum-support-execution-v59",
        "parent_environment_id": parent["environment"]["manifest_id"],
        "support_build_id": report["report_id"],
        "ordered_answer_contract": parent["config"]["ordered_answer_contract"],
        "official_qualification": False,
    }
    environment = {**execution, "manifest_id": manifest_identifier(execution)}
    native = {
        **old,
        "candidate": _private_path(root, build["candidate"]),
        "candidate_before": report["candidate_inventory"],
        "build": {
            **old["build"],
            **{
                key: build[key]
                for key in [
                    "artifact_sha256",
                    "artifact_mvid",
                    "godot_stub_sha256",
                    "runtime_sts2_sha256",
                ]
            },
        },
        "recipe": {**old["recipe"], "input_config_id": environment["manifest_id"]},
    }
    return {**parent, "native": native, "environment": environment}


def declaration(root: Path) -> dict[str, Any]:
    recipe = json.loads((root / RECIPE).read_text())
    if (
        recipe.get("schema_version") != "native-win-curriculum-continuation-v6"
        or recipe.get("workspace") != "artifacts/native-win-curriculum/study-v6"
        or recipe.get("launch_workspace") != "artifacts/native-win-curriculum/launch-v6"
        or verified(root, recipe["parent"]) != root / PARENT_RECIPE
    ):
        raise ValueError("Use the declared case-43 replacement and frozen parent")
    return dict(recipe)


def load(root: Path) -> dict[str, Any]:
    decl = declaration(root)
    if decl["implementation"] != implementation(root):
        raise ValueError("Continuation sources changed")
    parent = parent_load(root)
    report = identified(verified(root, decl["support"]["report"]))
    completed(root, decl["support"]["resource"])
    context = support_context(root, parent, report)
    saved = identified(verified(root, decl["audit"]["report"]))
    completed(root, decl["audit"]["resource"])
    if (
        saved["status"] != "sealed_cases_verified_failed_trial_excluded"
        or saved["parent_config_id"] != parent["config_id"]
        or saved["completed_cases"] != COMPLETED_CASES
        or len(saved["imports"]) != REUSABLE_SEALS
        or len(saved["historical_failures"]) != 5
        or any(failure["labels_allowed"] for failure in saved["historical_failures"])
    ):
        raise ValueError("Retained cases or historical failures do not match the saved audit")
    check_sources(root, saved["sources"])
    check_sources(root, saved["evidence"])
    check_sources(root, json.loads(verified(root, decl["protected"]).read_text()))
    control = identified(verified(root, decl["control"]["report"]))
    completed(root, decl["control"]["resource"])
    if (
        control["status"] != "trial_accept_and_verdicts_verified"
        or control["support_build_id"] != report["report_id"]
        or control["environment_id"] != context["environment"]["manifest_id"]
        or control["optimizer_updates"] != 0
        or control["training_labels_allowed"] is not False
        or set(control["verified_verdicts"])
        != {
            f"{entrant}/{verdict}"
            for entrant in ("merchant", "noble", "nondescript")
            for verdict in ("guilty", "innocent")
        }
        or control["checks"].get("reject_then_accept") is not True
        or not all(control["checks"].values())
    ):
        raise ValueError("Missing current Trial mechanics control")
    check_sources(root, control["sources"])
    check_sources(root, control["evidence"])
    prior = parent["config"]
    plan = continuation_plan(prior)
    original_seeds = {
        seed
        for group in ("fit", "heldout")
        for case in prior["plan"][group]
        for seed in case["seed_pool"]
    }
    for failure in saved["historical_failures"]:
        original_seeds.update(failure["case"]["seed_pool"])
    if original_seeds.intersection(plan["fit"][COMPLETED_CASES]["seed_pool"]):
        raise ValueError("The replacement world was already declared in prior evidence")
    config = {
        **prior,
        "schema_version": "native-win-curriculum-config-v6",
        "workspace": decl["workspace"],
        "plan": plan,
        "continuation_declaration_id": manifest_identifier(decl),
        "historical_incomplete_cases": len(saved["historical_failures"]),
        "reused_original_cases": COMPLETED_CASES,
    }
    pins = [decl["parent"], decl["protected"]]
    pins.extend(
        decl[group][part]
        for group in ("support", "audit", "control")
        for part in ("report", "resource")
    )
    return {
        **context,
        "parent_config": prior,
        "config": config,
        "config_id": manifest_identifier(config),
        "recipe": root / RECIPE,
        "declaration": decl,
        "imports": saved["imports"],
        "historical_failures": saved["historical_failures"],
        "sources": {
            **parent["sources"],
            **decl["implementation"],
            RECIPE: _sha_file(root / RECIPE),
            **{ref["path"]: ref["sha256"] for ref in pins},
        },
    }
