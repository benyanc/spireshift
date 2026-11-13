"""Finite privileged reward pickup comparisons with shared launcher and immutable evidence."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_bundle_bridge import _verify_bundle_prerequisites, _working_app_policy
from spireshift.engine_checkpoint import verify_checkpoint_input
from spireshift.engine_cli_probe import _probe_cli_document
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _private_path, _require_native_launch_support, _running_games
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_working_app import (
    load_working_app_policy,
    preflight_working_app,
    verify_working_app_receipt,
)
from spireshift.full_run_experience import atomic_json

SCENARIOS = {
    "calling-bell-claim-all",
    "calling-bell-claim-skip",
    "cauldron-fill-replace-skip",
    "cauldron-fill-skip",
}
HELPERS = {
    "engine-reward-tutorial-v2.mjs",
    "engine-reward-shipped-probe-v3.mjs",
    "engine-reward-bridge-contract-v1.mjs",
    "engine-shop-bridge-contract.mjs",
    "engine-rest-bridge-contract.mjs",
    "engine-journey-contract-v2.mjs",
    "engine-menu-probe.mjs",
    "engine-checkpoint-shipped-probe.mjs",
    "verify-engine-reward-saved-v3.mjs",
}


def _template(
    qualification: EngineQualificationConfig, path: Path, document: dict[str, Any]
) -> None:
    if (
        document.get("schema_version") != "engine-reward-bridge-config-v1"
        or document.get("stage") != "privileged_serialized_reward_pickup_differential_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("bridge_revision") != "v3"
        or not isinstance(document.get("scenario"), str)
        or document.get("scenario") not in SCENARIOS
        or not re.fullmatch(r"[A-Z0-9]{1,64}", str(document.get("seed", "")))
        or set(document.get("helpers_sha256", {})) != HELPERS
        or any(
            _sha_file(qualification.root / "scripts" / name) != document["helpers_sha256"][name]
            for name in HELPERS
        )
        or _working_app_policy(qualification, path, document) is None
    ):
        raise ValueError("Expected a pinned finite reward fixture with explicit shared app reuse")


def validate_reward_cases(document: dict[str, Any]) -> list[dict[str, Any]]:
    cases = document.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 8
        or any(
            not isinstance(row, dict)
            or not re.fullmatch(r"[a-z0-9-]{1,64}", str(row.get("case_id", "")))
            or not re.fullmatch(r"[A-Z0-9]{1,64}", str(row.get("seed", "")))
            or not isinstance(row.get("scenario"), str)
            or row.get("scenario") not in SCENARIOS
            for row in cases
        )
    ):
        raise ValueError("Expected eight explicitly named repeated reward cases")
    pairs = {(row["seed"], row["scenario"]) for row in cases}
    if (
        len({row["case_id"] for row in cases}) != 8
        or len(pairs) != 4
        or {row["scenario"] for row in cases} != SCENARIOS
        or any(sum((row["seed"], row["scenario"]) == pair for row in cases) != 2 for pair in pairs)
    ):
        raise ValueError("Each of four reward seed/scenario pairs must appear twice")
    return [dict(row) for row in cases]


def _batch_inputs(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], list[dict[str, Any]], Path, dict[str, Any], Path]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-reward-bridges-config-v1"
        or document.get("stage") != "owner_repeated_privileged_reward_differentials_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
    ):
        raise ValueError("Expected the fixed fifteen-minute owner reward stage")
    cases = validate_reward_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if (
        template_path.resolve().parent != path.resolve().parent
        or manifest_identifier(template) != document["template_id"]
    ):
        raise ValueError("Frozen reward comparison template changed")
    _template(qualification, template_path, template)
    return (
        document,
        cases,
        template_path,
        template,
        _private_path(qualification.root, document["workspace"]),
    )


def _launch_preflight(
    qualification: EngineQualificationConfig, path: Path, document: dict[str, Any], node: Path
) -> dict[str, Any]:
    _template(qualification, path, document)
    _require_native_launch_support()
    if _running_games() or not node.is_file() or not os.access(node, os.X_OK):
        raise ValueError("Close the game and pass an executable local Node runtime")
    pins = _verify_bundle_prerequisites(qualification, path, document, panel="reward_bridge")
    policy = _working_app_policy(qualification, path, document)
    assert policy is not None
    pool = preflight_working_app(policy)
    minimum = 500_000_000 if (policy.slot / "game").exists() else 3_500_000_000
    if shutil.disk_usage(qualification.root).free < minimum:
        raise ValueError(f"Allow {minimum} free bytes before this reward stage")
    return {"prerequisites": pins, "working_app_pool": pool, "minimum_free_bytes": minimum}


def preflight_reward_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    started = time.monotonic()
    document, cases, template_path, template, workspace = _batch_inputs(qualification, path)
    if workspace.exists():
        raise FileExistsError(
            "Preserve the completed/interrupted reward stage; no automatic resume"
        )
    result = {
        "schema_version": "engine-reward-preflight-v1",
        "status": "reward_preflight_pass",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        **_launch_preflight(qualification, template_path, template, node),
        "planned_cases": len(cases),
        "independent_seeds": len({row["seed"] for row in cases}),
        "workspace_created": False,
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "wall_seconds": time.monotonic() - started,
    }
    result["report_id"] = manifest_identifier(result)
    return result


def compare_reward_bridge(
    qualification: EngineQualificationConfig,
    path: Path,
    *,
    node: Path,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document = override if override is not None else json.loads(path.read_text())
    _launch_preflight(qualification, path, document, node)
    workspace = _private_path(qualification.root, document["workspace"])
    if workspace.exists():
        raise FileExistsError("Preserve this reward attempt; use a new versioned workspace")
    workspace.mkdir(parents=True)
    result: dict[str, Any] = {
        "schema_version": "engine-reward-bridge-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "seed": document["seed"],
        "scenario": document["scenario"],
        "working_app_config": document["working_app_config"],
        "working_app_config_id": document["working_app_config_id"],
        "privileged_fixture": True,
        "status": "reward_comparison_incomplete",
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "serialized_fixture_public_reward_pickup_ownership_capacity_and_skip_only",
    }
    try:
        native_path = qualification.root / document["native_config"]
        native_config = json.loads(native_path.read_text())
        native_config.update(
            seed=document["seed"],
            reward_bridge={"scenario": document["scenario"]},
            workspace=str((workspace / "native").relative_to(qualification.root)),
        )
        atomic_json(workspace / "native-config.json", native_config)
        native = _probe_cli_document(
            qualification, native_path, node, native_config, panel="reward_bridge"
        )
        native_report = workspace / "native-report.json"
        atomic_json(native_report, native)
        result.update(
            native_report=str(native_report.relative_to(qualification.root)),
            native_report_id=native["report_id"],
        )
        if native["status"] != "reward_bridge_public_projection_regression_pass":
            raise ValueError("Native reward prefix failed; no shipped launch follows")
        snapshot = Path(native["report_path"]).parent / "private-starting-snapshot.json"
        fixture = verify_checkpoint_input(
            qualification,
            {
                "checkpoint_report": result["native_report"],
                "checkpoint_report_id": native["report_id"],
                "seed": document["seed"],
                "snapshot_sha256": _sha_file(snapshot),
            },
            panel="reward_bridge",
        )
        fixture.update(
            workspace=str((workspace / "shipped").relative_to(qualification.root)),
            reward_report_path=str(native_report),
            scenario=document["scenario"],
            comparison_mode="reward_bridge_v3",
        )
        connector = load_connector_qualification_config(
            qualification.root / document["connector_config"], qualification
        )
        policy = _working_app_policy(qualification, path, document)
        assert policy is not None
        shipped = _probe_connector_private(
            connector, node=node, fixture=fixture, retain_working_game=False, working_app=policy
        )
        atomic_json(workspace / "shipped-report.json", shipped)
        result.update(
            shipped_report=str((workspace / "shipped-report.json").relative_to(qualification.root)),
            shipped_report_id=shipped["report_id"],
            working_app=shipped["working_app"],
        )
        if shipped["verdict"]["status"] != "shipped_checkpoint_input_pass":
            raise ValueError("Shipped reward comparison failed; evidence preserved")
        result["status"] = "reward_action_comparison_pass"
        result["saved_verification"] = verify_reward_saved(qualification, result, node=node)
    except (ValueError, OSError, RuntimeError) as error:
        result.update(status="reward_comparison_incomplete", error=str(error))
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "comparison.json", result)
    return result


def verify_reward_saved(
    qualification: EngineQualificationConfig, comparison: dict[str, Any], *, node: Path
) -> dict[str, Any]:
    if (
        comparison.get("status") != "reward_action_comparison_pass"
        or comparison.get("training_allowed") is not False
    ):
        raise ValueError("Expected a completed scoped reward comparison")
    native = _hashed(_private_path(qualification.root, comparison["native_report"]))
    shipped = _hashed(_private_path(qualification.root, comparison["shipped_report"]))
    for role, report in (("native", native), ("shipped", shipped)):
        if (
            report["report_id"] != comparison[f"{role}_report_id"]
            or report.get("qualification_config_id") != qualification.config_id
            or report.get("training_allowed") is not False
            or report.get("full_run_attempts") != 0
            or not report.get("checks")
            or any(value is not True for value in report["checks"].values())
        ):
            raise ValueError("Saved reward report binding or required checks changed")
    if (
        native.get("status") != "reward_bridge_public_projection_regression_pass"
        or shipped.get("verdict", {}).get("status") != "shipped_checkpoint_input_pass"
        or shipped.get("working_app") != comparison.get("working_app")
    ):
        raise ValueError("Saved reward success or reusable app receipt changed")
    if (
        native.get("ascension") != 8
        or native.get("character") != "Ironclad"
        or native.get("probe", {}).get("checkpoint", {}).get("seed") != comparison["seed"]
        or shipped.get("probe", {}).get("native_provenance", {}).get("actual_seed")
        != comparison["seed"]
    ):
        raise ValueError("Saved reward fixture seed/A8 provenance changed")
    policy_path = qualification.root / comparison["working_app_config"]
    if policy_path.resolve().parent != qualification.root / "configs/engine-qualification":
        raise ValueError("Saved reward app policy must stay in the qualification configs")
    policy = load_working_app_policy(policy_path, qualification)
    if policy.config_id != comparison["working_app_config_id"]:
        raise ValueError("Saved reward working app policy changed")
    receipt = comparison["working_app"]
    attempt = Path(receipt["attempt"])
    shipped_directory = (
        _private_path(qualification.root, comparison["shipped_report"]).parent / "shipped"
    )
    if attempt.parent != shipped_directory or not attempt.name.startswith("checkpoint-"):
        raise ValueError("Saved reward app receipt belongs to another attempt")
    verify_working_app_receipt(policy, receipt, attempt=attempt, archive_id=shipped["archive_id"])
    snapshots = _private_path(
        qualification.root,
        str(
            (Path(native["report_path"]).parent / "private-reward-snapshots.jsonl").relative_to(
                qualification.root
            )
        ),
    )
    process = subprocess.run(
        [str(node), str(qualification.root / "scripts/verify-engine-reward-saved-v3.mjs")],
        input=json.dumps(
            {
                "native_report": str(
                    _private_path(qualification.root, comparison["native_report"])
                ),
                "shipped_report": str(
                    _private_path(qualification.root, comparison["shipped_report"])
                ),
                "native_snapshots": str(snapshots),
                "scenario": comparison["scenario"],
            }
        ),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if process.returncode:
        raise ValueError("Saved reward verification failed: " + process.stderr[-500:])
    verified = json.loads(process.stdout)
    if (
        verified.get("valid") is not True
        or verified.get("games_launched") != 0
        or verified.get("training_allowed") is not False
    ):
        raise ValueError("Invalid saved reward verification")
    result = {
        **verified,
        "schema_version": "engine-reward-saved-verification-v1",
        "native_report_id": native["report_id"],
        "shipped_report_id": shipped["report_id"],
        "native_raw_snapshots_sha256": _sha_file(snapshots),
        "verifier_sha256": _sha_file(
            qualification.root / "scripts/verify-engine-reward-saved-v3.mjs"
        ),
    }
    result["report_id"] = manifest_identifier(result)
    return result


def compare_reward_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    preflight = preflight_reward_bridges(qualification, path, node=node)
    document, cases, template_path, template, workspace = _batch_inputs(qualification, path)
    if preflight["config_id"] != manifest_identifier(document):
        raise ValueError("Reward stage changed during preflight")
    workspace.mkdir(parents=True)
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": "engine-reward-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "preflight": preflight,
        "status": "in_progress",
        "cases": [],
        "planned_cases": 8,
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 8,
        "independent_seeds": len({row["seed"] for row in cases}),
        "seed_scenario_pairs": 4,
        "privileged_fixture": True,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
    }
    atomic_json(workspace / "in-progress.json", result)
    active = False
    try:
        for index, case in enumerate(cases, 1):
            if time.monotonic() - started > document["max_wall_seconds"] - 350:
                raise TimeoutError("Reward stage reached its finite launch allowance")
            print(
                f"Reward comparison {index}/8: {case['case_id']}; shared app, fresh profile.",
                flush=True,
            )
            config = copy.deepcopy(template)
            config.update(
                seed=case["seed"],
                scenario=case["scenario"],
                workspace=str((workspace / case["case_id"]).relative_to(qualification.root)),
            )
            atomic_json(workspace / f"case-{index:02d}-config.json", config)
            active = True
            result["not_attempted_cases"] -= 1
            comparison = compare_reward_bridge(
                qualification, template_path, node=node, override=config
            )
            result["cases"].append({**case, "comparison": comparison})
            if comparison["status"] != "reward_action_comparison_pass":
                raise ValueError("Reward comparison failed; no next case follows")
            result["completed_cases"] += 1
            active = False
            atomic_json(workspace / f"progress-{index:02d}.json", result)
        prefixes: dict[tuple[str, str], list[Any]] = {}
        for case in result["cases"]:
            shipped = _hashed(qualification.root / case["comparison"]["shipped_report"])
            prefixes.setdefault((case["seed"], case["scenario"]), []).append(
                [row["facts"] for row in shipped["probe"]["comparisons"]]
            )
        if any(rows[0] != rows[1] for rows in prefixes.values()):
            raise ValueError("Repeated public reward prefix changed")
        result.update(status="reward_comparisons_pass", repeated_public_prefixes_identical=True)
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        result.update(status="reward_comparisons_incomplete", error=str(error))
        result["failed_cases"] += int(active)
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "batch.json", result)
    (workspace / "in-progress.json").unlink()
    return result


def verify_reward_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document, cases, template_path, template, workspace = _batch_inputs(qualification, path)
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("qualification_config_id") != qualification.config_id
        or batch.get("status") != "reward_comparisons_pass"
        or batch.get("completed_cases") != 8
        or batch.get("planned_cases") != 8
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("repeated_public_prefixes_identical") is not True
        or batch.get("training_allowed") is not False
        or batch.get("full_run_attempts") != 0
        or batch.get("optimizer_steps") != 0
        or [{key: row[key] for key in ("case_id", "seed", "scenario")} for row in batch["cases"]]
        != cases
    ):
        raise ValueError("Expected the complete frozen eight-case reward stage")
    policy = _working_app_policy(qualification, template_path, template)
    assert policy is not None
    verified = []
    prefixes: dict[tuple[str, str], list[Any]] = {}
    for case in batch["cases"]:
        directory = workspace / case["case_id"]
        comparison = _hashed(directory / "comparison.json")
        effective = copy.deepcopy(template)
        effective.update(
            seed=case["seed"],
            scenario=case["scenario"],
            workspace=str(directory.relative_to(qualification.root)),
        )
        if (
            comparison != case["comparison"]
            or comparison.get("config_id") != manifest_identifier(effective)
            or comparison.get("native_report")
            != str((directory / "native-report.json").relative_to(qualification.root))
            or comparison.get("shipped_report")
            != str((directory / "shipped-report.json").relative_to(qualification.root))
            or comparison.get("seed") != case["seed"]
            or comparison.get("scenario") != case["scenario"]
        ):
            raise ValueError("Saved reward case/config changed")
        shipped = _hashed(_private_path(qualification.root, comparison["shipped_report"]))
        receipt = comparison["working_app"]
        attempt = Path(receipt["attempt"])
        if (
            not attempt.is_relative_to(directory / "shipped")
            or attempt.parent != directory / "shipped"
            or not attempt.name.startswith("checkpoint-")
        ):
            raise ValueError("Saved reward app receipt belongs to another attempt")
        verify_working_app_receipt(
            policy, receipt, attempt=attempt, archive_id=shipped["archive_id"]
        )
        audited = verify_reward_saved(qualification, comparison, node=node)
        if audited != comparison["saved_verification"]:
            raise ValueError("Saved reward reconstruction differs from recorded audit")
        verified.append(audited)
        prefixes.setdefault((case["seed"], case["scenario"]), []).append(
            [row["facts"] for row in shipped["probe"]["comparisons"]]
        )
    if any(len(rows) != 2 or rows[0] != rows[1] for rows in prefixes.values()):
        raise ValueError("Repeated saved reward facts differ")
    result = {
        "schema_version": "engine-reward-batch-saved-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "verified_cases": len(verified),
        "case_verification_ids": [row["report_id"] for row in verified],
        **{
            key: sum(row[key] for row in verified)
            for key in (
                "observations",
                "effect_decisions",
                "public_game_ui_actions",
                "tutorial_steps",
            )
        },
        "games_launched": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "claim_scope": "saved_eight_case_privileged_reward_raw_public_evidence_only",
    }
    result["report_id"] = manifest_identifier(result)
    return result
