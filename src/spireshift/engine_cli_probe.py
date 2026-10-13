"""Short native interaction and public projection checks; never training admission."""

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
from spireshift.engine_localization import verify_native_localization
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
    qualification: EngineQualificationConfig, path: Path, node: Path, *, panel: str = "rest"
) -> dict[str, Any]:
    return _probe_cli_document(qualification, path, node, json.loads(path.read_text()), panel=panel)


def _probe_cli_document(
    qualification: EngineQualificationConfig,
    path: Path,
    node: Path,
    document: dict[str, Any],
    *,
    panel: str,
) -> dict[str, Any]:
    if panel not in {
        "rest",
        "shop",
        "combat",
        "checkpoint",
        "journey",
        "rest_bridge",
        "shop_bridge",
        "bundle",
        "bundle_bridge",
        "reward_bridge",
        "combat_bridge",
    }:
        raise ValueError("Only explicitly scoped native interaction panels are supported")
    projected = document.get("schema_version") == f"engine-cli-{panel}-projection-config-v1"
    revision = document.get("public_projection_revision", "rest_v1")
    if (
        projected
        and panel
        in {"combat", "checkpoint", "journey", "rest_bridge", "shop_bridge", "combat_bridge"}
        and revision != "combat_v4"
    ):
        raise ValueError("Combat public projection requires its explicit frozen revision")
    if panel in {"bundle", "bundle_bridge", "reward_bridge"} and (
        not projected or revision != "bundle_v5"
    ):
        raise ValueError("Bundle checks require the separately pinned bundle projection")
    if revision not in {
        "rest_v1",
        "selection_shop_v2",
        "selection_shop_v3",
        "combat_v4",
        "bundle_v5",
    } or (projected and panel == "shop" and revision == "rest_v1"):
        raise ValueError("Unknown public interaction projection revision")
    stage = (
        f"privileged_named_{panel}_public_projection_only"
        if projected
        else f"privileged_named_{panel}_scenarios_only"
    )
    if (
        document.get("schema_version")
        not in {f"engine-cli-{panel}-probe-config-v1", f"engine-cli-{panel}-projection-config-v1"}
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("stage") != stage
        or document.get("character") != "Ironclad"
        or document.get("ascension") != 8
        or document.get("training_allowed") is not False
        or type(document.get("max_wall_seconds")) is not int
        or not 30 <= document["max_wall_seconds"] <= 180
    ):
        raise ValueError(f"Expected a short Ironclad/A8 {panel}-only qualification config")
    if panel in {
        "checkpoint",
        "journey",
        "rest_bridge",
        "shop_bridge",
        "bundle_bridge",
        "reward_bridge",
    } and (
        not projected
        or not re.fullmatch(r"[A-Z0-9]{1,64}", str(document.get("seed", "")))
        or document.get("content_policy") != "native_all_unlocked"
    ):
        raise ValueError("Checkpoint bridge requires an explicit seed and native unlock policy")
    if panel == "rest_bridge":
        if document.get("rest_bridge", {}).get("scenario") not in {
            "tent-heal-cancel-smith",
            "tent-smith-cancel-heal",
        }:
            raise ValueError("Expected an explicitly named finite Miniature Tent rest fixture")
        for name in (
            "engine-rest-bridge-contract.mjs",
            "engine-journey-contract-v2.mjs",
            "engine-menu-probe.mjs",
        ):
            if _sha_file(qualification.root / "scripts" / name) != document.get(
                "bridge_helpers_sha256", {}
            ).get(name):
                raise ValueError("Pinned rest fixture helper changed")
    if panel == "shop_bridge":
        if document.get("shop_bridge", {}).get("scenario") not in {
            "ordinary-purchases-removal",
            "courier-restock-removal",
        }:
            raise ValueError("Expected one explicitly named finite shop fixture")
        names = {
            "engine-shop-bridge-contract.mjs",
            "engine-rest-bridge-contract.mjs",
            "engine-journey-contract-v2.mjs",
            "engine-menu-probe.mjs",
        }
        if set(document.get("bridge_helpers_sha256", {})) != names:
            raise ValueError("Complete frozen shop fixture helper inventory is required")
        for name in names:
            if (
                _sha_file(qualification.root / "scripts" / name)
                != document["bridge_helpers_sha256"][name]
            ):
                raise ValueError("Pinned shop fixture helper changed")
    if panel == "combat_bridge":
        from spireshift.engine_profile import load_profile_policy

        plan = document.get("combat_bridge", {})
        combat_revision = document.get("combat_bridge_revision", "v1")
        names = {
            f"engine-combat-bridge-contract-{combat_revision}.mjs",
            "engine-rest-bridge-contract.mjs",
            "engine-journey-contract-v2.mjs",
            "engine-menu-probe.mjs",
        }
        if (
            not projected
            or combat_revision not in {"v6", "v7"}
            or combat_revision == "v7"
            and document.get("combat_surface_revision") != "v2"
            or document.get("content_policy") != "native_benchmark_full_v1"
            or not re.fullmatch(r"[A-Z0-9]{1,64}", str(document.get("seed", "")))
            or plan.get("scenario")
            not in (
                {"discard-automatic", "discard-duplicate"}
                if combat_revision == "v7"
                else {"corruption", "temporary-stats"}
            )
            or plan.get("max_actions") != 20
            or plan.get("starting_option") not in {"Stone Humidifier", "Winged Boots"}
            or set(document.get("bridge_helpers_sha256", {})) != names
            or any(
                _sha_file(qualification.root / "scripts" / name)
                != document["bridge_helpers_sha256"][name]
                for name in names
            )
        ):
            raise ValueError("Expected a frozen public combat-effects fixture")
        policy = load_profile_policy(qualification.root / document["profile_policy"], qualification)
        if manifest_identifier(policy) != document.get("profile_policy_id"):
            raise ValueError("Combat fixture benchmark profile changed")
    if panel == "journey":
        plan = document.get("journey", {})
        journey_revision = document.get("journey_revision", "v1")
        if journey_revision not in {"v1", "v2"}:
            raise ValueError("Unknown first-combat journey revision")
        if plan.get("max_actions") != 12 or not isinstance(plan.get("starting_option"), str):
            raise ValueError("A frozen twelve-action first-combat journey is required")
        for name in (
            "engine-journey-contract-v2.mjs"
            if journey_revision == "v2"
            else "engine-journey-contract.mjs",
            "engine-menu-probe.mjs",
        ):
            if _sha_file(qualification.root / "scripts" / name) != document.get(
                "journey_helpers_sha256", {}
            ).get(name):
                raise ValueError("A pinned journey comparison helper changed")
    if panel == "bundle":
        seeds = document.get("bundle_seeds")
        if (
            document.get("content_policy") != "native_all_unlocked"
            or not isinstance(seeds, list)
            or len(seeds) != 2
            or any(
                not isinstance(seed, str) or not re.fullmatch(r"[A-Z0-9]{1,64}", seed)
                for seed in seeds
            )
            or len(set(seeds)) != 2
            or document.get("bundle_probe_revision", "v1") not in {"v1", "v2"}
        ):
            raise ValueError("Bundle checks require two explicit native A8 seeds")
    if panel == "bundle_bridge":
        if document.get("bundle_bridge_revision", "v1") not in {"v1", "v2", "v3"}:
            raise ValueError("Unknown bundle bridge helper revision")
        if type(document.get("bundle_bridge", {}).get("index")) is not int or document[
            "bundle_bridge"
        ]["index"] not in {0, 1}:
            raise ValueError("Bundle bridge requires an explicit current pack index")
        for name in (
            f"engine-bundle-bridge-contract-{document.get('bundle_bridge_revision', 'v1')}.mjs",
            "engine-rest-bridge-contract.mjs",
            "engine-journey-contract-v2.mjs",
            "engine-menu-probe.mjs",
        ):
            if _sha_file(qualification.root / "scripts" / name) != document.get(
                "bridge_helpers_sha256", {}
            ).get(name):
                raise ValueError("Pinned bundle bridge helper changed")
    if panel == "reward_bridge":
        if document.get("reward_bridge_revision", "v1") not in {"v1", "v2", "v3"}:
            raise ValueError("Unknown native reward projection revision")
        if document.get("reward_bridge", {}).get("scenario") not in {
            "calling-bell-claim-all",
            "calling-bell-claim-skip",
            "cauldron-fill-replace-skip",
            "cauldron-fill-skip",
        }:
            raise ValueError("Expected one explicitly named finite reward pickup fixture")
        names = {
            "engine-reward-bridge-contract-v1.mjs",
            "engine-shop-bridge-contract.mjs",
            "engine-rest-bridge-contract.mjs",
            "engine-journey-contract-v2.mjs",
            "engine-menu-probe.mjs",
            "engine-checkpoint-shipped-probe.mjs",
        }
        if document.get("reward_bridge_revision", "v1") in {"v2", "v3"}:
            names.add(
                "engine-reward-rendered-text-"
                + ("v1" if document["reward_bridge_revision"] == "v2" else "v2")
                + ".mjs"
            )
        if set(document.get("bridge_helpers_sha256", {})) != names or any(
            _sha_file(qualification.root / "scripts" / name)
            != document["bridge_helpers_sha256"][name]
            for name in names
        ):
            raise ValueError("Pinned reward fixture helper inventory changed")
    _require_native_launch_support()
    if _running_games():
        raise ValueError("Close the existing game before the isolated native interaction check")
    if not node.is_file():
        raise ValueError("Pass the current local Node runtime")
    build_path = qualification.root / document["build_config"]
    if build_path.resolve().parent != path.resolve().parent:
        raise ValueError("Local build configuration must be beside the probe configuration")
    build_config = json.loads(build_path.read_text())
    report = json.loads(_private_path(qualification.root, document["build_report"]).read_text())
    build = verify_local_build_report(report, build_config, qualification)
    if report["report_id"] != document["build_report_id"]:
        raise ValueError("Interaction probe must bind the exact completed local build report")
    helper_name = (
        f"probe-engine-cli-combat-bridge-{document.get('combat_bridge_revision', 'v1')}.mjs"
        if projected and panel == "combat_bridge"
        else f"probe-engine-cli-reward-bridge-{document.get('reward_bridge_revision', 'v1')}.mjs"
        if projected and panel == "reward_bridge"
        else f"probe-engine-cli-bundle-bridge-{document.get('bundle_bridge_revision', 'v1')}.mjs"
        if projected and panel == "bundle_bridge"
        else f"probe-engine-cli-bundle-{document.get('bundle_probe_revision', 'v1')}.mjs"
        if projected and panel == "bundle"
        else "probe-engine-cli-shop-bridge.mjs"
        if projected and panel == "shop_bridge"
        else "probe-engine-cli-rest-bridge.mjs"
        if projected and panel == "rest_bridge"
        else (
            "probe-engine-cli-journey-v2.mjs"
            if document.get("journey_revision") == "v2"
            else "probe-engine-cli-journey.mjs"
        )
        if projected and panel == "journey"
        else "probe-engine-cli-checkpoint-projection.mjs"
        if projected and panel == "checkpoint"
        else "probe-engine-cli-mechanics-projection-v4.mjs"
        if projected and revision == "combat_v4"
        else "probe-engine-cli-mechanics-projection-v3.mjs"
        if projected and revision == "selection_shop_v3"
        else "probe-engine-cli-mechanics-projection.mjs"
        if projected and revision == "selection_shop_v2"
        else f"probe-engine-cli-{panel}-projection.mjs"
        if projected
        else f"probe-engine-cli-{panel}.mjs"
    )
    helper = qualification.root / "scripts" / helper_name
    library = qualification.root / "scripts/engine-cli-local-build.mjs"
    if (
        _sha_file(helper) != document["helper_sha256"]
        or _sha_file(library) != build_config["helper_sha256"]
        or _sha_file(qualification.root / build_config["local_patch"])
        != build_config["local_patch_sha256"]
    ):
        raise ValueError("The pinned interaction probe, build helper, or source patch changed")
    projection, sdk_before = None, None
    if projected:
        projection, sdk_before = verify_projection_inputs(qualification, document)
    runtime, runtime_before = verify_probe_runtime(qualification, document)
    if (
        revision in {"selection_shop_v2", "selection_shop_v3", "combat_v4", "bundle_v5"}
        and runtime is None
    ):
        raise ValueError("Native selection hooks require the pinned game-matching runtime")
    localization = (
        verify_native_localization(qualification, document["native_localization"])
        if "native_localization" in document
        else None
    )
    if (
        build_config.get("candidate_lineage")
        in {
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
        }
        and localization is None
    ):
        raise ValueError("The native text host requires exact extracted game localization")
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
    attempt = Path(tempfile.mkdtemp(prefix=f"{panel}-", dir=workspace))
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
                    *([localization] if localization is not None else []),
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
            "dotnet": str(runtime / "dotnet")
            if runtime is not None
            else report["build"]["toolchain"]["dotnet_command"],
            "expected": build_config["expected_repaired"],
            "managed_runtime_version": document["managed_runtime_version"],
            "panel": panel,
            **(
                {"seed": document["seed"], "content_policy": document["content_policy"]}
                if panel
                in {
                    "checkpoint",
                    "journey",
                    "rest_bridge",
                    "shop_bridge",
                    "bundle_bridge",
                    "reward_bridge",
                    "combat_bridge",
                }
                else {}
            ),
            **({"journey": document["journey"]} if panel == "journey" else {}),
            **({"rest_bridge": document["rest_bridge"]} if panel == "rest_bridge" else {}),
            **({"shop_bridge": document["shop_bridge"]} if panel == "shop_bridge" else {}),
            **({"bundle_seeds": document["bundle_seeds"]} if panel == "bundle" else {}),
            **({"bundle_bridge": document["bundle_bridge"]} if panel == "bundle_bridge" else {}),
            **({"reward_bridge": document["reward_bridge"]} if panel == "reward_bridge" else {}),
            **(
                {
                    "combat_bridge": document["combat_bridge"],
                    "profile_progress_sha256": policy["progress_sha256"],
                }
                if panel == "combat_bridge"
                else {}
            ),
        }
        if projected:
            spec["projection"] = projection
            spec["environment_fingerprint"] = manifest_identifier(
                {"build_report_id": report["report_id"], "projection_config": document}
            )
        environment = dict(os.environ)
        environment["DOTNET_ROLL_FORWARD"] = "LatestPatch" if runtime is not None else "Major"
        environment.pop("STS2_HEADLESS_QUIET", None)
        environment.pop("STS2_NATIVE_LOCALIZATION", None)
        if localization is not None:
            environment["STS2_NATIVE_LOCALIZATION"] = str(localization)
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
        result_path = attempt / f"{panel}-probe.json"
        probe = (
            json.loads(result_path.read_text()) if result_path.is_file() else {"status": "capped"}
        )
        if localization is not None:
            verify_native_localization(qualification, document["native_localization"])
        shared_after = _shared_snapshot(shared)
        archive_after = verify_game_archive(qualification, archive)
        passed_status = (
            f"{panel}_public_projection_regression_pass"
            if projected
            else f"{panel}_native_regression_pass"
        )
        checks = {
            f"native_{panel}_regressions_pass": probe.get("status") == passed_status,
            "same_private_candidate_unchanged": _inventory(candidate) == candidate_before,
            "shared_profile_unchanged": shared_before == shared_after,
            "frozen_archive_unchanged": archive_after["valid"],
            "uncapped_successful_process": not timed_out and child.returncode == 0,
        }
        if runtime is not None:
            checks["pinned_managed_runtime_unchanged"] = _inventory(runtime) == runtime_before
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
                "schema_version": f"engine-cli-{panel}-projection-probe-v1"
                if projected
                else f"engine-cli-{panel}-probe-v1",
                "config_id": manifest_identifier(document),
                "qualification_config_id": qualification.config_id,
                "build_report_id": report["report_id"],
                "archive_verification_before": verified["report_id"],
                "archive_verification_after": archive_after["report_id"],
                "shared_profile_sentinel": {"before": shared_before, "after": shared_after},
                "candidate_lineage": build_config["candidate_lineage"],
                "character": "Ironclad",
                "ascension": 8,
                "status": passed_status if all(checks.values()) else f"{panel}_probe_incomplete",
                "checks": checks,
                "probe": probe,
                "process": {
                    "returncode": child.returncode,
                    "timed_out": timed_out,
                    "wall_seconds": time.monotonic() - started,
                },
                "profile": str(profile),
                "managed_runtime_version": document["managed_runtime_version"],
                **(
                    {"native_localization": document["native_localization"]}
                    if localization is not None
                    else {}
                ),
                **(
                    {"managed_runtime_inventory_id": document["managed_runtime"]["inventory_id"]}
                    if runtime is not None
                    else {}
                ),
                "full_run_attempts": 0,
                "optimizer_steps": 0,
                "shipped_cross_host_parity": False,
                "training_allowed": False,
                "claim_scope": (
                    f"named_privileged_managed_native_{panel}_public_projection_not_shipped_parity"
                    if projected
                    else f"named_privileged_managed_native_{panel}_regressions_not_shipped_parity"
                ),
            },
        )
    except BaseException as error:
        _failure(attempt, error)
        raise


