"""Finite natural Scroll Boxes native/shipped comparisons; never learning admission."""

from __future__ import annotations

import copy
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_bundle_verification import verify_bundle_saved
from spireshift.engine_checkpoint import verify_checkpoint_input
from spireshift.engine_cli_probe import _probe_cli_document
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.full_run_experience import atomic_json

HELPERS = {
    "engine-bundle-shipped-probe-v3.mjs",
    "engine-bundle-bridge-contract-v3.mjs",
    "engine-rest-bridge-contract.mjs",
    "engine-journey-contract-v2.mjs",
    "engine-menu-probe.mjs",
    "engine-checkpoint-shipped-probe.mjs",
    "verify-engine-bundle-saved-v1.mjs",
}


def compare_bundle_bridge(
    qualification: EngineQualificationConfig,
    path: Path,
    *,
    node: Path,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = override if override is not None else json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-bundle-bridge-config-v1"
        or document.get("stage") != "natural_Neow_bundle_choice_differential_only"
        or document.get("bridge_revision") != "v3"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or type(document.get("index")) is not int
        or document["index"] not in {0, 1}
        or not re.fullmatch(r"[A-Z0-9]{1,64}", str(document.get("seed", "")))
        or set(document.get("helpers_sha256", {})) != HELPERS
    ):
        raise ValueError("Expected one explicitly seeded A8 natural bundle comparison")
    for name in HELPERS:
        if _sha_file(qualification.root / "scripts" / name) != document["helpers_sha256"][name]:
            raise ValueError("Pinned bundle comparison helper changed")
    native_path = qualification.root / document["native_config"]
    native_config = json.loads(native_path.read_text())
    if (
        native_path.resolve().parent != path.resolve().parent
        or manifest_identifier(native_config) != document["native_config_id"]
    ):
        raise ValueError("Bundle native template changed")
    connector_path = qualification.root / document["connector_config"]
    if connector_path.resolve().parent != path.resolve().parent:
        raise ValueError("Bundle Connector prerequisite must be beside its config")
    connector = load_connector_qualification_config(connector_path, qualification)
    if connector.config_id != document["connector_config_id"]:
        raise ValueError("Bundle shipped Host prerequisite changed")
    workspace = _private_path(qualification.root, document["workspace"])
    if workspace.exists():
        raise FileExistsError("Preserve this comparison; use a new versioned workspace")
    workspace.mkdir(parents=True)
    native_config = copy.deepcopy(native_config)
    native_config.update(
        seed=document["seed"],
        bundle_bridge={"index": document["index"]},
        workspace=str((workspace / "native").relative_to(qualification.root)),
    )
    atomic_json(workspace / "native-config.json", native_config)
    native = _probe_cli_document(
        qualification, native_path, node, native_config, panel="bundle_bridge"
    )
    native_report = workspace / "native-report.json"
    atomic_json(native_report, native)
    result = {
        "schema_version": "engine-bundle-bridge-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "seed": document["seed"],
        "index": document["index"],
        "native_report": str(native_report.relative_to(qualification.root)),
        "native_report_id": native["report_id"],
        "status": "bundle_comparison_incomplete",
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": (
            "natural_imported_Neow_Scroll_Boxes_visible_pack_identity_cost_upgrade_"
            "and_deck_award_only"
        ),
    }
    try:
        if native["status"] != "bundle_bridge_public_projection_regression_pass":
            raise ValueError("Native bundle prefix failed; no shipped launch follows")
        snapshot = Path(native["report_path"]).parent / "private-starting-snapshot.json"
        bound = {
            "checkpoint_report": str(native_report.relative_to(qualification.root)),
            "checkpoint_report_id": native["report_id"],
            "seed": document["seed"],
            "snapshot_sha256": _sha_file(snapshot),
        }
        fixture = verify_checkpoint_input(qualification, bound, panel="bundle_bridge")
        fixture.update(
            workspace=str((workspace / "shipped").relative_to(qualification.root)),
            bundle_report_path=str(native_report),
            comparison_mode="bundle_bridge_v3",
        )
        shipped = _probe_connector_private(
            connector, node=node, fixture=fixture, retain_working_game=False
        )
        atomic_json(workspace / "shipped-report.json", shipped)
        result.update(
            shipped_report=str((workspace / "shipped-report.json").relative_to(qualification.root)),
            shipped_report_id=shipped["report_id"],
            disposable_payload_removed_after_verified_success=shipped[
                "disposable_payload_removed_after_verified_success"
            ],
        )
        if shipped["verdict"]["status"] != "shipped_checkpoint_input_pass":
            raise ValueError("Shipped bundle comparison failed; evidence preserved")
        result["status"] = "bundle_action_comparison_pass"
        result["saved_verification"] = verify_bundle_saved(qualification, result, node=node)
    except (ValueError, OSError, RuntimeError) as error:
        result["status"] = "bundle_comparison_incomplete"
        result["error"] = str(error)
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "comparison.json", result)
    return result


