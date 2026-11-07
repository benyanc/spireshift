"""Privileged act/ending fixtures, separate from natural runs and all learning inputs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import load_objective
from spireshift.engine_cli_probe import verify_local_build_report, verify_probe_runtime
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_localization import verify_native_localization
from spireshift.engine_native import (
    _private_path,
    _run_boot,
    _running_games,
    _sandbox,
    _shared_snapshot,
    _verified_archive,
    load_native_qualification_config,
)
from spireshift.engine_profile import load_profile_policy, verify_benchmark_progress
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json

CHECKS = (
    {
        "fixed_A8",
        "three_native_acts",
        "third_act_stays_third_until_architect",
        "architect_requires_another_decision",
        "native_game_over",
        "native_victory_room",
        "wrapper_explicit_victory",
        "victory_despite_zero_hp",
        "global_test_mode_retained",
    }
    | {
        f"act_{act}_{suffix}"
        for act in (1, 2, 3)
        for suffix in (
            "current",
            "native_boss_room",
            "not_ended_before_fixture",
            "enemies_present",
            "boss_defeat_not_run_victory",
            "explicit_proceed",
            "pre_finished_native_room",
            "checkpoint_saved",
            "proceed_is_not_immediate_victory",
        )
    }
    | {f"act_{act}_advanced_once" for act in (1, 2)}
)
ISOLATION = {
    "candidate_unchanged",
    "runtime_unchanged",
    "shared_profile_unchanged",
    "archive_unchanged",
}


def validate_native_progression(raw: dict[str, Any], build: dict[str, Any], seed: str) -> None:
    """Reconstruct the milestone evidence; a checked flag alone cannot establish a win."""
    if (
        raw.get("schema_version")
        not in {
            "native-run-progression-check-v1",
            "native-run-progression-check-v2",
            "native-run-progression-check-v3",
        }
        or raw.get("status") != "native_progression_fixture_pass"
        or raw.get("seed") != seed
        or raw.get("error") is not None
        or raw.get("wrapper_sha256") != build["artifact_sha256"]
        or raw.get("game_sha256") != build["runtime_sts2_sha256"]
        or raw.get("godot_stub_sha256") != build["godot_stub_sha256"]
        or raw.get("managed_runtime_version") != "9.0.7"
        or raw.get("privileged_fixture") is not True
        or raw.get("training_allowed") is not False
        or any(
            raw.get(key) != 0
            for key in ("natural_victories", "full_run_attempts", "optimizer_steps")
        )
        or raw.get("native_fixture_starts") != 1
        or raw.get("fixture_forced_boss_defeats") != 3
        or raw.get("planned_forced_boss_defeats") != 3
        or set(raw.get("checks", {}))
        != CHECKS
        | (
            {f"act_{act}_native_boss_map_coordinate" for act in (1, 2, 3)}
            if raw.get("schema_version")
            in {"native-run-progression-check-v2", "native-run-progression-check-v3"}
            else set()
        )
        | (
            {"native_cleanup_completed"}
            if raw.get("schema_version") == "native-run-progression-check-v3"
            else set()
        )
        or any(value is not True for value in raw["checks"].values())
    ):
        raise ValueError("Incomplete or unbound privileged native progression fixture")
    if raw["schema_version"] == "native-run-progression-check-v3" and (
        raw.get("cleanup_identity", {}).get("active") is not False
        or any(
            raw.get("cleanup_identity", {}).get(key) is not False
            for key in (
                "action_executor_running",
                "pending_host_operation",
                "pending_card_selection",
                "pending_card_reward",
                "pending_reward_set",
                "pending_bundle",
            )
        )
    ):
        raise ValueError("Native progression did not cleanly release its run and pending work")
    expected_stages = (
        ["initial"]
        + [
            f"act_{act}_{suffix}"
            for act in (1, 2, 3)
            for suffix in (
                "boss_before_force_kill",
                "after_force_kill",
                "before_proceed",
                "after_proceed",
            )
        ]
        + ["terminal"]
    )
    states = raw.get("states", [])
    if [row.get("stage") for row in states] != expected_stages:
        raise ValueError("Missing or reordered native transition observation")
    by_stage = {row["stage"]: row for row in states}
    for row in states:
        identity, state = row.get("native", {}), row.get("state", {})
        if (
            identity.get("seed") != seed
            or identity.get("ascension") != 8
            or identity.get("profile_policy") != "native_benchmark_full_v1"
            or state.get("type") != "decision"
            or state.get("context", {}).get("ascension") != 8
            or state.get("player", {}).get("character_id") != "IRONCLAD"
        ):
            raise ValueError("Native fixture changed seed, character, difficulty or profile")
        terminal = row["stage"] == "terminal"
        # The Architect is already a victory room, but its dialogue must still
        # finish before native IsGameOver becomes true. Neither flag suffices alone.
        victory_room = row["stage"] in {"act_3_after_proceed", "terminal"}
        if (
            any(
                row.get(key) is not terminal or identity.get(key) is not terminal
                for key in ("native_game_over", "native_player_dead")
            )
            or row.get("is_victory_room") is not victory_room
            or identity.get("native_victory_room") is not victory_room
        ):
            raise ValueError("Native fixture prematurely ended or misclassified the victory room")
        if terminal and (
            state.get("decision") != "game_over"
            or state.get("victory") is not True
            or state.get("player", {}).get("hp") != 0
            or row.get("native_player_hp") != 0
        ):
            raise ValueError("Missing explicit native victory despite zero HP")
    checkpoints = raw.get("checkpoints", [])
    if [row.get("act") for row in checkpoints] != [1, 2, 3]:
        raise ValueError("Expected every before-Proceed checkpoint")
    for act, checkpoint in zip((1, 2, 3), checkpoints, strict=True):
        before = by_stage[f"act_{act}_before_proceed"]["state"]
        after = by_stage[f"act_{act}_after_proceed"]["state"]
        if (
            before.get("decision") != "combat_rewards_complete"
            or before.get("context", {}).get("act") != act
            or checkpoint.get("state") != before
            or after.get("context", {}).get("act") != min(act + 1, 3)
            or after.get("decision") != ("map_select" if act < 3 else "event_choice")
            or (act == 3 and after.get("event_name") != "The Architect")
        ):
            raise ValueError("Native Proceed skipped, repeated or incorrectly ended an act")
    actions = raw.get("delivered", [])
    if (
        [row.get("act") for row in actions if row.get("action") == "proceed"] != [1, 2, 3]
        or not any(row.get("action") == "choose_option" and row.get("act") == 3 for row in actions)
        or actions[-1].get("result") != by_stage["terminal"]["state"]
        or any(row.get("result", {}).get("type") != "decision" for row in actions)
    ):
        raise ValueError("Native ending lacks its delivered Proceed/dialogue sequence")


def progression_inputs(qualification: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-native-progression-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("stage") != "privileged_native_act_and_ending_only"
        or document.get("privileged_fixture") is not True
        or document.get("training_allowed") is not False
        or not re.fullmatch(r"SP1RESH1FTACT[0-9]{3}", str(document.get("seed", "")))
        or type(document.get("max_wall_seconds")) is not int
        or not 15 <= document["max_wall_seconds"] <= 90
    ):
        raise ValueError("Expected a finite privileged A8 act/ending fixture recipe")
    policy = load_profile_policy(qualification.root / document["profile_policy"], qualification)
    if manifest_identifier(policy) != document["profile_policy_id"]:
        raise ValueError("Progression benchmark profile changed")
    objective = qualification.root / document["objective_config"]
    if _sha_file(objective) != document["objective_sha256"]:
        raise ValueError("Progression objective changed")
    load_objective(objective)
    build_config = json.loads((qualification.root / document["build_config"]).read_text())
    report = _hashed(_private_path(qualification.root, document["build_report"]))
    build = verify_local_build_report(report, build_config, qualification)
    candidate = Path(build["candidate_directory"])
    if (
        report["report_id"] != document["build_report_id"]
        or _inventory(candidate) != report["private_candidate_inventory"]
        or _sha_file(qualification.root / build_config["local_patch"])
        != build_config["local_patch_sha256"]
    ):
        raise ValueError("Pinned progression candidate/source changed")
    runtime, runtime_tree = verify_probe_runtime(qualification, document)
    if runtime is None:
        raise ValueError("Progression fixture requires the exact game runtime")
    localization = verify_native_localization(qualification, document["native_localization"])
    checker = _private_path(qualification.root, document["checker"])
    archived_sources = _private_path(qualification.root, document["workspace"]) / "source-at-launch"
    sources = (
        archived_sources
        if archived_sources.is_dir()
        else qualification.root / "mod/SpireShift.RunProgressionCheck"
    )
    if (
        _sha_file(checker) != document["checker_sha256"]
        or set(document.get("checker_sources", {}))
        != {"Program.cs", "SpireShift.RunProgressionCheck.csproj"}
        or any(
            _sha_file(sources / name) != digest
            for name, digest in document["checker_sources"].items()
        )
    ):
        raise ValueError("Progression fixture executable or source changed")
    return dict(
        document=document,
        policy=policy,
        build=build,
        build_report=report,
        candidate=candidate,
        runtime=runtime,
        runtime_tree=runtime_tree,
        localization=localization,
        checker=checker,
    )


def _check_saved_native(inputs: dict[str, Any], workspace: Path) -> dict[str, Any]:
    raw = json.loads((workspace / "private-check.json").read_text())
    validate_native_progression(raw, inputs["build"], inputs["document"]["seed"])
    verify_benchmark_progress(workspace / "benchmark-progress.save", inputs["policy"])
    for row in raw["checkpoints"]:
        expected = workspace / f"act-{row['act']}-before-proceed.save"
        if Path(row["path"]) != expected or _sha_file(expected) != row["sha256"]:
            raise ValueError("Progression checkpoint path or bytes changed")
        if raw["schema_version"] in {
            "native-run-progression-check-v2",
            "native-run-progression-check-v3",
        }:
            validate_progression_save(json.loads(expected.read_text()), row["act"])
    # The upstream wrapper can log and swallow exceptions. Exit zero is insufficient.
    for name in ("stdout.log", "stderr.log"):
        if re.search(
            r"(?im)(?:^\[ERROR\]|^ERROR:|\b(?:MissingMethodException|NullReferenceException|"
            r"TypeLoadException|Unhandled exception)\b)",
            (workspace / name).read_text(),
        ):
            raise ValueError("Native progression contains a runtime error; retain its logs")
    return dict(raw)


def validate_progression_save(save: dict[str, Any], act: int) -> None:
    """A finished room without a visited map coordinate is not a reloadable boss fixture."""
    room = save.get("pre_finished_room", {})
    history = save.get("map_point_history", [])
    acts = save.get("acts", [])
    if (
        save.get("ascension") != 8
        or save.get("current_act_index") != act - 1
        or len(acts) != 3
        or room.get("room_type") != "boss"
        or room.get("is_pre_finished") is not True
        or room.get("encounter_id") != acts[act - 1].get("rooms", {}).get("boss_id")
        or not save.get("visited_map_coords")
        or len(history) != act
        or not history[-1]
        or history[-1][-1].get("map_point_type") != "boss"
        or not history[-1][-1].get("rooms")
        or history[-1][-1]["rooms"][-1].get("model_id") != room.get("encounter_id")
    ):
        raise ValueError(
            "Privileged boss save lacks native position, history or finished-room binding"
        )


def run_native_progression(qualification: EngineQualificationConfig, path: Path) -> dict[str, Any]:
    inputs = progression_inputs(qualification, path)
    document = inputs["document"]
    workspace = _private_path(qualification.root, document["workspace"])
    if workspace.exists():
        raise FileExistsError("Preserve this progression attempt; use a new versioned workspace")
    if _running_games():
        raise ValueError("Close the game before the isolated progression fixture")
    native = load_native_qualification_config(
        qualification.root / document["native_config"], qualification
    )
    archive, archive_verified = _verified_archive(native)
    workspace.mkdir(parents=True)
    atomic_json(workspace / "recipe.json", document)
    source_at_launch = workspace / "source-at-launch"
    source_at_launch.mkdir()
    for name in document["checker_sources"]:
        shutil.copyfile(
            qualification.root / "mod/SpireShift.RunProgressionCheck" / name,
            source_at_launch / name,
        )
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = _shared_snapshot(shared)
    sandbox = workspace / "profile-isolation.sb"
    sandbox.write_text(
        _sandbox(
            [
                shared,
                shared.parent / "Godot/app_userdata/SlayTheSpire2",
                shared.parent / "Steam",
                archive.parent,
                inputs["candidate"],
                inputs["runtime"],
                inputs["localization"],
                inputs["checker"].parent,
            ]
        )
    )
    profile = workspace / "private-profile"
    profile.mkdir()
    process = _run_boot(
        [
            "/usr/bin/env",
            f"STS2_NATIVE_LOCALIZATION={inputs['localization']}",
            "DOTNET_ROLL_FORWARD=LatestPatch",
            "/usr/bin/sandbox-exec",
            "-f",
            str(sandbox),
            str(inputs["runtime"] / "dotnet"),
            str(inputs["checker"]),
            str(inputs["candidate"]),
            document["seed"],
            str(workspace / "private-check.json"),
        ],
        profile,
        workspace,
        document["max_wall_seconds"],
    )
    atomic_json(workspace / "process.json", process)
    isolation = {
        "candidate_unchanged": _inventory(inputs["candidate"])
        == inputs["build_report"]["private_candidate_inventory"],
        "runtime_unchanged": _inventory(inputs["runtime"]) == inputs["runtime_tree"],
        "shared_profile_unchanged": _shared_snapshot(shared) == before,
        "archive_unchanged": verify_game_archive(qualification, archive)["valid"],
    }
    result: dict[str, Any] = {
        "schema_version": "engine-native-progression-v1",
        "qualification_config_id": qualification.config_id,
        "config_id": manifest_identifier(document),
        "status": "native_progression_incomplete",
        "seed": document["seed"],
        "process": process,
        "isolation": isolation,
        "shared_before": before,
        "shared_after": _shared_snapshot(shared),
        "archive_verification_id": archive_verified["report_id"],
        "privileged_fixture": True,
        "training_allowed": False,
        "natural_victories": 0,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "claim_scope": (
            "privileged_forced_boss_defeats_native_Proceed_act_transitions_and_Architect_victory_only"
        ),
    }
    try:
        if process["returncode"] != 0 or process["timed_out"] or not all(isolation.values()):
            raise ValueError(
                "Native progression failed or changed a protected input; inspect saved evidence"
            )
        raw = _check_saved_native(inputs, workspace)
        result.update(
            status="native_progression_pass",
            raw_report_sha256=_sha_file(workspace / "private-check.json"),
            checkpoints=[
                {"act": row["act"], "sha256": row["sha256"]} for row in raw["checkpoints"]
            ],
            checks=raw["checks"],
            source_inventory=document["checker_sources"],
            benchmark_progress_sha256=_sha_file(workspace / "benchmark-progress.save"),
        )
    except (ValueError, OSError, KeyError) as error:
        result["error"] = str(error)
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "summary.json", result)
    return result


def verify_native_progression(
    qualification: EngineQualificationConfig, path: Path
) -> dict[str, Any]:
    inputs = progression_inputs(qualification, path)
    document = inputs["document"]
    workspace = _private_path(qualification.root, document["workspace"])
    result = _hashed(workspace / "summary.json")
    if (
        result.get("config_id") != manifest_identifier(document)
        or result.get("qualification_config_id") != qualification.config_id
        or result.get("status") != "native_progression_pass"
        or result.get("raw_report_sha256") != _sha_file(workspace / "private-check.json")
        or result.get("training_allowed") is not False
        or result.get("privileged_fixture") is not True
        or result.get("full_run_attempts") != 0
        or result.get("natural_victories") != 0
        or set(result.get("isolation", {})) != ISOLATION
        or any(value is not True for value in result["isolation"].values())
        or result.get("shared_before") != result.get("shared_after")
        or result.get("process", {}).get("returncode") != 0
        or result.get("process", {}).get("timed_out") is not False
        or result.get("process") != json.loads((workspace / "process.json").read_text())
        or json.loads((workspace / "recipe.json").read_text()) != document
        or any(
            _sha_file(workspace / "source-at-launch" / name) != digest
            for name, digest in document["checker_sources"].items()
        )
    ):
        raise ValueError(
            "Saved progression report lost its recipe, runtime, scope or isolation binding"
        )
    raw = _check_saved_native(inputs, workspace)
    if (
        result.get("checks") != raw["checks"]
        or result.get("checkpoints")
        != [{"act": row["act"], "sha256": row["sha256"]} for row in raw["checkpoints"]]
        or result.get("benchmark_progress_sha256") != inputs["policy"]["progress_sha256"]
    ):
        raise ValueError("Saved native progression summary differs from its raw evidence")
    return {
        "valid": True,
        "native_report_id": result["report_id"],
        "checked_act_transitions": 3,
        "privileged_fixture": True,
        "natural_victories": 0,
        "games_replayed": 0,
        "training_allowed": False,
    }
