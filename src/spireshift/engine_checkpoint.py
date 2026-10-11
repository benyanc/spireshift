"""A single bounded shipped-host check from a verified native A8 starting save."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_native import _private_path
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file


def _saved_private_path(qualification: EngineQualificationConfig, value: str) -> Path:
    path = Path(value)
    relative = path.relative_to(qualification.root) if path.is_absolute() else path
    return _private_path(qualification.root, str(relative))


def verify_checkpoint_input(
    qualification: EngineQualificationConfig, document: dict[str, Any], *, panel: str = "checkpoint"
) -> dict[str, Any]:
    if panel not in {"checkpoint", "journey"}:
        raise ValueError("Unknown native checkpoint qualification scope")
    report = json.loads(
        _private_path(qualification.root, document["checkpoint_report"]).read_text()
    )
    body = {key: value for key, value in report.items() if key not in {"report_id", "report_path"}}
    probe = report.get("probe", {})
    checkpoint = probe.get("checkpoint", {})
    checks = report.get("checks", {})
    required_checks = (
        "frozen_archive_unchanged",
        f"native_{panel}_regressions_pass",
        "pinned_managed_runtime_unchanged",
        "pinned_sdk_tree_unchanged",
        "projection_identity_bound",
        "same_private_candidate_unchanged",
        "shared_profile_unchanged",
        "uncapped_successful_process",
    )
    if (
        manifest_identifier(body) != report.get("report_id")
        or report.get("schema_version") != f"engine-cli-{panel}-projection-probe-v1"
        or report.get("report_id") != document.get("checkpoint_report_id")
        or report.get("qualification_config_id") != qualification.config_id
        or report.get("status") != f"{panel}_public_projection_regression_pass"
        or any(checks.get(key) is not True for key in required_checks)
        or not all(value is True for value in checks.values())
        or report.get("training_allowed") is not False
        or checkpoint.get("ascension") != 8
        or checkpoint.get("content_policy") != "native_all_unlocked"
        or checkpoint.get("seed") != document.get("seed")
    ):
        raise ValueError("An exact completed native A8 checkpoint qualification is required")
    file = _saved_private_path(qualification, checkpoint["path"])
    attempt = _saved_private_path(qualification, report["report_path"]).parent
    snapshot = _saved_private_path(qualification, str(attempt / "private-starting-snapshot.json"))
    if (
        file.parent != attempt
        or _sha_file(file) != checkpoint["sha256"]
        or _sha_file(snapshot) != document.get("snapshot_sha256")
    ):
        raise ValueError("The bound native checkpoint or public snapshot changed")
    return {
        "checkpoint_path": str(file),
        "checkpoint_sha256": checkpoint["sha256"],
        "snapshot_path": str(snapshot),
        "seed": checkpoint["seed"],
    }


def probe_shipped_checkpoint(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    return _probe_shipped_checkpoint_document(
        qualification, path, json.loads(path.read_text()), node=node
    )


def _probe_shipped_checkpoint_document(
    qualification: EngineQualificationConfig,
    path: Path,
    document: dict[str, Any],
    *,
    node: Path,
) -> dict[str, Any]:
    if (
        document.get("schema_version") != "engine-shipped-checkpoint-config-v1"
        or document.get("stage") != "single_native_A8_checkpoint_public_input_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("comparison_scope")
        != "starting_option_titles_and_availability_only_not_complete_semantic_parity"
    ):
        raise ValueError("Expected a scoped single-checkpoint configuration; no training admission")
    payload_policy = document.get("successful_payload_policy", "retain")
    if payload_policy not in {"retain", "remove_after_verified_success"}:
        raise ValueError("Unknown disposable checkpoint payload policy")
    for name in ("engine-checkpoint-shipped-probe.mjs", "engine-menu-probe.mjs"):
        if _sha_file(qualification.root / "scripts" / name) != document["helpers_sha256"].get(name):
            raise ValueError("A pinned shipped checkpoint helper changed")
    fixture = verify_checkpoint_input(qualification, document)
    if "workspace" in document:
        workspace = _private_path(qualification.root, document["workspace"])
        fixture["workspace"] = str(workspace.relative_to(qualification.root))
    connector_path = qualification.root / document["connector_config"]
    if connector_path.resolve().parent != path.resolve().parent:
        raise ValueError("The exact Connector prerequisite must be beside the checkpoint config")
    connector = load_connector_qualification_config(connector_path, qualification)
    if connector.config_id != document.get("connector_config_id"):
        raise ValueError("The pinned Connector prerequisite changed")
    # Preserve the original menu/toolchain identity; fixture identity is separately recorded.
    result = _probe_connector_private(
        connector,
        node=node,
        fixture=fixture,
        retain_working_game=payload_policy == "retain",
    )
    verify_checkpoint_input(qualification, document)
    private_report_path = result["report_path"]
    result = {
        key: value for key, value in result.items() if key not in {"report_id", "report_path"}
    }
    result["checkpoint_config_id"] = manifest_identifier(document)
    result["checkpoint_report_id"] = document["checkpoint_report_id"]
    result["checkpoint_sha256"] = fixture["checkpoint_sha256"]
    result["private_shipped_report_path"] = private_report_path
    result["shipped_cross_host_parity"] = False
    result["report_id"] = manifest_identifier(result)
    return result
