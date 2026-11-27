"""Explicit benchmark progress and bounded native description/API qualification."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import (
    verify_local_build_report,
    verify_probe_runtime,
)
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
from spireshift.engine_qualification import EngineQualificationConfig, _inventory, _sha_file
from spireshift.full_run_experience import atomic_json

PROFILE = "native_benchmark_full_v1"
CHECKS = {
    "benchmark_start",
    "native_unlock_epochs",
    "native_seen_encounters",
    "native_prior_run_gate",
    "all_acts_discovered",
    "fresh_tutorial_profile",
    "fixed_A8",
    "normal_act_selection_and_rng",
    "started_with_lobby_act_sequence",
    "profile_export",
    "inspection_checkpoint_export",
    "image_glyph_multiplicity",
    "ordered_named_amounts",
}


def load_profile_policy(path: Path, qualification: EngineQualificationConfig) -> dict[str, Any]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-profile-policy-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("factory") != PROFILE
        or document.get("character") != "Ironclad"
        or document.get("ascension") != 8
        or document.get("content") != "native_UnlockState_all"
        or document.get("act_discovery") != "all_native_acts_seen"
        or document.get("act_selection") != "native_lobby_seeded_random"
        or document.get("tutorials") != "enabled_no_completed_entries"
        or document.get("training_allowed") is not False
        or not re.fullmatch(r"[0-9a-f]{64}", str(document.get("progress_sha256", "")))
    ):
        raise ValueError("Expected an explicit game-bound Ironclad/A8 benchmark profile")
    return dict(document)


def verify_benchmark_progress(path: Path, policy: dict[str, Any]) -> dict[str, Any]:
    """Exact native export digest plus human-readable startup semantics; never an account edit."""
    if _sha_file(path) != policy["progress_sha256"]:
        raise ValueError("Native benchmark progress differs from its frozen factory export")
    progress = json.loads(path.read_text())
    stats = progress.get("character_stats", [])
    epochs = progress.get("epochs", [])
    acts = progress.get("discovered_acts", [])
    if (
        progress.get("schema_version") != policy["progress_schema"]
        or progress.get("unique_id") != "spireshift-benchmark-full-v1"
        or progress.get("enable_ftues") is not True
        or progress.get("ftue_completed") != []
        or len(stats) != 1
        or stats[0].get("id") != "CHARACTER.IRONCLAD"
        or stats[0].get("max_ascension") != 8
        or stats[0].get("preferred_ascension") != 8
        or stats[0].get("total_losses") != policy["native_prior_run_count"]
        or stats[0].get("total_wins") != 0
        or len(epochs) != policy["native_epoch_count"]
        or len({row["id"] for row in epochs}) != len(epochs)
        or any(row.get("state") != policy["native_revealed_epoch_state"] for row in epochs)
        or len(acts) != policy["native_act_count"]
        or len(set(acts)) != len(acts)
        or len(progress.get("encounter_stats", [])) != policy["native_encounter_count"]
    ):
        raise ValueError("Benchmark progress has changed unlock/discovery/A8/tutorial semantics")
    return dict(progress)


def validate_profile_description_report(
    document: dict[str, Any], build: dict[str, Any], seed: str, policy: dict[str, Any]
) -> dict[str, Any]:
    counts = Counter(row.get("kind") for row in document.get("rows", []))
    excluded = document.get("excluded", [])
    excluded_potions = [row for row in excluded if row.get("kind") == "potion"]
    if (
        document.get("schema_version") != "native-profile-description-check-v1"
        or document.get("seed") != seed
        or document.get("wrapper_sha256") != build["artifact_sha256"]
        or document.get("game_sha256") != build["runtime_sts2_sha256"]
        or document.get("managed_runtime_version") != "9.0.7"
        or document.get("privileged_fixture") is not True
        or document.get("training_allowed") is not False
        or document.get("shipped_game_compared") is not False
        or document.get("full_run_attempts") != 0
        or document.get("optimizer_steps") != 0
        or document.get("native_fixture_starts") != 1
        or document.get("global_test_mode_retained") is not True
        or document.get("profile_json_sha256") != policy["progress_sha256"]
        or set(document.get("checks", {})) != CHECKS
        or any(value is not True for value in document["checks"].values())
        or document.get("errors") != []
        or len(excluded_potions) != len(excluded)
        or any(row.get("reason") != "native_pool_IsMock" for row in excluded)
        or document.get("successful_descriptions") != sum(counts.values())
        or counts["potion"] + len(excluded) != document.get("planned_potions")
        or counts["relic"] != document.get("planned_relics")
        or counts["card"] != document.get("planned_cards")
        or counts["upgraded_card"] != document.get("planned_upgraded_cards")
        or set(counts) != {"potion", "relic", "card", "upgraded_card"}
        or any(
            not isinstance(row.get("description"), str) or not row["description"]
            for row in document["rows"]
        )
        or len({(row["kind"], row["id"]) for row in document["rows"]}) != len(document["rows"])
        or document.get("original_normal_act_selection") != document.get("managed_act_selection")
    ):
        raise ValueError("Incomplete, failed or unbound native profile/description denominator")
    return {"description_counts": dict(counts), "excluded_native_mock_models": len(excluded)}


def profile_inputs(
    qualification: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], Path, Path, Path, dict[str, Any]]:
    document = json.loads(path.read_text())
    if (
        document.get("schema_version") != "engine-profile-description-config-v1"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("stage") != "privileged_native_profile_and_description_oracle_only"
        or document.get("training_allowed") is not False
    ):
        raise ValueError("Expected a separate finite profile/description qualification recipe")
    policy = load_profile_policy(qualification.root / document["profile_policy"], qualification)
    if manifest_identifier(policy) != document["profile_policy_id"]:
        raise ValueError("Profile policy changed")
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
        raise ValueError("Pinned profile/text candidate or source changed")
    runtime, _ = verify_probe_runtime(qualification, document)
    if runtime is None:
        raise ValueError("Profile check requires the game-matching runtime")
    localization = verify_native_localization(qualification, document["native_localization"])
    checker = _private_path(qualification.root, document["checker"])
    source = qualification.root / "mod/SpireShift.ProfileDescriptionCheck"
    if (
        _sha_file(checker) != document["checker_sha256"]
        or set(document["checker_sources"])
        != {"Program.cs", "SpireShift.ProfileDescriptionCheck.csproj"}
        or any(
            _sha_file(source / name) != digest
            for name, digest in document["checker_sources"].items()
        )
    ):
        raise ValueError("Profile oracle checker or its source changed")
    return document, policy, candidate, runtime, localization, build


def run_native_profile_case(
    qualification: EngineQualificationConfig, recipe: Path, workspace: Path, seed: str
) -> dict[str, Any]:
    if not re.fullmatch(r"[A-Z0-9]{1,64}", seed) or _running_games():
        raise ValueError("Close the game and use an explicit bounded profile seed")
    document, policy, candidate, runtime, localization, build = profile_inputs(
        qualification, recipe
    )
    workspace = _private_path(qualification.root, str(workspace.relative_to(qualification.root)))
    if workspace.exists():
        raise FileExistsError("Preserve this native profile attempt; use a new versioned workspace")
    workspace.mkdir(parents=True)
    native = load_native_qualification_config(
        qualification.root / document["native_config"], qualification
    )
    archive, archive_verified = _verified_archive(native)
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    shared_before = _shared_snapshot(shared)
    sandbox = workspace / "profile-isolation.sb"
    sandbox.write_text(
        _sandbox(
            [shared, shared.parent / "Steam", archive.parent, candidate, runtime, localization]
        )
    )
    profile = workspace / "private-profile"
    profile.mkdir()
    process = _run_boot(
        [
            "/usr/bin/env",
            f"STS2_NATIVE_LOCALIZATION={localization}",
            "DOTNET_ROLL_FORWARD=LatestPatch",
            "/usr/bin/sandbox-exec",
            "-f",
            str(sandbox),
            str(runtime / "dotnet"),
            str(qualification.root / document["checker"]),
            str(candidate),
            seed,
            str(workspace / "private-check.json"),
        ],
        profile,
        workspace,
        45,
    )
    atomic_json(workspace / "process.json", process)
    if process["returncode"] or process["timed_out"]:
        raise ValueError("Native profile/description check failed; preserve its full report/logs")
    raw = json.loads((workspace / "private-check.json").read_text())
    counts = validate_profile_description_report(raw, build, seed, policy)
    verify_benchmark_progress(workspace / "benchmark-progress.save", policy)
    if _shared_snapshot(shared) != shared_before:
        raise ValueError("Profile check changed shared game data")
    result = {
        "schema_version": "engine-native-profile-case-v1",
        "qualification_config_id": qualification.config_id,
        "config_id": manifest_identifier(document),
        "seed": seed,
        "profile_policy_id": manifest_identifier(policy),
        "status": "native_profile_descriptions_pass",
        "process": process,
        **counts,
        "raw_report_sha256": _sha_file(workspace / "private-check.json"),
        "progress_sha256": _sha_file(workspace / "benchmark-progress.save"),
        "checkpoint_sha256": _sha_file(workspace / "native-checkpoint.save"),
        "native_state_sha256": _sha_file(workspace / "private-starting-state.json"),
        "archive_verification_id": archive_verified["report_id"],
        "privileged_fixture": True,
        "training_allowed": False,
        "full_run_attempts": 0,
    }
    result["report_id"] = manifest_identifier(result)
    atomic_json(workspace / "native-profile-case.json", result)
    return result
