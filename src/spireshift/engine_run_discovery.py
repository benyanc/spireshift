"""Finite serial discovery: retain blocked games, continue isolated seeds, never admit learning."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_startup import compare_new_run, verify_new_run
from spireshift.full_run_experience import atomic_json


def load_discovery_recipe(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], list[tuple[Path, dict[str, Any]]]]:
    document = json.loads(path.read_text())
    cases = document.get("cases", [])
    if (
        document.get("schema_version") != "engine-run-discovery-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("workers") != 1
        or document.get("reporting_revision") not in {None, "outcomes_v2"}
        or not isinstance(cases, list)
        or not 1 <= len(cases) <= 8
        or type(document.get("max_wall_seconds")) is not int
        or not 180 <= document["max_wall_seconds"] <= 7500
        or document.get("resource_caps")
        != {
            "max_wall_seconds": document["max_wall_seconds"] + 20,
            "max_cpu_seconds": 1800 * len(cases),
            "max_storage_bytes": 4_000_000_000,
            "max_memory_bytes": 8_000_000_000,
        }
    ):
        raise ValueError("Expected a finite one-worker actual-engine discovery recipe")
    workspace = _private_path(qualification.root, document["workspace"])
    loaded = []
    for case in cases:
        recipe_path = qualification.root / case["recipe"]
        recipe = json.loads(recipe_path.read_text())
        case_workspace = _private_path(qualification.root, recipe["workspace"])
        if (
            manifest_identifier(recipe) != case["config_id"]
            or recipe.get("shipped_ui_revision") != "natural_v4"
            or recipe.get("diagnostic_limits", {}).get("mode") != "discovery"
            or case_workspace.parent != workspace
            or recipe.get("training_allowed") is not False
        ):
            raise ValueError(
                "Every discovery case must bind a fresh child recipe and bounded recovery"
            )
        loaded.append((recipe_path, recipe))
    if len({recipe["seed"] for _, recipe in loaded}) != len(cases) or len(
        {recipe["workspace"] for _, recipe in loaded}
    ) != len(cases):
        raise ValueError("Discovery cases must have independent seeds and output locations")
    return document, loaded


def case_outcome(case: dict[str, Any]) -> dict[str, Any]:
    """Distinguish a complete diagnostic batch from its games and interface omissions."""
    gameplay = case["gameplay"]
    error = case.get("error")
    if error is None and case.get("verification"):
        error = case["verification"].get("error")
    recovered = bool(case["diagnostics"].get("recoveries"))
    completed = case["status"] == "natural_shipped_run_pass"
    message = str(error or "").lower()
    if completed:
        failure = None
    elif case["status"] == "infrastructure_failure":
        failure = "infrastructure"
    elif "delivery" in message:
        failure = "action_delivery"
    elif "repeated natural-run public state" in message:
        failure = "repeated_state"
    elif "cap" in message:
        failure = "resource_or_decision_cap"
    elif case["diagnostics"].get("issues"):
        failure = "unsupported_state"
    elif recovered:
        failure = "diagnostic_recovery"
    else:
        failure = "unclassified_incomplete"
    return {
        "case_id": case["case_id"],
        "seed": case.get("seed"),
        "status": case["status"],
        "outcome": ("completed_victory" if gameplay.get("victory") is True else "completed_loss")
        if completed
        else "incomplete",
        "terminal_observed": gameplay.get("terminal") is True,
        "recovered": recovered,
        "decisions": gameplay.get("decisions", 0),
        "reached_floor": gameplay.get("maximum_floor", 0),
        "failure_kind": failure,
        "error": error,
    }


def discovery_summary(
    cases: list[dict[str, Any]], planned: int, *, include_outcomes: bool = False
) -> dict[str, Any]:
    issues: dict[str, dict[str, Any]] = {}
    clean = recovered = terminal = victories = 0
    for case in cases:
        clean += case["status"] == "natural_shipped_run_pass"
        terminal += case["gameplay"].get("terminal") is True
        recovered += bool(case["diagnostics"].get("recoveries"))
        victories += (
            case["status"] == "natural_shipped_run_pass" and case["gameplay"].get("victory") is True
        )
        for issue in case["diagnostics"].get("issues", []):
            key = issue["issue_id"]
            if key not in issues:
                issues[key] = {
                    k: issue[k] for k in ("issue_id", "kind", "context", "field", "reason")
                }
                issues[key].update(occurrences=0, affected_cases=[])
            issues[key]["occurrences"] += issue["occurrences"]
            issues[key]["affected_cases"].append(case["case_id"])
    result = {
        "benchmark_denominator": planned,
        "completed_cases": clean,
        "failed_cases": len(cases) - clean,
        "not_attempted_cases": planned - len(cases),
        "observed_terminal_runs": terminal,
        "recovered_cases": recovered,
        "clean_victories": victories,
        "issues": list(issues.values()),
        "unique_issues": len(issues),
    }
    if include_outcomes:
        outcomes = [case_outcome(case) for case in cases]
        failures: dict[str, int] = {}
        for outcome in outcomes:
            if outcome["failure_kind"] is not None:
                kind = outcome["failure_kind"]
                failures[kind] = failures.get(kind, 0) + 1
        result.update(case_outcomes=outcomes, failures_by_kind=failures)
    return result


def discover_runs(
    qualification: EngineQualificationConfig, path: Path, *, node: Path, preflight: bool = False
) -> dict[str, Any]:
    document, recipes = load_discovery_recipe(qualification, path)
    include_outcomes = document.get("reporting_revision") == "outcomes_v2"
    workspace = _private_path(qualification.root, document["workspace"])
    if workspace.exists() and not preflight:
        raise FileExistsError("Preserve the saved discovery batch; no automatic retry")
    checks = [
        compare_new_run(qualification, recipe, node=node, preflight=True) for recipe, _ in recipes
    ]
    if any(check["ready_for_diagnostic"] is not True for check in checks):
        raise ValueError(
            "Preserve existing discovery cases; all planned output paths must be fresh"
        )
    if preflight:
        return {
            "schema_version": "engine-run-discovery-preflight-v1",
            "config_id": manifest_identifier(document),
            "planned_cases": len(recipes),
            "ready_for_diagnostic": not workspace.exists(),
            "games_launched": 0,
            "training_allowed": False,
        }
    workspace.mkdir(parents=True)
    atomic_json(workspace / "in-progress.json", {"config_id": manifest_identifier(document)})
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": "engine-run-discovery-report-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "cases": [],
        "planned_cases": len(recipes),
        "training_allowed": False,
        "optimizer_steps": 0,
        "bulk_learning_admitted": False,
        "claim_scope": "finite_natural_A8_diagnostic_issue_collection_only",
    }
    try:
        for recipe_path, recipe in recipes:
            # Do not launch a new case unless its entire cap fits within the frozen batch cap.
            if (
                time.monotonic() - started + recipe["natural_run_limits"]["max_wall_seconds"] + 30
                > document["max_wall_seconds"]
            ):
                result["error"] = (
                    "Batch cap leaves insufficient time for the next complete case allowance"
                )
                break
            case: dict[str, Any] = {
                "case_id": Path(recipe["workspace"]).name,
                "seed": recipe["seed"],
                "recipe": str(recipe_path.relative_to(qualification.root)),
                "status": "infrastructure_failure",
                "gameplay": {},
                "diagnostics": {"issues": [], "recoveries": []},
                "verification": None,
                "games_launched": None,
                "full_run_attempts": None,
            }
            result["cases"].append(case)
            report = compare_new_run(qualification, recipe_path, node=node)
            case.update(
                report_id=report["report_id"],
                gameplay=report["gameplay"],
                diagnostics=report["diagnostics"],
                games_launched=report["games_launched"],
                full_run_attempts=report["full_run_attempts"],
            )
            # A sealed incomplete case is safe to move past only after its app/profile reset
            # and saved evidence verify. Infrastructure/integrity errors abort the batch.
            verification = verify_new_run(qualification, recipe_path, node=node)
            case.update(
                status=report["status"], verification=verification, error=verification.get("error")
            )
            summary = discovery_summary(
                result["cases"], len(recipes), include_outcomes=include_outcomes
            )
            if include_outcomes:
                outcome = case_outcome(case)
                print(
                    f"Case {case['case_id']}: {outcome['outcome']}; "
                    f"floor {outcome['reached_floor']}; {outcome['decisions']} actions; "
                    f"reason: {outcome['failure_kind'] or 'none'}"
                    f"{': ' + outcome['error'] if outcome['error'] else ''}.",
                    flush=True,
                )
            print(
                f"Discovery: {len(result['cases'])}/{len(recipes)} cases; "
                f"{summary['completed_cases']} clean endings; "
                f"{summary['failed_cases']} incomplete/recovered; "
                f"{summary['unique_issues']} distinct issues; best reached floor "
                f"{max(row['gameplay']['maximum_floor'] for row in result['cases'])}.",
                flush=True,
            )
            atomic_json(
                workspace / f"progress-{len(result['cases']):03d}.json", {**result, **summary}
            )
    except Exception as error:
        result["error"] = str(error)
        if result["cases"] and result["cases"][-1]["status"] == "infrastructure_failure":
            result["cases"][-1]["error"] = str(error)
    result.update(
        discovery_summary(result["cases"], len(recipes), include_outcomes=include_outcomes)
    )
    result.update(
        wall_seconds=time.monotonic() - started,
        games_launched=None
        if any(case["games_launched"] is None for case in result["cases"])
        else sum(case["games_launched"] for case in result["cases"]),
        full_run_attempts=None
        if any(case["full_run_attempts"] is None for case in result["cases"])
        else sum(case["full_run_attempts"] for case in result["cases"]),
        status="discovery_complete"
        if len(result["cases"]) == len(recipes) and "error" not in result
        else "discovery_incomplete",
    )
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "summary.json", result)
    return result


def verify_discovery_runs(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document, recipes = load_discovery_recipe(qualification, path)
    include_outcomes = document.get("reporting_revision") == "outcomes_v2"
    workspace = _private_path(qualification.root, document["workspace"])
    report = json.loads((workspace / "summary.json").read_text())
    if report["report_id"] != manifest_identifier(
        {k: v for k, v in report.items() if k != "report_id"}
    ) or report["config_id"] != manifest_identifier(document):
        raise ValueError("Saved discovery report changed")
    unverified = []
    for case, (recipe_path, recipe) in zip(report["cases"], recipes, strict=False):
        if case["status"] == "infrastructure_failure":
            if (
                case["verification"] is not None
                or report["status"] != "discovery_incomplete"
                or not case.get("error")
            ):
                raise ValueError("An infrastructure failure cannot be treated as a verified case")
            unverified.append(case["case_id"])
            continue
        verified = verify_new_run(qualification, recipe_path, node=node)
        child = json.loads(
            (_private_path(qualification.root, recipe["workspace"]) / "summary.json").read_text()
        )
        if (
            case["report_id"] != verified["report_id"]
            or case["seed"] != recipe["seed"]
            or case["verification"] != verified
            or case["gameplay"] != child["gameplay"]
            or case["diagnostics"] != child["diagnostics"]
            or case["status"] != child["status"]
            or (include_outcomes and case.get("error") != verified.get("error"))
        ):
            raise ValueError("Saved discovery case changed")
    expected = discovery_summary(report["cases"], len(recipes), include_outcomes=include_outcomes)
    if any(report[key] != value for key, value in expected.items()) or len(report["cases"]) > len(
        recipes
    ):
        raise ValueError("Saved discovery denominator or issue collection changed")
    return {
        "valid": not unverified,
        "unverified_cases": unverified,
        "report_id": report["report_id"],
        "status": report["status"],
        **expected,
        "games_replayed": 0,
        "training_allowed": False,
    }
