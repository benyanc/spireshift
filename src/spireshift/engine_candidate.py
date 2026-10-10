"""Build the pinned same-game CLI candidate; never launch game episodes."""

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
    _failure,
    _finish,
    _private_path,
    _running_games,
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


def build_cli_candidate(
    qualification: EngineQualificationConfig, path: Path, node: Path
) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-cli-build-config-v1"
        or document.get("stage") != "build_only_no_games"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("training_allowed") is not False
    ):
        raise ValueError("Expected an exact-game build-only configuration")
    config_id = manifest_identifier(document)
    if (
        type(document.get("max_wall_seconds")) is not int
        or not 30 <= document["max_wall_seconds"] <= 240
    ):
        raise ValueError("CLI candidate build requires a short cap, at most four minutes")
    native_path = qualification.root / document["native_config"]
    if native_path.resolve().parent != path.resolve().parent:
        raise ValueError(
            "Native build prerequisite configuration must be beside this configuration"
        )
    native = load_native_qualification_config(native_path, qualification)
    if _running_games():
        raise ValueError("Close the existing game before the isolated CLI candidate build")
    if not node.is_file():
        raise ValueError("Pass the current local Node runtime with --node")
    archive, verified = _verified_archive(native)
    menu_path = _private_path(qualification.root, document["menu_report"])
    menu = json.loads(menu_path.read_text())
    body = {key: value for key, value in menu.items() if key not in {"report_id", "report_path"}}
    if (
        manifest_identifier(body) != menu.get("report_id")
        or menu.get("report_id") != document["menu_report_id"]
        or menu.get("qualification_config_id") != qualification.config_id
        or menu.get("verdict", {}).get("status") != "shipped_connector_menu_pass"
    ):
        raise ValueError("A verified same-game Connector menu pass is required before building")
    source = next(item for item in qualification.document["sources"] if item["name"] == "headless")
    root = _private_path(qualification.root, source["path"])
    manifest_file = root / "experiments/managed-exact/manifest.json"
    patch = root / "experiments/managed-exact/patches/sts2-cli-d11aa88-v01110.patch"
    if (
        _sha_file(manifest_file) != document["managed_manifest_sha256"]
        or _sha_file(patch) != document["source_patch_sha256"]
    ):
        raise ValueError("Pinned managed build manifest or source patch changed")
    manifest = json.loads(manifest_file.read_text())
    if manifest.get("upstream", {}).get("revision") != document["upstream_revision"]:
        raise ValueError("Managed candidate must use the exact CLI revision in its patch ledger")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="build-", dir=workspace))
    atomic_json(attempt / "in-progress.json", {"config_id": config_id, "training_allowed": False})
    try:
        environment = dict(os.environ)
        # Static fingerprint helper targets net9.0; this host has the .NET 10 SDK/runtime.
        # Record the setting, do not conceal compiler/runtime drift or relax artifact pins.
        environment["DOTNET_ROLL_FORWARD"] = "Major"
        spec = {
            "headless_root": str(root),
            "attempt": str(attempt),
            "game": str(archive / GAME_RELATIVE),
        }
        started = time.monotonic()
        timed_out = False
        with (attempt / "stdout.log").open("wb") as out, (attempt / "stderr.log").open("wb") as err:
            child = subprocess.Popen(
                [str(node), str(qualification.root / "scripts/build-engine-cli-candidate.mjs")],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                env=environment,
                cwd=qualification.root,
                start_new_session=True,
            )
            try:
                child.communicate(json.dumps(spec).encode(), timeout=document["max_wall_seconds"])
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                _stop_child(child)
        result_file = attempt / "candidate-build.json"
        built = (
            json.loads(result_file.read_text())
            if result_file.is_file()
            else {"status": "build_capped"}
        )
        archive_after = verify_game_archive(qualification, archive)
        passed = (
            built.get("status") == "candidate_built_unqualified"
            and child.returncode == 0
            and not timed_out
            and archive_after["valid"]
        )
        return _finish(
            attempt,
            {
                "schema_version": "engine-cli-build-v1",
                "config_id": config_id,
                "qualification_config_id": qualification.config_id,
                "menu_report_id": menu["report_id"],
                "managed_manifest_sha256": document["managed_manifest_sha256"],
                "source_patch_sha256": document["source_patch_sha256"],
                "upstream_revision": document["upstream_revision"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "status": "candidate_built_unqualified" if passed else "candidate_build_incomplete",
                "build": built,
                "process": {
                    "returncode": child.returncode,
                    "timed_out": timed_out,
                    "wall_seconds": time.monotonic() - started,
                },
                "helper_runtime_roll_forward": "Major",
                "node_version": subprocess.run(
                    [str(node), "--version"], capture_output=True, text=True, timeout=5, check=True
                ).stdout.strip(),
                "private_candidate_inventory": _inventory(attempt / "candidate")
                if (attempt / "candidate").is_dir()
                else [],
                "games_launched": 0,
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "mechanics_qualified": False,
                "training_allowed": False,
                "claim_scope": "exact_pinned_cli_build_only_not_runtime_or_semantic_parity",
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise
