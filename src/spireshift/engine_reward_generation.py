"""Bounded privileged native reward checks; not a shipped-game or selection comparison."""

from __future__ import annotations

import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_cli_probe import verify_local_build_report, verify_probe_runtime
from spireshift.engine_journey_verification import _hashed
from spireshift.engine_localization import verify_native_localization
from spireshift.engine_native import (
    _failure,
    _finish,
    _private_path,
    _run_boot,
    _running_games,
    _sandbox,
    _shared_snapshot,
    _verified_archive,
    load_native_qualification_config,
)
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.full_run_experience import atomic_json

METHODS = {
    "CallingBell": "0d5b8425a6c2c4c23ba79d895539c2c1b09cff7e43336905e0167de0b9cc85b8",
    "Cauldron": "83954045994c75187b8342adedc55a8fc5ee3e46961c3c6ec20ee9be7c6023e2",
}


def compare_reward_fixtures(
    rows: dict[str, dict[str, Any]], seed: str, relic: str, pins: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Compare full private RNG/pool state without exposing it as player input."""
    if set(rows) != {"reference", "legacy", "repaired"} or relic not in METHODS:
        raise ValueError("Expected original-normal, original-test and repaired-test fixtures")
    for role, row in rows.items():
        pin = pins["repaired" if role == "repaired" else "legacy"]
        count = 3 if relic == "CallingBell" else 5
        facts = row.get("generated_rewards")
        if (
            row.get("schema_version") != "native-reward-generation-fixture-v1"
            or row.get("seed") != seed
            or row.get("relic") != relic
            or row.get("mode") != ("original_normal" if role == "reference" else "test")
            or row.get("wrapper_sha256") != pin["artifact_sha256"]
            or row.get("game_sha256") != pin["runtime_sts2_sha256"]
            or row.get("stub_sha256") != pin["godot_stub_sha256"]
            or row.get("original_method_il_sha256") != METHODS[relic]
            or row.get("managed_runtime_version") != "9.0.7"
            or row.get("global_test_mode_retained") is not True
            or row.get("privileged_fixture") is not True
            or row.get("training_allowed") is not False
            or row.get("shipped_game_compared") is not False
            or row.get("full_run_attempts") != 0
            or row.get("reward_selections") != 0
            or row.get("hook_installed") is not (role == "repaired")
            or row.get("hook_methods") != (2 if role == "repaired" else 0)
            or row.get("populated_at_construction") != [role == "legacy"] * count
            or not isinstance(facts, list)
            or len(facts) != count
            or any(
                not isinstance(fact, dict)
                or fact.get("kind") != ("relic" if relic == "CallingBell" else "potion")
                or not isinstance(fact.get("id"), str)
                or not fact["id"]
                or not isinstance(fact.get("rarity"), str)
                or fact["rarity"] in {"", "unknown"}
                for fact in facts
            )
            or any(
                not isinstance(row.get(key), dict)
                or set(row[key]) != {"run_rng", "player_rng", "relic_grab_bag"}
                or any(not isinstance(value, dict) or not value for value in row[key].values())
                for key in ("private_before", "private_after")
            )
        ):
            raise ValueError(f"Unbound or incomplete native reward fixture: {role}")
    reference = rows["reference"]
    if any(row["private_before"] != reference["private_before"] for row in rows.values()):
        raise ValueError("Native reward fixtures started from different RNG/pool state")
    compared = ("generated_rewards", "private_after")
    if any(rows["repaired"][key] != reference[key] for key in compared):
        raise ValueError("Repaired reward generation differs from the original normal branch")
    if all(rows["legacy"][key] == reference[key] for key in compared):
        raise ValueError("Fixture did not expose the original preset reward shortcut")
    return {
        "candidate_matches_original_normal": True,
        "legacy_shortcut_exposed": True,
        "private_rng_and_pool_state_compared": True,
        "shipped_game_compared": False,
        "training_allowed": False,
    }


def check_native_reward_generation(
    qualification: EngineQualificationConfig, config_path: Path
) -> dict[str, Any]:
    document = json.loads(config_path.read_text())
    seeds = document.get("seeds")
    if (
        document.get("schema_version") != "engine-native-reward-generation-config-v1"
        or document.get("stage") != "privileged_native_original_method_differentials_only"
        or document.get("qualification_config_id") != qualification.config_id
        or document.get("character") != "Ironclad"
        or document.get("ascension") != 8
        or document.get("training_allowed") is not False
        or document.get("repeats") != 2
        or not isinstance(seeds, list)
        or len(seeds) != 2
        or any(
            not isinstance(seed, str) or not re.fullmatch(r"[A-Z0-9]{1,32}", seed) for seed in seeds
        )
        or len(set(seeds)) != 2
        or type(document.get("max_wall_seconds")) is not int
        or not 30 <= document["max_wall_seconds"] <= 240
    ):
        raise ValueError("Expected two fixed A8 reward seeds repeated twice with a short cap")
    if _running_games():
        raise ValueError("Close the game before the isolated native reward check")
    build_reports, builds = {}, {}
    for role in ("legacy", "repaired"):
        pins = document[role]
        config = json.loads((qualification.root / pins["build_config"]).read_text())
        report = _hashed(_private_path(qualification.root, pins["build_report"]))
        if report["report_id"] != pins["build_report_id"]:
            raise ValueError("Reward check build report changed")
        builds[role] = verify_local_build_report(report, config, qualification)
        if (
            _sha_file(qualification.root / config["local_patch"]) != config["local_patch_sha256"]
            or _sha_file(qualification.root / "scripts/engine-cli-local-build.mjs")
            != config["helper_sha256"]
        ):
            raise ValueError("Reward build source ledger changed")
        build_reports[role] = report
    native = load_native_qualification_config(
        qualification.root / document["native_config"], qualification
    )
    archive, before = _verified_archive(native)
    runtime, runtime_inventory = verify_probe_runtime(qualification, document)
    if runtime is None:
        raise ValueError("Native reward checks require the pinned game-matching runtime")
    localization = verify_native_localization(qualification, document["native_localization"])
    checker = _private_path(qualification.root, document["checker"])
    sources = qualification.root / "mod/SpireShift.RewardGenerationCheck"
    if (
        _sha_file(checker) != document["checker_sha256"]
        or set(document["checker_sources"])
        != {"Program.cs", "SpireShift.RewardGenerationCheck.csproj"}
        or any(
            _sha_file(sources / name) != sha for name, sha in document["checker_sources"].items()
        )
    ):
        raise ValueError("Native reward checker or source changed")
    candidates = {
        role: _private_path(
            qualification.root,
            str(Path(build["candidate_directory"]).relative_to(qualification.root)),
        )
        for role, build in builds.items()
    }
    for role, candidate in candidates.items():
        if _inventory(candidate) != build_reports[role]["private_candidate_inventory"]:
            raise ValueError("Native reward candidate files changed")
    workspace = _private_path(qualification.root, document["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    if (workspace / "report.json").exists() or (workspace / "in-progress.json").exists():
        raise FileExistsError("Preserve the completed or interrupted reward check")
    attempt = Path(tempfile.mkdtemp(prefix="rewards-", dir=workspace))
    atomic_json(workspace / "in-progress.json", {"attempt": str(attempt)})
    atomic_json(attempt / "in-progress.json", {"training_allowed": False})
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    shared_before = _shared_snapshot(shared)
    protected = [
        shared,
        shared.parent / "Godot/app_userdata/SlayTheSpire2",
        archive.parent,
        shared.parent / "Steam/steamapps",
        shared.parent / "Steam/userdata",
        *candidates.values(),
        runtime,
        localization,
        checker.parent,
    ]
    sandbox = attempt / "profile-isolation.sb"
    sandbox.write_text(_sandbox(protected))
    started = time.monotonic()
    try:
        cases: list[dict[str, Any]] = []
        previous: dict[tuple[str, str], dict[str, Any]] = {}
        fixture_starts = 0
        for seed in seeds:
            for relic in METHODS:
                for repeat in range(1, 3):
                    case = attempt / f"{seed}-{relic}-{repeat}"
                    case.mkdir()
                    rows = {}
                    for role in ("reference", "legacy", "repaired"):
                        cell = case / role
                        cell.mkdir()
                        profile = cell / "private-profile"
                        profile.mkdir()
                        output = cell / "private-fixture.json"
                        candidate = candidates["repaired" if role == "repaired" else "legacy"]
                        remaining = document["max_wall_seconds"] - (time.monotonic() - started)
                        if remaining < 1:
                            raise TimeoutError("Native reward check reached its stage cap")
                        process = _run_boot(
                            [
                                "/usr/bin/env",
                                f"STS2_NATIVE_LOCALIZATION={localization}",
                                "DOTNET_ROLL_FORWARD=LatestPatch",
                                "/usr/bin/sandbox-exec",
                                "-f",
                                str(sandbox),
                                str(runtime / "dotnet"),
                                str(checker),
                                str(candidate),
                                seed,
                                relic,
                                "original_normal" if role == "reference" else "test",
                                str(output),
                            ],
                            profile,
                            cell,
                            max(1, min(15, int(remaining))),
                        )
                        fixture_starts += 1
                        atomic_json(cell / "process.json", process)
                        if process["returncode"] or process["timed_out"] or not output.is_file():
                            raise ValueError(
                                f"Native reward fixture failed: {seed}/{relic}/{repeat}/{role}"
                            )
                        rows[role] = json.loads(output.read_text())
                    verdict = compare_reward_fixtures(rows, seed, relic, builds)
                    facts = {
                        role: {
                            key: row[key]
                            for key in ("generated_rewards", "private_before", "private_after")
                        }
                        for role, row in rows.items()
                    }
                    key = (seed, relic)
                    if repeat == 2 and facts != previous[key]:
                        raise ValueError("Repeated native reward fixture state changed")
                    previous[key] = facts
                    cases.append({"seed": seed, "relic": relic, "repeat": repeat, **verdict})
        after = verify_game_archive(qualification, archive)
        if (
            not after["valid"]
            or _shared_snapshot(shared) != shared_before
            or _inventory(runtime) != runtime_inventory
            or any(
                _inventory(candidate) != build_reports[role]["private_candidate_inventory"]
                for role, candidate in candidates.items()
            )
        ):
            raise ValueError(
                "Native reward check altered its archive, profile or candidate/runtime inputs"
            )
        verify_native_localization(qualification, document["native_localization"])
        if _sha_file(checker) != document["checker_sha256"]:
            raise ValueError("Native reward checker changed during execution")
        result = _finish(
            attempt,
            {
                "schema_version": "engine-native-reward-generation-v1",
                "config_id": manifest_identifier(document),
                "qualification_config_id": qualification.config_id,
                "build_report_ids": {
                    role: report["report_id"] for role, report in build_reports.items()
                },
                "checker_sha256": document["checker_sha256"],
                "archive_verification_before": before["report_id"],
                "archive_verification_after": after["report_id"],
                "status": "native_original_method_differentials_pass",
                "planned_cases": 8,
                "completed_cases": len(cases),
                "native_fixture_starts": fixture_starts,
                "independent_seeds": 2,
                "seed_relic_pairs": 4,
                "repeated_private_state_identical": True,
                "cases": cases,
                "shared_profile_unchanged": True,
                "wall_seconds": time.monotonic() - started,
                "privileged_fixture": True,
                "shipped_game_compared": False,
                "full_run_attempts": 0,
                "reward_selections": 0,
                "optimizer_steps": 0,
                "training_allowed": False,
                "mechanics_qualified": False,
                "claim_scope": (
                    "two_relics_generation_and_population_only_shared_native_initialization_"
                    "stubs_and_pools_not_pickup_or_shipped_UI_parity"
                ),
            },
        )
        atomic_json(workspace / "report.json", result)
        (workspace / "in-progress.json").unlink()
        return result
    except BaseException as error:
        _failure(attempt, error)
        raise
