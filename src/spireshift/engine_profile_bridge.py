"""Finite benchmark-profile and public-text comparisons, using the existing shared app."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import verify_projection_inputs
from spireshift.engine_connector import (
    _probe_connector_private,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _private_path, _running_games
from spireshift.engine_profile import (
    profile_inputs,
    run_native_profile_case,
    validate_profile_description_report,
    verify_benchmark_progress,
)
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_working_app import (
    load_working_app_policy,
    preflight_working_app,
    verify_working_app_receipt,
)
from spireshift.full_run_experience import atomic_json

HELPERS = {
    "project-engine-profile-state-v1.mjs",
    "engine-profile-text-contract-v1.mjs",
    "engine-profile-shipped-probe-v1.mjs",
    "verify-engine-profile-saved-v1.mjs",
    "engine-menu-probe.mjs",
    "engine-checkpoint-shipped-probe.mjs",
    "engine-rest-bridge-contract.mjs",
    "engine-journey-contract-v2.mjs",
}


def profile_bridge_inputs(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-profile-bridge-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or set(document.get("helpers_sha256", {})) != HELPERS
        or any(
            _sha_file(qualification.root / "scripts" / name) != document["helpers_sha256"][name]
            for name in HELPERS
        )
    ):
        raise ValueError("Expected a pinned scoped profile/text bridge recipe")
    native_path = qualification.root / document["native_profile_config"]
    native = json.loads(native_path.read_text())
    if manifest_identifier(native) != document["native_profile_config_id"]:
        raise ValueError("Profile/text oracle recipe changed")
    return document, native_path, native


def compare_profile_bridge(
    qualification: EngineQualificationConfig,
    path: Path,
    *,
    node: Path,
    seed: str | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    document, native_path, native_config = profile_bridge_inputs(qualification, path)
    selected_seed = seed or document["seed"]
    directory = workspace or _private_path(qualification.root, document["workspace"])
    if directory.exists():
        raise FileExistsError("Preserve this profile/text comparison; no automatic restart")
    directory.mkdir(parents=True)
    result: dict[str, Any] = {
        "schema_version": "engine-profile-bridge-v1",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "seed": selected_seed,
        "status": "profile_comparison_incomplete",
        "privileged_fixture": True,
        "training_allowed": False,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "workspace": str(directory.relative_to(qualification.root)),
    }
    try:
        native = run_native_profile_case(
            qualification, native_path, directory / "native", selected_seed
        )
        result["native_report_id"] = native["report_id"]
        raw = json.loads((directory / "native/private-check.json").read_text())
        projection, _ = verify_projection_inputs(qualification, native_config)
        attempt = directory / "projection"
        attempt.mkdir()
        source = next(row for row in qualification.document["sources"] if row["name"] == "headless")
        canonical_path = directory / "public-inspection.json"
        process = subprocess.run(
            [str(node), str(qualification.root / "scripts/project-engine-profile-state-v1.mjs")],
            input=json.dumps(
                {
                    "headless_root": str(qualification.root / source["path"]),
                    "projection": projection,
                    "attempt": str(attempt),
                    "native_state": str(directory / "native/private-starting-state.json"),
                    "native_pid": raw["process_id"],
                    "environment_fingerprint": native["report_id"],
                    "output": str(canonical_path),
                }
            ),
            text=True,
            capture_output=True,
            timeout=30,
        )
        (attempt / "stdout.log").write_text(process.stdout)
        (attempt / "stderr.log").write_text(process.stderr)
        if process.returncode:
            raise ValueError("Saved native profile projection failed; preserve diagnostics")
        canonical = json.loads(canonical_path.read_text())
        snapshot_path = directory / "public-snapshot.json"
        atomic_json(snapshot_path, canonical["snapshot"])
        policy = load_working_app_policy(
            qualification.root / document["working_app_config"], qualification
        )
        if policy.config_id != document["working_app_config_id"]:
            raise ValueError("Profile bridge working-app policy changed")
        connector = load_connector_qualification_config(
            qualification.root / document["connector_config"], qualification
        )
        fixture = {
            "workspace": str((directory / "shipped").relative_to(qualification.root)),
            "comparison_mode": "profile_text_v1",
            "seed": selected_seed,
            "checkpoint_path": str(directory / "native/native-checkpoint.save"),
            "checkpoint_sha256": native["checkpoint_sha256"],
            "snapshot_path": str(snapshot_path),
            "canonical_path": str(canonical_path),
            "benchmark_progress": str(
                (directory / "native/benchmark-progress.save").relative_to(qualification.root)
            ),
            "profile_policy": native_config["profile_policy"],
            "profile_policy_id": native_config["profile_policy_id"],
        }
        shipped = _probe_connector_private(
            connector, node=node, fixture=fixture, retain_working_game=False, working_app=policy
        )
        atomic_json(directory / "shipped-report.json", shipped)
        result.update(shipped_report_id=shipped["report_id"], working_app=shipped["working_app"])
        if shipped["verdict"]["status"] != "shipped_checkpoint_input_pass":
            raise ValueError("Shipped benchmark profile/text comparison failed")
        result["status"] = "profile_comparison_pass"
        result["saved_verification"] = verify_profile_bridge(
            qualification, path, directory, node=node
        )
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        result.update(status="profile_comparison_incomplete", error=str(error))
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(directory / "comparison.json", result)
    return result


def verify_profile_bridge(
    qualification: EngineQualificationConfig, path: Path, directory: Path, *, node: Path
) -> dict[str, Any]:
    document, native_path, _ = profile_bridge_inputs(qualification, path)
    native_config, profile, candidate, runtime, localization, build = profile_inputs(
        qualification, native_path
    )
    native = _hashed(directory / "native/native-profile-case.json")
    raw_path = directory / "native/private-check.json"
    if native["raw_report_sha256"] != _sha_file(raw_path):
        raise ValueError("Native profile oracle record changed")
    raw = json.loads(raw_path.read_text())
    validate_profile_description_report(raw, build, native["seed"], profile)
    verify_benchmark_progress(directory / "native/benchmark-progress.save", profile)
    for name, key in (
        ("native-checkpoint.save", "checkpoint_sha256"),
        ("private-starting-state.json", "native_state_sha256"),
    ):
        if _sha_file(directory / "native" / name) != native[key]:
            raise ValueError("Native profile checkpoint or observation changed")
    shipped = _hashed(directory / "shipped-report.json")
    if (
        shipped.get("qualification_config_id") != qualification.config_id
        or shipped.get("verdict", {}).get("status") != "shipped_checkpoint_input_pass"
        or shipped.get("training_allowed") is not False
        or any(value is not True for value in shipped["checks"].values())
    ):
        raise ValueError("Incomplete saved shipped profile checks")
    receipt = shipped["working_app"]
    policy = load_working_app_policy(
        qualification.root / document["working_app_config"], qualification
    )
    attempt = Path(receipt["attempt"])
    if attempt.parent != directory / "shipped":
        raise ValueError("Profile app receipt belongs to another comparison")
    verify_working_app_receipt(policy, receipt, attempt=attempt, archive_id=shipped["archive_id"])
    consent = shipped.get("profile_settings_consent", {}).get("benchmark_profile", {})
    if consent != {
        "profile_policy_id": manifest_identifier(profile),
        "progress_sha256": profile["progress_sha256"],
        "fresh_tutorials": True,
    }:
        raise ValueError("Shipped benchmark profile was not bound before launch")
    process = subprocess.run(
        [str(node), str(qualification.root / "scripts/verify-engine-profile-saved-v1.mjs")],
        input=json.dumps(
            {
                "canonical": str(directory / "public-inspection.json"),
                "shipped": str(directory / "shipped-report.json"),
                "native": str(raw_path),
            }
        ),
        capture_output=True,
        text=True,
        timeout=15,
    )
    if process.returncode:
        raise ValueError("Saved profile/text verification failed: " + process.stderr[-500:])
    verified = json.loads(process.stdout)
    result = {
        **verified,
        "schema_version": "engine-profile-saved-verification-v1",
        "native_report_id": native["report_id"],
        "shipped_report_id": shipped["report_id"],
        "canonical_sha256": _sha_file(directory / "public-inspection.json"),
        "verifier_sha256": _sha_file(
            qualification.root / "scripts/verify-engine-profile-saved-v1.mjs"
        ),
    }
    result["report_id"] = manifest_identifier(result)
    return result


def validate_profile_cases(document: dict[str, Any]) -> list[dict[str, str]]:
    cases = document.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != 8
        or any(
            not isinstance(row, dict)
            or set(row) != {"case_id", "seed"}
            or not re.fullmatch(r"[a-z0-9-]{1,64}", str(row["case_id"]))
            or not re.fullmatch(r"[A-Z0-9]{1,64}", str(row["seed"]))
            for row in cases
        )
        or len({row["case_id"] for row in cases}) != 8
        or len({row["seed"] for row in cases}) != 4
        or any(
            sum(row["seed"] == seed for row in cases) != 2
            for seed in {row["seed"] for row in cases}
        )
    ):
        raise ValueError("Expected four fixed profile seeds, each explicitly repeated twice")
    return [dict(row) for row in cases]


def _profile_batch(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], list[dict[str, str]], Path, Path]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-profile-bridges-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 900
    ):
        raise ValueError("Expected the separately frozen fifteen-minute profile panel")
    cases = validate_profile_cases(document)
    template_path = qualification.root / document["template"]
    template = json.loads(template_path.read_text())
    if manifest_identifier(template) != document["template_id"]:
        raise ValueError("Profile batch template changed")
    return document, cases, template_path, _private_path(qualification.root, document["workspace"])


def preflight_profile_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    started = time.monotonic()
    document, cases, template_path, workspace = _profile_batch(qualification, path)
    if workspace.exists() or _running_games() or not node.is_file():
        raise ValueError(
            "Preserve previous results, close the game and pass the local Node runtime"
        )
    template, native_path, native_config = profile_bridge_inputs(qualification, template_path)
    profile_inputs(qualification, native_path)
    verify_projection_inputs(qualification, native_config)
    load_connector_qualification_config(
        qualification.root / template["connector_config"], qualification
    )
    policy = load_working_app_policy(
        qualification.root / template["working_app_config"], qualification
    )
    if policy.config_id != template["working_app_config_id"]:
        raise ValueError("Working-app policy changed")
    pool = preflight_working_app(policy)
    minimum = 500_000_000 if (policy.slot / "game").exists() else 3_500_000_000
    if shutil.disk_usage(qualification.root).free < minimum:
        raise ValueError("Insufficient free space for the bounded profile panel")
    result = {
        "schema_version": "engine-profile-preflight-v1",
        "status": "profile_preflight_pass",
        "config_id": manifest_identifier(document),
        "planned_cases": len(cases),
        "independent_seeds": 4,
        "working_app_pool": pool,
        "minimum_free_bytes": minimum,
        "workspace_created": False,
        "games_launched": 0,
        "training_allowed": False,
        "wall_seconds": time.monotonic() - started,
    }
    result["report_id"] = manifest_identifier(result)
    return result


def compare_profile_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    preflight = preflight_profile_bridges(qualification, path, node=node)
    document, cases, template_path, workspace = _profile_batch(qualification, path)
    workspace.mkdir(parents=True)
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": "engine-profile-bridges-v1",
        "status": "in_progress",
        "config_id": manifest_identifier(document),
        "qualification_config_id": qualification.config_id,
        "preflight": preflight,
        "planned_cases": 8,
        "completed_cases": 0,
        "failed_cases": 0,
        "not_attempted_cases": 8,
        "independent_seeds": 4,
        "cases": [],
        "privileged_fixture": True,
        "training_allowed": False,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
    }
    atomic_json(workspace / "in-progress.json", result)
    active = False
    try:
        for index, case in enumerate(cases, 1):
            if time.monotonic() - started > document["max_wall_seconds"] - 180:
                raise TimeoutError("Profile panel reached its finite launch allowance")
            print(
                f"Profile/text comparison {index}/8: {case['case_id']}; "
                "shared app, fresh benchmark profile.",
                flush=True,
            )
            active = True
            result["not_attempted_cases"] -= 1
            comparison = compare_profile_bridge(
                qualification,
                template_path,
                node=node,
                seed=case["seed"],
                workspace=workspace / case["case_id"],
            )
            result["cases"].append({**case, "comparison": comparison})
            if comparison["status"] != "profile_comparison_pass":
                raise ValueError("Profile/text comparison failed; no next case follows")
            result["completed_cases"] += 1
            active = False
            atomic_json(workspace / f"progress-{index:02d}.json", result)
        prefixes: dict[str, list[Any]] = {}
        for case in result["cases"]:
            facts = json.loads(
                (workspace / case["case_id"] / "public-inspection.json").read_text()
            )["facts"]
            prefixes.setdefault(case["seed"], []).append(facts)
        if any(values[0] != values[1] for values in prefixes.values()):
            raise ValueError("Repeated public benchmark profile/text facts changed")
        result.update(status="profile_comparisons_pass", repeated_public_prefixes_identical=True)
    except (ValueError, OSError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        result.update(status="profile_comparisons_incomplete", error=str(error))
        result["failed_cases"] += int(active)
    result["wall_seconds"] = time.monotonic() - started
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "batch.json", result)
    (workspace / "in-progress.json").unlink()
    return result


def verify_profile_bridges(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    document, cases, template_path, workspace = _profile_batch(qualification, path)
    batch = _hashed(workspace / "batch.json")
    if (
        batch.get("config_id") != manifest_identifier(document)
        or batch.get("status") != "profile_comparisons_pass"
        or batch.get("completed_cases") != 8
        or batch.get("failed_cases") != 0
        or batch.get("not_attempted_cases") != 0
        or batch.get("training_allowed") is not False
        or [{key: row[key] for key in ("case_id", "seed")} for row in batch["cases"]] != cases
    ):
        raise ValueError("Expected the complete frozen eight-case profile panel")
    audits = []
    prefixes: dict[str, list[Any]] = {}
    for case in batch["cases"]:
        directory = workspace / case["case_id"]
        comparison = _hashed(directory / "comparison.json")
        if (
            comparison != case["comparison"]
            or comparison.get("seed") != case["seed"]
            or comparison.get("workspace") != str(directory.relative_to(qualification.root))
        ):
            raise ValueError("Profile comparison binding changed")
        audit = verify_profile_bridge(qualification, template_path, directory, node=node)
        if audit != comparison["saved_verification"]:
            raise ValueError("Profile raw audit differs from the recorded result")
        audits.append(audit)
        prefixes.setdefault(case["seed"], []).append(
            json.loads((directory / "public-inspection.json").read_text())["facts"]
        )
    if any(values[0] != values[1] for values in prefixes.values()):
        raise ValueError("Repeated saved profile facts differ")
    result = {
        "schema_version": "engine-profile-batch-verification-v1",
        "valid": True,
        "batch_report_id": batch["report_id"],
        "verified_cases": 8,
        "case_verification_ids": [row["report_id"] for row in audits],
        "games_launched": 0,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "training_allowed": False,
    }
    result["report_id"] = manifest_identifier(result)
    return result