def validate_bundle_cases(document: dict[str, Any]) -> list[dict[str, Any]]:
    cases = document.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 8
        or any(not isinstance(case, dict) for case in cases)
        or any(
            not isinstance(case.get("case_id"), str)
            or not re.fullmatch(r"[a-z0-9-]{1,48}", case["case_id"])
            or not isinstance(case.get("seed"), str)
            or not re.fullmatch(r"[A-Z0-9]{1,64}", case["seed"])
            or type(case.get("index")) is not int
            or case["index"] not in {0, 1}
            for case in cases
        )
        or len({case["case_id"] for case in cases}) != 8
    ):
        raise ValueError("Expected eight unique named seed/pack comparison cases")
    pairs = {(case["seed"], case["index"]) for case in cases}
    if (
        len({case["seed"] for case in cases}) != 2
        or len(pairs) != 4
        or any(sum((case["seed"], case["index"]) == pair for case in cases) != 2 for pair in pairs)
    ):
        raise ValueError("Use two seeds, both packs, and two repeats of every seed/pack pair")
    return [{key: case[key] for key in ("case_id", "seed", "index")} for case in cases]


def compare_bundle_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-bundle-bridges-config-v1"
        or document.get("stage") != "owner_repeated_natural_bundle_differentials_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
    ):
        raise ValueError("Expected a finite owner bundle comparison batch")
    cases = validate_bundle_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
    ):
        raise ValueError("Bundle comparison template changed")
    workspace = _private_path(qualification.root, document["workspace"])
    if workspace.exists():
        raise FileExistsError("Preserve this batch; no automatic resume")
    workspace.mkdir(parents=True)
    result: dict[str, Any] = {
        "schema_version": "engine-bundle-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "status": "in_progress",
        "cases": [],
        "planned_cases": 8,
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 8,
        "independent_seeds": 2,
        "seed_pack_pairs": 4,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "repeated_natural_Neow_Scroll_Boxes_pack_preview_and_award_only",
    }
    atomic_json(workspace / "in-progress.json", result)
    started = time.monotonic()
    active = None
    try:
        for number, case in enumerate(cases, 1):
            if time.monotonic() - started > document["max_wall_seconds"] - 250:
                raise TimeoutError("Bundle batch reached its finite launch allowance")
            if shutil.disk_usage(workspace).free < 3_500_000_000:
                raise ValueError("Allow 3.5 GB free before the next disposable game copy")
            active = case
            result["not_attempted_cases"] -= 1
            print(
                f"Bundle comparison {number}/8: {case['case_id']}; one disposable A8 game.",
                flush=True,
            )
            config = copy.deepcopy(template)
            config.update(
                seed=case["seed"],
                index=case["index"],
                workspace=str((workspace / case["case_id"]).relative_to(qualification.root)),
            )
            atomic_json(workspace / f"case-{number:02d}-config.json", config)
            comparison = compare_bundle_bridge(
                qualification, template_path, node=node, override=config
            )
            result["cases"].append({**case, "comparison": comparison})
            if comparison["status"] != "bundle_action_comparison_pass":
                raise ValueError("Bundle comparison failed; no next case follows")
            result["completed_cases"] += 1
            active = None
            atomic_json(workspace / f"progress-{number:02d}.json", result)
        prefixes: dict[tuple[str, int], list[Any]] = {}
        for case in result["cases"]:
            shipped = json.loads(
                (qualification.root / case["comparison"]["shipped_report"]).read_text()
            )
            prefixes.setdefault((case["seed"], case["index"]), []).append(
                [row["facts"] for row in shipped["probe"]["comparisons"]]
            )
        if any(values[0] != values[1] for values in prefixes.values()):
            raise ValueError("Repeated bundle public prefix changed")
        result.update(status="bundle_comparisons_pass", repeated_public_prefixes_identical=True)
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        result.update(status="bundle_comparisons_incomplete", error=str(error))
        if active is not None:
            result["failed_cases"] += 1
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "batch.json", result)
    (workspace / "in-progress.json").unlink()
    return result


