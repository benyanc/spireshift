"""Reproducible, separately identified local Host build; no games or learning."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import (
    _stop_child,
    _verify_toolchain,
    load_connector_qualification_config,
)
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_native import _failure, _finish, _private_path, _verified_archive
from spireshift.engine_qualification import (
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json


def validate_connector_build_proposal(
    proposed: dict[str, Any], document: dict[str, Any], recipe_relative: str
) -> None:
    """Refuse copied historical lineage before creating a new build/toolchain."""
    if proposed.get("local_build") != {
        "build_config": recipe_relative,
        "build_config_id": manifest_identifier(document),
        "build_report": document["output_report"],
    }:
        raise ValueError("Local Host proposal must bind this exact recipe, report and patch")


def build_connector_candidate(
    qualification: EngineQualificationConfig, path: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-connector-build-config-v1"
        or document.get("stage") != "local_host_build_only_no_games"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
        or document.get("max_wall_seconds") != 180
        or document.get("source_revision") != "e0651024117d22bdeb95142766917103d87c0185"
    ):
        raise ValueError("Expected the scoped pinned local Connector build recipe")
    base_path = qualification.root / document["base_connector_config"]
    base = load_connector_qualification_config(base_path, qualification)
    base_tools = _verify_toolchain(base)
    archive, verified = _verified_archive(base.native)
    patch = qualification.root / document["patch"]
    if (
        patch.resolve().parent != qualification.root / "patches/engine"
        or patch.is_symlink()
        or _sha_file(patch) != document["patch_sha256"]
        or base.config_id != document["base_connector_config_id"]
    ):
        raise ValueError("The original Connector or scoped source patch changed")
    output_config = qualification.root / document["output_connector_config"]
    proposed = json.loads(output_config.read_text())
    load_connector_qualification_config(output_config, qualification)
    validate_connector_build_proposal(
        proposed, document, str(path.resolve().relative_to(qualification.root))
    )
    destination = _private_path(qualification.root, proposed["toolchain"])
    if destination.exists():
        raise FileExistsError("Preserve the existing local Host tools; do not rebuild in place")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="build-", dir=workspace))
    atomic_json(
        attempt / "in-progress.json",
        {"config_id": manifest_identifier(document), "training_allowed": False},
    )
    started = time.monotonic()
    environment = {**os.environ, "DOTNET_ROLL_FORWARD": "Major"}
    counter = 0

    def run(args: list[str], *, cwd: Path = qualification.root) -> str:
        nonlocal counter
        remaining = document["max_wall_seconds"] - (time.monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("The local Host build cap expired")
        log = attempt / f"step-{counter:03d}.log"
        counter += 1
        with log.open("wb") as error_log:
            child = subprocess.Popen(
                args,
                cwd=cwd,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=error_log,
                start_new_session=True,
            )
            try:
                output, _ = child.communicate(timeout=min(45, remaining))
            finally:
                _stop_child(child)
        if child.returncode != 0:
            raise ValueError(f"Local Host build command failed; preserve {log.name}")
        (attempt / f"step-{counter - 1:03d}-stdout.log").write_bytes(output)
        return output.decode()

    try:
        cache = _private_path(qualification.root, document["source_cache"])
        if not cache.exists():
            run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    "v1.1.0-rc.1",
                    document["source_url"],
                    str(cache),
                ]
            )
        if run(["git", "rev-parse", "HEAD"], cwd=cache).strip() != document["source_revision"]:
            raise ValueError("Pinned Connector source revision changed")
        if run(["git", "status", "--porcelain"], cwd=cache).strip():
            raise ValueError("Original Connector source has local edits")
        sdk = run(["dotnet", "--version"]).strip()
        if sdk != document["sdk_version"]:
            raise ValueError("Local Host compiler version changed")
        identities = []
        roots = []
        data = (
            archive / GAME_RELATIVE / "SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64"
        )
        for index in (1, 2):
            source = attempt / f"source-{index}"
            roots.append(source)
            run(["git", "clone", "--no-hardlinks", str(cache), str(source)])
            run(["git", "remote", "set-url", "origin", document["source_url"]], cwd=source)
            run(["git", "apply", "--whitespace=error-all", str(patch)], cwd=source)
            run(["git", "add", "host"], cwd=source)
            commit_env = {
                "GIT_AUTHOR_NAME": "SpireShift Qualification",
                "GIT_AUTHOR_EMAIL": "qualification@spireshift.invalid",
                "GIT_COMMITTER_NAME": "SpireShift Qualification",
                "GIT_COMMITTER_EMAIL": "qualification@spireshift.invalid",
                "GIT_AUTHOR_DATE": document["commit_date"],
                "GIT_COMMITTER_DATE": document["commit_date"],
            }
            environment.update(commit_env)
            run(
                ["git", "-c", "commit.gpgsign=false", "commit", "-m", document["commit_message"]],
                cwd=source,
            )
            revision = run(["git", "rev-parse", "HEAD"], cwd=source).strip()
            if revision != proposed["connector"]["source_revision"]:
                raise ValueError("Local Host source commit differs from the frozen patch recipe")
            output_directory = source / "host/out"
            run(
                [
                    "dotnet",
                    "build",
                    str(source / "host/STS2Connector.Host.csproj"),
                    "-c",
                    "Release",
                    "-o",
                    str(output_directory),
                    "--no-incremental",
                    "--nologo",
                    f"-p:STS2GameDataDir={data}",
                    "-p:UseSharedCompilation=false",
                    "-p:Deterministic=true",
                    "-p:ContinuousIntegrationBuild=true",
                    f"-p:PathMap={source}=/_/sts2-connector",
                    f"-p:SourceRevision={revision}",
                ]
            )
            identity_output = run(
                [
                    "dotnet",
                    "run",
                    "--project",
                    str(source / "host/tools/STS2.ArtifactIdentity"),
                    "--",
                    str(output_directory / "STS2_MCP.dll"),
                ]
            )
            identity = json.loads(identity_output.strip().splitlines()[-1])
            if (
                identity["sha256"] != proposed["connector"]["artifact_sha256"]
                or identity["module_version_id"] != proposed["connector"]["artifact_mvid"]
            ):
                raise ValueError("Local Host binary differs from its separate frozen identity")
            identities.append(identity)
        if identities[0] != identities[1]:
            raise ValueError("Fresh local Host builds differ")
        archive_after = verify_game_archive(qualification, archive)
        if not archive_after["valid"] or archive_after["report_id"] != verified["report_id"]:
            raise ValueError("Frozen game changed during the local Host build")
        result = _finish(
            attempt,
            {
                "schema_version": "engine-connector-build-v1",
                "status": "local_connector_built_unqualified",
                "config_id": manifest_identifier(document),
                "qualification_config_id": qualification.config_id,
                "base_connector_config_id": base.config_id,
                "base_toolchain_report_id": base_tools["report_id"],
                "upstream_revision": document["source_revision"],
                "source_revision": proposed["connector"]["source_revision"],
                "patch_sha256": _sha_file(patch),
                "sdk_version": sdk,
                "fresh_builds": identities,
                "artifact": str(roots[0] / "host/out/STS2_MCP.dll"),
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "wall_seconds": time.monotonic() - started,
                "games_launched": 0,
                "optimizer_steps": 0,
                "training_allowed": False,
                "claim_scope": (
                    "reproduced_local_host_build_only_not_release_seal_or_mechanics_admission"
                ),
            },
        )
        atomic_json(qualification.root / document["output_report"], result)
        if proposed["local_build"]["build_config_id"] != manifest_identifier(document):
            raise ValueError("Local Host configuration does not bind this build recipe")
        # A separately inventoried local tree retains the original SDK and installer.
        shutil.copytree(base.private("toolchain"), destination)
        payload = destination / "release/payload"
        shutil.copy2(result["artifact"], payload / "STS2_MCP.dll")
        identity_body = json.loads((payload / "build-identity.json").read_text())
        identity_body.update(proposed["connector"])
        (payload / "build-identity.json").unlink()
        atomic_json(payload / "build-identity.json", identity_body)
        # An upstream runtime seal must never be represented as sealing this local artifact.
        (destination / "seal.download").unlink()
        (destination / "release/release-manifest.json").unlink()
        toolchain = {
            "schema_version": "engine-connector-toolchain-v1",
            "config_id": manifest_identifier(proposed),
            "local_build_report": document["output_report"],
            "local_build_report_id": result["report_id"],
            "upstream_toolchain_report_id": base_tools["report_id"],
            "authority": "exact_process_local_source_canary_unsealed_local_patch",
            "inventory": [
                row for row in _inventory(destination) if row["path"] != "toolchain.json"
            ],
            "games_launched": 0,
            "training_allowed": False,
        }
        toolchain["report_id"] = manifest_identifier(toolchain)
        (destination / "toolchain.json").unlink()
        atomic_json(destination / "toolchain.json", toolchain)
        _hashed(qualification.root / document["output_report"])
        return result
    except BaseException as error:
        _failure(attempt, error)
        raise
