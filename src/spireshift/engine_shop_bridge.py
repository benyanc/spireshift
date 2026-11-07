"""Finite native/shipped shop comparisons, explicitly privileged and never training."""

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
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_rest_verification import verify_rest_bridges
from spireshift.full_run_experience import atomic_json

SCENARIOS = {"ordinary-purchases-removal", "courier-restock-removal"}
HELPERS = {
    "engine-shop-shipped-probe-v1.mjs",
    "engine-shop-bridge-contract.mjs",
    "engine-rest-bridge-contract.mjs",
    "engine-journey-contract-v2.mjs",
    "engine-menu-probe.mjs",
}


def validate_shop_template(
    qualification: EngineQualificationConfig, path: Path, document: dict[str, Any]
) -> tuple[dict[str, Any], Path]:
    if (
        document.get("schema_version") != "engine-shop-bridge-config-v1"
        or document.get("stage") != "privileged_shop_save_public_action_differential_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("scenario") not in SCENARIOS
        or document.get("comparison_scope")
        != "current_stock_prices_legal_menu_card_potion_purchases_removal_cancel_confirm_and_exit"
        or not re.fullmatch(r"[A-Z0-9]{1,64}", str(document.get("seed", "")))
        or set(document.get("helpers_sha256", {})) != HELPERS
        or "rest_tutorial_baseline" in document
    ):
        raise ValueError("Expected one explicit finite A8 shop-save comparison")
    for name in HELPERS:
        if _sha_file(qualification.root / "scripts" / name) != document["helpers_sha256"][name]:
            raise ValueError("Pinned shop comparison helper changed")
    native_path = qualification.root / document["native_config"]
    native = json.loads(native_path.read_text())
    if (
        native_path.resolve().parent != path.resolve().parent
        or manifest_identifier(native) != document["native_config_id"]
    ):
        raise ValueError("Pinned native shop fixture configuration changed")
    return native, native_path