def verify_bundle_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    """Reconstruct a saved eight-case batch; never launch or resume a game."""
    document = json.loads(path.read_text())
    planned = validate_bundle_cases(document)
    if (
        document.get("schema_version") != "engine-bundle-bridges-config-v1"
        or document.get("stage") != "owner_repeated_natural_bundle_differentials_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
    ):
        raise ValueError("Expected the frozen scoped bundle batch configuration")
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
        or set(template.get("helpers_sha256", {})) != HELPERS
        or any(
            _sha_file(qualification.root / "scripts" / name) != template["helpers_sha256"][name]
            for name in HELPERS
        )
    ):
        raise ValueError("Frozen bundle batch template/helper changed")
    workspace = _private_path(qualification.root, document["workspace"])
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("qualification_config_id") != qualification.config_id
        or batch.get("status") != "bundle_comparisons_pass"
        or batch.get("completed_cases") != 8
        or batch.get("planned_cases") != 8
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("repeated_public_prefixes_identical") is not True
        or batch.get("full_run_attempts") != 0
        or batch.get("optimizer_steps") != 0
        or batch.get("training_allowed") is not False
        or [{k: c.get(k) for k in ("case_id", "seed", "index")} for c in batch["cases"]] != planned
    ):
        raise ValueError("Expected the complete frozen eight-case bundle batch")
    verified = []
    prefixes: dict[tuple[str, int], list[Any]] = {}
    for case in batch["cases"]:
        directory = workspace / case["case_id"]
        comparison = _hashed(directory / "comparison.json")
        effective = copy.deepcopy(template)
        effective.update(
            seed=case["seed"],
            index=case["index"],
            workspace=str(directory.relative_to(qualification.root)),
        )
        if (
            comparison != case["comparison"]
            or comparison.get("config_id") != manifest_identifier(effective)
            or comparison.get("native_report")
            != str((directory / "native-report.json").relative_to(qualification.root))
            or comparison.get("shipped_report")
            != str((directory / "shipped-report.json").relative_to(qualification.root))
            or comparison.get("disposable_payload_removed_after_verified_success") is not True
        ):
            raise ValueError("Saved bundle case/config binding changed")
        verification = verify_bundle_saved(qualification, comparison, node=node)
        if verification != comparison.get("saved_verification"):
            raise ValueError("Saved bundle reconstruction differs from its recorded audit")
        verified.append(verification)
        shipped = _hashed(qualification.root / comparison["shipped_report"])
        prefixes.setdefault((case["seed"], case["index"]), []).append(
            [row["facts"] for row in shipped["probe"]["comparisons"]]
        )
    if any(len(rows) != 2 or rows[0] != rows[1] for rows in prefixes.values()):
        raise ValueError("Repeated saved bundle facts differ")
    result = {
        "schema_version": "engine-bundle-batch-saved-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "verified_cases": len(verified),
        "independent_seeds": 2,
        **{
            key: sum(row[key] for row in verified)
            for key in (
                "observations",
                "effect_decisions",
                "public_game_ui_actions",
                "preview_steps",
            )
        },
        "case_verification_ids": [row["report_id"] for row in verified],
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "claim_scope": "saved_eight_case_bundle_raw_public_evidence_only",
    }
    result["report_id"] = manifest_identifier(result)
    return result
