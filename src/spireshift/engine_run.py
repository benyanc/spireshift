"""Bounded natural A8 diagnostics over a pinned public interface; never admits learning."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.engine_cli_probe import (
    verify_local_build_report,
    verify_probe_runtime,
    verify_projection_inputs,
)
from spireshift.engine_connector import _stop_child
from spireshift.engine_localization import verify_native_localization
from spireshift.engine_native import (
    DATA_RELATIVE,
    _private_path,
    _require_native_launch_support,
    _running_games,
    _sandbox,
    _shared_snapshot,
    _verified_archive,
    load_native_qualification_config,
)
from spireshift.engine_profile import PROFILE, load_profile_policy
from spireshift.engine_qualification import (
    GAME_RELATIVE,
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.engine_startup import _script_closure
from spireshift.full_run_experience import atomic_json

HELPERS = {
    "probe-engine-native-run-v1.mjs",
    "engine-run-contract-v1.mjs",
    "engine-bundle-surface-v1.mjs",
    "engine-menu-probe.mjs",
}

PUBLIC_FAMILIES = {
    "event_option",
    "map_navigation",
    "combat_turn",
    "rest_site",
    "shop_inventory",
    "card_selection",
    "card_bundle_selection",
    "reward_claim",
    "card_reward_selection",
    "reward_completion",
    "treasure_chest",
    "treasure_relic_selection",
    "treasure_completion",
    "game_over",
    "native_generated_card_choice",
}
PRIVATE_FIELDS = {
    "native_ref",
    "room_ref",
    "option_ref",
    "selection_ref",
    "merchant_ref",
    "raw_request",
    "seed",
    "rng",
    "draw_order",
    "act_sequence",
    "privileged_act_sequence",
    "native_game_over",
    "native_victory_room",
    "native_player_dead",
}


def _assert_saved_public(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _assert_saved_public(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key in PRIVATE_FIELDS:
                raise ValueError(f"Private field in saved player input: {key}")
            _assert_saved_public(item)


def _verify_saved_observation(row: dict[str, Any], runtime: str) -> None:
    _assert_saved_public({"snapshot": row["snapshot"], "reads": row.get("reads", [])})
    snapshot = row["snapshot"]
    menu = snapshot["bound_actions"]
    actions = menu["actions"]
    kind = snapshot["interaction"]["kind"]
    if (
        snapshot["session"]["runtime_instance_id"] != runtime
        or snapshot["completeness"]["status"] != "complete"
        or snapshot["information_policy"]["includes_hidden_information"] is not False
        or snapshot["persistent"]["content"]["run"]["ascension"] != 8
        or kind not in PUBLIC_FAMILIES
        or menu["status"] != "complete"
        or len(actions) != menu["total_count"]
        or len(actions) != menu["materialized_count"]
        or len({action["bound_action_id"] for action in actions}) != len(actions)
        or any(
            action["interaction_id"] != snapshot["interaction"]["interaction_id"]
            for action in actions
        )
        or snapshot["status"] != ("observed" if kind == "game_over" else "interactive")
        or (not actions) != (kind == "game_over")
    ):
        raise ValueError("Saved public observation has an incomplete, stale or unsupported menu")
    for read in row.get("reads", []):
        if (
            read["expected_snapshot_id"] != snapshot["snapshot_id"]
            or read["observed_snapshot_id"] != snapshot["snapshot_id"]
            or read["completeness"]["status"] != "complete"
            or read["information_policy"]["includes_hidden_information"] is not False
        ):
            raise ValueError("Saved public read is stale or incomplete")


def load_run_recipe(path: Path, qualification: EngineQualificationConfig) -> dict[str, Any]:
    document = json.loads(path.read_text())
    helpers = (
        _script_closure(qualification.root / "scripts", {"probe-engine-native-run-v5.mjs"})
        if document.get("policy_revision") == "diagnostic_v5"
        else _script_closure(qualification.root / "scripts", {"probe-engine-native-run-v4.mjs"})
        if document.get("policy_revision") == "diagnostic_v4"
        else _script_closure(qualification.root / "scripts", {"probe-engine-native-run-v3.mjs"})
        if document.get("policy_revision") == "diagnostic_v3"
        else _script_closure(qualification.root / "scripts", {"probe-engine-native-run-v2.mjs"})
        if document.get("policy_revision") == "diagnostic_v2"
        else HELPERS
    )
    if (
        document.get("schema_version") != "engine-native-run-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("character") != "Ironclad"
        or document.get("ascension") != 8
        or document.get("content_policy") != PROFILE
        or document.get("stage") != "natural_public_loop_diagnostic_only"
        or document.get("training_allowed") is not False
        or document.get("privileged_fixture") is not False
        or not re.fullmatch(
            r"SP1RESH1FTA8D1AG[0-9]{3}"
            if document.get("seed_policy") == "native_canonical_v1"
            else r"SPIRESHIFTA8DIAG[0-9]{3}",
            str(document.get("seed", "")),
        )
        or document.get("seed_policy") not in {None, "native_canonical_v1"}
        or type(document.get("max_wall_seconds")) is not int
        or not 30 <= document["max_wall_seconds"] <= 180
        or type(document.get("max_decisions")) is not int
        or not 1 <= document["max_decisions"] <= 4096
        or document.get("max_repeated_states") != 3
        or document.get("policy_revision")
        not in {None, "diagnostic_v2", "diagnostic_v3", "diagnostic_v4", "diagnostic_v5"}
        or set(document.get("helpers_sha256", {})) != helpers
    ):
        raise ValueError("Expected a short, fixed-A8 natural public-run diagnostic recipe")
    return dict(document)


def _run_inputs(qualification: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    document = load_run_recipe(path, qualification)
    objective_path = qualification.root / document["objective_config"]
    if _sha_file(objective_path) != document["objective_sha256"]:
        raise ValueError("Natural run objective changed")
    objective = load_objective(objective_path)
    inputs = json.loads((qualification.root / document["input_config"]).read_text())
    if (
        manifest_identifier(inputs) != document["input_config_id"]
        or inputs.get("schema_version") != "engine-native-run-inputs-config-v1"
        or inputs.get("public_projection_revision") != "native_run_v1"
        or inputs.get("combat_bridge_revision") != "v7"
        or inputs.get("combat_surface_revision") not in {"v2", "v3", "v4"}
        or inputs.get("qualification_config_id") != qualification.config_id
        or inputs.get("content_policy") != PROFILE
    ):
        raise ValueError("Natural run must bind the current exact-slot public input configuration")
    policy = load_profile_policy(qualification.root / inputs["profile_policy"], qualification)
    if manifest_identifier(policy) != inputs["profile_policy_id"]:
        raise ValueError("Natural run benchmark profile changed")
    projection, sdk_before = verify_projection_inputs(qualification, inputs)
    runtime, runtime_before = verify_probe_runtime(qualification, inputs)
    if runtime is None:
        raise ValueError("Natural run requires the pinned game-matching runtime")
    localization = verify_native_localization(qualification, inputs["native_localization"])
    build_config = json.loads((qualification.root / inputs["build_config"]).read_text())
    report = json.loads(_private_path(qualification.root, inputs["build_report"]).read_text())
    build = verify_local_build_report(report, build_config, qualification)
    candidate = _private_path(
        qualification.root, str(Path(build["candidate_directory"]).relative_to(qualification.root))
    )
    if (
        report["report_id"] != inputs["build_report_id"]
        or _inventory(candidate) != report["private_candidate_inventory"]
        or _sha_file(qualification.root / build_config["local_patch"])
        != build_config["local_patch_sha256"]
        or any(
            _sha_file(qualification.root / "scripts" / name) != digest
            for name, digest in document["helpers_sha256"].items()
        )
    ):
        raise ValueError("Natural run candidate, source or helpers changed")
    native = load_native_qualification_config(
        qualification.root / build_config["native_config"], qualification
    )
    archive, verified = _verified_archive(native)
    return {
        "recipe": document,
        "inputs": inputs,
        "projection": projection,
        "sdk_before": sdk_before,
        "runtime": runtime,
        "runtime_before": runtime_before,
        "localization": localization,
        "candidate": candidate,
        "candidate_before": report["private_candidate_inventory"],
        "build": build,
        "archive": archive,
        "archive_verified": verified,
        "objective": objective.as_dict(),
    }


def preflight_native_run(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    _require_native_launch_support()
    if not node.is_file() or _running_games():
        raise ValueError("Use the local Node runtime and close any running game")
    inputs = _run_inputs(qualification, path)
    recipe = inputs["recipe"]
    workspace = _private_path(qualification.root, recipe["workspace"])
    return {
        "schema_version": "engine-native-run-preflight-v1",
        "config_id": manifest_identifier(recipe),
        "ready_for_diagnostic": not workspace.exists(),
        "workspace": str(workspace),
        "objective": inputs["objective"],
        "games_launched": 0,
        "training_allowed": False,
        "game_apps_created": 0,
        "terminal_semantics_qualified": False,
    }


def probe_native_run(
    qualification: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    _require_native_launch_support()
    if not node.is_file() or _running_games():
        raise ValueError("Use the local Node runtime and close any running game")
    inputs = _run_inputs(qualification, path)
    recipe, candidate, runtime = inputs["recipe"], inputs["candidate"], inputs["runtime"]
    archive, localization = inputs["archive"], inputs["localization"]
    workspace = _private_path(qualification.root, recipe["workspace"])
    if workspace.exists():
        raise FileExistsError("Preserve the saved native run; use a new versioned recipe to retry")
    workspace.mkdir(parents=True)
    atomic_json(workspace / "in-progress.json", {"config_id": manifest_identifier(recipe)})
    sources = workspace / "source-at-launch"
    sources.mkdir()
    for name in recipe["helpers_sha256"]:
        (sources / name).write_bytes((qualification.root / "scripts" / name).read_bytes())
    atomic_json(sources / "recipe.json", recipe)
    profile = workspace / "private-profile"
    profile.mkdir()
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    shared_before = _shared_snapshot(shared)
    user_data = shared.parent
    (workspace / "profile-isolation.sb").write_text(
        _sandbox(
            [
                shared,
                user_data / "Godot/app_userdata/SlayTheSpire2",
                user_data / "Steam",
                archive.parent,
                candidate,
                runtime,
                localization,
            ]
        )
    )
    source = next(row for row in qualification.document["sources"] if row["name"] == "headless")
    spec = {
        "headless_root": str(_private_path(qualification.root, source["path"])),
        "attempt": str(workspace),
        "profile": str(profile),
        "candidate": str(candidate),
        "artifact": str(candidate / "src/Sts2Headless/bin/Release/net9.0/Sts2Headless.dll"),
        "game_data": str(archive / GAME_RELATIVE / DATA_RELATIVE),
        "dotnet": str(runtime / "dotnet"),
        "expected": inputs["build"],
        "managed_runtime_version": "9.0.7",
        "projection": inputs["projection"],
        "environment_fingerprint": manifest_identifier(
            {"build_report_id": inputs["inputs"]["build_report_id"], "recipe": recipe}
        ),
        "objective": inputs["objective"],
        **{
            key: recipe[key]
            for key in ("seed", "content_policy", "max_decisions", "max_repeated_states")
        },
    }
    environment = dict(os.environ)
    environment["DOTNET_ROLL_FORWARD"] = "LatestPatch"
    environment["STS2_NATIVE_LOCALIZATION"] = str(localization)
    for name in ("SteamAppId", "SteamGameId", "STS2_HEADLESS_QUIET"):
        environment.pop(name, None)
    started = time.monotonic()
    timed_out = False
    with (workspace / "stdout.log").open("wb") as out, (workspace / "stderr.log").open("wb") as err:
        child = subprocess.Popen(
            [
                str(node),
                str(
                    qualification.root
                    / "scripts"
                    / (
                        "probe-engine-native-run-v4.mjs"
                        if recipe.get("policy_revision") == "diagnostic_v4"
                        else "probe-engine-native-run-v3.mjs"
                        if recipe.get("policy_revision") == "diagnostic_v3"
                        else "probe-engine-native-run-v2.mjs"
                        if recipe.get("policy_revision") == "diagnostic_v2"
                        else "probe-engine-native-run-v1.mjs"
                    )
                ),
            ],
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
            cwd=qualification.root,
            env=environment,
            start_new_session=True,
        )
        try:
            child.communicate(json.dumps(spec).encode(), timeout=recipe["max_wall_seconds"])
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            _stop_child(child)
    raw_path = workspace / "run-probe.json"
    probe = json.loads(raw_path.read_text()) if raw_path.is_file() else {"status": "missing_result"}
    frozen_after = verify_game_archive(qualification, archive)
    checks = {
        "candidate_unchanged": _inventory(candidate) == inputs["candidate_before"],
        "shared_profile_unchanged": _shared_snapshot(shared) == shared_before,
        "frozen_archive_unchanged": frozen_after["valid"],
        "runtime_unchanged": _inventory(runtime) == inputs["runtime_before"],
        "sdk_unchanged": _inventory(Path(inputs["projection"]["node_modules"]))
        == inputs["sdk_before"],
    }
    verify_native_localization(qualification, inputs["inputs"]["native_localization"])
    status = "wall_cap" if timed_out else probe.get("status", "incomplete")
    if not all(checks.values()):
        status = "isolation_failure"
    if status == "candidate_terminal" and child.returncode != 0:
        status = "process_failure"
    files = {
        name: _sha_file(workspace / name)
        for name in (
            "run-probe.json",
            "private-transcript.jsonl",
            "public-run.jsonl",
            "diagnostics.json",
        )
        if (workspace / name).is_file()
    }
    body = {
        "schema_version": "engine-native-run-report-v1",
        "config_id": manifest_identifier(recipe),
        "qualification_config_id": qualification.config_id,
        "input_config_id": recipe["input_config_id"],
        "build_report_id": inputs["inputs"]["build_report_id"],
        "seed": recipe["seed"],
        "objective": inputs["objective"],
        "status": status,
        "benchmark_denominator": 1,
        "probe": probe,
        "checks": checks,
        "files": files,
        "process": {
            "returncode": child.returncode,
            "timed_out": timed_out,
            "wall_seconds": time.monotonic() - started,
        },
        "game_apps_created": 0,
        "privileged_fixture": False,
        "optimizer_steps": 0,
        "training_allowed": False,
        "terminal_semantics_qualified": False,
        "claim_scope": "pinned_natural_A8_public_loop_diagnostic_only",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(workspace / "summary.json", result)
    return result


def verify_native_run(
    qualification: EngineQualificationConfig, report_path: Path
) -> dict[str, Any]:
    """Reconstruct a successful diagnostic from sealed saved actions; no engine is started."""
    workspace = _private_path(
        qualification.root, str(report_path.parent.resolve().relative_to(qualification.root))
    )
    report = json.loads(report_path.read_text())
    body = {key: value for key, value in report.items() if key != "report_id"}
    recipe = load_run_recipe(workspace / "source-at-launch/recipe.json", qualification)
    if (
        report.get("schema_version") != "engine-native-run-report-v1"
        or report.get("report_id") != manifest_identifier(body)
        or report.get("qualification_config_id") != qualification.config_id
        or report.get("config_id") != manifest_identifier(recipe)
        or report.get("seed") != recipe["seed"]
        or report.get("status") != "candidate_terminal"
        or report.get("benchmark_denominator") != 1
        or report.get("training_allowed") is not False
        or report.get("privileged_fixture") is not False
        or report.get("terminal_semantics_qualified") is not False
        or report.get("optimizer_steps") != 0
        or report.get("game_apps_created") != 0
        or not report.get("checks")
        or any(value is not True for value in report["checks"].values())
        or report.get("process", {}).get("returncode") != 0
        or report.get("process", {}).get("timed_out") is not False
        or set(report.get("files", {}))
        != {"run-probe.json", "private-transcript.jsonl", "public-run.jsonl", "diagnostics.json"}
    ):
        raise ValueError("Expected a sealed, uncapped natural-run diagnostic, without admission")
    for name, digest in report["files"].items():
        if _sha_file(workspace / name) != digest:
            raise ValueError("Saved native-run evidence changed")
    for name, digest in recipe["helpers_sha256"].items():
        if _sha_file(workspace / "source-at-launch" / name) != digest:
            raise ValueError("Saved diagnostic helper identity changed")
    probe = json.loads((workspace / "run-probe.json").read_text())
    if probe != report["probe"] or probe.get("full_run_attempts") != 1:
        raise ValueError("Diagnostic probe/attempt denominator changed")
    transcript = [
        json.loads(row) for row in (workspace / "private-transcript.jsonl").read_text().splitlines()
    ]
    starts = [row for row in transcript if row["request"]["cmd"] == "start_run"]
    allowed = {"runtime_identity", "run_identity", "start_run", "get_map", "action", "quit"}
    if (
        len(starts) != 1
        or starts[0]["request"].get("character") != "Ironclad"
        or starts[0]["request"].get("ascension") != 8
        or starts[0]["request"].get("seed") != recipe["seed"]
        or starts[0]["request"].get("content_policy") != PROFILE
        or any(row["request"].get("cmd") not in allowed for row in transcript)
    ):
        raise ValueError("Natural run contains a reset, fixture mutation or unbound start")
    rows = [json.loads(row) for row in (workspace / "public-run.jsonl").read_text().splitlines()]
    if not rows:
        raise ValueError("Natural run has no saved observations")
    observations: list[dict[str, Any]] = []
    runtime = rows[0]["snapshot"]["session"]["runtime_instance_id"]
    index = 0
    while index < len(rows):
        observation = rows[index]
        if observation["stage"] != "observation" or observation["index"] != len(observations):
            raise ValueError("Diagnostic observation order changed")
        snapshot = observation["snapshot"]
        _verify_saved_observation(observation, runtime)
        observations.append(snapshot)
        if index == len(rows) - 1:
            break
        if index + 3 >= len(rows):
            raise ValueError("Incomplete diagnostic action/receipt chain")
        action_row, receipt_row, successor = rows[index + 1 : index + 4]
        action = action_row.get("action")
        receipt = receipt_row.get("receipt")
        if (
            action_row["stage"] != "action"
            or receipt_row["stage"] != "receipt"
            or action_row["index"] != observation["index"]
            or receipt_row["index"] != observation["index"]
            or action not in snapshot["bound_actions"]["actions"]
            or action_row["snapshot"] != snapshot
            or receipt_row["snapshot"] != snapshot
            or receipt is None
            or receipt.get("delivery") != "delivered"
            or receipt["action"]["bound_action_id"] != action["bound_action_id"]
            or receipt.get("successor") != successor["snapshot"]
            or successor["stage"] != "observation"
        ):
            raise ValueError("Diagnostic action was stale, unadvertised or not delivered")
        index += 3
    terminal = observations[-1]
    end = probe["private_final_identity"]
    identities = [row["response"] for row in transcript if row["request"]["cmd"] == "run_identity"]
    if (
        len(identities) != 2
        or identities[0] != probe["private_start_identity"]
        or identities[-1] != end
        or identities[0].get("seed") != recipe["seed"]
        or identities[0].get("ascension") != 8
        or identities[0].get("started_with_neow") is not True
        or identities[0].get("native_player_dead") is not False
        or identities[0].get("native_game_over") is not False
        or probe.get("runtime_errors") != []
    ):
        raise ValueError("Native starting/ending identities or runtime errors do not reconstruct")
    victory = terminal["interaction"]["content"]["surface"].get("victory")
    if (
        terminal["interaction"]["kind"] != "game_over"
        or type(victory) is not bool
        or probe.get("native_ending_evidence_agrees") is not True
        or not all(
            type(end.get(name)) is bool
            for name in ("native_game_over", "native_victory_room", "native_player_dead")
        )
        or not (
            end["native_game_over"] and end["native_victory_room"]
            if victory
            else end["native_player_dead"]
            or end["native_game_over"]
            and not end["native_victory_room"]
        )
    ):
        raise ValueError("Diagnostic ending is not supported by native flags")
    run = probe["run"]
    compute = run.get("agent_cpu_seconds")
    counts = dict(Counter(snapshot["interaction"]["kind"] for snapshot in observations))
    decisions = len(observations) - 1
    native_actions = sum(row["request"]["cmd"] == "action" for row in transcript)
    maximum_floor = max(
        snapshot["persistent"]["content"]["run"]["floor"] for snapshot in observations
    )
    if (
        run.get("decisions") != decisions
        or native_actions != decisions
        or run.get("decision_families") != counts
        or run.get("maximum_floor") != maximum_floor
        or run.get("victory") is not victory
        or run.get("terminal") is not True
        or type(compute) not in {int, float}
        or not math.isfinite(compute)
        or not 0 <= compute <= report["objective"]["whole_run_budget"]
    ):
        raise ValueError("Diagnostic counts/outcome/compute do not reconstruct")
    return {
        "valid": True,
        "report_id": report["report_id"],
        "observations": len(observations),
        "delivered_decisions": decisions,
        "maximum_floor": maximum_floor,
        "decision_families": counts,
        "candidate_victory": victory,
        "native_ending_evidence_agrees": True,
        "games_replayed": 0,
        "training_allowed": False,
        "terminal_semantics_qualified": False,
    }