def verify_probe_runtime(
    qualification: EngineQualificationConfig, document: dict[str, Any]
) -> tuple[Path | None, list[dict[str, Any]] | None]:
    """Separate the build SDK from the exact managed runtime used by native game hooks."""
    pins = document.get("managed_runtime")
    if pins is None:
        return None, None
    if (
        not isinstance(pins, dict)
        or pins.get("version") != "9.0.7"
        or document.get("managed_runtime_version") != pins["version"]
        or pins.get("roll_forward") != "LatestPatch"
    ):
        raise ValueError("Expected the explicitly pinned game-matching managed runtime")
    runtime = _private_path(qualification.root, pins["directory"])
    inventory = _inventory(runtime)
    if (
        manifest_identifier({"files": inventory}) != pins["inventory_id"]
        or _sha_file(runtime / "dotnet") != pins["dotnet_sha256"]
    ):
        raise ValueError("Pinned managed runtime files changed")
    return runtime, inventory


def verify_projection_inputs(
    qualification: EngineQualificationConfig, document: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bind the exact MIT hook, public surface helper and installed SDK without downloads."""
    if "combat_surface_revision" in document and (
        document.get("combat_surface_revision") != "v2"
        or document.get("combat_bridge_revision") != "v7"
        or document.get("schema_version") != "engine-cli-combat_bridge-projection-config-v1"
    ):
        raise ValueError("Explicit potion-slot projection is restricted to its new bridge revision")
    pins = document["projection"]
    headless = next(
        item for item in qualification.document["sources"] if item["name"] == "headless"
    )
    if pins.get("source_revision") != headless["commit"]:
        raise ValueError("Rest projection must use the qualification's pinned Headless revision")
    source = (
        _private_path(qualification.root, headless["path"]) / "src/managed-player-environment.mjs"
    )
    revision = document.get("public_projection_revision", "rest_v1")
    patch = qualification.root / (
        "patches/engine/sts2-headless-player-projection-v2.patch"
        if revision in {"combat_v4", "bundle_v5"}
        else "patches/engine/sts2-headless-player-projection-v1.patch"
    )
    if _sha_file(source) != pins["source_sha256"] or _sha_file(patch) != pins["patch_sha256"]:
        raise ValueError("Rest projection source or hook patch changed")
    helpers = [
        "engine-player-projection.mjs",
        "engine-rest-surface.mjs",
        "probe-engine-cli-rest.mjs",
    ]
    if revision in {"selection_shop_v2", "selection_shop_v3", "combat_v4", "bundle_v5"}:
        helpers.extend(["engine-selection-shop-surface.mjs", "probe-engine-cli-shop.mjs"])
        if revision in {"combat_v4", "bundle_v5"}:
            helpers.extend(
                [
                    "engine-combat-surface-v2.mjs"
                    if document.get("combat_surface_revision") == "v2"
                    else "engine-combat-surface.mjs",
                    "probe-engine-cli-combat.mjs",
                ]
            )
        if revision == "bundle_v5":
            helpers.extend(
                [
                    "engine-bundle-surface-v1.mjs",
                    f"probe-engine-cli-bundle-{document.get('bundle_probe_revision', 'v1')}.mjs",
                ]
            )
    elif revision != "rest_v1":
        raise ValueError("Unknown public interaction projection revision")
    for name in helpers:
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
