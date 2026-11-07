"""A small privileged act/ending comparison, reusing the fixed shipped app."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_profile import verify_benchmark_progress
from spireshift.engine_progression import progression_inputs, verify_native_progression
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_startup import _script_closure
from spireshift.engine_working_app import (
    load_working_app_policy,
    preflight_working_app,
    verify_working_app_receipt,
)
from spireshift.full_run_experience import atomic_json


def bridge_inputs(qualification: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    revision = document.get("probe_revision", "v1")
    verifier_revision = document.get("saved_verifier_revision", revision)
    helpers = _script_closure(
        qualification.root / "scripts",
        {
            f"engine-progression-shipped-probe-{revision}.mjs",
            f"verify-engine-progression-saved-{verifier_revision}.mjs",
        },
    )
    if (
        document.get("schema_version") != "engine-progression-bridges-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("stage") != "privileged_shipped_act_and_ending_only"
        or document.get("privileged_fixture") is not True
        or document.get("training_allowed") is not False
        or document.get("acts") not in ([3], [1, 2], [1, 2, 3])
        or revision not in {"v1", "v2", "v3", "v4", "v5"}
        or verifier_revision not in {"v1", "v2", "v3", "v4"}
        or set(document.get("helpers_sha256", {})) != helpers
        or any(
            _sha_file(qualification.root / "scripts" / name) != digest
            for name, digest in document["helpers_sha256"].items()
        )
    ):
        raise ValueError("Expected a separate pinned one- or three-case progression fixture recipe")
    native_path = qualification.root / document["native_config"]
    native = progression_inputs(qualification, native_path)
    verified = verify_native_progression(qualification, native_path)
    if (
        manifest_identifier(native["document"]) != document["native_config_id"]
        or verified["native_report_id"] != document["native_report_id"]
    ):
        raise ValueError("Native progression fixture prerequisite changed")
    connector = load_connector_qualification_config(
        qualification.root / document["connector_config"], qualification
    )
    policy = load_working_app_policy(
        qualification.root / document["working_app_config"], qualification
    )
    if (
        connector.config_id != document["connector_config_id"]
        or policy.config_id != document["working_app_config_id"]
    ):
        raise ValueError("Pinned shipped Host or working-app policy changed")
    return dict(document=document, native=native, connector=connector, policy=policy)


def preflight_progression_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    inputs = bridge_inputs(qualification, path)
    document = inputs["document"]
    if not node.is_file() or _running_games():
        raise ValueError(
            "Close the game and supply the local Node runtime for the progression fixture"
        )
    reuse = preflight_working_app(inputs["policy"])
    return {
        "ready_for_diagnostic": True,
        "planned_cases": len(document["acts"]),
        "native_report_id": document["native_report_id"],
        "working_app": reuse,
        "privileged_fixture": True,
        "full_run_attempts": 0,
        "training_allowed": False,
    }


def _fixture(
    inputs: dict[str, Any], qualification: EngineQualificationConfig, directory: Path, act: int
) -> dict[str, Any]:
    native = inputs["native"]
    config = native["document"]
    workspace = _private_path(qualification.root, config["workspace"])
    raw = json.loads((workspace / "private-check.json").read_text())
    checkpoint = raw["checkpoints"][act - 1]
    after = next(row for row in raw["states"] if row["stage"] == f"act_{act}_after_proceed")[
        "state"
    ]
    return {
        "comparison_mode": "progression_" + inputs["document"].get("probe_revision", "v1"),
        "privileged_fixture": True,
        "workspace": str((directory / "shipped").relative_to(qualification.root)),
        "act": act,
        "seed": config["seed"],
        "checkpoint_path": checkpoint["path"],
        "checkpoint_sha256": checkpoint["sha256"],
        "benchmark_progress": str(
            (workspace / "benchmark-progress.save").relative_to(qualification.root)
        ),
        "profile_policy": config["profile_policy"],
        "profile_policy_id": config["profile_policy_id"],
        "target": {
            "act": after["context"]["act"],
            "act_definition_id": after["context"]["act_definition_id"],
        },
    }


def verify_progression_case(
    qualification: EngineQualificationConfig,
    inputs: dict[str, Any],
    directory: Path,
    act: int,
    *,
    node: Path,
    verifier_override: Path | None = None,
) -> dict[str, Any]:
    fixture = json.loads((directory / "fixture.json").read_text())
    if fixture != _fixture(inputs, qualification, directory, act):
        raise ValueError("Saved progression fixture differs from its bound native checkpoint")
    verify_benchmark_progress(
        qualification.root / fixture["benchmark_progress"], inputs["native"]["policy"]
    )
    if _sha_file(Path(fixture["checkpoint_path"])) != fixture["checkpoint_sha256"]:
        raise ValueError("Progression fixture save changed")
    shipped = _hashed(directory / "shipped-report.json")
    if (
        shipped.get("qualification_config_id") != qualification.config_id
        or shipped.get("config_id") != inputs["connector"].config_id
        or shipped.get("training_allowed") is not False
        or shipped.get("full_run_attempts") != 0
        or shipped.get("verdict", {}).get("status") != "shipped_checkpoint_input_pass"
        or not shipped.get("checks")
        or any(value is not True for value in shipped["checks"].values())
    ):
        raise ValueError("Incomplete shipped progression/ending comparison")
    receipt = shipped["working_app"]
    attempt = Path(receipt["attempt"])
    if attempt.parent != directory / "shipped":
        raise ValueError("Progression app receipt belongs to a different attempt")
    verify_working_app_receipt(
        inputs["policy"], receipt, attempt=attempt, archive_id=shipped["archive_id"]
    )
    expected_consent = {
        "profile_policy_id": fixture["profile_policy_id"],
        "progress_sha256": inputs["native"]["policy"]["progress_sha256"],
        "fresh_tutorials": True,
    }
    if shipped.get("profile_settings_consent", {}).get("benchmark_profile") != expected_consent:
        raise ValueError("Progression profile was not bound before the shipped launch")
    revision = inputs["document"].get(
        "saved_verifier_revision",
        inputs["document"].get("probe_revision", "v1"),
    )
    verifier = (
        verifier_override
        or qualification.root / "scripts" / f"verify-engine-progression-saved-{revision}.mjs"
    )
    checked = subprocess.run(
        [
            str(node),
            str(verifier),
        ],
        input=json.dumps(
            {
                "shipped": str(directory / "shipped-report.json"),
                "control": str(attempt / "checkpoint-control.json"),
                "fixture": str(directory / "fixture.json"),
            }
        ),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if checked.returncode:
        raise ValueError("Saved progression reconstruction failed: " + checked.stderr[-800:])
    return dict(json.loads(checked.stdout))


def compare_progression_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    preflight_progression_bridges(qualification, path, node=node)
    inputs = bridge_inputs(qualification, path)
    document = inputs["document"]
    workspace = _private_path(qualification.root, document["workspace"])
    if workspace.exists():
        raise FileExistsError("Preserve this progression comparison; no automatic replay or retry")
    workspace.mkdir(parents=True)
    atomic_json(workspace / "recipe.json", document)
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": "engine-progression-bridges-v1",
        "qualification_config_id": qualification.config_id,
        "config_id": manifest_identifier(document),
        "native_report_id": document["native_report_id"],
        "status": "progression_comparisons_incomplete",
        "planned_cases": len(document["acts"]),
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": len(document["acts"]),
        "cases": [],
        "privileged_fixture": True,
        "natural_victories": 0,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": (
            "privileged_before_Proceed_saves_native_act_targets_and_explicit_final_win_only"
        ),
    }
    for act in document["acts"]:
        directory = workspace / f"act-{act}"
        directory.mkdir()
        case: dict[str, Any] = {"act": act, "status": "incomplete"}
        result["cases"].append(case)
        result["not_attempted_cases"] -= 1
        try:
            fixture = _fixture(inputs, qualification, directory, act)
            atomic_json(directory / "fixture.json", fixture)
            shipped = _probe_connector_private(
                inputs["connector"],
                node=node,
                fixture=fixture,
                retain_working_game=False,
                working_app=inputs["policy"],
            )
            atomic_json(directory / "shipped-report.json", shipped)
            case["shipped_report_id"] = shipped["report_id"]
            case["verification"] = verify_progression_case(
                qualification, inputs, directory, act, node=node
            )
            case["status"] = "pass"
            result["completed_cases"] += 1
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
            case["error"] = str(error)
            result["failed_cases"] += 1
            break
    if result["completed_cases"] == result["planned_cases"]:
        result["status"] = "progression_comparisons_pass"
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "summary.json", result)
    return result


def verify_progression_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    inputs = bridge_inputs(qualification, path)
    document = inputs["document"]
    workspace = _private_path(qualification.root, document["workspace"])
    result = _hashed(workspace / "summary.json")
    if (
        result.get("qualification_config_id") != qualification.config_id
        or result.get("config_id") != manifest_identifier(document)
        or result.get("native_report_id") != document["native_report_id"]
        or result.get("status") != "progression_comparisons_pass"
        or result.get("completed_cases") != len(document["acts"])
        or result.get("planned_cases") != len(document["acts"])
        or result.get("failed_cases") != 0
        or result.get("not_attempted_cases") != 0
        or result.get("privileged_fixture") is not True
        or result.get("training_allowed") is not False
        or result.get("full_run_attempts") != 0
        or result.get("natural_victories") != 0
        or [row.get("act") for row in result.get("cases", [])] != document["acts"]
        or json.loads((workspace / "recipe.json").read_text()) != document
    ):
        raise ValueError("Incomplete, relabeled or changed progression comparison denominator")
    verifications = []
    for act, case in zip(document["acts"], result["cases"], strict=True):
        directory = workspace / f"act-{act}"
        verified = verify_progression_case(qualification, inputs, directory, act, node=node)
        if (
            case.get("status") != "pass"
            or case.get("verification") != verified
            or case.get("shipped_report_id")
            != _hashed(directory / "shipped-report.json")["report_id"]
        ):
            raise ValueError("Progression case summary differs from its delivered public trace")
        verifications.append(verified)
    return {
        "valid": True,
        "batch_report_id": result["report_id"],
        "cases": verifications,
        "privileged_fixture": True,
        "natural_victories": 0,
        "games_replayed": 0,
        "training_allowed": False,
    }


def audit_saved_progression(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    """An explicit new verifier can audit a successful game from a failed old checker.

    The original batch/case status remains unchanged. Its full denominator and
    verifier error remain bound in this supplemental saved-only report.
    """
    document = json.loads(path.read_text())
    verifier = qualification.root / "scripts/verify-engine-progression-saved-v3.mjs"
    if (
        document.get("schema_version") != "engine-progression-saved-audit-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("privileged_fixture") is not True
        or _sha_file(verifier) != document.get("verifier_sha256")
        or type(document.get("act")) is not int
        or document["act"] not in (1, 2, 3)
    ):
        raise ValueError("Expected an explicit pinned saved-only progression audit")
    source_path = qualification.root / document["source_config"]
    inputs = bridge_inputs(qualification, source_path)
    if manifest_identifier(inputs["document"]) != document["source_config_id"]:
        raise ValueError("Saved progression audit source recipe changed")
    workspace = _private_path(qualification.root, inputs["document"]["workspace"])
    source = _hashed(workspace / "summary.json")
    if (
        source.get("report_id") != document["source_report_id"]
        or source.get("config_id") != document["source_config_id"]
        or document["act"] not in inputs["document"]["acts"]
    ):
        raise ValueError("Saved progression audit source batch changed")
    directory = workspace / f"act-{document['act']}"
    verified = verify_progression_case(
        qualification, inputs, directory, document["act"], node=node, verifier_override=verifier
    )
    return {
        "schema_version": "engine-progression-saved-audit-v1",
        "valid": True,
        "config_id": manifest_identifier(document),
        "source_report_id": source["report_id"],
        "source_batch_status_unchanged": source["status"],
        "source_batch_denominator": {
            key: source[key]
            for key in ("planned_cases", "completed_cases", "failed_cases", "not_attempted_cases")
        },
        "source_shipped_report_id": _hashed(directory / "shipped-report.json")["report_id"],
        "verifier_sha256": _sha_file(verifier),
        "act": document["act"],
        **verified,
        "claim_scope": "supplemental_saved_shipped_transition_audit_only_original_batch_unchanged",
    }
