"""Fit matched full and short credit traces, then measure fresh native A8 wins."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_action_credit_session import plan as pilot_plan
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import LIMITS, copied_state
from spireshift.native_a8_mix_session import PREFIX_CHOICES, Study, game, unchanged
from spireshift.native_a8_own_ppo import update
from spireshift.native_a8_own_training import FAILURES, SCOPE, State, save_checkpoint
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_paired_report import summarize
from spireshift.native_a8_tactical_session import boundary, frozen
from spireshift.native_a8_temporal_credit import FULL, METHODS, SHORT, build_credit
from spireshift.native_a8_world_credit import SETTINGS
from spireshift.native_a8_world_credit_reload import admitted, require_reloads
from spireshift.native_a8_world_credit_session import journal, tally
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_a8_temporal_credit_session"
RECIPE = "configs/native-learning/sts2-v0.111.0-a8-temporal-credit-v1.json"
WRAPPER = "scripts/compare-a8-temporal-credit-v1.sh"
SCREEN = "docs/evidence/native-a8-temporal-credit-screen-v1.json"
AREA = "artifacts/native-a8-temporal-credit"
SCHEMA = "native-a8-temporal-credit-comparison-v1"
READY = "temporal_credit_fits_frozen"
COMPLETE = "temporal_credit_development_complete"
SHORT_LIMITS = {**LIMITS, "wall_seconds": 270, "cpu_seconds": 490}
ARMS = ("original", "within_world", FULL, SHORT)
WORLDS = [f"SP1RESH1FTA8TC1D{i:03d}" for i in range(1, 9)]
PREFIX = "SP1RESH1FTA8TC1P001"


@dataclass
class Session:
    base: Study
    cfg: dict[str, Any]
    source: ChunkJournal
    owner: dict[str, Any]
    screen: dict[str, Any]
    references: dict[tuple[int, str], State]


def implementation(root: Path) -> dict[str, str]:
    paths = (
        WRAPPER,
        "src/spireshift/native_a8_world_credit_audit.py",
        "src/spireshift/native_a8_temporal_credit.py",
        "src/spireshift/native_a8_temporal_credit_session.py",
    )
    return {path: _sha_file(root / path) for path in paths}


def tasks(control: bool) -> list[dict[str, Any]]:
    return [
        {
            "key": f"{'prefix' if control else 'dev'}-{i:02d}-p{p}-{arm.replace('_', '-')}",
            "seed": seed,
            "player": p,
            "arm": arm,
            "partition": "reload_control" if control else "development",
        }
        for i, seed in enumerate([PREFIX] if control else WORLDS, 1)
        for p in PLAYERS
        for arm in ((FULL, SHORT) if control else ARMS)
    ]


def inputs(root: Path) -> Session:
    base, recipe, prior_reload, short_states = admitted(root)
    require_reloads(base, prior_reload, short_states)
    cfg = json.loads((root / RECIPE).read_text())
    screen = identified(verified(root, cfg["screen"]))
    audit = identified(verified(root, screen["source_audit"]))
    owner = identified(verified(root, audit["owner"]))
    source = journal(root, recipe, False)
    before = frozen(root, base.ctx)
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["environment_id"] != base.cfg["environment_id"]
        or cfg["objective"] != base.cfg["objective"]
        or cfg["screen"]["path"] != SCREEN
        or cfg["implementation"] != implementation(root)
        or cfg["control"] != tasks(True)
        or cfg["study"] != tasks(False)
        or cfg["traces"] != METHODS
        or cfg["settings"] != SETTINGS
        or screen["status"] != "temporal_credit_screen_passed"
        or screen["passed"] is not True
        or screen["held_out_evaluation_data_used"] is not False
        or screen["frozen_checks"] != before
        or audit["frozen_checks"] != before
        or audit["config_id"] != source.config_id
        or owner["config_id"] != source.config_id
    ):
        raise ValueError("Require the exact saved temporal-credit screen and frozen study")
    history = json.loads(verified(root, base.ctx["config"]["parent_recipe"]).read_text())
    used = set(
        json.loads(verified(root, history["seed_history"]).read_text())["canonical_prior_seeds"]
    )
    used.update(history["plan"]["reserved_evaluation_seeds"])
    used.update(base.ctx["paired_panel"]["worlds"])
    used.update([*base.cfg["development"], base.cfg["prefix_seed"], base.cfg["ending_seed"]])
    used.update(entry["seed"] for entry in base.bank["entries"].values())
    used.update(
        seed
        for cases in base.ctx["practice_cases"].values()
        for case in cases
        for seed in case["seed_pool"]
    )
    used.update(t["seed"] for t in prior_reload["reloads"])
    used.update(t["seed"] for control in (False, True) for t in pilot_plan(control))
    for phase in ("control", "study"):
        used.update(t["seed"] for rows in recipe[phase].values() for t in rows)
        old = base.source.recipe[phase]
        used.update([*old["development"], *old["reload"], *(t["seed"] for t in old["training"])])
    new = [PREFIX, *WORLDS]
    if (
        len(set(new)) != len(new)
        or used.intersection(new)
        or any(s != canonical_seed(s) for s in new)
    ):
        raise ValueError("Reload and evaluation worlds must be fresh and separate")
    references = {}
    for p, state in base.originals.items():
        key = f"fit-p{p}"
        request = {
            "player": p,
            "original_id": state[2],
            "training_seals": [
                owner["seals"][t["key"]] for t in recipe["study"]["training"] if t["player"] == p
            ],
        }
        seal = source.completed(key, request)
        if (
            seal is None
            or seal["report_id"] != owner["seals"][key]
            or seal["result"] != audit["fits"][str(p)]
        ):
            raise ValueError("Require the exact previous within-world reference")
        references[p, "original"] = state
        references[p, "within_world"] = copied_state(source, p, "within_world", seal["result"])
    return Session(base, cfg, source, owner, screen, references)


def preparation(session: Session) -> ChunkJournal:
    return ChunkJournal(
        session.base.root, {**session.cfg, "workspace": session.cfg["fit_workspace"]}
    )


def fit_request(session: Session, p: int) -> dict[str, Any]:
    return {
        "player": p,
        "original_id": session.base.originals[p][2],
        "screen_id": session.screen["report_id"],
        "source_id": session.owner["report_id"],
    }


def fit(session: Session, p: int, target: Path) -> dict[str, Any]:
    base = session.base
    credit = build_credit(base, session.source.recipe, session.source, session.owner, p)
    if credit.diagnostics != session.screen["players"][str(p)]:
        raise ValueError("Forecast and saved training gradients did not reproduce")
    model, adam, state_id = base.originals[p]
    checkpoints, work, fitted = {}, {}, {}
    for arm, worlds in credit.rows.items():
        rows = [d for decisions in worlds.values() for d in decisions]
        learned, optimizer, stats = update(model, adam, rows, SETTINGS, 97100 + p)
        if (
            stats["stop_reason"] != "epoch_limit"
            or stats["optimizer_steps"] < 1
            or learned.actor.genome == model.actor.genome
        ):
            raise ValueError(f"The {arm} update exceeded its guard or left the actor unchanged")
        destination = target / arm
        destination.mkdir()
        checkpoints[arm] = save_checkpoint(destination, (learned, optimizer, state_id))
        fitted[arm] = learned
        work[arm] = stats
    if (
        work[FULL]["optimizer_steps"] != work[SHORT]["optimizer_steps"]
        or fitted[FULL].actor.genome == fitted[SHORT].actor.genome
    ):
        raise ValueError("Require matched updates and two distinct actors")
    return {
        "checkpoints": checkpoints,
        "work": work,
        "optimizer_updates_per_copy": work[FULL]["optimizer_steps"],
        "critics_exactly_matched": fitted[FULL].value_weights == fitted[SHORT].value_weights,
        "native_training_decisions": credit.diagnostics["decisions"],
    }


def execute(
    session: Session,
    deadline: float,
    *,
    control: bool,
    attempt: int = 0,
    ready: dict[str, Any] | None = None,
    states: dict[tuple[int, str], State] | None = None,
) -> dict[str, Any]:
    base, cfg = session.base, session.cfg
    store = preparation(session) if control else ChunkJournal(base.root, cfg)
    before, profile = frozen(base.root, base.ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
    current = dict(states or session.references)
    games: dict[str, dict[str, Any]] = {}
    seals: dict[str, str] = {}
    initials: dict[str, str] = {}
    fits: dict[str, Any] = {}
    plan = cfg["control" if control else "study"]
    stop = None
    key = "preflight"

    def check() -> None:
        unchanged(base, before, deadline)
        if json.loads((base.root / RECIPE).read_text()) != cfg:
            raise ValueError("The temporal-credit recipe changed")
        check_sources(base.root, cfg["implementation"])
        boundary(base.root, base.ctx, before, profile)

    with store.lock():
        try:
            check()
            if control:
                for p in PLAYERS:
                    key = f"fit-p{p}"
                    request = fit_request(session, p)
                    seal = store.completed(key, request)
                    if seal is None:
                        result = fit(session, p, store.begin(key, request))
                        check()
                        seal = store.commit(key, request, result)
                    fits[str(p)], seals[key] = seal["result"], seal["report_id"]
                    for arm in METHODS:
                        current[p, arm] = copied_state(store, p, arm, seal["result"])
                    print(
                        f"{key} sealed {fits[str(p)]['optimizer_updates_per_copy']} "
                        "updates per copy",
                        flush=True,
                    )
            for task in plan:
                key = task["key"]
                state = current[task["player"], task["arm"]]
                request = {"task": task, "state_id": state[2]}
                seal = store.completed(key, request)
                if seal is None:
                    check()
                    if deadline - time.monotonic() < 18:
                        raise TimeoutError("Too little time to start an isolated native worker")
                    store.begin(key, request)
                    row = game(base, store, task, state, deadline)
                    if control and (
                        row["outcome"] != "capped" or row["native_decisions"] != PREFIX_CHOICES
                    ):
                        raise ValueError("Reload must deliver the exact four-choice prefix")
                    check()
                    seal = store.commit(key, request, row)
                    print(f"{key} {row['outcome']} (floor {row['maximum_floor']})", flush=True)
                row = seal["result"]
                if (
                    row["task"] != task
                    or row["model_id"] != state[0].model_id
                    or initials.setdefault(task["seed"], row["initial_public_input_id"])
                    != row["initial_public_input_id"]
                ):
                    raise ValueError("The matched native start or checkpoint differs")
                games[key], seals[key] = row, seal["report_id"]
            key = "final_verification"
            check()
            if execution_runtime(base.ctx["node"]) != base.runtime:
                raise ValueError("Numerical runtime changed")
            if not control and require_prepared(session)[0] != ready:
                raise ValueError("The sealed comparison copies changed")
        except FAILURES as exc:
            stop = {"unit": key, "error": f"{type(exc).__name__}: {exc}"}

        planned = {t["key"] for t in plan}
        failed = key if stop and key in planned and store.path(key).exists() else None
        counts = tally(plan, games, failed)
        comparison = {}
        if not control:
            for reference in ("original", "within_world", FULL):
                paired = {
                    (
                        t["seed"],
                        t["player"],
                        "original" if t["arm"] == reference else "fitted",
                    ): games.get(t["key"], {"outcome": "failed"})
                    for t in plan
                    if t["arm"] in (reference, SHORT) and (t["key"] in games or t["key"] == failed)
                }
                comparison[f"{SHORT}_minus_{reference}"] = {
                    "reference_arm": reference,
                    "candidate_arm": SHORT,
                    **summarize(WORLDS, paired),
                }
        status = "temporal_credit_incomplete"
        if stop is None:
            if control:
                status = READY
            elif counts["win"] + counts["loss"] == len(plan):
                status = COMPLETE
        return write(
            store.workspace / ("report.json" if control else f"attempt-{attempt}.json"),
            {
                "schema_version": SCHEMA,
                "status": status,
                "config_id": store.config_id,
                "screen_id": session.screen["report_id"],
                "preparation_id": ready["report_id"] if ready else None,
                "outcomes": counts,
                "fits": fits,
                "games": games,
                "seals": seals,
                "development": comparison,
                "stop": stop,
                "optimizer_updates_on_copies": 2
                * sum(f["optimizer_updates_per_copy"] for f in fits.values()),
                "original_optimizer_updates": 0,
                "forced_action_probes_used": 0,
                "frozen_checks": before if stop is None else None,
                **SCOPE,
            },
        )


def require_prepared(session: Session) -> tuple[dict[str, Any], dict[tuple[int, str], State]]:
    store = preparation(session)
    proof = identified(store.workspace / "report.json")
    resource = identified(_private_path(session.base.root, session.cfg["fit_resource"]))
    expected = {t["key"] for t in session.cfg["control"]} | {f"fit-p{p}" for p in PLAYERS}
    if (
        proof["status"] != READY
        or proof["config_id"] != store.config_id
        or proof["screen_id"] != session.screen["report_id"]
        or proof["stop"] is not None
        or proof["frozen_checks"] != frozen(session.base.root, session.base.ctx)
        or set(proof["seals"]) != expected
        or resource["status"] != "completed"
        or resource["exit_code"] != 0
        or resource["cap"] is not None
        or resource["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--check"]
        or resource["limits"] != SHORT_LIMITS
        or resource["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Require the exact sealed fits and native reload checks")
    states = dict(session.references)
    for p in PLAYERS:
        key = f"fit-p{p}"
        seal = store.completed(key, fit_request(session, p))
        if seal is None or seal["report_id"] != proof["seals"][key]:
            raise ValueError("The fitted model or optimizer seal differs")
        for arm in METHODS:
            states[p, arm] = copied_state(store, p, arm, seal["result"])
    for task in session.cfg["control"]:
        key = task["key"]
        state = states[task["player"], task["arm"]]
        seal = store.completed(key, {"task": task, "state_id": state[2]})
        if seal is None or seal["report_id"] != proof["seals"][key]:
            raise ValueError("The native reload seal differs")
    return proof, states


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--evaluate", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the launcher with its fixed numerical settings")
        session = inputs(root)
        if args.check:
            result = execute(session, started + SHORT_LIMITS["wall_seconds"] - 18, control=True)
            print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
            return 0 if result["status"] == READY else 2
        if args.prepare:
            workspace = preparation(session).workspace
            resource = _private_path(root, session.cfg["fit_resource"])
            mode, limits = ["--check"], SHORT_LIMITS
        else:
            proof, states = require_prepared(session)
            if args.preflight:
                print(
                    json.dumps(
                        {
                            "status": READY,
                            "preparation_id": proof["report_id"],
                            "planned_games": len(session.cfg["study"]),
                        }
                    )
                )
                return 0
            if args.evaluate is not None:
                result = execute(
                    session,
                    started + LIMITS["wall_seconds"] - 25,
                    control=False,
                    attempt=args.evaluate,
                    ready=proof,
                    states=states,
                )
                print(json.dumps({k: v for k, v in result.items() if k not in {"games", "seals"}}))
                return 0 if result["status"] == COMPLETE else 2
            attempt = time.time_ns()
            workspace = _private_path(root, session.cfg["workspace"])
            resource = workspace.with_name(f"{workspace.name}-{attempt}-resources.json")
            mode, limits = ["--evaluate", str(attempt)], LIMITS
            print(
                "Close STS2. Allow about 15–25 minutes for 64 fresh A8 games. Zero updates.",
                flush=True,
            )
        if resource.exists():
            raise FileExistsError("Preserve the previous resource receipt")
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, *mode],
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
