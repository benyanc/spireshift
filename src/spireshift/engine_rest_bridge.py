"""Finite rest/upgrade effect comparisons from explicit privileged save fixtures."""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import verify_checkpoint_input
from spireshift.engine_cli_probe import _probe_cli_document
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed, verify_journey_bridges
from spireshift.engine_native import _no_symlinks, _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json

SCENARIOS = {"tent-heal-cancel-smith", "tent-smith-cancel-heal"}


def verify_rest_tutorial_baseline(
    qualification: EngineQualificationConfig, baseline: dict[str, Any], connector_id: str
) -> None:
    """Bind the copied progress to the native profile that exposed the unsupported popup."""
    source = _hashed(_private_path(qualification.root, baseline["source_report"]))
    profile = Path(source["profile"])
    parent = Path.home() / "Library/Application Support/SpireShift/engine-profiles"
    _no_symlinks(profile)
    progress = _private_path(qualification.root, baseline["path"])
    original = profile / "default/1/modded/profile1/saves/progress.save"
    snapshot = source.get("probe", {}).get("latest_snapshot", {})
    if (
        baseline.get("scope")
        != "native_generated_rest_site_ftue_seen_only_not_other_tutorial_or_fresh_profile_control"
        or source["report_id"] != baseline["source_report_id"]
        or source.get("qualification_config_id") != qualification.config_id
        or source.get("config_id") != connector_id
        or profile.parent != parent
        or not profile.name.startswith(qualification.document["archive_name"] + "-checkpoint-")
        or snapshot.get("interaction", {}).get("kind") != "unsupported"
        or snapshot.get("interaction", {}).get("content", {}).get("context", {}).get("kind")
        != "rest"
        or any(
            source.get("checks", {}).get(key) is not True
            for key in (
                "loaded_identity",
                "profile_path_logged",
                "shared_profile_unchanged",
                "natural_shutdown",
            )
        )
        or _sha_file(original) != baseline["sha256"]
        or _sha_file(progress) != baseline["sha256"]
    ):
        raise ValueError("Rest tutorial baseline lacks unchanged native-profile provenance")
    body = json.loads(progress.read_text())
    if body.get("ftue_completed") != ["rest_site_ftue"] or body.get("enable_ftues") is not True:
        raise ValueError("Only the native rest tutorial may already be seen")


def compare_rest_bridge(
    qualification: EngineQualificationConfig,
    path: Path,
    *,
    node: Path,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = override if override is not None else json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-rest-bridge-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("stage") != "privileged_rest_save_public_action_differential_only"
        or document.get("training_allowed") is not False
        or document.get("scenario") not in SCENARIOS
        or not re.fullmatch(r"[A-Z0-9]{1,64}", str(document.get("seed", "")))
    ):
        raise ValueError("Expected one explicit finite A8 rest-save fixture comparison")
    prerequisite = verify_journey_bridges(
        qualification, qualification.root / document["journey_bridge_config"], node=node
    )
    if prerequisite["batch_report_id"] != document["journey_bridge_report_id"]:
        raise ValueError("Completed first-combat prerequisite changed")
    helpers = (
        "engine-rest-shipped-probe.mjs",
        "engine-rest-bridge-contract.mjs",
        "engine-journey-contract-v2.mjs",
        "engine-menu-probe.mjs",
    )
    if set(document.get("helpers_sha256", {})) != set(helpers):
        raise ValueError("The complete frozen rest helper inventory is required")
    for name, expected in document["helpers_sha256"].items():
        if Path(name).name != name or _sha_file(qualification.root / "scripts" / name) != expected:
            raise ValueError("Pinned shipped rest comparison helper changed")
    if "rest_tutorial_baseline" in document:
        verify_rest_tutorial_baseline(
            qualification, document["rest_tutorial_baseline"], document["connector_config_id"]
        )
    native_path = qualification.root / document["native_config"]
    native_config = json.loads(native_path.read_text())
    if (
        native_path.resolve().parent != path.resolve().parent
        or manifest_identifier(native_config) != document["native_config_id"]
    ):
        raise ValueError("Pinned native rest fixture configuration changed")
    workspace = _private_path(qualification.root, document["workspace"])
    if (workspace / "comparison.json").exists() or (workspace / "native-report.json").exists():
        raise FileExistsError("Preserve the existing rest comparison; no automatic restart")
    native_config = copy.deepcopy(native_config)
    native_config.update(
        seed=document["seed"],
        workspace=str((workspace / "native").relative_to(qualification.root)),
        rest_bridge={"scenario": document["scenario"]},
    )
    atomic_json(workspace / "native-config.json", native_config)
    native = _probe_cli_document(
        qualification, native_path, node, native_config, panel="rest_bridge"
    )
    native_report = workspace / "native-report.json"
    atomic_json(native_report, native)
    result: dict[str, Any] = {
        "schema_version": "engine-rest-bridge-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "seed": document["seed"],
        "scenario": document["scenario"],
        "native_report": str(native_report.relative_to(qualification.root)),
        "native_report_id": native["report_id"],
        "status": "rest_comparison_incomplete",
        "privileged_fixture": True,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": (
            "privileged_A8_single_card_Miniature_Tent_heal_smith_cancel_confirm_"
            "and_proceed_public_effects_only"
        ),
    }
    if native["status"] != "rest_bridge_public_projection_regression_pass":
        result["error"] = native.get("probe", {}).get("error", "Native rest fixture failed")
    else:
        snapshot = Path(native["report_path"]).parent / "private-starting-snapshot.json"
        bound = {
            "checkpoint_report": result["native_report"],
            "checkpoint_report_id": native["report_id"],
            "snapshot_sha256": _sha_file(snapshot),
            "seed": document["seed"],
        }
        fixture = verify_checkpoint_input(qualification, bound, panel="rest_bridge")
        fixture.update(
            comparison_mode="rest_bridge_v1",
            rest_report_path=str(native_report),
            workspace=str((workspace / "shipped").relative_to(qualification.root)),
        )
        if "rest_tutorial_baseline" in document:
            fixture["rest_tutorial_baseline"] = document["rest_tutorial_baseline"]
        connector_path = qualification.root / document["connector_config"]
        if connector_path.resolve().parent != path.resolve().parent:
            raise ValueError("The pinned Connector configuration must remain beside this config")
        connector = load_connector_qualification_config(connector_path, qualification)
        if connector.config_id != document["connector_config_id"]:
            raise ValueError("Pinned shipped Host prerequisite changed")
        shipped = _probe_connector_private(
            connector, node=node, fixture=fixture, retain_working_game=False
        )
        verify_checkpoint_input(qualification, bound, panel="rest_bridge")
        if json.loads(native_report.read_text()) != native:
            raise ValueError("Native rest plan changed during the shipped comparison")
        shipped_path = workspace / "shipped-report.json"
        atomic_json(shipped_path, shipped)
        passed = shipped["verdict"]["status"] == "shipped_checkpoint_input_pass"
        result.update(
            status="rest_action_comparison_pass" if passed else "rest_comparison_incomplete",
            shipped_report=str(shipped_path.relative_to(qualification.root)),
            shipped_report_id=shipped["report_id"],
            public_actions_delivered=shipped["probe"].get("public_actions_requested")
            if passed
            else None,
            semantic_actions_delivered=shipped["probe"].get("semantic_actions_delivered")
            if passed
            else None,
            upgrade_ui_steps=len(shipped["probe"].get("upgrade_ui_steps", [])),
            compared_snapshots=len(shipped["probe"].get("comparisons", [])),
            first_difference=shipped["probe"].get("first_difference"),
            error=shipped["probe"].get("error"),
            native_public_prefix_id=manifest_identifier(native["probe"]["journey"]),
            disposable_payload_removed_after_verified_success=shipped[
                "disposable_payload_removed_after_verified_success"
            ],
        )
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "comparison.json", result)
    return result


def validate_rest_cases(document: dict[str, Any]) -> list[dict[str, str]]:
    rows = document.get("cases")
    if (
        not isinstance(rows, list)
        or len(rows) != 8
        or any(
            not isinstance(row, dict)
            or not re.fullmatch(r"[a-z0-9-]{1,64}", str(row.get("case_id", "")))
            or not re.fullmatch(r"[A-Z0-9]{1,64}", str(row.get("seed", "")))
            or row.get("scenario") not in SCENARIOS
            for row in rows
        )
    ):
        raise ValueError("Expected eight named rest cases from the two frozen sequences")
    pairs = {(row["seed"], row["scenario"]) for row in rows}
    if (
        len({row["case_id"] for row in rows}) != 8
        or len({row["seed"] for row in rows}) != 2
        or len(pairs) != 4
        or any(sum((row["seed"], row["scenario"]) == pair for row in rows) != 2 for pair in pairs)
    ):
        raise ValueError("Two independent seeds, two sequences, twice each are required")
    return [{key: row[key] for key in ("case_id", "seed", "scenario")} for row in rows]


def compare_rest_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-rest-bridges-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
    ):
        raise ValueError("Expected the finite owner rest comparison batch")
    cases = validate_rest_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
    ):
        raise ValueError("Frozen rest comparison template changed")
    workspace = _private_path(qualification.root, document["workspace"])
    marker, output = workspace / "in-progress.json", workspace / "batch.json"
    if marker.exists() or output.exists():
        raise FileExistsError("Preserve this batch; no automatic restart or overwrite")
    result: dict[str, Any] = {
        "schema_version": "engine-rest-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "status": "in_progress",
        "cases": [],
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 8,
        "planned_cases": 8,
        "independent_seeds": 2,
        "seed_scenario_pairs": 4,
        "privileged_fixture": True,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "repeated_privileged_single_card_rest_fixture_public_action_effects_only",
    }
    atomic_json(marker, result)
    started = time.monotonic()
    active = None
    try:
        for i, case in enumerate(cases):
            if (
                time.monotonic() - started > 650
                or shutil.disk_usage(workspace).free < 3_500_000_000
            ):
                raise ValueError(
                    "Insufficient remaining time or disk space for another disposable host"
                )
            active = case
            result["not_attempted_cases"] -= 1
            print(
                f"Rest comparison {i + 1}/8 ({case['case_id']}); six public actions, one host.",
                flush=True,
            )
            effective = copy.deepcopy(template)
            effective.update(
                seed=case["seed"],
                scenario=case["scenario"],
                workspace=str((workspace / case["case_id"]).relative_to(qualification.root)),
            )
            atomic_json(workspace / case["case_id"] / "config.json", effective)
            comparison = compare_rest_bridge(
                qualification, template_path, node=node, override=effective
            )
            result["cases"].append(
                {
                    **case,
                    "report": str(
                        (workspace / case["case_id"] / "comparison.json").relative_to(
                            qualification.root
                        )
                    ),
                    **comparison,
                }
            )
            if comparison["status"] != "rest_action_comparison_pass":
                raise ValueError("First rest divergence retained; no next case follows")
            result["completed_cases"] += 1
            active = None
            atomic_json(workspace / "progress" / f"comparison-{i + 1:03d}.json", result)
            print(f"Rest comparison {i + 1}/8 passed and saved.", flush=True)
        pairs: dict[tuple[str, str], list[str]] = {
            (row["seed"], row["scenario"]): [] for row in result["cases"]
        }
        for row in result["cases"]:
            pairs[(row["seed"], row["scenario"])].append(row["native_public_prefix_id"])
        result["repeated_public_prefixes_identical"] = all(
            values[0] == values[1] for values in pairs.values()
        )
        if not result["repeated_public_prefixes_identical"]:
            raise ValueError("Repeated rest fixture prefix changed")
        result["status"] = "rest_comparisons_pass"
    except (OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        result.update(status="rest_comparisons_incomplete", error=str(error) or "interrupted")
        if active is not None:
            result["failed_cases"] += 1
            result["failed_case"] = active
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(output, result)
    marker.unlink()
    return result
