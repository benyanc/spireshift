"""Compare frozen expanded and original archive fits on fresh A8 worlds."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_archive_batch import known_seeds
from spireshift.native_a8_archive_expand_fit import admit, request
from spireshift.native_a8_archive_fit_session import ERRORS, check_inputs
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_mix_session import PREFIX_CHOICES, game
from spireshift.native_a8_own_training import SCOPE, State, restored
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import ARMS, TERMINAL, summarize
from spireshift.native_a8_tactical_session import boundary
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_archive_expand_compare"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-expanded-archive-compare-v1.json"
AREA = "artifacts/native-a8-archive-fitting"
SCHEMA = "native-a8-expanded-archive-comparison-v1"
COMPLETE = "a8_expanded_archive_comparison_complete"
CONTROL = "a8_expanded_archive_control_verified"
LIMITS = {
    "wall_seconds": 1800,
    "cpu_seconds": 3600,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}
SHORT_LIMITS = {**LIMITS, "wall_seconds": 250, "cpu_seconds": 400}
DEVELOPMENT = [f"SP1RESH1FTA8AEXD{i:03d}" for i in range(1, 13)]
PREFIX_WORLD = "SP1RESH1FTA8AEXC003"
ENDING_WORLD = "SP1RESH1FTA8AEXC004"


def tasks(cfg: dict[str, Any], control: bool) -> list[dict[str, Any]]:
    worlds = [cfg["prefix_world"]] if control else cfg["development"]
    result = [
        {
            "key": f"world-{i:02d}-p{p}-{arm}",
            "player": p,
            "seed": seed,
            "arm": arm,
            "partition": "reload_control" if control else "development",
        }
        for i, seed in enumerate(worlds, 1)
        for p in PLAYERS
        for arm in (ARMS if (p + i) % 2 == 0 else ARMS[::-1])
    ]
    if control:
        result.append(
            {
                "key": "ending-p2-fitted",
                "player": 2,
                "seed": cfg["ending_world"],
                "arm": "fitted",
                "partition": "ending_control",
            }
        )
    return result


def store_for(root: Path, cfg: dict[str, Any], control: bool) -> ChunkJournal:
    return ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]} if control else cfg)


def resource_path(store: ChunkJournal) -> Path:
    return store.workspace.with_name(f"{store.workspace.name}-resources.json")


def require_control(root: Path, cfg: dict[str, Any], states: dict[tuple[int, str], State]) -> str:
    store = store_for(root, cfg, True)
    report = identified(store.workspace / "report.json")
    receipt = identified(resource_path(store))
    plan = tasks(cfg, True)
    if (
        report["status"] != CONTROL
        or report["config_id"] != store.config_id
        or report["stop"] is not None
        or report["optimizer_updates"] != 0
        or not all(report["frozen_checks"].values())
        or set(report["seals"]) != {task["key"] for task in plan}
        or receipt["status"] != "completed"
        or receipt["exit_code"] != 0
        or receipt["cap"] is not None
        or receipt["limits"] != SHORT_LIMITS
        or receipt["command"]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", "control"]
        or receipt["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact native checks for the two sealed fits")
    for task in plan:
        key = task["key"]
        state = states[task["player"], task["arm"]]
        seal = store.completed(key, {"task": task, "state_id": state[2], "control_id": None})
        if seal is None or seal["report_id"] != report["seals"][key]:
            raise ValueError("A short native check changed")
    return str(report["report_id"])


def compare(root: Path, control: bool, deadline: float, execute: bool, preflight: bool) -> int:
    study, fit_cfg, partitions, parents = admit(root)
    cfg = json.loads((root / RECIPE).read_text())
    fit_store = ChunkJournal(root, fit_cfg)
    proof_path = verified(root, cfg["fit_result"])
    proof = identified(proof_path)
    seeds = [*cfg["development"], cfg["prefix_world"], cfg["ending_world"]]
    used = (
        known_seeds(study.base)
        | {case["seed"] for case in study.bank["worlds"].values()}
        | set(partitions["train"])
        | set(partitions["holdout"])
        | set(study.cfg["development"] + study.cfg["final_test"])
        | {study.cfg["control"]["prefix_world"], study.cfg["control"]["ending_world"]}
    )
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["objective"] != study.cfg["objective"]
        or cfg["environment_id"] != study.base.ctx["environment_id"]
        or proof_path != fit_store.workspace / "report.json"
        or proof["config_id"] != fit_store.config_id
        or proof["partitions"] != partitions
        or proof["frozen_checks"] != study.frozen_checks
        or cfg["development"] != DEVELOPMENT
        or cfg["prefix_world"] != PREFIX_WORLD
        or cfg["ending_world"] != ENDING_WORLD
        or cfg["workspace"] != f"{AREA}/expanded-comparison-v1"
        or cfg["control_workspace"] != f"{AREA}/expanded-comparison-control-v2"
        or len(seeds) != len(set(seeds))
        or used.intersection(seeds)
        or any(canonical_seed(seed) != seed for seed in seeds)
        or cfg["workspace"] == cfg["control_workspace"]
    ):
        raise ValueError("Require exact frozen fits and fresh development worlds")
    check_sources(root, cfg["implementation"])
    states = {(p, "original"): parents[p] for p in PLAYERS}
    for p in PLAYERS:
        key = f"fit-p{p}"
        seal = fit_store.completed(key, request(study, partitions, p))
        if seal is None or seal["report_id"] != proof["seals"][key]:
            raise ValueError("A frozen expanded checkpoint differs")
        states[p, "fitted"] = restored(fit_store, key, seal)
    control_id = None if control else require_control(root, cfg, states)
    store = store_for(root, cfg, control)
    plan = tasks(cfg, control)
    limits = SHORT_LIMITS if control else LIMITS
    if preflight:
        print(
            json.dumps(
                {
                    "status": "expanded_archive_comparison_ready",
                    "control_id": control_id,
                    "planned_games": len(plan),
                    "frozen_checks": study.frozen_checks,
                }
            )
        )
        return 0
    path = store.workspace / "report.json"
    if path.is_file():
        result = identified(path)
        if result["config_id"] != store.config_id or result["control_id"] != control_id:
            raise ValueError("Saved comparison belongs to another recipe")
        for task in plan:
            key = task["key"]
            if key in result["seals"]:
                state = states[task["player"], task["arm"]]
                seal = store.completed(
                    key,
                    {
                        "task": task,
                        "state_id": state[2],
                        "control_id": control_id,
                    },
                )
                if seal is None or seal["report_id"] != result["seals"][key]:
                    raise ValueError("A saved comparison seal differs")
        print(json.dumps({k: v for k, v in result.items() if k not in {"cases", "seals"}}))
        return 0 if result["status"] in {COMPLETE, CONTROL} else 2
    if _running_games():
        raise ValueError("Close STS2 and wait for any other native worker")
    if not execute:
        if not control:
            print("Compare 48 fresh A8 games with both frozen fits. Allow about 8 to 15 minutes.")
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                MODULE,
                "--execute",
                "control" if control else "study",
            ],
            experiment_kind=ExperimentKind.OTHER,
            report_path=resource_path(store),
            artifact_roots=[store.workspace],
            working_directory=root,
            limits=ResourceLimits(**limits),
        )
        print(json.dumps(tracked.report))
        return 2 if tracked.exit_code is None else tracked.exit_code

    base, before = study.base, study.frozen_checks
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    rows, seals, outcomes = {}, {}, {}
    initial: dict[str, str] = {}
    stop = None
    with store.lock():
        for task in plan:
            key, seed, p, arm = (task[k] for k in ("key", "seed", "player", "arm"))
            state = states[p, arm]
            spec = {"task": task, "state_id": state[2], "control_id": control_id}
            try:
                seal = store.completed(key, spec)
                if seal is None:
                    if time.monotonic() >= deadline - 45:
                        raise TimeoutError("Preserve the remaining unstarted games")
                    boundary(root, base.ctx, before, profile)
                    store.begin(key, spec)
                    row = game(base, store, task, state, deadline)
                    boundary(root, base.ctx, before, profile)
                else:
                    row = seal["result"]
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or initial.setdefault(seed, row["initial_public_input_id"])
                    != row["initial_public_input_id"]
                    or row["outcome"] not in {*TERMINAL, "capped"}
                ):
                    raise ValueError("The matched start, model or outcome differs")
                if task["partition"] == "reload_control" and (
                    row["outcome"],
                    row["native_decisions"],
                ) != ("capped", PREFIX_CHOICES):
                    raise ValueError("The short check did not reach its exact prefix")
                if task["partition"] == "ending_control" and row["outcome"] not in TERMINAL:
                    raise ValueError("The ending control did not reach a genuine native ending")
                if seal is None:
                    seal = store.commit(key, spec, row)
                    print(f"{key} {row['outcome']} at floor {row['maximum_floor']}", flush=True)
                rows[key], seals[key], outcomes[seed, p, arm] = row, seal["report_id"], row
            except ERRORS as exc:
                stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
                if store.path(key).exists():
                    outcomes[seed, p, arm] = {"outcome": "failed"}
                break
        check_inputs(study)
        check_sources(root, cfg["implementation"])
        boundary(root, base.ctx, before, profile)
        for p in PLAYERS:
            seal = fit_store.completed(f"fit-p{p}", request(study, partitions, p))
            if seal is None or seal["report_id"] != proof["seals"][f"fit-p{p}"]:
                raise ValueError("The sealed expanded checkpoint changed during evaluation")
        complete = (
            stop is None
            and len(rows) == len(plan)
            and (control or all(row["outcome"] in TERMINAL for row in rows.values()))
        )
        status = (CONTROL if control else COMPLETE) if complete else "comparison_incomplete"
        development = None if control else summarize(cfg["development"], outcomes)
        if development is not None:
            development["act1_clears"] = {
                str(p): {
                    arm: sum(
                        outcomes.get((seed, p, arm), {}).get("completed_acts", 0) >= 1
                        for seed in cfg["development"]
                    )
                    for arm in ARMS
                }
                for p in PLAYERS
            }
        result = write(
            path,
            {
                "schema_version": SCHEMA,
                "config_id": store.config_id,
                "fit_report_id": proof["report_id"],
                "control_id": control_id,
                "status": status,
                "planned_games": len(plan),
                "development": development,
                "cases": rows,
                "seals": seals,
                "stop": stop,
                "frozen_checks": before,
                "optimizer_updates": 0,
                **SCOPE,
            },
        )
    print(json.dumps({k: v for k, v in result.items() if k not in {"cases", "seals"}}))
    return 0 if complete else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--control", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", choices=("control", "study"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        control = args.control or args.execute == "control"
        limits = SHORT_LIMITS if control else LIMITS
        return compare(
            Path.cwd(),
            control,
            time.monotonic() + limits["wall_seconds"] - 12,
            execute=args.execute is not None,
            preflight=args.preflight,
        )
    except ERRORS as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
