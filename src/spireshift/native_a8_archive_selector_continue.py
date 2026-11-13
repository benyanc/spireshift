"""Compare the sealed A8 fits on the four worlds that never started."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift import native_a8_archive_expand_compare as previous
from spireshift import native_systematic_selectors_v2 as selectors
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_archive_batch import known_seeds
from spireshift.native_a8_archive_expand_fit import admit, request
from spireshift.native_a8_archive_fit_inputs import UPDATES, ArchiveFit
from spireshift.native_a8_archive_fit_session import ERRORS, check_inputs, fit_request, journal
from spireshift.native_a8_boss_checks import SHARED_PROFILE
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

MODULE = "spireshift.native_a8_archive_selector_continue"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-expanded-archive-selector-v2.json"
WRAPPER = "scripts/continue-a8-expanded-archive-v2.sh"
SCHEMA = "native-a8-expanded-archive-selector-continuation-v2"
CONTROL_PASSED = "native_selector_formats_verified"
COMPLETE = "a8_expanded_archive_selector_continuation_complete"
SHORT_LIMITS = {**previous.LIMITS, "wall_seconds": 220, "cpu_seconds": 360}
STOPPED = "world-08-p3-original"
UNSTARTED = previous.DEVELOPMENT[8:]
SCOPE_LIMITS = {"optimizer_updates": 0, "training_allowed": False, **SCOPE}


def implementation(root: Path) -> dict[str, str]:
    files = {
        WRAPPER,
        f"src/{MODULE.replace('.', '/')}.py",
        "src/spireshift/native_systematic_selectors_v2.py",
        "tests/unit/test_native_systematic_selectors.py",
    }
    for script in (
        selectors.WORKER,
        selectors.CONVERTER,
        selectors.MATRIX,
        selectors.SAVED,
        selectors.ORDERED_PROOF,
    ):
        files.update(f"scripts/{name}" for name in worker_helpers(root, script))
    return {name: _sha_file(root / name) for name in sorted(files)}


@dataclass
class Comparison:
    root: Path
    cfg: dict[str, Any]
    study: ArchiveFit
    fit_store: ChunkJournal
    fit_proof: dict[str, Any]
    fit_requests: dict[str, dict[str, Any]]
    baseline: dict[str, Any]
    states: dict[tuple[int, str], State]
    tasks: list[dict[str, Any]]

    def verify_fits(self) -> None:
        check_inputs(self.study)
        original = journal(self.study, False)
        for p in PLAYERS:
            key = f"fit-p{p}"
            reference = original.completed(key, fit_request(self.study, p, UPDATES))
            expanded = self.fit_store.completed(key, self.fit_requests[key])
            if (
                reference is None
                or reference["report_id"] != self.baseline["seals"][key]
                or expanded is None
                or expanded["report_id"] != self.fit_proof["seals"][key]
            ):
                raise ValueError("The frozen reference or expanded full checkpoint changed")

    def store(self, control: bool) -> ChunkJournal:
        recipe = {**self.cfg, "workspace": self.cfg["control_workspace"]} if control else self.cfg
        return ChunkJournal(self.root, recipe)


def load(root: Path) -> Comparison:
    cfg = json.loads((root / RECIPE).read_text())
    study, fit_cfg, partitions, parents = admit(root)
    parent_path = verified(root, cfg["parent_recipe"])
    old = json.loads(parent_path.read_text())
    old_store = previous.store_for(root, old, False)
    report_path = verified(root, cfg["parent_report"])
    report = identified(report_path)
    old_plan = previous.tasks(old, False)
    plan = [task for task in old_plan if task["seed"] in UNSTARTED]
    expected = {task["key"] for task in old_plan if task not in plan} - {STOPPED}
    seeds = list(cfg["control_seeds"].values())
    used = (
        known_seeds(study.base)
        | {case["seed"] for case in study.bank["worlds"].values()}
        | set(partitions["train"])
        | set(partitions["holdout"])
        | set(study.cfg["development"] + study.cfg["final_test"])
        | set(old["development"] + [old["prefix_world"], old["ending_world"]])
    )
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["environment_id"] != study.base.ctx["environment_id"]
        or cfg["objective"] != study.cfg["objective"]
        or cfg["development"] != UNSTARTED
        or cfg["workspace"] == cfg["control_workspace"]
        or parent_path != root / previous.RECIPE
        or report_path != old_store.workspace / "report.json"
        or report["config_id"] != old_store.config_id
        or report["status"] != "comparison_incomplete"
        or report["stop"]["unit"] != STOPPED
        or report["stop"]["error"]
        != ("ValueError: Native worker failed: Shop catalog is outside its declared current owner")
        or report["optimizer_updates"] != 0
        or report["frozen_checks"] != study.frozen_checks
        or len(plan) != 16
        or len(expected) != 31
        or set(report["cases"]) != expected
        or set(report["seals"]) != expected
        or any(old_store.path(task["key"]).exists() for task in plan)
        or set(cfg["control_seeds"]) != {"direct", "compact", "normal"}
        or len(set(seeds)) != 3
        or set(seeds) & used
        or any(canonical_seed(seed) != seed for seed in seeds)
        or cfg["implementation"] != implementation(root)
    ):
        raise ValueError(
            "Require the exact stopped comparison, fresh controls and 16 unstarted cases"
        )
    for name, ref in cfg["saved_evidence"].items():
        if verified(root, ref).parent != old_store.path(STOPPED) / "worker":
            raise ValueError(f"Saved {name} is outside the stopped selector episode")
    fit_store = ChunkJournal(root, fit_cfg)
    proof_path = verified(root, old["fit_result"])
    proof = identified(proof_path)
    if (
        proof_path != fit_store.workspace / "report.json"
        or proof["status"] != "expanded_archive_fits_sealed"
        or proof["config_id"] != fit_store.config_id
        or proof["partitions"] != partitions
        or proof["frozen_checks"] != study.frozen_checks
    ):
        raise ValueError("Require the exact sealed expanded fits")
    baseline = identified(verified(root, fit_cfg["baseline_result"]))
    states = {(p, "original"): parents[p] for p in PLAYERS}
    requests = {f"fit-p{p}": request(study, partitions, p) for p in PLAYERS}
    for p in PLAYERS:
        key = f"fit-p{p}"
        seal = fit_store.completed(key, requests[key])
        if seal is None or seal["report_id"] != proof["seals"][key]:
            raise ValueError("The sealed expanded fit differs")
        states[p, "fitted"] = restored(fit_store, key, seal)
    previous.require_control(root, old, states)
    return Comparison(root, cfg, study, fit_store, proof, requests, baseline, states, plan)


def control_plan(run: Comparison) -> dict[str, dict[str, Any]]:
    seeds = run.cfg["control_seeds"]
    return {
        "saved": {"evidence": run.cfg["saved_evidence"]},
        "direct": {"seed": seeds["direct"], "cards": 3},
        "compact": {"seed": seeds["compact"], "cards": 13},
        "normal": {
            "task": {
                "key": "normal",
                "seed": seeds["normal"],
                "player": 2,
                "arm": "fitted",
                "partition": "ending_control",
            },
            "state_id": run.states[2, "fitted"][2],
        },
    }


def saved_report(
    store: ChunkJournal, plan: dict[str, dict[str, Any]], accepted: str, **pins: Any
) -> dict[str, Any] | None:
    path = store.workspace / "report.json"
    if not path.is_file():
        return None
    result = identified(path)
    if (
        result["config_id"] != store.config_id
        or any(result[k] != v for k, v in pins.items())
        or (result["status"] == accepted and set(result["seals"]) != set(plan))
    ):
        raise ValueError("Saved selector report belongs to another experiment")
    for key, report_id in result["seals"].items():
        seal = store.completed(key, plan[key])
        if seal is None or seal["report_id"] != report_id or seal["result"] != result["cases"][key]:
            raise ValueError("Saved selector evidence changed")
    return result


def verify_boundary(run: Comparison, profile: dict[str, Any]) -> None:
    check_sources(run.root, run.cfg["implementation"])
    if json.loads((run.root / RECIPE).read_text()) != run.cfg:
        raise ValueError("Selector recipe changed during execution")
    for ref in (
        run.cfg["parent_recipe"],
        run.cfg["parent_report"],
        *run.cfg["saved_evidence"].values(),
    ):
        verified(run.root, ref)
    run.verify_fits()
    boundary(run.root, run.study.base.ctx, run.study.frozen_checks, profile)


def execute_controls(run: Comparison, store: ChunkJournal, deadline: float) -> dict[str, Any]:
    plan, base = control_plan(run), run.study.base
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    rows, seals = {}, {}
    with store.lock():
        for key, spec in plan.items():
            seal = store.completed(key, spec)
            if seal is None:
                if time.monotonic() >= deadline - 35:
                    raise TimeoutError("Selector controls reached their deadline")
                boundary(run.root, base.ctx, run.study.frozen_checks, profile)
                target = store.begin(key, spec)
                if key == "saved":
                    matrix = selectors.node(base.ctx, "--test", f"scripts/{selectors.MATRIX}")
                    (target / "selector-matrix.tap").write_text(matrix)
                    row = selectors.saved_selector(base.ctx, spec["evidence"])
                    row["systematic_matrix_passed"] = True
                elif key == "normal":
                    row = selectors.play(
                        base, store, spec["task"], run.states[2, "fitted"], deadline
                    )
                    if row["outcome"] not in TERMINAL:
                        raise ValueError(
                            "The normal-start check must reach a genuine native ending"
                        )
                else:
                    ctx = {**base.ctx, "execution_id": store.config_id}
                    row = selectors.shop_control(ctx, target, spec["seed"], spec["cards"], deadline)
                boundary(run.root, base.ctx, run.study.frozen_checks, profile)
                seal = store.commit(key, spec, row)
                print(f"Selector check {key} verified", flush=True)
            rows[key], seals[key] = seal["result"], seal["report_id"]
        verify_boundary(run, profile)
        return write(
            store.workspace / "report.json",
            {
                "schema_version": SCHEMA,
                "status": CONTROL_PASSED,
                "config_id": store.config_id,
                "cases": rows,
                "seals": seals,
                "fit_report_id": run.fit_proof["report_id"],
                "frozen_checks": run.study.frozen_checks,
                **SCOPE_LIMITS,
            },
        )


def study_plan(run: Comparison, control_id: str) -> dict[str, dict[str, Any]]:
    return {
        task["key"]: {
            "task": task,
            "state_id": run.states[task["player"], task["arm"]][2],
            "control_id": control_id,
        }
        for task in run.tasks
    }


def execute_study(
    run: Comparison, store: ChunkJournal, control_id: str, deadline: float
) -> dict[str, Any]:
    plan, base = study_plan(run, control_id), run.study.base
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    rows, seals, outcomes = {}, {}, {}
    starts: dict[str, str] = {}
    stop = None
    with store.lock():
        for key, spec in plan.items():
            task = spec["task"]
            seed, p, arm = task["seed"], task["player"], task["arm"]
            state = run.states[p, arm]
            try:
                seal = store.completed(key, spec)
                if seal is None:
                    if time.monotonic() >= deadline - 45:
                        raise TimeoutError("Preserve the remaining unstarted games")
                    boundary(run.root, base.ctx, run.study.frozen_checks, profile)
                    store.begin(key, spec)
                    row = selectors.play(base, store, task, state, deadline)
                    boundary(run.root, base.ctx, run.study.frozen_checks, profile)
                else:
                    row = seal["result"]
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or starts.setdefault(seed, row["initial_public_input_id"])
                    != row["initial_public_input_id"]
                    or row["outcome"] not in {*TERMINAL, "capped"}
                ):
                    raise ValueError("The matched start, model or outcome differs")
                if seal is None:
                    seal = store.commit(key, spec, row)
                    print(f"{key} {row['outcome']} at floor {row['maximum_floor']}", flush=True)
                rows[key], seals[key], outcomes[seed, p, arm] = row, seal["report_id"], row
            except ERRORS as exc:
                stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
                if store.path(key).exists():
                    outcomes[seed, p, arm] = {"outcome": "failed"}
                break
        verify_boundary(run, profile)
        complete = (
            stop is None
            and len(rows) == len(plan)
            and all(row["outcome"] in TERMINAL for row in rows.values())
        )
        development = summarize(UNSTARTED, outcomes)
        development["act1_clears"] = {
            str(p): {
                arm: sum(
                    outcomes.get((seed, p, arm), {}).get("completed_acts", 0) >= 1
                    for seed in UNSTARTED
                )
                for arm in ARMS
            }
            for p in PLAYERS
        }
        return write(
            store.workspace / "report.json",
            {
                "schema_version": SCHEMA,
                "config_id": store.config_id,
                "status": COMPLETE if complete else "comparison_incomplete",
                "control_id": control_id,
                "fit_report_id": run.fit_proof["report_id"],
                "parent_report_id": identified(verified(run.root, run.cfg["parent_report"]))[
                    "report_id"
                ],
                "parent_sealed_games": 31,
                "parent_stopped_unit": STOPPED,
                "pooled_with_parent": False,
                "planned_games": len(plan),
                "development": development,
                "cases": rows,
                "seals": seals,
                "stop": stop,
                "frozen_checks": run.study.frozen_checks,
                **SCOPE_LIMITS,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute", choices=("control", "study"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        run = load(Path.cwd())
        control = args.check or args.execute == "control"
        control_store = run.store(True)
        store = run.store(control)
        frozen = {"frozen_checks": run.study.frozen_checks, **SCOPE_LIMITS}
        checks = saved_report(
            control_store,
            control_plan(run),
            CONTROL_PASSED,
            fit_report_id=run.fit_proof["report_id"],
            **frozen,
        )
        if not control and (checks is None or checks["status"] != CONTROL_PASSED):
            raise ValueError("Require sealed saved, direct, compact and normal-start controls")
        if not control:
            resources = identified(previous.resource_path(control_store))
            if (
                resources["status"] != "completed"
                or resources["exit_code"] != 0
                or resources["cap"] is not None
                or resources["limits"] != SHORT_LIMITS
                or resources["command"]
                != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute", "control"]
                or resources["artifacts"]["roots"] != [str(control_store.workspace)]
            ):
                raise ValueError("Require the exact bounded control execution receipt")
        control_id = checks["report_id"] if checks else None
        expected = CONTROL_PASSED if control else COMPLETE
        existing = (
            checks
            if control
            else saved_report(
                store,
                study_plan(run, str(control_id)),
                COMPLETE,
                control_id=control_id,
                fit_report_id=run.fit_proof["report_id"],
                **frozen,
            )
        )
        if args.preflight:
            if existing is None:
                for key, spec in study_plan(run, str(control_id)).items():
                    store.completed(key, spec)
            run.verify_fits()
            print(
                json.dumps(
                    {
                        "status": "selector_continuation_ready"
                        if existing is None
                        else existing["status"],
                        "planned_games": len(run.tasks),
                        "worlds": UNSTARTED,
                        "control_id": control_id,
                        **frozen,
                    }
                )
            )
            return 0 if existing is None or existing["status"] == COMPLETE else 2
        if existing is None:
            if _running_games():
                raise ValueError("Close STS2 and wait for any other native worker")
            limits = SHORT_LIMITS if control else previous.LIMITS
            if args.execute is None:
                if not control:
                    print(
                        "Sixteen native A8 games on four previously unstarted worlds.", flush=True
                    )
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
                    report_path=previous.resource_path(store),
                    artifact_roots=[store.workspace],
                    working_directory=run.root,
                    limits=ResourceLimits(**limits),
                )
                print(json.dumps(tracked.report))
                return 2 if tracked.exit_code is None else tracked.exit_code
            deadline = time.monotonic() + limits["wall_seconds"] - 12
            existing = (
                execute_controls(run, store, deadline)
                if control
                else execute_study(run, store, str(control_id), deadline)
            )
        print(json.dumps({k: v for k, v in existing.items() if k not in {"cases", "seals"}}))
        return 0 if existing["status"] == expected else 2
    except ERRORS as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **SCOPE_LIMITS})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
