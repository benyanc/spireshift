"""Private exact-assembly source inspection, launched as a separate owner stage.

Extracted proprietary material never enters Git, policies or training data.
Successful extraction is not a mechanics or simulator-parity pass.
"""

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
    _sandbox,
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


def inspect_game_source(qualification: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-source-config-v1"
        or document.get("stage") != "private_source_inspection_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
    ):
        raise ValueError("Expected an exact-game private source inspection configuration")
    config_id = manifest_identifier(document)
    cap = document.get("max_wall_seconds")
    if type(cap) is not int or not 60 <= cap <= 1800:
        raise ValueError("Private source inspection requires a cap of at most 30 minutes")
    native_path = qualification.root / document["native_config"]
    if native_path.resolve().parent != path.resolve().parent:
        raise ValueError("Native inspection tool configuration must be beside this configuration")
    native = load_native_qualification_config(native_path, qualification)
    _require_native_launch_support()
    archive, verified = _verified_archive(native)
    tool = native.document["decompiler"]
    for item in tool["files"]:
        if _sha_file(_private_path(qualification.root, item["path"])) != item["sha256"]:
            raise ValueError("Pinned decompiler changed before source inspection")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="source-", dir=workspace))
    atomic_json(attempt / "in-progress.json", {"config_id": config_id, "training_allowed": False})
    try:
        user_data = Path.home() / "Library/Application Support"
        sandbox = attempt / "read-only-game.sb"
        sandbox.write_text(
            _sandbox(
                [
                    archive.parent,
                    user_data / "SlayTheSpire2",
                    user_data / "Steam/steamapps",
                    user_data / "Steam/userdata",
                ]
            ),
            encoding="utf-8",
        )
        data = archive / GAME_RELATIVE / DATA_RELATIVE
        output = attempt / "decompiled"
        executable = _private_path(qualification.root, tool["executable"])
        command = [
            "/usr/bin/sandbox-exec",
            "-f",
            str(sandbox),
            str(executable),
            "--disable-updatecheck",
            "--project",
            "--nested-directories",
            "--referencepath",
            str(data),
            "--outputdir",
            str(output),
            str(data / "sts2.dll"),
        ]
        environment = dict(os.environ)
        environment["DOTNET_ROLL_FORWARD"] = "Major"
        started = time.monotonic()
        capped = False
        with (attempt / "stdout.log").open("wb") as out, (attempt / "stderr.log").open("wb") as err:
            child = subprocess.Popen(
                command,
                env=environment,
                stdout=out,
                stderr=err,
                cwd=qualification.root,
                start_new_session=True,
            )
            try:
                child.wait(timeout=cap)
            except subprocess.TimeoutExpired:
                capped = True
            finally:
                _stop_child(child)
        inventory = _inventory(output) if output.is_dir() else []
        sources = [item for item in inventory if item["path"].endswith(".cs")]
        archive_after = verify_game_archive(qualification, archive)
        tools_unchanged = all(
            _sha_file(_private_path(qualification.root, item["path"])) == item["sha256"]
            for item in tool["files"]
        )
        checks = {
            "tool_completed": child.returncode == 0 and not capped,
            "sources_present": bool(sources),
            "project_created": any(item["path"].endswith(".csproj") for item in inventory),
            "archive_still_valid": archive_after["valid"],
            "tools_unchanged": tools_unchanged,
        }
        return _finish(
            attempt,
            {
                "schema_version": "engine-private-source-inspection-v1",
                "config_id": config_id,
                "qualification_config_id": qualification.config_id,
                "assembly_sha256": qualification.target["assembly_sha256"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "decompiler_version": tool["version"],
                "checks": checks,
                "status": "private_source_extraction_complete"
                if all(checks.values())
                else "private_source_extraction_incomplete",
                "process": {
                    "returncode": child.returncode,
                    "timed_out": capped,
                    "wall_seconds": time.monotonic() - started,
                },
                "source_files": len(sources),
                "files": len(inventory),
                "bytes": sum(item["bytes"] for item in inventory),
                "source_inventory_id": manifest_identifier(inventory),
                "inventory": inventory,
                "output": str(output),
                "command": command,
                "games_launched": 0,
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "mechanics_qualified": False,
                "training_allowed": False,
                "claim_scope": (
                    "private_exact_assembly_source_extraction_"
                    "not_runtime_behavior_or_complete_mechanics"
                ),
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise
