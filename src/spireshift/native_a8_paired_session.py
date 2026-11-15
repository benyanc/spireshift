"""Compare both frozen update-200 players with their originals on fresh A8 worlds."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_paired_inputs import PLAYERS, freeze, load
from spireshift.native_a8_paired_report import ARMS, diagnostics, summarize
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import episode, prepare, write
from spireshift.native_win5_inputs import completed

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-paired-finals-v1.json"
AREA = "artifacts/native-a8-paired"
WORLDS = [f"SP1RESH1FTA8PA1R{i:03d}" for i in range(1, 13)]
CONTROL = "SP1RESH1FTA8PA1RC01"
LIMITS = {
    "wall_seconds": 5400,
    "cpu_seconds": 14400,
    "resident_memory_bytes": 4000000000,
    "storage_bytes": 4000000000,
}
GAME_LIMIT_KEYS = (
    "episode_cpu_seconds",
    "episode_wall_seconds",
    "maximum_decisions",
    "maximum_rounds_per_fight",
)
IMPLEMENTATION = (
    "src/spireshift/native_a8_architect_check.py",
    "src/spireshift/native_a8_paired_inputs.py",
    "src/spireshift/native_a8_paired_report.py",
    "src/spireshift/native_a8_paired_session.py",
    "scripts/compare-a8-fitted-v1.sh",
)


def declaration(root: Path) -> dict[str, Any]:
    cfg = json.loads((root / RECIPE).read_text())
    if (
        cfg["schema_version"] != "native-a8-paired-finals-v1"
        or cfg["workspace"] != f"{AREA}/study-v1"
        or cfg["worlds"] != WORLDS
        or cfg["control_world"] != CONTROL
        or cfg["session_limits"] != LIMITS
        or cfg["implementation"] != {name: _sha_file(root / name) for name in IMPLEMENTATION}
    ):
        raise ValueError("Use the exact finite development comparison and source files")
    return dict(cfg)


def binding(cfg: dict[str, Any]) -> str:
    return manifest_identifier({k: v for k, v in cfg.items() if k != "short_control"})


def qualified_inputs(root: Path, cfg: dict[str, Any], *, control: bool) -> dict[str, Any]:
    ctx = load(root)
    plan = ctx["config"]["plan"]
    used = set(
        json.loads(verified(root, ctx["config"]["seed_history"]).read_text())[
            "canonical_prior_seeds"
        ]
    )
    used.update(plan["reserved_evaluation_seeds"])
    for phase in ("fit", "heldout"):
        used.update(seed for case in plan[phase] for seed in case["seed_pool"])
    for failure in ctx["historical_failures"]:
        used.update(failure["case"]["seed_pool"])
    endpoint = identified(verified(root, cfg["architect"]["report"]))
    completed(root, cfg["architect"]["resource"])
    objective = ObjectiveSpec.from_mapping(ctx["native"]["objective"])
    if (
        ({*WORLDS, CONTROL} & (used | {endpoint["seed"]}))
        or cfg["game_limits"] != {key: plan[key] for key in GAME_LIMIT_KEYS}
        or cfg["objective"] != objective.as_dict()
        or objective != ctx["score"].evaluation_objective
        or objective.whole_run_budget != cfg["game_limits"]["episode_cpu_seconds"]
        or endpoint["status"] != "architect_persistence_verified"
        or endpoint["environment_id"] != ctx["environment"]["manifest_id"]
        or endpoint["objective"] != cfg["objective"]
        or endpoint["fitting_evidence_id"] != ctx["fitting_evidence"]["report_id"]
        or not endpoint["checks"]
        or not all(endpoint["checks"].values())
        or endpoint["normal_start_evaluation_wins"] != 0
        or endpoint["optimizer_updates"] != 0
        or cfg["fitting_evidence_id"] != endpoint["fitting_evidence_id"]
    ):
        raise ValueError(
            "Require fresh worlds, the frozen objective and verified Architect persistence"
        )
    check_sources(root, endpoint["sources"])
    check_sources(root, endpoint["evidence"])
    if not control:
        proof = identified(verified(root, cfg["short_control"]["report"]))
        completed(root, cfg["short_control"]["resource"])
        if (
            proof["status"] != "four_frozen_normal_start_prefixes_verified"
            or proof["binding_id"] != binding(cfg)
            or proof["control_world"] != CONTROL
            or proof["native_deliveries"] != 24
            or proof["optimizer_updates"] != 0
            or proof["main_games"] != 0
        ):
            raise ValueError("The exact four-cell short check is required")
        check_sources(root, proof["evidence"])
    return ctx


def tasks(worlds: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "key": f"world-{index + 1:02d}-p{player}-{arm}",
            "world": world,
            "player": player,
            "arm": arm,
        }
        for index, world in enumerate(worlds)
        for player in PLAYERS
        for arm in (ARMS if (index + player) % 2 == 0 else ARMS[::-1])
    ]


def play(
    ctx: dict[str, Any], task: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    model = ctx["models" if task["arm"] == "original" else "finals"][task["player"]]
    start = prepare(
        ctx,
        {
            "key": task["key"],
            "seed_pool": [task["world"]],
            "player": task["player"],
            "partition": "a8_development_evaluation",
            "entry": "natural",
        },
        target,
        deadline,
    )
    result = episode(ctx, start, "student", target, deadline, model=model)
    ending = result["native_ending"]
    if result["status"] == "capped":
        outcome = "capped"
    elif (
        result["status"] == "complete"
        and result["native_terminal"] is True
        and ending
        and ending["native_ending_evidence_agrees"] is True
    ):
        outcome = "win" if result["full_run_win"] else "loss"
    else:
        raise ValueError("A complete game requires an independently checked native ending")
    if result["model_id"] != model.model_id or result["optimizer_updates"] != 0:
        raise ValueError("The selected checkpoint changed or received an update")
    return {
        **task,
        "outcome": outcome,
        "model_id": model.model_id,
        "native_terminal": result["native_terminal"],
        "verified_native_deliveries": result["actual_deliveries_independently_verified"],
        "initial_public_input_id": result["initial_public_input_id"],
        "episode_report_id": result["report_id"],
        **diagnostics(target / "shared-public.jsonl.gz", outcome == "win"),
    }


def same_start(rows: list[dict[str, Any]]) -> None:
    if len({row["initial_public_input_id"] for row in rows}) > 1:
        raise ValueError("A same-world cell has a different initial playable input or menu")


def run_control(
    root: Path, ctx: dict[str, Any], cfg: dict[str, Any], deadline: float
) -> dict[str, Any]:
    out = root / AREA / "control-v1"
    out.mkdir(parents=True, exist_ok=False)
    before = freeze(root, ctx)
    local_ctx = {
        **ctx,
        "config": {**ctx["config"], "plan": {**ctx["config"]["plan"], "maximum_decisions": 6}},
    }
    rows = []
    for task in tasks([CONTROL]):
        target = out / task["key"]
        target.mkdir()
        row = play(local_ctx, task, target, deadline)
        if (
            row["outcome"] != "capped"
            or row["native_terminal"]
            or row["verified_native_deliveries"] != 6
        ):
            raise ValueError("The short check requires exactly six delivered choices on every cell")
        rows.append(row)
        same_start(rows)
    if freeze(root, ctx) != before:
        raise ValueError("Frozen inputs changed during the short check")
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-paired-prefix-control-v1",
            "status": "four_frozen_normal_start_prefixes_verified",
            "binding_id": binding(cfg),
            "control_world": CONTROL,
            "initial_public_input_id": rows[0]["initial_public_input_id"],
            "cells": rows,
            "native_deliveries": sum(row["verified_native_deliveries"] for row in rows),
            "main_games": 0,
            "optimizer_updates": 0,
            "checks": before,
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )


def run_panel(
    root: Path,
    ctx: dict[str, Any],
    cfg: dict[str, Any],
    attempt: int,
    deadline: float,
) -> dict[str, Any]:
    store = ChunkJournal(root, cfg)
    planned = tasks(WORLDS)
    games: dict[tuple[str, int, str], dict[str, Any]] = {}
    same_world: dict[str, list[dict[str, Any]]] = {}
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    before = freeze(root, ctx)
    shared_before = _shared_snapshot(shared)
    stopped: dict[str, Any] | None = None
    with store.lock():
        chunks = store.workspace / "chunks"
        keys = {task["key"] for task in planned}
        if any(p.name not in keys for p in chunks.glob("*")):
            raise ValueError("Preserve unexpected study files")
        saved = {task["key"]: store.completed(task["key"], task) for task in planned}
        sealed_keys = [key for key, seal in saved.items() if seal is not None]
        if sealed_keys != [task["key"] for task in planned[: len(sealed_keys)]]:
            raise ValueError("Preserve the study. Its sealed games do not form a prefix.")
        for task in planned:
            world, player, arm = task["world"], task["player"], task["arm"]
            key = world, player, arm
            sealed = saved[task["key"]]
            if sealed is not None:
                row = sealed["result"]
                same_start([*same_world.get(world, []), row])
            else:
                if deadline - time.monotonic() < 150:
                    stopped = {"reason": "wall_reserve_at_clean_boundary"}
                    break
                target = store.begin(task["key"], task)
                try:
                    row = play(ctx, task, target, deadline)
                    same_start([*same_world.get(world, []), row])
                    store.commit(task["key"], task, row)
                except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    stopped = {"reason": "preserved_unsealed_game", "task": task, "error": str(exc)}
                    games[key] = {**task, "outcome": "failed"}
                    break
                print(f"{task['key']} {row['outcome']}", flush=True)
            games[key] = row
            same_world.setdefault(world, []).append(row)
        after = freeze(root, ctx)
        if after != before or _shared_snapshot(shared) != shared_before:
            raise ValueError("Frozen inputs or the shared STS2 profile changed")
        report = store.workspace / f"attempt-{attempt}.json"
        status = (
            "stopped_preserving_evidence"
            if stopped and stopped["reason"] == "preserved_unsealed_game"
            else "paused_at_clean_boundary"
            if stopped
            else "native_development_comparison_completed"
        )
        return write(
            report,
            {
                "schema_version": "native-a8-paired-finals-result-v1",
                "status": status,
                "config_id": store.config_id,
                "environment_id": ctx["environment"]["manifest_id"],
                "objective": cfg["objective"],
                "fitting_evidence_id": cfg["fitting_evidence_id"],
                "architect_report_id": identified(verified(root, cfg["architect"]["report"]))[
                    "report_id"
                ],
                "planned_worlds": WORLDS,
                "planned_games": len(planned),
                "summary": summarize(WORLDS, games),
                "cells": [
                    games.get((t["world"], t["player"], t["arm"]), {**t, "outcome": "unattempted"})
                    for t in planned
                ],
                "stop": stopped,
                "frozen_checks": after,
                "shared_profile_unchanged": True,
                "optimizer_updates": 0,
                "final_test_worlds_used": False,
                "official_live_qualification_granted": False,
                "promotion_allowed": False,
                "automatic_follow_up": False,
            },
        )


def owner_main(root: Path, cfg: dict[str, Any]) -> int:
    attempt = time.time_ns()
    command = [
        "uv",
        "run",
        "--no-sync",
        "spireshift",
        "resources",
        "run",
        "--kind",
        "other",
        "--report",
        f"artifacts/resources/a8-paired-finals-v1-{attempt}.json",
        "--artifact-root",
        cfg["workspace"],
        "--workers",
        "1",
    ]
    for flag, name in (
        ("--max-wall-seconds", "wall_seconds"),
        ("--max-cpu-seconds", "cpu_seconds"),
        ("--max-memory-bytes", "resident_memory_bytes"),
        ("--max-storage-bytes", "storage_bytes"),
    ):
        command.extend([flag, str(cfg["session_limits"][name])])
    command.extend(
        [
            "--",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-m",
            "spireshift.native_a8_paired_session",
            "--run",
            "--attempt",
            str(attempt),
        ]
    )
    print(
        "Compare each update-200 checkpoint with its original on 12 fresh Ironclad/A8 worlds.\n"
        "48 normal-start native games. Frozen game v0.111.0 / 41cef1ea, support build 60.\n"
        "Genuine terminal wins first, with act, boss, map and shop diagnostics.\n"
        "Zero updates. Clean seals resume. An uncertain game is preserved without retry.\n"
        "Allow about 10–30 minutes. The outer limit is 90 minutes.",
        flush=True,
    )
    return subprocess.call(command, cwd=root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--control", action="store_true")
    mode.add_argument("--run", action="store_true")
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root = Path.cwd()
    if _running_games():
        raise ValueError("Close STS2 before the isolated native comparison")
    cfg = declaration(root)
    if not args.run and not args.control:
        return owner_main(root, cfg)
    if any(os.environ.get(name) != "1" for name in THREADS):
        raise ValueError("Use the pinned single-thread numerical settings")
    started = time.monotonic()
    ctx = qualified_inputs(root, cfg, control=args.control)
    if args.control:
        result = run_control(root, ctx, cfg, started + 265)
    else:
        if args.attempt is None or args.attempt < 1:
            parser.error("Run through the resource-tracked owner launcher")
        result = run_panel(root, ctx, cfg, args.attempt, started + LIMITS["wall_seconds"] - 45)
    print(json.dumps({key: result[key] for key in ("status", "report_id", "optimizer_updates")}))
    return (
        0
        if result["status"]
        in {
            "four_frozen_normal_start_prefixes_verified",
            "native_development_comparison_completed",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
