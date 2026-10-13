"""Finite public combat-effect differentials; never a learning or full-run stage."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import (
    _probe_cli_document,
    verify_local_build_report,
    verify_probe_runtime,
    verify_projection_inputs,
)
from spireshift.engine_connector import (
    _probe_connector_private,
    _settings_template,
    _verify_toolchain,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_localization import verify_native_localization
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_profile import load_profile_policy, verify_benchmark_progress
from spireshift.engine_qualification import EngineQualificationConfig, _inventory, _sha_file
from spireshift.engine_working_app import (
    load_working_app_policy,
    preflight_working_app,
    verify_working_app_receipt,
)
from spireshift.full_run_experience import atomic_json

HELPERS = {
    "engine-combat-bridge-contract-v6.mjs",
    "engine-combat-shipped-probe-v4.mjs",
    "verify-engine-combat-saved-v4.mjs",
    "engine-menu-probe.mjs",
    "engine-combat-shuffle-v1.mjs",
    "engine-checkpoint-shipped-probe.mjs",
    "engine-journey-tutorial-v4.mjs",
    "engine-journey-contract-v2.mjs",
    "engine-rest-bridge-contract.mjs",
}
SEEDS = {"SPIRESHIFTPROFILE003": "Stone Humidifier", "SPIRESHIFTPROFILE004": "Winged Boots"}
SCENARIOS = {"corruption", "temporary-stats"}
DISCARD_SCENARIOS = {"discard-automatic", "discard-duplicate"}
DISCARD_HELPERS = (
    HELPERS
    - {
        "engine-combat-bridge-contract-v6.mjs",
        "engine-combat-shipped-probe-v4.mjs",
        "verify-engine-combat-saved-v4.mjs",
    }
) | {
    "engine-combat-bridge-contract-v7.mjs",
    "engine-combat-shipped-probe-v5.mjs",
    "verify-engine-combat-saved-v5.mjs",
    "engine-combat-surface-v2.mjs",
}


def combat_scope(document: dict[str, Any]) -> tuple[set[str], set[str], str, str, str]:
    revision = document.get("bridge_revision", "effects_v1")
    if revision == "effects_v1":
        return SCENARIOS, HELPERS, "v6", "combat_bridge_v4", "verify-engine-combat-saved-v4.mjs"
    if revision == "potion_discard_v1":
        return (
            DISCARD_SCENARIOS,
            DISCARD_HELPERS,
            "v7",
            "combat_bridge_v5",
            "verify-engine-combat-saved-v5.mjs",
        )
    raise ValueError("Unknown finite combat comparison revision")


def combat_bridge_inputs(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    document = json.loads(path.read_text())
    scenarios, helpers, native_revision, _, _ = combat_scope(document)
    if (
        document.get("schema_version") != "engine-combat-bridge-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("seed") not in SEEDS
        or document.get("scenario") not in scenarios
        or set(document.get("helpers_sha256", {})) != helpers
        or any(
            _sha_file(qualification.root / "scripts" / name) != document["helpers_sha256"][name]
            for name in helpers
        )
    ):
        raise ValueError("Expected a pinned, finite two-scenario A8 combat comparison")
    native_path = qualification.root / document["native_config"]
    native = json.loads(native_path.read_text())
    if (
        manifest_identifier(native) != document["native_config_id"]
        or native.get("combat_bridge_revision") != native_revision
        or native.get("content_policy") != "native_benchmark_full_v1"
        or native.get("seed") != document["seed"]
        or native.get("combat_bridge", {}).get("scenario") != document["scenario"]
    ):
        raise ValueError("Combat comparison native recipe changed")
    return document, native_path, native


def compare_combat_bridge(
    qualification: EngineQualificationConfig,
    path: Path,
    *,
    node: Path,
    case: dict[str, str] | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    document, native_path, template = combat_bridge_inputs(qualification, path)
    scenarios, _, _, mode, _ = combat_scope(document)
    seed = case["seed"] if case else document["seed"]
    scenario = case["scenario"] if case else document["scenario"]
    if seed not in SEEDS or scenario not in scenarios:
        raise ValueError("Unknown frozen combat seed/scenario")
    directory = workspace or _private_path(qualification.root, document["workspace"])
    if directory.exists():
        raise FileExistsError("Preserve this combat attempt; no automatic restart")
    directory.mkdir(parents=True)
    result: dict[str, Any] = {
        "schema_version": "engine-combat-bridge-v1",
        "qualification_config_id": qualification.config_id,
        "config_id": manifest_identifier(document),
        "seed": seed,
        "scenario": scenario,
        "workspace": str(directory.relative_to(qualification.root)),
        "status": "combat_comparison_incomplete",
        "privileged_fixture": True,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
    }
    try:
        effective = dict(template)
        if case is not None or "saved_native_report" not in document:
            effective.update(
                seed=seed,
                workspace=str((directory / "native").relative_to(qualification.root)),
                combat_bridge={
                    "scenario": scenario,
                    "starting_option": SEEDS[seed],
                    "max_actions": 20,
                },
            )
            native = _probe_cli_document(
                qualification, native_path, node, effective, panel="combat_bridge"
            )
        else:
            native = _hashed(_private_path(qualification.root, document["saved_native_report"]))
        atomic_json(directory / "native-recipe.json", effective)
        atomic_json(directory / "native-report.json", native)
        if (
            native.get("config_id") != manifest_identifier(effective)
            or native.get("status") != "combat_bridge_public_projection_regression_pass"
            or any(value is not True for value in native.get("checks", {}).values())
        ):
            raise ValueError("Native combat prefix failed; shipped comparison was not started")
        native_attempt = _private_path(
            qualification.root,
            str(Path(native["report_path"]).parent.relative_to(qualification.root)),
        )
        profile = load_profile_policy(
            qualification.root / effective["profile_policy"], qualification
        )
        progress = native_attempt / "benchmark-progress.save"
        verify_benchmark_progress(progress, profile)
        policy = load_working_app_policy(
            qualification.root / document["working_app_config"], qualification
        )
        if policy.config_id != document["working_app_config_id"]:
            raise ValueError("Combat working-app policy changed")
        connector = load_connector_qualification_config(
            qualification.root / document["connector_config"], qualification
        )
        fixture = {
            "workspace": str((directory / "shipped").relative_to(qualification.root)),
            "comparison_mode": mode,
            "seed": seed,
            "scenario": scenario,
            "combat_report_path": str(directory / "native-report.json"),
            "checkpoint_path": native["probe"]["checkpoint"]["path"],
            "checkpoint_sha256": native["probe"]["checkpoint"]["sha256"],
            "snapshot_path": str(native_attempt / "private-starting-snapshot.json"),
            "benchmark_progress": str(progress.relative_to(qualification.root)),
            "profile_policy": effective["profile_policy"],
            "profile_policy_id": effective["profile_policy_id"],
        }
        result["native_report_id"] = native["report_id"]
        shipped = _probe_connector_private(
            connector, node=node, fixture=fixture, retain_working_game=False, working_app=policy
        )
        atomic_json(directory / "shipped-report.json", shipped)
        result.update(shipped_report_id=shipped["report_id"], working_app=shipped["working_app"])
        if shipped["verdict"]["status"] != "shipped_checkpoint_input_pass":
            raise ValueError(
                "Shipped combat effect comparison failed; preserve its first difference"
            )
        result["saved_verification"] = verify_combat_bridge(
            qualification, path, directory, node=node
        )
        result["status"] = "combat_comparison_pass"
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        result["error"] = str(error)
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(directory / "comparison.json", result)
    return result


def verify_combat_bridge(
    qualification: EngineQualificationConfig, path: Path, directory: Path, *, node: Path
) -> dict[str, Any]:
    document, _, template = combat_bridge_inputs(qualification, path)
    scenarios, _, _, _, verifier = combat_scope(document)
    effective = json.loads((directory / "native-recipe.json").read_text())
    native = _hashed(directory / "native-report.json")
    if (
        native.get("config_id") != manifest_identifier(effective)
        or native.get("status") != "combat_bridge_public_projection_regression_pass"
        or effective.get("seed") not in SEEDS
        or effective.get("combat_bridge", {}).get("scenario") not in scenarios
        or effective
        != {
            **template,
            "seed": effective["seed"],
            "workspace": effective["workspace"],
            "combat_bridge": {
                "scenario": effective["combat_bridge"]["scenario"],
                "starting_option": SEEDS[effective["seed"]],
                "max_actions": 20,
            },
        }
        or not native.get("checks")
        or any(value is not True for value in native["checks"].values())
    ):
        raise ValueError("Saved native combat recipe or verdict changed")
    native_attempt = _private_path(
        qualification.root, str(Path(native["report_path"]).parent.relative_to(qualification.root))
    )
    if _hashed(native_attempt / "report.json") != {
        k: v for k, v in native.items() if k != "report_path"
    }:
        raise ValueError("Native combat evidence is no longer bound to its source attempt")
    checkpoint = _private_path(
        qualification.root,
        str(Path(native["probe"]["checkpoint"]["path"]).relative_to(qualification.root)),
    )
    if (
        checkpoint.parent != native_attempt
        or _sha_file(checkpoint) != native["probe"]["checkpoint"]["sha256"]
    ):
        raise ValueError("Combat checkpoint changed")
    profile = load_profile_policy(qualification.root / effective["profile_policy"], qualification)
    verify_benchmark_progress(native_attempt / "benchmark-progress.save", profile)
    shipped = _hashed(directory / "shipped-report.json")
    if shipped.get("verdict", {}).get("status") != "shipped_checkpoint_input_pass" or any(
        value is not True for value in shipped["checks"].values()
    ):
        raise ValueError("Incomplete saved shipped combat checks")
    policy = load_working_app_policy(
        qualification.root / document["working_app_config"], qualification
    )
    receipt = shipped["working_app"]
    if Path(receipt["attempt"]).parent != directory / "shipped":
        raise ValueError("Combat app receipt belongs to another attempt")
    verify_working_app_receipt(
        policy, receipt, attempt=Path(receipt["attempt"]), archive_id=shipped["archive_id"]
    )
    if shipped.get("profile_settings_consent", {}).get("benchmark_profile") != {
        "profile_policy_id": manifest_identifier(profile),
        "progress_sha256": profile["progress_sha256"],
        "fresh_tutorials": True,
    }:
        raise ValueError("Shipped combat benchmark profile was not bound before launch")
    process = subprocess.run(
        [str(node), str(qualification.root / "scripts" / verifier)],
        input=json.dumps(
            {
                "native": str(directory / "native-report.json"),
                "snapshots": str(native_attempt / "private-combat-snapshots.jsonl"),
                "shipped": str(directory / "shipped-report.json"),
                "scenario": effective["combat_bridge"]["scenario"],
            }
        ),
        text=True,
        capture_output=True,
        timeout=20,
    )
    if process.returncode:
        raise ValueError("Saved combat reconstruction failed: " + process.stderr[-600:])
    result = {
        "schema_version": "engine-combat-saved-verification-v1",
        "native_report_id": native["report_id"],
        "shipped_report_id": shipped["report_id"],
        **json.loads(process.stdout),
    }
    result["report_id"] = manifest_identifier(result)
    return result


def validate_combat_cases(
    document: dict[str, Any], *, scenarios: set[str] | None = None
) -> list[dict[str, str]]:
    scenarios = SCENARIOS if scenarios is None else scenarios
    cases = document.get("cases", [])
    counts: dict[tuple[str, str], int] = {}
    if not isinstance(cases, list) or len(cases) != 8:
        raise ValueError("Eight fixed combat cases are required")
    for case in cases:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "seed", "scenario"}
            or not isinstance(case["seed"], str)
            or case["seed"] not in SEEDS
            or not isinstance(case["scenario"], str)
            or case["scenario"] not in scenarios
            or not isinstance(case["case_id"], str)
            or not case["case_id"].replace("-", "").isalnum()
        ):
            raise ValueError("Malformed frozen combat case")
        pair = (case["seed"], case["scenario"])
        counts[pair] = counts.get(pair, 0) + 1
    if len({row["case_id"] for row in cases}) != 8 or counts != {
        (seed, scene): 2 for seed in SEEDS for scene in scenarios
    }:
        raise ValueError("Every combat seed/scenario must repeat exactly twice")
    return list(cases)


def _combat_batch(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], list[dict[str, str]], Path, Path]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-combat-bridges-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or type(document.get("max_wall_seconds")) is not int
        or document["max_wall_seconds"] != 900
    ):
        raise ValueError("Expected the separate owner combat-effects panel")
    template = qualification.root / document["template"]
    bridge, _, _ = combat_bridge_inputs(qualification, template)
    scenarios, _, _, _, _ = combat_scope(bridge)
    if manifest_identifier(json.loads(template.read_text())) != document["template_id"]:
        raise ValueError("Combat panel template changed")
    return (
        document,
        validate_combat_cases(document, scenarios=scenarios),
        template,
        _private_path(qualification.root, document["workspace"]),
    )


def preflight_combat_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document, cases, template, workspace = _combat_batch(qualification, path)
    bridge, _, native = combat_bridge_inputs(qualification, template)
    if workspace.exists() or _running_games():
        raise ValueError("Preserve any prior panel and close STS2 before the next stage")
    if not node.is_file():
        raise ValueError("An executable local Node runtime is required")
    if not os.access(node, os.X_OK):
        raise ValueError("The local Node runtime is not executable")
    build_config = json.loads((qualification.root / native["build_config"]).read_text())
    report = _hashed(_private_path(qualification.root, native["build_report"]))
    build = verify_local_build_report(report, build_config, qualification)
    candidate = _private_path(
        qualification.root, str(Path(build["candidate_directory"]).relative_to(qualification.root))
    )
    if (
        report["report_id"] != native["build_report_id"]
        or _inventory(candidate) != report["private_candidate_inventory"]
        or _sha_file(qualification.root / build_config["local_patch"])
        != build_config["local_patch_sha256"]
        or _sha_file(qualification.root / "scripts/engine-cli-local-build.mjs")
        != build_config["helper_sha256"]
        or _sha_file(
            qualification.root
            / f"scripts/probe-engine-cli-combat-bridge-{native['combat_bridge_revision']}.mjs"
        )
        != native["helper_sha256"]
    ):
        raise ValueError("Combat candidate, build or native helper changed")
    runtime, _ = verify_probe_runtime(qualification, native)
    if runtime is None:
        raise ValueError("Combat comparison needs the exact game-matching runtime")
    verify_native_localization(qualification, native["native_localization"])
    profile = load_profile_policy(qualification.root / native["profile_policy"], qualification)
    if manifest_identifier(profile) != native["profile_policy_id"]:
        raise ValueError("Combat benchmark profile changed")
    verify_projection_inputs(qualification, native)
    connector = load_connector_qualification_config(
        qualification.root / bridge["connector_config"], qualification
    )
    if connector.config_id != bridge.get("connector_config_id"):
        raise ValueError("Combat owner panel requires a pinned current Host recipe")
    _verify_toolchain(connector)
    _settings_template(connector)
    policy = load_working_app_policy(
        qualification.root / bridge["working_app_config"], qualification
    )
    if policy.config_id != bridge["working_app_config_id"]:
        raise ValueError("Combat working-app policy changed")
    pool = preflight_working_app(policy)
    minimum = 500_000_000 if (policy.slot / "game").exists() else 3_500_000_000
    if shutil.disk_usage(qualification.root).free < minimum:
        raise ValueError("Insufficient free space for the bounded combat panel")
    result = {
        "schema_version": "engine-combat-preflight-v1",
        "config_id": manifest_identifier(document),
        "status": "combat_preflight_pass",
        "planned_cases": len(cases),
        "working_app_pool": pool,
        "minimum_free_bytes": minimum,
        "native_build_report_id": report["report_id"],
        "connector_config_id": connector.config_id,
        "profile_policy_id": native["profile_policy_id"],
        "workspace_created": False,
        "games_launched": 0,
        "training_allowed": False,
    }
    result["report_id"] = manifest_identifier(result)
    return result


def repeated_combat_prefixes(rows: list[dict[str, Any]], workspace: Path) -> bool:
    """Compare public facts and action semantics, excluding fresh runtime/entity identifiers."""
    prefixes: dict[tuple[str, str], list[Any]] = {}
    for row in rows:
        native = _hashed(workspace / row["case_id"] / "native-report.json")
        prefixes.setdefault((row["seed"], row["scenario"]), []).append(native["probe"]["journey"])
    return len(prefixes) == 4 and all(
        len(values) == 2 and values[0] == values[1] for values in prefixes.values()
    )


def compare_combat_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    started = time.monotonic()
    document, cases, template, workspace = _combat_batch(qualification, path)
    bridge, _, _ = combat_bridge_inputs(qualification, template)
    preflight = preflight_combat_bridges(qualification, path, node=node)
    workspace.mkdir(parents=True)
    result: dict[str, Any] = {
        "schema_version": "engine-combat-bridges-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "status": "in_progress",
        "cases": [],
        "planned_cases": 8,
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 8,
        "independent_seeds": 2,
        "seed_scenario_pairs": 4,
        "privileged_fixture": True,
        "preflight": preflight,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
        "shipped_cross_host_parity": False,
        "claim_scope": "repeated_privileged_two_scenario_exact_slot_combat_potion_discard_only"
        if bridge.get("bridge_revision") == "potion_discard_v1"
        else "repeated_privileged_two_scenario_second_turn_public_combat_effects_only",
    }
    atomic_json(workspace / "in-progress.json", result)
    active = False
    try:
        for index, case in enumerate(cases, 1):
            if time.monotonic() - started > document["max_wall_seconds"] - 280:
                raise TimeoutError("Combat panel reached its finite launch allowance")
            print(
                f"Combat effect comparison {index}/8: {case['case_id']}; "
                "shared app, fresh benchmark profile.",
                flush=True,
            )
            active = True
            result["not_attempted_cases"] -= 1
            comparison = compare_combat_bridge(
                qualification, template, node=node, case=case, workspace=workspace / case["case_id"]
            )
            result["cases"].append({**case, "comparison": comparison})
            if comparison["status"] != "combat_comparison_pass":
                raise ValueError("Combat comparison failed; no next case follows")
            result["completed_cases"] += 1
            active = False
            atomic_json(workspace / f"progress-{index:02d}.json", result)
        if not repeated_combat_prefixes(result["cases"], workspace):
            raise ValueError("Repeated public combat facts or action semantics changed")
        result.update(status="combat_comparisons_pass", repeated_public_prefixes_identical=True)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(status="combat_comparisons_incomplete", error=str(error))
        result["failed_cases"] += int(active)
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "batch.json", result)
    (workspace / "in-progress.json").unlink()
    return result


def verify_combat_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document, cases, template, workspace = _combat_batch(qualification, path)
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("status") != "combat_comparisons_pass"
        or batch.get("completed_cases") != 8
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("repeated_public_prefixes_identical") is not True
        or batch.get("training_allowed") is not False
        or batch.get("full_run_attempts") != 0
        or batch.get("optimizer_steps") != 0
        or [{key: row[key] for key in ("case_id", "seed", "scenario")} for row in batch["cases"]]
        != cases
    ):
        raise ValueError("Expected the complete frozen eight-case combat panel")
    audits = []
    for case in batch["cases"]:
        directory = workspace / case["case_id"]
        comparison = _hashed(directory / "comparison.json")
        if (
            comparison != case["comparison"]
            or comparison.get("seed") != case["seed"]
            or comparison.get("scenario") != case["scenario"]
            or comparison.get("workspace") != str(directory.relative_to(qualification.root))
            or comparison.get("status") != "combat_comparison_pass"
        ):
            raise ValueError("Combat case binding changed")
        audit = verify_combat_bridge(qualification, template, directory, node=node)
        if audit != comparison["saved_verification"]:
            raise ValueError("Combat raw audit changed")
        audits.append(audit)
    if not repeated_combat_prefixes(batch["cases"], workspace):
        raise ValueError("Repeated raw public combat prefixes changed")
    result = {
        "schema_version": "engine-combat-batch-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "verified_cases": 8,
        "case_verification_ids": [row["report_id"] for row in audits],
        "repeated_public_prefixes_identical": True,
        "games_launched": 0,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
    }
    result["report_id"] = manifest_identifier(result)
    return result
