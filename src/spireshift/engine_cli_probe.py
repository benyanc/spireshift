"""Short native rest and public projection regressions; never training admission."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _stop_child
from spireshift.engine_native import (
    DATA_RELATIVE,
    _failure,
    _finish,
    _private_path,
    _require_native_launch_support,
    _running_games,
    _sandbox,
    _shared_snapshot,
    _verified_archive,
    load_native_qualification_config,
)
from spireshift.engine_qualification import (
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json


def verify_local_build_report(
    document: dict[str, Any], build_config: dict[str, Any], qualification: EngineQualificationConfig
) -> dict[str, Any]:
    """Refuse stale successes and any repair, compiler, or game identity drift."""
    body = {
        key: value for key, value in document.items() if key not in {"report_id", "report_path"}
    }
    if (
        manifest_identifier(body) != document.get("report_id")
        or document.get("schema_version") != "engine-cli-build-v2"
        or document.get("status") != "candidate_built_unqualified"
        or document.get("config_id") != manifest_identifier(build_config)
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("process", {}).get("returncode") != 0
        or document.get("process", {}).get("timed_out") is not False
    ):
        raise ValueError("A verified exact local repaired CLI build is required before probing")
    builds = document.get("build", {}).get("repaired", [])
    if not isinstance(builds, list) or len(builds) != 2:
        raise ValueError("The repaired CLI requires two matching fresh builds")
    for build in builds:
        if any(
            build.get(key) != expected
            for key, expected in build_config["expected_repaired"].items()
        ):
            raise ValueError("Repaired CLI build no longer matches its frozen local pins")
    return dict(builds[0])


def probe_cli_rest(
    qualification: EngineQualificationConfig, path: Path, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    projected = document.get("schema_version") == "engine-cli-rest-projection-config-v1"
    stage = (
        "privileged_named_rest_public_projection_only"
        if projected
        else "privileged_named_rest_scenarios_only"
    )
    if (
        document.get("schema_version")
        not in {"engine-cli-rest-probe-config-v1", "engine-cli-rest-projection-config-v1"}
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("stage") != stage
        or document.get("character") != "Ironclad"
        or document.get("ascension") != 8
        or document.get("training_allowed") is not False
        or type(document.get("max_wall_seconds")) is not int
        or not 30 <= document["max_wall_seconds"] <= 180
    ):
        raise ValueError("Expected a short Ironclad/A8 rest-only native qualification config")
    _require_native_launch_support()
    if _running_games():
        raise ValueError("Close the existing game before the isolated native rest check")
    if not node.is_file():
        raise ValueError("Pass the current local Node runtime")
    build_path = qualification.root / document["build_config"]
    if build_path.resolve().parent != path.resolve().parent:
        raise ValueError("Local build configuration must be beside the probe configuration")
    build_config = json.loads(build_path.read_text())
    report = json.loads(_private_path(qualification.root, document["build_report"]).read_text())
    build = verify_local_build_report(report, build_config, qualification)
    if report["report_id"] != document["build_report_id"]:
        raise ValueError("Rest probe must bind the exact completed local build report")
    helper = qualification.root / (
        "scripts/probe-engine-cli-rest-projection.mjs"
        if projected
        else "scripts/probe-engine-cli-rest.mjs"
    )
    library = qualification.root / "scripts/engine-cli-local-build.mjs"
    if (
        _sha_file(helper) != document["helper_sha256"]
        or _sha_file(library) != build_config["helper_sha256"]
        or _sha_file(qualification.root / build_config["local_patch"])
        != build_config["local_patch_sha256"]
    ):
        raise ValueError("The pinned rest probe, build helper, or source patch changed")
    projection, sdk_before = None, None
    if projected:
        projection, sdk_before = verify_projection_inputs(qualification, document)
    native = load_native_qualification_config(
        qualification.root / build_config["native_config"], qualification
    )
    archive, verified = _verified_archive(native)
    candidate = Path(build["candidate_directory"])
    candidate = _private_path(qualification.root, str(candidate.relative_to(qualification.root)))
    artifact = candidate / "src/Sts2Headless/bin/Release/net9.0/Sts2Headless.dll"
    for file, expected in (
        (artifact, build["artifact_sha256"]),
        (artifact.parent / "GodotSharp.dll", build["godot_stub_sha256"]),
        (candidate / "lib/sts2.dll", build["runtime_sts2_sha256"]),
        (candidate / "lib/sts2.dll.original", build["runtime_sts2_sha256"]),
    ):
        if _sha_file(file) != expected:
            raise ValueError("Repaired candidate disk assemblies no longer match the saved build")
    for folder, entries in (
        (candidate / "lib", build["game_dependencies"]),
        (artifact.parent, build["runtime_dependencies"]),
    ):
        if any(_sha_file(folder / item["path"]) != item["sha256"] for item in entries):
            raise ValueError("Candidate runtime dependency changed")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="rest-", dir=workspace))
    atomic_json(attempt / "in-progress.json", {"training_allowed": False})
    user_data = Path.home() / "Library/Application Support"
    shared = user_data / "SlayTheSpire2"
    shared_before = _shared_snapshot(shared)
    candidate_before = _inventory(candidate)
    try:
        if candidate_before != report["private_candidate_inventory"]:
            raise ValueError("Candidate files changed since the verified local build")
        profile = attempt / "private-profile"
        profile.mkdir()
        (attempt / "profile-isolation.sb").write_text(
            _sandbox(
                [
                    shared,
                    user_data / "Godot/app_userdata/SlayTheSpire2",
                    archive.parent,
                    user_data / "Steam/steamapps",
                    user_data / "Steam/userdata",
                    candidate,
                ]
            )
        )
        source = next(
            item for item in qualification.document["sources"] if item["name"] == "headless"
        )
        spec = {
            "headless_root": str(_private_path(qualification.root, source["path"])),
            "attempt": str(attempt),
            "candidate": str(candidate),
            "artifact": str(artifact),
            "game_data": str(archive / GAME_RELATIVE / DATA_RELATIVE),
            "profile": str(profile),
            "dotnet": report["build"]["toolchain"]["dotnet_command"],
            "expected": build_config["expected_repaired"],
            "managed_runtime_version": document["managed_runtime_version"],
        }
        if projected:
            spec["projection"] = projection
            spec["environment_fingerprint"] = manifest_identifier(
                {"build_report_id": report["report_id"], "projection_config": document}
            )
        environment = dict(os.environ)
        environment["DOTNET_ROLL_FORWARD"] = "Major"
        environment.pop("STS2_HEADLESS_QUIET", None)
        started = time.monotonic()
        timed_out = False
        with (attempt / "stdout.log").open("wb") as out, (attempt / "stderr.log").open("wb") as err:
            child = subprocess.Popen(
                [str(node), str(helper)],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                cwd=qualification.root,
                env=environment,
                start_new_session=True,
            )
            try:
                child.communicate(json.dumps(spec).encode(), timeout=document["max_wall_seconds"])
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                _stop_child(child)
        result_path = attempt / "rest-probe.json"
        probe = (
            json.loads(result_path.read_text()) if result_path.is_file() else {"status": "capped"}
        )
        shared_after = _shared_snapshot(shared)
        archive_after = verify_game_archive(qualification, archive)
        passed_status = (
            "rest_public_projection_regression_pass" if projected else "rest_native_regression_pass"
        )
        checks = {
            "native_rest_regressions_pass": probe.get("status") == passed_status,
            "same_private_candidate_unchanged": _inventory(candidate) == candidate_before,
            "shared_profile_unchanged": shared_before == shared_after,
            "frozen_archive_unchanged": archive_after["valid"],
            "uncapped_successful_process": not timed_out and child.returncode == 0,
        }
        if projected:
            assert projection is not None
            checks["projection_identity_bound"] = probe.get("projection_identity") == {
                key: projection[key]
                for key in (
                    "source_revision",
                    "source_sha256",
                    "patch_sha256",
                    "patched_source_sha256",
                    "sdk_inventory_id",
                )
            }
            checks["pinned_sdk_tree_unchanged"] = (
                _inventory(Path(projection["node_modules"])) == sdk_before
            )
        return _finish(
            attempt,
            {
                "schema_version": "engine-cli-rest-projection-probe-v1"
                if projected
                else "engine-cli-rest-probe-v1",
                "config_id": manifest_identifier(document),
                "qualification_config_id": qualification.config_id,
                "build_report_id": report["report_id"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "shared_profile_sentinel": {"before": shared_before, "after": shared_after},
                "candidate_lineage": build_config["candidate_lineage"],
                "character": "Ironclad",
                "ascension": 8,
                "status": passed_status if all(checks.values()) else "rest_probe_incomplete",
                "checks": checks,
                "probe": probe,
                "process": {
                    "returncode": child.returncode,
                    "timed_out": timed_out,
                    "wall_seconds": time.monotonic() - started,
                },
                "profile": str(profile),
                "managed_runtime_version": document["managed_runtime_version"],
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "shipped_cross_host_parity": False,
                "training_allowed": False,
                "claim_scope": (
                    "named_privileged_managed_native_rest_public_projection_not_shipped_parity"
                    if projected
                    else "named_privileged_managed_native_rest_regressions_not_shipped_parity"
                ),
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise


def verify_projection_inputs(
    qualification: EngineQualificationConfig, document: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bind the exact MIT hook, public surface helper and installed SDK without downloads."""
    pins = document["projection"]
    headless = next(
        item for item in qualification.document["sources"] if item["name"] == "headless"
    )
    if pins.get("source_revision") != headless["commit"]:
        raise ValueError("Rest projection must use the qualification's pinned Headless revision")
    source = (
        _private_path(qualification.root, headless["path"]) / "src/managed-player-environment.mjs"
    )
    patch = qualification.root / "patches/engine/sts2-headless-player-projection-v1.patch"
    if _sha_file(source) != pins["source_sha256"] or _sha_file(patch) != pins["patch_sha256"]:
        raise ValueError("Rest projection source or hook patch changed")
    for name in (
        "engine-player-projection.mjs",
        "engine-rest-surface.mjs",
        "probe-engine-cli-rest.mjs",
    ):
        if _sha_file(qualification.root / "scripts" / name) != pins["helpers_sha256"].get(name):
            raise ValueError("A pinned rest projection dependency changed")
    sdk = _private_path(qualification.root, pins["node_modules"])
    inventory = _inventory(sdk)
    if manifest_identifier({"files": inventory}) != pins["sdk_inventory_id"]:
        raise ValueError("Pinned SDK/dependency inventory changed; do not install substitutes")
    return {
        **{
            key: pins[key]
            for key in (
                "source_revision",
                "source_sha256",
                "patch_sha256",
                "patched_source_sha256",
                "sdk_inventory_id",
            )
        },
        "patch": str(patch),
        "node_modules": str(sdk),
    }, inventory