def compare_shop_bridge(
    qualification: EngineQualificationConfig,
    path: Path,
    *,
    node: Path,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = override if override is not None else json.loads(path.read_text())
    native_config, native_path = validate_shop_template(qualification, path, document)
    prerequisite = verify_rest_bridges(
        qualification, qualification.root / document["rest_bridge_config"], node=node
    )
    if prerequisite["batch_report_id"] != document["rest_bridge_report_id"]:
        raise ValueError("Completed fresh-rest prerequisite changed")
    connector_path = qualification.root / document["connector_config"]
    if connector_path.resolve().parent != path.resolve().parent:
        raise ValueError("Pinned Connector configuration must remain beside this config")
    connector = load_connector_qualification_config(connector_path, qualification)
    if connector.config_id != document["connector_config_id"]:
        raise ValueError("Pinned shipped Host prerequisite changed")
    workspace = _private_path(qualification.root, document["workspace"])
    if any(
        (workspace / name).exists()
        for name in ("comparison.json", "native-report.json", "native-config.json")
    ):
        raise FileExistsError("Preserve the existing shop comparison; no automatic restart")
    native_config = copy.deepcopy(native_config)
    native_config.update(
        seed=document["seed"],
        workspace=str((workspace / "native").relative_to(qualification.root)),
        shop_bridge={"scenario": document["scenario"]},
    )
    atomic_json(workspace / "native-config.json", native_config)
    native = _probe_cli_document(
        qualification, native_path, node, native_config, panel="shop_bridge"
    )
    native_report = workspace / "native-report.json"
    atomic_json(native_report, native)
    result: dict[str, Any] = {
        "schema_version": "engine-shop-bridge-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "seed": document["seed"],
        "scenario": document["scenario"],
        "native_report": str(native_report.relative_to(qualification.root)),
        "native_report_id": native["report_id"],
        "status": "shop_comparison_incomplete",
        "privileged_fixture": True,
        "fresh_profile_required": True,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "privileged_A8_shop_stock_prices_card_potion_purchase_removal_and_exit_only",
    }
    if native["status"] != "shop_bridge_public_projection_regression_pass":
        result["error"] = native.get("probe", {}).get("error", "Native shop fixture failed")
    else:
        snapshot = Path(native["report_path"]).parent / "private-starting-snapshot.json"
        bound = {
            "checkpoint_report": result["native_report"],
            "checkpoint_report_id": native["report_id"],
            "snapshot_sha256": _sha_file(snapshot),
            "seed": document["seed"],
        }
        fixture = verify_checkpoint_input(qualification, bound, panel="shop_bridge")
        fixture.update(
            comparison_mode="shop_bridge_v1",
            scenario=document["scenario"],
            shop_report_path=str(native_report),
            workspace=str((workspace / "shipped").relative_to(qualification.root)),
        )
        shipped = _probe_connector_private(
            connector, node=node, fixture=fixture, retain_working_game=False
        )
        verify_checkpoint_input(qualification, bound, panel="shop_bridge")
        if json.loads(native_report.read_text()) != native:
            raise ValueError("Native shop plan changed during the shipped comparison")
        shipped_path = workspace / "shipped-report.json"
        atomic_json(shipped_path, shipped)
        passed = shipped["verdict"]["status"] == "shipped_checkpoint_input_pass"
        result.update(
            status="shop_action_comparison_pass" if passed else "shop_comparison_incomplete",
            shipped_report=str(shipped_path.relative_to(qualification.root)),
            shipped_report_id=shipped["report_id"],
            public_actions_delivered=shipped["probe"].get("public_actions_requested")
            if passed
            else None,
            semantic_actions_delivered=shipped["probe"].get("semantic_actions_delivered")
            if passed
            else None,
            shop_ui_steps=len(shipped["probe"].get("shop_ui_steps", [])),
            potion_tutorial_steps=len(shipped["probe"].get("potion_tutorial_steps", [])),
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


def validate_shop_cases(document: dict[str, Any]) -> list[dict[str, str]]:
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
        raise ValueError("Expected eight named shop cases from two frozen scenarios")
    pairs = {(row["seed"], row["scenario"]) for row in rows}
    if (
        len({row["case_id"] for row in rows}) != 8
        or len({row["seed"] for row in rows}) != 2
        or len(pairs) != 4
        or any(sum((row["seed"], row["scenario"]) == pair for row in rows) != 2 for pair in pairs)
    ):
        raise ValueError("Two independent seeds, two shop scenarios, twice each are required")
    return [{key: row[key] for key in ("case_id", "seed", "scenario")} for row in rows]


def compare_shop_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-shop-bridges-config-v1"
        or document.get("stage") != "owner_privileged_shop_fixture_differentials_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
    ):
        raise ValueError("Expected the finite owner shop comparison batch")
    cases = validate_shop_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
    ):
        raise ValueError("Frozen shop comparison template changed")
    validate_shop_template(qualification, template_path, template)
    workspace = _private_path(qualification.root, document["workspace"])
    marker, output = workspace / "in-progress.json", workspace / "batch.json"
    if marker.exists() or output.exists():
        raise FileExistsError("Preserve this batch; no automatic restart or overwrite")
    result: dict[str, Any] = {
        "schema_version": "engine-shop-bridges-v1",
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
        "fresh_profile_required": True,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "repeated_privileged_shop_stock_prices_purchase_removal_and_exit_only",
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
                raise ValueError("Insufficient remaining time or disk for another disposable host")
            active = case["case_id"]
            effective = copy.deepcopy(template)
            directory = workspace / active
            effective.update(
                seed=case["seed"],
                scenario=case["scenario"],
                workspace=str(directory.relative_to(qualification.root)),
            )
            atomic_json(directory / "config.json", effective)
            print(f"Shop comparison {i + 1}/8: {active}; one isolated host.", flush=True)
            comparison = compare_shop_bridge(
                qualification, template_path, node=node, override=effective
            )
            row = {
                "case_id": active,
                "report": str((directory / "comparison.json").relative_to(qualification.root)),
                **comparison,
            }
            result["cases"].append(row)
            result["not_attempted_cases"] -= 1
            if comparison["status"] != "shop_action_comparison_pass":
                result["failed_cases"] += 1
                raise ValueError(f"Shop comparison failed at {active}; preserve its evidence")
            result["completed_cases"] += 1
            active = None
            atomic_json(workspace / "progress" / f"comparison-{i + 1:03d}.json", result)
            print(
                f"Passed {case['case_id']}: {comparison['compared_snapshots']} observations, "
                f"{comparison['semantic_actions_delivered']} decisions.",
                flush=True,
            )
        prefixes: dict[tuple[str, str], list[str]] = {}
        for row in result["cases"]:
            prefixes.setdefault((row["seed"], row["scenario"]), []).append(
                row["native_public_prefix_id"]
            )
        result["repeated_public_prefixes_identical"] = all(
            len(set(values)) == 1 for values in prefixes.values()
        )
        if result["repeated_public_prefixes_identical"] is not True:
            raise ValueError("Repeated native shop prefixes differ")
        result["status"] = "shop_comparisons_pass"
    except (ValueError, OSError, KeyError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        if active is not None and not any(row["case_id"] == active for row in result["cases"]):
            result["failed_cases"] += 1
            result["not_attempted_cases"] -= 1
        result.update(
            status="shop_comparisons_incomplete",
            failed_case=active,
            error=str(error) or "interrupted",
        )
    result["wall_seconds"] = time.monotonic() - started
    result["potion_tutorial_steps"] = sum(
        row.get("potion_tutorial_steps", 0) for row in result["cases"]
    )
    result["report_id"] = manifest_identifier(result)
    atomic_json(output, result)
    return result
