"""Collect fresh model-owned games and training-only continuations from natural states."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from collections import defaultdict
from collections.abc import Generator
from contextlib import closing
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift import native_a8_own_experience
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_action_credit_session import plan as pilot_plan
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_coverage_policy import (
    Continuation,
    Root,
    resolve_root,
    select_roots,
    training_source,
)
from spireshift.native_a8_family_credit import REPORT as FAMILY_REPORT
from spireshift.native_a8_feedback_session import LIMITS, PREFIX_CHOICES, SHORT_LIMITS
from spireshift.native_a8_mix_audit import source
from spireshift.native_a8_mix_session import game, unchanged
from spireshift.native_a8_own_training import FAILURES, SCOPE
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_a8_temporal_credit_audit import STATUS as AUDITED
from spireshift.native_a8_temporal_credit_session import AREA as TEMPORAL_AREA
from spireshift.native_a8_temporal_credit_session import Session, inputs
from spireshift.native_a8_world_credit import DRAWS
from spireshift.native_a8_world_credit_session import tally
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_coverage_session"
SCHEMA = "native-a8-model-owned-coverage-v1"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-model-owned-coverage-v1.json"
WRAPPER = "scripts/collect-a8-model-owned-coverage-v1.sh"
AREA = "artifacts/native-a8-model-owned-coverage"
ASSESSMENT = f"{TEMPORAL_AREA}/assessment-v1-1794239333646300000/report.json"
NORMAL_WORLDS = tuple(f"SP1RESH1FTA8CV1T{i:03d}" for i in range(1, 25))
BRANCH = "continuation_training_only"
CONTROL = "continuation_control"
READY = "model_owned_coverage_control_verified"
COMPLETE = "model_owned_coverage_collected"
TERMINAL = {"win", "loss"}


@dataclass(frozen=True)
class Collection:
    temporal: Session
    cfg: dict[str, Any]
    roots: dict[str, Root]


def fresh_worlds(session: Session) -> None:
    base = session.base
    history = json.loads(verified(base.root, base.ctx["config"]["parent_recipe"]).read_text())
    used = set(
        json.loads(verified(base.root, history["seed_history"]).read_text())[
            "canonical_prior_seeds"
        ]
    )
    used.update(history["plan"]["reserved_evaluation_seeds"])
    used.update(base.ctx["paired_panel"]["worlds"])
    used.update([*base.cfg["development"], base.cfg["prefix_seed"], base.cfg["ending_seed"]])
    used.update(entry["seed"] for entry in base.bank["entries"].values())
    for cases in base.ctx["practice_cases"].values():
        used.update(seed for case in cases for seed in case["seed_pool"])
    for stage in ("control", "study"):
        used.update(task["seed"] for task in session.cfg[stage])
        used.update(task["seed"] for task in pilot_plan(stage == "control"))
        used.update(
            task["seed"] for tasks in session.source.recipe[stage].values() for task in tasks
        )
        own = base.source.recipe[stage]
        used.update([*own["development"], *own["reload"], *(t["seed"] for t in own["training"])])
    if used.intersection(NORMAL_WORLDS) or any(s != canonical_seed(s) for s in NORMAL_WORLDS):
        raise ValueError(
            "Collection worlds must be distinct from prior and reserved evaluation worlds"
        )


def schedule(roots: list[dict[str, Any]], *, control: bool) -> list[dict[str, Any]]:
    branches = [
        {
            "key": f"{root['id']}-draw-{draw}",
            "seed": root["source_task"]["seed"],
            "seed_id": root["source_task"]["seed_id"],
            "player": root["source_task"]["player"],
            "partition": CONTROL if control else BRANCH,
            "root": root["id"],
        }
        for root in roots
        if not control or root["id"].endswith("-middle-combat")
        for draw in range(2 if control else DRAWS)
    ]
    if control:
        return branches
    return [
        {
            "key": f"normal-{i:02d}-p{p}",
            "seed": seed,
            "seed_id": 410_000 + i,
            "player": p,
            "partition": "train",
            "round": 1,
        }
        for i, seed in enumerate(NORMAL_WORLDS, 1)
        for p in PLAYERS
    ] + branches


def expected_recipe(session: Session) -> dict[str, Any]:
    root, base = session.base.root, session.base
    audit_path, family_path = (_private_path(root, name) for name in (ASSESSMENT, FAMILY_REPORT))
    audit, family = identified(audit_path), identified(family_path)
    before = frozen(root, base.ctx)
    if (
        audit["status"] != AUDITED
        or audit["environment_id"] != base.cfg["environment_id"]
        or audit["frozen_checks"] != before
        or any(row["wins"] or row["act1_clears"] for row in audit["arms"].values())
        or family["status"] != "family_credit_screen_complete"
        or family["training_config_id"] != session.source.config_id
        or family["temporal_screen_id"] != session.screen["report_id"]
        or family["frozen_checks"] != before
        or family["held_out_evaluation_data_used"] is not False
        or family["qualifying_traces"] != []
    ):
        raise ValueError("Require verified evidence for broader coverage with the shared scorer")
    fresh_worlds(session)
    roots = select_roots(session)
    paths = (
        WRAPPER,
        "src/spireshift/native_a8_coverage_policy.py",
        "src/spireshift/native_a8_coverage_session.py",
        "src/spireshift/native_a8_family_credit.py",
        "src/spireshift/native_a8_temporal_credit_audit.py",
    )
    return {
        "schema_version": SCHEMA,
        "workspace": f"{AREA}/collection-v1",
        "control_workspace": f"{AREA}/control-v1",
        "control_resource": f"{AREA}/control-v1-resources.json",
        "environment_id": base.cfg["environment_id"],
        "objective": base.cfg["objective"],
        "score_spec_id": base.ctx["score"].spec_id,
        "game_limits": base.cfg["game_limits"],
        "original_full_state_ids": {str(p): base.originals[p][2] for p in PLAYERS},
        "audit": source(root, audit_path),
        "family_screen": source(root, family_path),
        "implementation": {path: _sha_file(root / path) for path in paths},
        "roots": roots,
        "control": schedule(roots, control=True),
        "study": schedule(roots, control=False),
    }


def load(root: Path) -> Collection:
    temporal = inputs(root)
    cfg = json.loads((root / RECIPE).read_text())
    with (temporal.source.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        if cfg != expected_recipe(temporal):
            raise ValueError("Require the exact collection recipe and sealed training roots")
        roots = {spec["id"]: resolve_root(temporal, spec) for spec in cfg["roots"]}
    return Collection(temporal, cfg, roots)


def journal(collection: Collection, control: bool) -> ChunkJournal:
    cfg = collection.cfg
    return ChunkJournal(
        collection.temporal.base.root,
        {**cfg, "workspace": cfg["control_workspace"] if control else cfg["workspace"]},
    )


def request(collection: Collection, task: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": task,
        "state_id": collection.cfg["original_full_state_ids"][str(task["player"])],
    }


def play(
    collection: Collection, store: ChunkJournal, task: dict[str, Any], deadline: float
) -> dict[str, Any]:
    base = collection.temporal.base
    state = base.originals[task["player"]]
    if task["partition"] == "train":
        return game(base, store, task, state, deadline)
    root = collection.roots[task["root"]]
    prefix = root.spec["prefix_native_deliveries"]
    draw_seed = f"{task['seed']}/a8-coverage-v1/{task['partition']}/{task['key']}"

    def chooser(
        ctx: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
    ) -> Continuation:
        if (
            variant != "own_policy"
            or start["scenario"] != task
            or start["seed"] != root.spec["source_task"]["seed"]
            or start["save_path"] is not None
            or start["evaluation_eligible"] is not False
            or model.model_id != state[0].model_id
        ):
            raise ValueError("Require the original policy and exact training-only continuation")
        return Continuation(model, ctx["score"], root, draw_seed)

    if task["partition"] == CONTROL:
        limits = {**base.cfg["game_limits"], "maximum_decisions": prefix + PREFIX_CHOICES}
        base = replace(base, cfg={**base.cfg, "game_limits": limits})
    with patch.object(native_a8_own_experience, "policy", chooser):
        row = game(base, store, task, state, deadline)
    suffix = max(0, row["native_decisions"] - prefix)
    first = None
    if suffix:
        rows = cast(
            Generator[list[native_a8_own_experience.FrameChoice], None, None],
            native_a8_own_experience.groups(store.path(task["key"]), state[0].model_id),
        )
        with closing(rows):
            for i, group in enumerate(rows):
                if i == prefix:
                    first = group[0][1]["draw_key"]
                    break
        if first is None:
            raise ValueError("Missing first delivered suffix sample")
    elif row["outcome"] in TERMINAL:
        raise ValueError("A terminal continuation must deliver a choice from the verified root")
    return {
        **row,
        "continuation": {
            "root_input_id": root.spec["root_input_id"],
            "reconstructed_prefix_deliveries": min(prefix, row["native_decisions"]),
            "suffix_deliveries": suffix,
            "first_suffix_draw_key": first,
            "prefix_is_training_data": False,
        },
    }


def control_draws(plan: list[dict[str, Any]], rows: dict[str, Any]) -> dict[str, list[str]]:
    draws: dict[str, list[str]] = defaultdict(list)
    for task in plan:
        row = rows[task["key"]]
        continuation = row["continuation"]
        draw, suffix = continuation["first_suffix_draw_key"], continuation["suffix_deliveries"]
        if (
            not draw
            or not 1 <= suffix <= PREFIX_CHOICES
            or (row["outcome"] == "capped" and suffix != PREFIX_CHOICES)
        ):
            raise ValueError("The short control must deliver its exact prefix and suffix")
        draws[task["root"]].append(draw)
    if len(draws) != len(PLAYERS) or any(len(set(keys)) != 2 for keys in draws.values()):
        raise ValueError("Require independent draws from each exact control root")
    return dict(draws)


def execute(
    collection: Collection, attempt: int, deadline: float, *, control: bool
) -> dict[str, Any]:
    base, cfg = collection.temporal.base, collection.cfg
    store = journal(collection, control)
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    plan = cfg["control" if control else "study"]
    rows: dict[str, Any] = {}
    seals: dict[str, str] = {}
    key, stop = "preflight", None
    draws = None

    def check() -> None:
        unchanged(base, before, deadline)
        if json.loads((base.root / RECIPE).read_text()) != cfg:
            raise ValueError("The coverage recipe changed")
        check_sources(base.root, cfg["implementation"])
        boundary(base.root, base.ctx, before, profile)

    with store.lock():
        try:
            check()
            for task in plan:
                key = task["key"]
                expected = request(collection, task)
                seal = store.completed(key, expected)
                if seal is None:
                    check()
                    if deadline - time.monotonic() < 18:
                        raise TimeoutError("Too little time to start an isolated native worker")
                    store.begin(key, expected)
                    row = play(collection, store, task, deadline)
                    check()
                    seal = store.commit(key, expected, row)
                    print(f"{key} {row['outcome']} (floor {row['maximum_floor']})", flush=True)
                rows[key], seals[key] = seal["result"], seal["report_id"]
            key = "final_verification"
            check()
            for root in collection.roots.values():
                training_source(collection.temporal, root.spec["source_task"])
            if execution_runtime(base.ctx["node"]) != base.runtime:
                raise ValueError("The frozen numerical runtime changed")
            if control:
                draws = control_draws(plan, rows)
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
        failed = (
            key
            if stop and key in {task["key"] for task in plan} and store.path(key).exists()
            else None
        )
        return write(
            store.workspace / ("report.json" if control else f"attempt-{attempt}.json"),
            {
                "schema_version": SCHEMA,
                "status": "stopped_preserving_evidence" if stop else READY if control else COMPLETE,
                "config_id": store.config_id,
                "outcomes": tally(plan, rows, failed),
                "control_draws": draws,
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


def require_control(collection: Collection) -> dict[str, Any]:
    store = journal(collection, True)
    base, cfg = collection.temporal.base, collection.cfg
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(base.root, cfg["control_resource"]))
    if (
        proof["status"] != READY
        or proof["config_id"] != store.config_id
        or proof["frozen_checks"] != frozen(base.root, base.ctx)
        or proof["optimizer_updates"] != 0
        or proof["stop"] is not None
        or resource["status"] != "completed"
        or resource["cap"] is not None
        or resource["exit_code"] != 0
        or resource["artifacts"]["roots"] != [str(store.workspace)]
        or resource["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
    ):
        raise ValueError("Require the exact successful short continuation controls")
    for task in cfg["control"]:
        key = task["key"]
        seal = store.completed(key, request(collection, task))
        if (
            seal is None
            or seal["report_id"] != proof["seals"][key]
            or seal["result"] != proof["games"][key]
        ):
            raise ValueError("A continuation control seal changed")
    if control_draws(cfg["control"], proof["games"]) != proof["control_draws"]:
        raise ValueError("The verified control draws changed")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--plan", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--collect", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        if args.plan:
            cfg = expected_recipe(inputs(root))
            with (root / RECIPE).open("x") as plan_file:
                json.dump(cfg, plan_file, indent=2, sort_keys=True)
                plan_file.write("\n")
            return 0
        collection = load(root)
        if args.control or args.collect is not None:
            if not args.control:
                require_control(collection)
            limits = SHORT_LIMITS if args.control else LIMITS
            report = execute(
                collection,
                args.collect or 0,
                started + limits["wall_seconds"] - 18,
                control=args.control,
            )
            print(json.dumps({k: v for k, v in report.items() if k not in {"games", "seals"}}))
            return 0 if report["status"] in {READY, COMPLETE} else 2
        store = journal(collection, args.check)
        if args.check:
            report_path = _private_path(root, collection.cfg["control_resource"])
            mode, limits = ["--control"], SHORT_LIMITS
        else:
            ready = require_control(collection)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": READY,
                            "control_id": ready["report_id"],
                            "planned_games": len(collection.cfg["study"]),
                        }
                    )
                )
                return 0
            attempt = time.time_ns()
            report_path = store.workspace.with_name(
                f"{store.workspace.name}-{attempt}-resources.json"
            )
            mode, limits = ["--collect", str(attempt)], LIMITS
            print(
                "Close STS2. Collect 48 fresh starts and 24 training-only continuations. "
                "Allow about 15–25 minutes. Zero updates.",
                flush=True,
            )
        if report_path.exists():
            raise FileExistsError("Preserve the previous resource receipt")
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, *mode],
            experiment_kind=ExperimentKind.OTHER,
            report_path=report_path,
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
