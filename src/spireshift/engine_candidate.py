"""Build the pinned same-game CLI candidate; never launch game episodes."""

from __future__ import annotations

import json
import os
import re
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
    local = document.get("schema_version") == "engine-cli-build-config-v2"
    if (
        document.get("schema_version")
        not in {"engine-cli-build-config-v1", "engine-cli-build-config-v2"}
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
    local_fields: dict[str, Any] = {}
    helper = qualification.root / "scripts/build-engine-cli-candidate.mjs"
    if local:
        helper = qualification.root / "scripts/engine-cli-local-build.mjs"
        if document.get("candidate_lineage") not in {
            "spireshift_cli_rest_v1_local_toolchain",
            "spireshift_cli_selection_shop_v2_local_toolchain",
            "spireshift_cli_selection_shop_v3_local_toolchain",
            "spireshift_cli_combat_v4_local_toolchain",
            "spireshift_cli_content_v5_local_toolchain",
            "spireshift_cli_localization_v6_local_toolchain",
            "spireshift_cli_event_proceed_v7_local_toolchain",
            "spireshift_cli_save_restore_v8_local_toolchain",
            "spireshift_cli_potion_pricing_v9_local_toolchain",
            "spireshift_cli_shop_energy_v10_local_toolchain",
            "spireshift_cli_reward_rng_v11_local_toolchain",
            "spireshift_cli_bundle_choice_v12_local_toolchain",
            "spireshift_cli_profile_descriptions_v13_local_toolchain",
            "spireshift_cli_combat_observation_v14_local_toolchain",
            "spireshift_cli_combat_preview_v15_local_toolchain",
            "spireshift_cli_event_text_v16_local_toolchain",
            "spireshift_cli_event_text_v17_local_toolchain",
            "spireshift_cli_card_modifiers_v18_local_toolchain",
            "spireshift_cli_generated_choice_v19_local_toolchain",
            "spireshift_cli_native_run_v20_local_toolchain",
            "spireshift_cli_native_run_v21_local_toolchain",
            "spireshift_cli_native_run_v22_local_toolchain",
            "spireshift_cli_native_run_v23_local_toolchain",
            "spireshift_cli_native_run_v24_local_toolchain",
            "spireshift_cli_native_run_v27_local_toolchain",
            "spireshift_cli_native_run_v28_local_toolchain",
            "spireshift_cli_native_run_v29_local_toolchain",
            "spireshift_cli_native_run_v30_local_toolchain",
            "spireshift_cli_native_run_v31_local_toolchain",
            "spireshift_cli_native_run_v32_local_toolchain",
            "spireshift_cli_native_run_v33_local_toolchain",
            "spireshift_cli_native_run_v34_local_toolchain",
        }:
            raise ValueError("Repaired CLI requires its distinct local build lineage")
        patch_relative = Path(document.get("local_patch", ""))
        if (
            patch_relative.is_absolute()
            or ".." in patch_relative.parts
            or patch_relative.parts[:2] != ("patches", "engine")
        ):
            raise ValueError("Local CLI patch must be a repository-owned engine patch")
        patch_file = qualification.root / patch_relative
        if (
            patch_file.is_symlink()
            or _sha_file(patch_file) != document.get("local_patch_sha256")
            or _sha_file(helper) != document.get("helper_sha256")
        ):
            raise ValueError("Pinned local CLI patch or build helper changed")
        toolchain = document.get("expected_toolchain", {})
        if (
            not isinstance(toolchain, dict)
            or not re.fullmatch(r"\d+\.\d+\.\d+", str(toolchain.get("sdk_version", "")))
            or not re.fullmatch(r"\d+\.\d+\.\d+", str(toolchain.get("reference_version", "")))
            or not all(
                re.fullmatch(r"[0-9a-f]{64}", str(toolchain.get(key, "")))
                for key in ("csc_sha256", "reference_pack_id")
            )
        ):
            raise ValueError("Local CLI compiler and target reference pack must be pinned")
        for field in ("expected_baseline", "expected_repaired"):
            pins = document.get(field)
            if (
                not isinstance(pins, dict)
                or not re.fullmatch(r"[0-9a-f-]{36}", str(pins.get("artifact_mvid", "")))
                or not all(
                    re.fullmatch(r"[0-9a-f]{64}", str(pins.get(key, "")))
                    for key in (
                        "artifact_sha256",
                        "godot_stub_sha256",
                        "runtime_sts2_sha256",
                        "reference_pack_id",
                        "source_diff_id",
                        "runtime_dependencies_id",
                    )
                )
            ):
                raise ValueError("Both local CLI builds require complete frozen artifact pins")
        if document["expected_repaired"]["source_diff_id"] != document.get(
            "expected_source_diff_id"
        ):
            raise ValueError("Local combined source identity must match its repaired build pin")
        local_fields = {
            "clone_cache": str(_private_path(qualification.root, document["clone_cache"])),
            "local_patch": str(patch_file),
            "local_patch_sha256": document["local_patch_sha256"],
            "expected_source_diff_id": document["expected_source_diff_id"],
            "expected_toolchain": toolchain,
            "expected_baseline": document["expected_baseline"],
            "expected_repaired": document["expected_repaired"],
        }
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
            **local_fields,
        }
        started = time.monotonic()
        timed_out = False
        with (attempt / "stdout.log").open("wb") as out, (attempt / "stderr.log").open("wb") as err:
            child = subprocess.Popen(
                [str(node), str(helper)],
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
        expected_status = (
            "local_candidate_built_unqualified" if local else "candidate_built_unqualified"
        )
        passed = (
            built.get("status") == expected_status
            and child.returncode == 0
            and not timed_out
            and archive_after["valid"]
        )
        return _finish(
            attempt,
            {
                "schema_version": "engine-cli-build-v2" if local else "engine-cli-build-v1",
                "config_id": config_id,
                "qualification_config_id": qualification.config_id,
                "menu_report_id": menu["report_id"],
                "managed_manifest_sha256": document["managed_manifest_sha256"],
                "source_patch_sha256": document["source_patch_sha256"],
                "upstream_revision": document["upstream_revision"],
                "candidate_lineage": document.get("candidate_lineage", "upstream_binary_exact_pin"),
                "local_patch_sha256": document.get("local_patch_sha256"),
                "helper_sha256": _sha_file(helper),
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
