"""Collect model-owned prepared A8 practice in a separate training partition."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_boss_worker, native_win4_game
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_boss_worker import BossWorker
from spireshift.native_a8_feedback_session import LIMITS, inputs, require_preparation
from spireshift.native_a8_own_training import FAILURES, SCOPE, State
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_practice_goal import (
    BOSS_ROOM,
    KIND,
    TWO_ROOMS,
    VARIANT,
    PracticeGoal,
    policy,
    verify_delivery_counts,
)
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.native_win4_worker import SCRIPT as SETUP_SCRIPT
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_practice_session"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-practice-mix-v2.json"
WRAPPER = "scripts/collect-a8-practice-mix-v1.sh"
SCRIPT = "engine-a8-practice-worker-v1.mjs"
CONTRACT = "native_a8_model_owned_practice_v1"
CONTROL_LIMITS = {**LIMITS, "wall_seconds": 265, "cpu_seconds": 480}
SCHEMA = "native-a8-model-owned-practice-v1"
TEMPLATES = {
    "OVERGROWTH": ("fit-007-replacement-1", "fit-008", "fit-009"),
    "UNDERDOCKS": ("fit-019", "fit-020", "fit-021"),
    "HIVE": ("fit-031-replacement-1", "fit-032-replacement-1", "fit-033"),
    "GLORY": ("fit-043-replacement-1", "fit-044", "fit-045"),
}


class PracticeWorker(BossWorker):
    def __init__(self, ctx: dict[str, Any], target: Path) -> None:
        self.adapter = ctx["confirmation_adapter"]
        q = ctx["qualification"]
        with patch.multiple(native_a8_boss_worker, SCRIPT=SCRIPT, PROJECTION=CONTRACT):
            super().__init__(
                q,
                ctx["native"],
                target,
                Path(ctx["node"]),
                worker_helpers(q.root, SCRIPT),
                ctx["execution_id"],
            )

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "confirmation_adapter": self.adapter}
        return super().request(command, timeout=timeout, **values)


def implementation(root: Path) -> dict[str, str]:
    paths = {WRAPPER, "scripts/engine-win-curriculum-save-v1.mjs"}
    paths.update(f"scripts/{name}" for name in worker_helpers(root, SCRIPT))
    paths.update(f"scripts/{name}" for name in worker_helpers(root, SETUP_SCRIPT))
    paths.update(f"src/spireshift/native_a8_practice_{name}.py" for name in ("goal", "session"))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def schedule(plan: dict[str, Any], *, control: bool) -> list[dict[str, Any]]:
    templates = {c["key"]: c for c in plan["fit"]}
    slots: list[tuple[str, str, str]] = []
    tiers = ("healthy", "lean", "preboss")
    for definition, names in TEMPLATES.items():
        for tier, name in zip(tiers, names, strict=True):
            if control:
                count = int(tier != "preboss" or definition == "HIVE")
            else:
                count = 2 if tier == "preboss" else 3
            slots.extend([(definition, tier, name)] * count)

    result = []
    phase = "q2" if control else "m"
    for ordinal, (definition, tier, name) in enumerate(slots, 1):
        base = templates[name]
        entry = "preboss" if tier == "preboss" else "act_start"
        if base["entry"] != entry or base["act_definition"] != definition:
            raise ValueError("Prepared practice template does not match its declared stratum")
        result.append(
            {
                **base,
                "key": f"{phase}-{ordinal:03d}",
                "template": name,
                "tier": tier,
                "partition": "practice_control" if control else "practice_train",
                "goal": BOSS_ROOM if tier == "preboss" else TWO_ROOMS,
                "boss": None,
                "seed_pool": [
                    canonical_seed(f"SP1RESH1FTA8PM1{phase.upper()}{ordinal:03}P{number:02}")
                    for number in range(1, 17)
                ],
            }
        )
    return result


def load_inputs(
    root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[int, State], str]:
    cfg = json.loads((root / RECIPE).read_text())
    prior, ctx, runtime, _, old = inputs(root)
    prep, states = require_preparation(root, prior, old)
    outcome = identified(verified(root, cfg["feedback_assessment"]))
    earlier = identified(verified(root, cfg["first_control"]))
    template = json.loads(verified(root, cfg["template_source"]).read_text())["plan"]
    reserved = {
        seed for name in ("fit", "heldout") for c in template[name] for seed in c["seed_pool"]
    }
    reserved.update(template["reserved_evaluation_seeds"])
    reserved.update([*prior["development"], prior["trial_seed"], prior["prefix_seed"]])
    plans = {
        "control": schedule(template, control=True),
        "collection": schedule(template, control=False),
    }
    seeds = [seed for case in plans["control"] + plans["collection"] for seed in case["seed_pool"]]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["environment_id"] != prior["environment_id"]
        or cfg["objective"] != prior["objective"]
        or cfg["game_limits"] != prior["game_limits"]
        or outcome["status"] != "matched_combat_feedback_independently_verified"
        or outcome["preparation_id"] != prep["report_id"]
        or outcome["sealed_games"] != 48
        or earlier["status"] != "practice_control_incomplete"
        or earlier["stop"] is not None
        or not earlier["coverage"]["all_segments_completed"]
        or earlier["planned_segments"] != 10
        or earlier["preparation_id"] != prep["report_id"]
        or cfg["implementation"] != implementation(root)
        or cfg["case_inventory_id"] != manifest_identifier(plans)
        or len(set(seeds)) != len(seeds)
        or reserved.intersection(seeds)
    ):
        raise ValueError("Practice recipe, prerequisites or partition membership differ")
    return (
        cfg,
        {**ctx, "practice_cases": plans},
        runtime,
        {p: states[p, "original"] for p in PLAYERS},
        prep["report_id"],
    )


def journal(root: Path, cfg: dict[str, Any], control: bool) -> ChunkJournal:
    return ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]} if control else cfg)


def status(
    cases: list[dict[str, Any]], rows: dict[str, dict[str, Any]], *, control: bool
) -> dict[str, Any]:
    counts: dict[str, Any] = {}
    early_coverage = True
    for definition in TEMPLATES:
        expected = [c for c in cases if c["act_definition"] == definition]
        worlds: set[str] = set()
        players: set[int] = set()
        counts[definition] = {}
        for tier in ("healthy", "lean", "preboss"):
            keys = [c["key"] for c in expected if c["tier"] == tier]
            labels: Counter[str] = Counter()
            for key in keys:
                for player in PLAYERS:
                    row = rows.get(f"{key}-p{player}", {})
                    label = row.get("outcome", "unattempted")
                    labels[label] += 1
                    if tier != "preboss" and label == "goal":
                        worlds.add(key)
                        players.add(player)
            if keys:
                counts[definition][tier] = dict(labels)
        early_coverage &= len(worlds) >= (1 if control else 2) and (
            control or players == set(PLAYERS)
        )
    all_completed = len(rows) == len(cases) * len(PLAYERS) and all(
        row["outcome"] in {"goal", "loss"} for row in rows.values()
    )
    return {
        "by_act_definition_and_tier": counts,
        "all_segments_completed": all_completed,
        "attainable_room_outcomes_in_each_act": early_coverage,
        "room_coverage_candidate": all_completed and early_coverage,
        "later_act_boss_goal_successes": sum(
            r.get("goal") == BOSS_ROOM and r.get("outcome") == "goal" and r["act"] > 1
            for r in rows.values()
        ),
    }


def collect(
    root: Path,
    cfg: dict[str, Any],
    ctx: dict[str, Any],
    runtime: dict[str, Any],
    originals: dict[int, State],
    prep_id: str,
    *,
    control: bool,
    attempt: int,
    deadline: float,
) -> dict[str, Any]:
    store = journal(root, cfg, control)
    before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    cases = ctx["practice_cases"]["control" if control else "collection"]
    env = {**ctx, "config": {"plan": cfg["game_limits"]}, "execution_id": store.config_id}
    rows: dict[str, dict[str, Any]] = {}
    setups: dict[str, str] = {}
    stop = None
    key = "preflight"

    def check() -> None:
        if time.monotonic() >= deadline:
            raise TimeoutError("Prepared practice reached its session deadline")
        if json.loads((root / RECIPE).read_text()) != cfg:
            raise ValueError("Prepared practice recipe changed")
        check_sources(root, cfg["implementation"])
        boundary(root, ctx, before, profile)

    with store.lock():
        try:
            for case in cases:
                key = setup_key = f"{case['key']}-start"
                request = {"case": case}
                setup = store.completed(key, request)
                if setup is None:
                    check()
                    path = store.begin(key, request)
                    start = native_win4_game.prepare(env, case, path, deadline)
                    if start["status"] != "ready" or start["evaluation_eligible"] is not False:
                        raise ValueError("Prepared practice needs an outcome-blind native start")
                    check()
                    setup = store.commit(key, request, start)
                setups[setup_key] = setup["report_id"]
                start = setup["result"]
                initial = None
                for player in PLAYERS:
                    key = f"{case['key']}-p{player}"
                    state = originals[player]
                    request = {
                        "start_seal": setup["report_id"],
                        "state_id": state[2],
                        "player": player,
                        "preparation_id": prep_id,
                    }
                    seal = store.completed(key, request)
                    if seal is None:
                        check()
                        path = store.begin(key, request)
                        play_start = write(
                            path / "start.json",
                            {
                                **{k: v for k, v in start.items() if k != "report_id"},
                                "kind": KIND,
                                "setup_id": start["report_id"],
                            },
                        )
                        goal = PracticeGoal(case["goal"], case["act"])
                        with patch.multiple(
                            native_win4_game, policy=policy, worker=PracticeWorker, terminal=goal
                        ):
                            episode = native_win4_game.episode(
                                env, play_start, VARIANT, path, deadline, model=state[0]
                            )
                        delivered, factors = verify_delivery_counts(state, path, episode)
                        outcome = (
                            "capped"
                            if episode["status"] == "capped"
                            else "goal"
                            if episode["curriculum_success"]
                            else "loss"
                        )
                        if (
                            episode["native_terminal"]
                            and not episode["native_ending"]["native_ending_evidence_agrees"]
                            or outcome == "goal"
                            and episode["native_terminal"]
                            or outcome == "loss"
                            and not episode["native_terminal"]
                        ):
                            raise ValueError("Practice endpoint lacks its matching native evidence")
                        row = {
                            "case_key": case["key"],
                            "seed": start["seed"],
                            "player": player,
                            "act": case["act"],
                            "act_definition": case["act_definition"],
                            "tier": case["tier"],
                            "goal": case["goal"],
                            "outcome": outcome,
                            "completed_combat_rooms": [
                                {"floor": floor, "encounter_type": kind}
                                for floor, kind in goal.completed.items()
                            ],
                            "ending_hp": episode["ending_hp"],
                            "native_decisions": delivered,
                            "local_answer_factors": factors,
                            "model_id": state[0].model_id,
                            "episode_report_id": episode["report_id"],
                            "initial_public_input_id": episode["initial_public_input_id"],
                        }
                        check()
                    else:
                        row = seal["result"]
                    if (
                        row["model_id"] != state[0].model_id
                        or row["seed"] != start["seed"]
                        or not row["initial_public_input_id"]
                        or (initial is not None and initial != row["initial_public_input_id"])
                    ):
                        raise ValueError(
                            "The two practice initializers need an exact matched start"
                        )
                    initial = row["initial_public_input_id"]
                    if seal is None:
                        seal = store.commit(key, request, row)
                        print(
                            f"{key} {case['act_definition']} {case['tier']} {row['outcome']}",
                            flush=True,
                        )
                    rows[key] = {**row, "seal_id": seal["report_id"]}
            key = "final_verification"
            check()
            if execution_runtime(ctx["node"]) != runtime:
                raise ValueError("Frozen numerical runtime changed")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}
            if "-p" in key and key not in rows:
                rows[key] = {"outcome": "failed"}

        summary = status(cases, rows, control=control)
        passed = stop is None and summary["room_coverage_candidate"]
        return write(
            store.workspace / ("report.json" if control else f"attempt-{attempt}.json"),
            {
                "schema_version": SCHEMA,
                "status": "stopped_preserving_evidence"
                if stop
                else (
                    "practice_control_verified"
                    if control and passed
                    else "practice_control_incomplete"
                    if control
                    else "practice_collection_complete"
                ),
                "config_id": store.config_id,
                "preparation_id": prep_id,
                "planned_worlds": len(cases),
                "planned_segments": len(cases) * len(PLAYERS),
                "setups": setups,
                "segments": rows,
                "coverage": summary,
                "stop": stop,
                "frozen_checks": before if stop is None else None,
                "shared_profile_unchanged": True if stop is None else None,
                "normal_start_evaluation_games": 0,
                "optimizer_updates": 0,
                "training_admission_granted": False,
                **SCOPE,
            },
        )


def require_control(root: Path, cfg: dict[str, Any], prep_id: str) -> dict[str, Any]:
    store = journal(root, cfg, True)
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(root, cfg["control_resource"]))
    if (
        proof["status"] != "practice_control_verified"
        or proof["config_id"] != store.config_id
        or proof["preparation_id"] != prep_id
        or not proof["coverage"]["room_coverage_candidate"]
        or not all(proof["frozen_checks"].values())
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["limits"] != CONTROL_LIMITS
        or resource["command"][:7]
        != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--execute-control"]
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact passing prepared practice control")
    seals = {**proof["setups"], **{k: v["seal_id"] for k, v in proof["segments"].items()}}
    for key, seal_id in seals.items():
        request = json.loads((store.path(key) / "active.json").read_text())["request"]
        seal = store.completed(key, request)
        if seal is None or seal["report_id"] != seal_id:
            raise ValueError("Prepared practice control seal changed")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--control", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--execute-control", type=int)
    modes.add_argument("--execute-collection", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned launcher with the fixed numerical settings")
        cfg, ctx, runtime, originals, prep = load_inputs(root)
        control = args.control or args.execute_control is not None
        store = journal(root, cfg, control)
        limits = CONTROL_LIMITS if control else LIMITS
        if not control:
            proof = require_control(root, cfg, prep)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": "practice_collection_ready",
                            "control_id": proof["report_id"],
                            "planned_worlds": len(ctx["practice_cases"]["collection"]),
                            "planned_segments": len(ctx["practice_cases"]["collection"])
                            * len(PLAYERS),
                            "frozen_checks": frozen(root, ctx),
                        }
                    )
                )
                return 0
        inner = args.execute_control if control else args.execute_collection
        if inner is not None:
            result = collect(
                root,
                cfg,
                ctx,
                runtime,
                originals,
                prep,
                control=control,
                attempt=inner,
                deadline=started + limits["wall_seconds"] - 15,
            )
            print(
                json.dumps({k: v for k, v in result.items() if k not in {"segments", "setups"}}),
                flush=True,
            )
            return (
                0
                if result["status"] in {"practice_control_verified", "practice_collection_complete"}
                else 2
            )
        attempt = time.time_ns()
        if control:
            resource = _private_path(root, cfg["control_resource"])
            if store.workspace.exists() or resource.exists():
                raise FileExistsError("Preserve the earlier prepared practice control")
        else:
            resource = store.workspace.with_name(f"{store.workspace.name}-{attempt}-resources.json")
            print(
                "Close STS2. 64 prepared practice segments across 32 A8 worlds. "
                "Allow about 7–15 minutes. Training-only collection, zero updates.",
                flush=True,
            )
        mode = "--execute-control" if control else "--execute-collection"
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, mode, str(attempt)],
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
