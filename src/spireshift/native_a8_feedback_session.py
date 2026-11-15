"""Prepare exact checkpoint copies, then compare their fresh normal-start A8 play."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_control import MECHANICS, check_endings, trial
from spireshift.native_a8_feedback_credit import ARMS, ROOM_WEIGHT, audited_source, fit
from spireshift.native_a8_feedback_host import AREA, SCRIPT, load_adapter, worker
from spireshift.native_a8_own_training import FAILURES, SCOPE, State
from spireshift.native_a8_own_training_inputs import admitted_context, declaration
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_structured_state import load
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_feedback_session"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-combat-feedback-v1.json"
WRAPPER = "scripts/compare-a8-combat-feedback-v1.sh"
SCHEMA = "native-a8-matched-combat-feedback-v1"
RESULT = "docs/evidence/native-a8-own-training-result-v1.json"
PREPARED = "matched_combat_feedback_ready"
DEVELOPMENT = [f"SP1RESH1FTA8CF1D{i:03d}" for i in range(1, 9)]
LIMITS = {
    "wall_seconds": 5400,
    "cpu_seconds": 14400,
    "storage_bytes": 4_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
SHORT_LIMITS = {**LIMITS, "wall_seconds": 260, "cpu_seconds": 420}
PREFIX_CHOICES = 4


def implementation(root: Path) -> dict[str, str]:
    names = [
        WRAPPER,
        *(f"scripts/{name}" for name in worker_helpers(root, SCRIPT)),
        *(
            f"src/spireshift/native_a8_feedback_{part}.py"
            for part in ("control", "credit", "host", "session")
        ),
    ]
    return {name: _sha_file(root / name) for name in sorted(set(names))}


def inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], ChunkJournal, dict[str, Any]]:
    cfg = json.loads((root / RECIPE).read_text())
    old = declaration(root)
    ctx, runtime = admitted_context(root, old)
    evidence = identified(verified(root, cfg["source_audit"]))
    mechanics = identified(verified(root, cfg["source_mechanics"]))
    source, report = audited_source(root, old, evidence, mechanics["study"]["report"])
    study_seeds = {
        *old["study"]["development"],
        *old["control"]["reload"],
        *(task["seed"] for task in old["study"]["training"] + old["control"]["training"]),
        *ctx["paired_panel"]["worlds"],
    }
    new_seeds = [*cfg["development"], cfg["trial_seed"], cfg["prefix_seed"]]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["actor_room_weight"] != ROOM_WEIGHT
        or cfg["environment_id"] != ctx["environment_id"]
        or cfg["policy_contract"] != old["policy_contract"]
        or cfg["game_limits"] != old["game_limits"]
        or cfg["objective"] != old["objective"]
        or cfg["development"] != DEVELOPMENT
        or cfg["source_audit"]["path"] != RESULT
        or cfg["source_mechanics"]["path"] != MECHANICS
        or cfg["implementation"] != implementation(root)
        or len(set(new_seeds)) != len(new_seeds)
        or study_seeds.intersection(new_seeds)
        or any(canonical_seed(seed) != seed for seed in new_seeds)
        or mechanics["environment_id"] != ctx["environment_id"]
    ):
        raise ValueError("Combat feedback recipe differs from the frozen, disjoint comparison")
    raw = verified(root, cfg["saved_victory_raw"])
    match = verified(root, mechanics["architect"]["matched_saving_disabled_diagnostic"])
    if raw != match.with_name("native-check.json"):
        raise ValueError("Require the exact saved native victory trace")
    return (
        cfg,
        {
            **ctx,
            "confirmation_adapter": load_adapter(root, ctx, cfg["adapter_build"]),
            "execution_id": manifest_identifier(cfg),
        },
        runtime,
        source,
        report,
    )


def preparation(root: Path, cfg: dict[str, Any]) -> ChunkJournal:
    return ChunkJournal(root, {**cfg, "workspace": cfg["preparation_workspace"]})


def run_game(
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    task: dict[str, Any],
    target: Path,
    state: State,
    deadline: float,
) -> dict[str, Any]:
    limits = cfg["game_limits"].copy()
    if task["partition"] == "reload_control":
        limits["maximum_decisions"] = PREFIX_CHOICES
    with patch.object(native_a8_own_experience, "worker", worker):
        return native_a8_own_experience.play(
            {**ctx, "config": {"plan": limits}}, task, target, state[0], deadline
        )


def copied_state(store: ChunkJournal, player: int, arm: str, result: dict[str, Any]) -> State:
    state = load(store.path(f"fit-p{player}") / arm / "state.json")
    checkpoint = result["checkpoints"][arm]
    if (
        state[2] != checkpoint["state_id"]
        or state[0].model_id != checkpoint["model_id"]
        or manifest_identifier(state[1].as_dict()) != checkpoint["optimizer_id"]
        or state[1].steps != checkpoint["optimizer_steps"]
    ):
        raise ValueError("Prepared full model or Adam state differs")
    return state


def prepare(
    root: Path,
    cfg: dict[str, Any],
    ctx: dict[str, Any],
    runtime: dict[str, Any],
    source: ChunkJournal,
    report: dict[str, Any],
    deadline: float,
) -> dict[str, Any]:
    store = preparation(root, cfg)
    before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    with store.lock():
        boundary(root, ctx, before, profile)
        mechanics = identified(verified(root, cfg["source_mechanics"]))
        saved = check_endings(root, ctx["node"], mechanics)
        trial_request = {"seed": cfg["trial_seed"], "diagnostic_only": True}
        control = trial(
            ctx, store.begin("trial", trial_request) / "control", cfg["trial_seed"], deadline
        )
        boundary(root, ctx, before, profile)
        trial_seal = store.commit("trial", trial_request, control)
        fits = {}
        prefixes = {}
        for player in PLAYERS:
            key = f"fit-p{player}"
            request = {"player": player, "source_report_id": report["report_id"]}
            target = store.begin(key, request)
            result = fit(source, report, ctx, player, target)
            fits[str(player)] = store.commit(key, request, result)["report_id"]
            print(
                f"p{player}: {result['decisions']} matched decisions, "
                f"{result['room_credit_decisions']} with room feedback, "
                f"{result['matched_optimizer_updates_per_fitted_arm']} updates per fitted arm.",
                flush=True,
            )
            for arm in ARMS:
                key = f"prefix-p{player}-{arm}"
                task = {
                    "key": key,
                    "player": player,
                    "arm": arm,
                    "seed": cfg["prefix_seed"],
                    "partition": "reload_control",
                }
                state = copied_state(store, player, arm, result)
                request = {"task": task, "state_id": state[2]}
                row = run_game(ctx, cfg, task, store.begin(key, request), state, deadline)
                if row["outcome"] != "capped" or row["native_decisions"] != PREFIX_CHOICES:
                    raise ValueError("Reloaded model did not deliver its exact short prefix")
                boundary(root, ctx, before, profile)
                prefixes[key] = store.commit(key, request, row)["report_id"]
        check_sources(root, cfg["implementation"])
        if execution_runtime(ctx["node"]) != runtime:
            raise ValueError("The frozen numerical runtime changed")
        return write(
            store.workspace / "report.json",
            {
                "status": PREPARED,
                "config_id": store.config_id,
                "source_report_id": report["report_id"],
                "saved_endings": saved,
                "trial": control,
                "trial_seal": trial_seal["report_id"],
                "fits": fits,
                "prefixes": prefixes,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "development_games": 0,
            },
        )


def require_preparation(
    root: Path, cfg: dict[str, Any], report: dict[str, Any]
) -> tuple[dict[str, Any], dict[tuple[int, str], State]]:
    store = preparation(root, cfg)
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(root, cfg["preparation_resource"]))
    trial_seal = store.completed("trial", {"seed": cfg["trial_seed"], "diagnostic_only": True})
    if (
        proof["status"] != PREPARED
        or proof["config_id"] != store.config_id
        or proof["source_report_id"] != report["report_id"]
        or proof["development_games"] != 0
        or proof["saved_endings"]
        != {"saved_correct_endings_accepted": 73, "flipped_labels_rejected": 73}
        or trial_seal is None
        or proof["trial_seal"] != trial_seal["report_id"]
        or proof["trial"] != trial_seal["result"]
        or proof["trial"]["status"] != "native_confirmation_control_verified"
        or proof["trial"]["native_deliveries"] != 5
        or not all(proof["frozen_checks"].values())
        or proof["shared_profile_unchanged"] is not True
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["limits"] != SHORT_LIMITS
        or resource["command"][:7]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute-preparation"]
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact successful mechanics and matched fitting checks")
    states = {}
    initial_inputs = set()
    for player in PLAYERS:
        key = f"fit-p{player}"
        seal = store.completed(key, {"player": player, "source_report_id": report["report_id"]})
        if seal is None or seal["report_id"] != proof["fits"][str(player)]:
            raise ValueError("Missing verified exact fitted checkpoint")
        for arm in ARMS:
            state = copied_state(store, player, arm, seal["result"])
            states[player, arm] = state
            key = f"prefix-p{player}-{arm}"
            task = {
                "key": key,
                "player": player,
                "arm": arm,
                "seed": cfg["prefix_seed"],
                "partition": "reload_control",
            }
            prefix = store.completed(key, {"task": task, "state_id": state[2]})
            if prefix is None or prefix["report_id"] != proof["prefixes"][key]:
                raise ValueError("Missing native reload check for the exact full state")
            initial_inputs.add(prefix["result"]["initial_public_input_id"])
    if len(initial_inputs) != 1:
        raise ValueError("The reload checks started from different normal-start public inputs")
    return proof, states


def tasks(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for index, seed in enumerate(cfg["development"], 1):
        for player in PLAYERS:
            rotation = (index + player) % len(ARMS)
            for arm in ARMS[rotation:] + ARMS[:rotation]:
                result.append(
                    {
                        "key": f"dev-{index:02d}-p{player}-{arm}",
                        "seed": seed,
                        "player": player,
                        "arm": arm,
                        "partition": "development",
                    }
                )
    return result


def compare(
    root: Path,
    cfg: dict[str, Any],
    ctx: dict[str, Any],
    runtime: dict[str, Any],
    source_report: dict[str, Any],
    attempt: int,
    deadline: float,
) -> dict[str, Any]:
    proof, states = require_preparation(root, cfg, source_report)
    store = ChunkJournal(root, cfg)
    before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    games: dict[str, Any] = {}
    initials: dict[str, str] = {}
    rows: dict[tuple[str, int, str], dict[str, Any]] = {}
    stop = None
    key = "preflight"

    def check() -> None:
        if time.monotonic() >= deadline:
            raise TimeoutError("Study deadline reached; preserve the unfinished unit")
        if json.loads((root / RECIPE).read_text()) != cfg:
            raise ValueError("Combat feedback recipe changed")
        check_sources(root, cfg["implementation"])
        boundary(root, ctx, before, profile)

    with store.lock():
        try:
            for task in tasks(cfg):
                key, seed, player, arm = (task[name] for name in ("key", "seed", "player", "arm"))
                state = states[player, arm]
                request = {"task": task, "state_id": state[2], "preparation_id": proof["report_id"]}
                seal = store.completed(key, request)
                if seal is None:
                    check()
                    target = store.begin(key, request)
                    row = run_game(ctx, cfg, task, target, state, deadline)
                    check()
                else:
                    row = seal["result"]
                initial = row["initial_public_input_id"]
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or not initial
                    or initials.setdefault(seed, initial) != initial
                ):
                    raise ValueError("A matched world or its frozen checkpoint differs")
                if seal is None:
                    seal = store.commit(key, request, row)
                    print(f"{key} {row['outcome']} (floor {row['maximum_floor']})", flush=True)
                games[key] = {"seal_id": seal["report_id"], **row}
                rows[seed, player, arm] = row
            key = "final_verification"
            check()
            final, _ = require_preparation(root, cfg, source_report)
            if final != proof or execution_runtime(ctx["node"]) != runtime:
                raise ValueError("Prepared states or numerical runtime changed during evaluation")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
            for task in tasks(cfg):
                if key == task["key"] and store.path(key).exists():
                    rows[task["seed"], task["player"], task["arm"]] = {"outcome": "failed"}
        comparisons = {}
        for left, right in (("floor", "room"), ("original", "room"), ("original", "floor")):
            comparisons[f"{right}_minus_{left}"] = summarize(
                cfg["development"],
                {
                    (seed, player, "original" if arm == left else "fitted"): row
                    for (seed, player, arm), row in rows.items()
                    if arm in (left, right)
                },
            )
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": SCHEMA,
                "status": "stopped_preserving_evidence"
                if stop
                else "matched_combat_feedback_complete",
                "stop": stop,
                "config_id": store.config_id,
                "preparation_id": proof["report_id"],
                "games": games,
                "planned_worlds": cfg["development"],
                "planned_games": len(tasks(cfg)),
                "development": comparisons,
                "optimizer_updates": 0,
                "frozen_checks": before if stop is None else None,
                "shared_profile_unchanged": True if stop is None else None,
                **SCOPE,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute-preparation", type=int)
    modes.add_argument("--execute-study", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned launcher with the fixed numerical settings")
        cfg, ctx, runtime, source, report = inputs(root)
        if args.preflight:
            proof, _ = require_preparation(root, cfg, report)
            print(
                json.dumps(
                    {
                        "status": PREPARED,
                        "preparation_id": proof["report_id"],
                        "games": len(tasks(cfg)),
                        "frozen_checks": frozen(root, ctx),
                    }
                )
            )
            return 0
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        if args.execute_preparation:
            result = prepare(
                root, cfg, ctx, runtime, source, report, started + SHORT_LIMITS["wall_seconds"] - 12
            )
            print(json.dumps(result), flush=True)
            return 0
        if args.execute_study:
            result = compare(
                root,
                cfg,
                ctx,
                runtime,
                report,
                args.execute_study,
                started + LIMITS["wall_seconds"] - 20,
            )
            print(json.dumps({k: v for k, v in result.items() if k != "games"}), flush=True)
            return 0 if result["stop"] is None else 2
        attempt = time.time_ns()
        if args.prepare:
            workspace = preparation(root, cfg).workspace
            resource = _private_path(root, cfg["preparation_resource"])
            if workspace.exists() or resource.exists():
                raise FileExistsError("Preserve the existing short check and its resource receipt")
            mode, limits = "--execute-preparation", SHORT_LIMITS
        else:
            require_preparation(root, cfg, report)
            workspace = _private_path(root, cfg["workspace"])
            resource = _private_path(root, f"{AREA}/comparison-v1-{attempt}-resources.json")
            mode, limits = "--execute-study", LIMITS
            print(
                "48 normal-start Ironclad/A8 games. About 10–25 minutes, 90-minute cap. "
                "Three frozen model-only arms per world and initializer. Zero updates.",
                flush=True,
            )
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, mode, str(attempt)],
            experiment_kind=ExperimentKind.TRAINING if args.prepare else ExperimentKind.OTHER,
            report_path=resource,
            artifact_roots=[workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except FAILURES as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
