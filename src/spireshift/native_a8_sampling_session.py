"""Test whether more selective model sampling yields usable Act 1 training outcomes."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_audit import STATUS as AUDITED
from spireshift.native_a8_coverage_policy import Root
from spireshift.native_a8_coverage_session import AREA as COVERAGE_AREA
from spireshift.native_a8_coverage_session import Collection, load, request, require_control
from spireshift.native_a8_coverage_session import journal as coverage_journal
from spireshift.native_a8_feedback_session import LIMITS, SHORT_LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import game, unchanged
from spireshift.native_a8_own_training import FAILURES, SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_sampling_roots import (
    TEMPERATURES,
    SamplingContinuation,
    resolve,
    select_roots,
    source_game,
)
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

AREA = "artifacts/native-a8-sampling"
ASSESSMENT = f"{COVERAGE_AREA}/assessment-v1-1794243638550996000/report.json"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-sampling-v1.json"
WRAPPER = "scripts/compare-a8-sampling-v1.sh"
MODULE = "spireshift.native_a8_sampling_session"
SCHEMA = "native-a8-act1-sampling-v1"
READY = "act1_sampling_control_verified"
COMPLETE = "act1_sampling_comparison_complete"
TERMINAL = {"win", "loss"}


@dataclass(frozen=True)
class Study:
    coverage: Collection
    owner: dict[str, Any]
    cfg: dict[str, Any]
    roots: dict[str, Root]


def schedule(roots: list[dict[str, Any]], control: bool) -> list[dict[str, Any]]:
    phase = "control" if control else "training_only"
    return [
        {
            "key": f"{spec['id']}-draw-{draw}-{arm}",
            "seed": spec["source_task"]["seed"],
            "player": spec["source_task"]["player"],
            "partition": phase,
            "root": spec["id"],
            "draw": draw,
            "arm": arm,
        }
        for spec in roots
        if not control or spec["id"].endswith("-elite-1")
        for draw in range(1 if control else 2)
        for arm in TEMPERATURES
    ]


def expected(
    coverage: Collection, roots: list[dict[str, Any]] | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = coverage.temporal.base
    path = _private_path(base.root, ASSESSMENT)
    audit = identified(path)
    owner_path = verified(base.root, audit["owner"])
    owner = identified(owner_path)
    if (
        audit["status"] != AUDITED
        or audit["config_id"] != coverage_journal(coverage, False).config_id
        or audit["frozen_checks"] != frozen(base.root, base.ctx)
        or audit["outcomes"]["loss"] != len(coverage.cfg["study"])
        or any(audit["varied_roots_by_initializer"][str(p)] >= 2 for p in PLAYERS)
        or owner_path.parent != coverage_journal(coverage, False).workspace
    ):
        raise ValueError("Require the completed coverage audit and sparse suffix signal")
    if roots is None:
        roots = select_roots(coverage, owner)
    roster = [
        f"p{p}-{encounter}-{i}" for p in PLAYERS for encounter in ("boss", "elite") for i in (1, 2)
    ]
    if (
        [spec["id"] for spec in roots] != roster
        or any(
            spec["encounter"] not in {"boss", "elite"} or spec["hp"] * 2 < spec["max_hp"]
            for spec in roots
        )
        or any(
            len({s["source_task"]["seed"] for s in roots if s["source_task"]["player"] == p}) != 4
            for p in PLAYERS
        )
    ):
        raise ValueError("Require two healthy boss and two healthy elite roots per initializer")
    paths = (
        WRAPPER,
        "src/spireshift/native_a8_sampling_roots.py",
        "src/spireshift/native_a8_sampling_session.py",
        "src/spireshift/native_a8_coverage_audit.py",
    )
    return owner, {
        "schema_version": SCHEMA,
        "environment_id": coverage.cfg["environment_id"],
        "objective": coverage.cfg["objective"],
        "score_spec_id": coverage.cfg["score_spec_id"],
        "game_limits": coverage.cfg["game_limits"],
        "original_full_state_ids": coverage.cfg["original_full_state_ids"],
        "workspace": f"{AREA}/comparison-v1",
        "control_workspace": f"{AREA}/control-v1",
        "control_resource": f"{AREA}/control-v1-resources.json",
        "source_audit": source(base.root, path),
        "implementation": {path: _sha_file(base.root / path) for path in paths},
        "temperatures": TEMPERATURES,
        "root_selection": "two_per_owner_by_public_health_then_depth_then_task_per_initializer_v1",
        "roots": roots,
        "control": schedule(roots, True),
        "study": schedule(roots, False),
    }


def inputs(root: Path, *, planning: bool = False) -> Study:
    coverage = load(root)
    require_control(coverage)
    cfg = None if planning else json.loads((root / RECIPE).read_text())
    source_store = coverage_journal(coverage, False)
    with (source_store.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        owner, recipe = expected(coverage, None if cfg is None else cfg["roots"])
        if cfg is not None and cfg != recipe:
            raise ValueError("Require the exact sampling recipe")
        roots = {spec["id"]: resolve(coverage, owner, spec) for spec in recipe["roots"]}
    return Study(coverage, owner, recipe, roots)


def journal(study: Study, control: bool) -> ChunkJournal:
    cfg = study.cfg
    return ChunkJournal(
        study.coverage.temporal.base.root,
        {**cfg, "workspace": cfg["control_workspace"] if control else cfg["workspace"]},
    )


def play(
    study: Study, store: ChunkJournal, task: dict[str, Any], deadline: float
) -> dict[str, Any]:
    base = study.coverage.temporal.base
    state = base.originals[task["player"]]
    root = study.roots[task["root"]]
    draw_seed = f"{task['seed']}/a8-sampling-v1/{task['partition']}/{task['root']}/{task['draw']}"

    def chooser(
        ctx: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
    ) -> SamplingContinuation:
        if (
            variant != "own_policy"
            or start["scenario"] != task
            or start["seed"] != root.spec["source_task"]["seed"]
            or start["save_path"] is not None
            or start["evaluation_eligible"] is not False
            or model.model_id != state[0].model_id
        ):
            raise ValueError("Require the exact training-only sampling root")
        return SamplingContinuation(model, ctx["score"], root, draw_seed, task["arm"])

    with patch.object(native_a8_own_experience, "policy", chooser):
        row = game(base, store, task, state, deadline)
    prefix = root.spec["prefix_native_deliveries"]
    first = None
    for i, group in enumerate(
        native_a8_own_experience.groups(store.path(task["key"]), state[0].model_id)
    ):
        temp = TEMPERATURES["standard" if i < prefix else task["arm"]]
        if any(choice["temperature"] != temp for _, choice in group):
            raise ValueError("Sampling temperature changed outside its declared suffix")
        if i == prefix:
            first = group[0][1]["draw_key"]
    if row["outcome"] in TERMINAL and first is None:
        raise ValueError("The terminal game did not pass through its declared root")
    return {
        **row,
        "root_input_id": root.spec["root_input_id"],
        "first_suffix_draw_key": first,
        "prefix_deliveries": min(prefix, row["native_decisions"]),
        "suffix_deliveries": max(0, row["native_decisions"] - prefix),
        "prefix_is_training_data": False,
    }


def summarize(plan: list[dict[str, Any]], rows: dict[str, Any]) -> dict[str, Any]:
    pairs: dict[tuple[str, int], dict[str, Any]] = defaultdict(dict)
    clears: Counter[str] = Counter()
    rescues: dict[int, set[str]] = defaultdict(set)
    for task in plan:
        row = rows.get(task["key"])
        if row is not None and row["outcome"] in TERMINAL:
            pairs[task["root"], task["draw"]][task["arm"]] = row
            clears[task["arm"]] += row["completed_acts"] >= 1
    complete = 0
    for pair in pairs.values():
        if set(pair) != set(TEMPERATURES):
            continue
        old, new = pair["standard"], pair["sharp"]
        if (
            not old["first_suffix_draw_key"]
            or old["first_suffix_draw_key"] != new["first_suffix_draw_key"]
            or old["root_input_id"] != new["root_input_id"]
        ):
            raise ValueError("A paired draw must match its root and first sampling stream")
        complete += 1
        if old["completed_acts"] == 0 and new["completed_acts"] >= 1:
            task = new["task"]
            rescues[task["player"]].add(task["seed"])
    return {
        "planned_pairs": len(plan) // 2,
        "terminal_pairs": complete,
        "act1_clears": {arm: clears[arm] for arm in TEMPERATURES},
        "sharp_only_clear_worlds_by_initializer": {str(p): len(rescues[p]) for p in PLAYERS},
        "candidate_for_further_training_collection": (
            complete == len(plan) // 2
            and clears["sharp"] > clears["standard"]
            and all(rescues[p] for p in PLAYERS)
            and len(set.union(*(rescues[p] for p in PLAYERS))) >= 2
        ),
    }


def execute(study: Study, attempt: int, deadline: float, *, control: bool) -> dict[str, Any]:
    base, cfg = study.coverage.temporal.base, study.cfg
    store = journal(study, control)
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    plan = cfg["control" if control else "study"]
    rows: dict[str, Any] = {}
    seals: dict[str, str] = {}
    key, stop, summary = "preflight", None, None

    def check() -> None:
        unchanged(base, before, deadline)
        if json.loads((base.root / RECIPE).read_text()) != cfg:
            raise ValueError("Sampling recipe changed after launch")
        check_sources(base.root, cfg["implementation"])
        boundary(base.root, base.ctx, before, profile)

    with store.lock():
        try:
            check()
            for task in plan:
                key = task["key"]
                expected = request(study.coverage, task)
                seal = store.completed(key, expected)
                if seal is None:
                    check()
                    if deadline - time.monotonic() < 18:
                        raise TimeoutError("Too little time for a clean native start")
                    store.begin(key, expected)
                    row = play(study, store, task, deadline)
                    check()
                    seal = store.commit(key, expected, row)
                    print(
                        f"{key} {row['outcome']} (completed acts {row['completed_acts']})",
                        flush=True,
                    )
                rows[key], seals[key] = seal["result"], seal["report_id"]
            key = "final_verification"
            check()
            if execution_runtime(base.ctx["node"]) != base.runtime:
                raise ValueError("Frozen numerical runtime changed")
            for root in study.roots.values():
                source_game(study.coverage, study.owner, root.spec["source_task"])
            summary = summarize(plan, rows)
            if control and summary["terminal_pairs"] != len(plan) // 2:
                raise ValueError("Short controls require matching roots and genuine native endings")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
        planned = {task["key"] for task in plan}
        failed = key if stop and key in planned and store.path(key).exists() else None
        return write(
            store.workspace / ("report.json" if control else f"attempt-{attempt}.json"),
            {
                "schema_version": SCHEMA,
                "status": "stopped_preserving_evidence" if stop else READY if control else COMPLETE,
                "config_id": store.config_id,
                "outcomes": tally(plan, rows, failed),
                "summary": summary,
                "games": rows,
                "seals": seals,
                "stop": stop,
                "frozen_checks": before if not stop else None,
                "optimizer_updates": 0,
                "training_admission_granted": False,
                "full_game_playing_strength_evaluated": False,
                **SCOPE,
            },
        )


def require_short(study: Study) -> dict[str, Any]:
    base, cfg = study.coverage.temporal.base, study.cfg
    store = journal(study, True)
    report = identified(store.workspace / "report.json")
    resource = identified(_private_path(base.root, cfg["control_resource"]))
    if (
        report["status"] != READY
        or report["config_id"] != store.config_id
        or report["stop"] is not None
        or report["optimizer_updates"] != 0
        or report["frozen_checks"] != frozen(base.root, base.ctx)
        or report["summary"] != summarize(cfg["control"], report["games"])
        or report["summary"]["terminal_pairs"] != len(cfg["control"]) // 2
        or resource["status"] != "completed"
        or resource["cap"] is not None
        or resource["exit_code"] != 0
        or resource["limits"] != SHORT_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or resource["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
    ):
        raise ValueError("Require the exact short sampling controls")
    for task in cfg["control"]:
        key = task["key"]
        seal = store.completed(key, request(study.coverage, task))
        if (
            seal is None
            or seal["report_id"] != report["seals"][key]
            or seal["result"] != report["games"][key]
        ):
            raise ValueError("Saved short control changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--compare", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        study = inputs(root, planning=args.plan)
        if args.plan:
            with (root / RECIPE).open("x") as output:
                json.dump(study.cfg, output, indent=2, sort_keys=True)
                output.write("\n")
            return 0
        if args.control or args.compare is not None:
            if not args.control:
                require_short(study)
            limits = SHORT_LIMITS if args.control else LIMITS
            result = execute(
                study,
                args.compare or 0,
                started + limits["wall_seconds"] - 18,
                control=args.control,
            )
            print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
            return 0 if result["status"] in {READY, COMPLETE} else 2
        store = journal(study, args.check)
        if args.check:
            resource = _private_path(root, study.cfg["control_resource"])
            mode, limits = ["--control"], SHORT_LIMITS
        else:
            proof = require_short(study)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": READY,
                            "control_id": proof["report_id"],
                            "planned_games": len(study.cfg["study"]),
                        }
                    )
                )
                return 0
            attempt = time.time_ns()
            resource = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
            mode, limits = ["--compare", str(attempt)], LIMITS
            print(
                "Close STS2. Compare 32 training-only continuations in about 8–15 minutes. "
                "Zero updates.",
                flush=True,
            )
        if resource.exists():
            raise FileExistsError("Preserve the previous resource receipt")
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, *mode],
            experiment_kind=ExperimentKind.OTHER,
            report_path=resource,
            artifact_roots=[store.workspace],
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
