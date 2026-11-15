"""Check saved combat branches and qualify a tactical teacher on fresh A8 worlds."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
from collections import Counter
from contextlib import ExitStack, closing
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_boss2_game import play as play_reference
from spireshift.native_a8_boss2_inputs import declaration, freeze, load, short_check
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_boss_session import WORLD_RESERVE, qualify
from spireshift.native_a8_rescue_curriculum import first_change
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_rescue_inputs import CONTROL_LIMITS, GAME_LIMITS, SESSION_LIMITS
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_a8_tactical_episode import play
from spireshift.native_a8_tactical_policy import CONTRACT, lethal_plan, tactical_choice
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-tactical-qualification-v1.json"
MODULE = "spireshift.native_a8_tactical_session"
REFERENCES = ("original", "fitted", "survival", "boss_v2")
WORLD_BUFFER = WORLD_RESERVE + GAME_LIMITS["episode_wall_seconds"] + 20


def context(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    parent = declaration(root)
    ctx = load(root, parent)
    receipts = short_check(root, ctx)
    if (
        receipts is None
        or cfg["schema_version"] != "native-a8-act1-tactical-qualification-v1"
        or cfg["objective"] != parent["objective"]
        or cfg["gate"] != parent["gate"]
        or cfg["game_limits"] != GAME_LIMITS
        or cfg["teacher"] != CONTRACT
        or cfg["references"] != list(REFERENCES)
    ):
        raise ValueError(
            "Tactical qualification requires the pinned build, objective and reference gate"
        )
    ctx["reward_short_receipts"] = receipts
    old = ctx["config"]
    curriculum = json.loads(verified(root, old["parent_recipe"]).read_text())
    history = json.loads(verified(root, curriculum["seed_history"]).read_text())
    used = set(history["canonical_prior_seeds"]) | set(ctx["paired_panel"]["worlds"])
    used.update(curriculum["plan"]["reserved_evaluation_seeds"])
    used.update(
        seed
        for phase in ("fit", "heldout")
        for slot in curriculum["plan"][phase]
        for seed in slot["seed_pool"]
    )
    used.update(c["seed"] for phase in old["worlds"].values() for c in phase)
    for recipe in (ctx["boss_config"], parent):
        used.update(c["seed"] for c in recipe["worlds"])
    used.update(c["seed"] for c in parent["control_worlds"])
    used.update((old["control"]["seed"], ctx["boss_config"]["control"]["seed"]))
    starts = [*cfg["worlds"], *cfg["diagnostic_worlds"], cfg["smoke"]]
    if len({c["seed"] for c in starts}) != len(starts) or used.intersection(
        c["seed"] for c in starts
    ):
        raise ValueError("Tactical qualification and smoke worlds must be fresh and disjoint")
    return {
        **ctx,
        "tactical_config": cfg,
        "tactical_execution_id": manifest_identifier(
            {"parent_execution_id": ctx["execution_id"], "config": cfg}
        ),
    }


def frozen(root: Path, ctx: dict[str, Any]) -> dict[str, bool]:
    cfg = ctx["tactical_config"]
    if json.loads((root / RECIPE).read_text()) != cfg:
        raise ValueError("Tactical execution recipe changed")
    check_sources(root, cfg["implementation"])
    for ref in cfg["source_evidence"].values():
        verified(root, ref)
    return freeze(root, ctx)


def checked_sources(
    root: Path, ctx: dict[str, Any], locks: ExitStack
) -> dict[str, tuple[Path, dict[str, str]]]:
    cfg = ctx["tactical_config"]
    branch_cfg = json.loads(verified(root, cfg["branch_recipe"]).read_text())
    branch_receipt = identified(verified(root, cfg["source_evidence"]["branches"]))
    branch_report = identified(verified(root, branch_receipt["branch_report"]))
    v2_receipt = identified(verified(root, cfg["source_evidence"]["qualification"]))
    v2_report = identified(verified(root, v2_receipt["saved_audit"]))
    qualification, branches = (
        ChunkJournal(root, ctx["reward_config"]),
        ChunkJournal(root, branch_cfg),
    )
    if (
        branch_report["config_id"] != branches.config_id
        or v2_report["config_id"] != qualification.config_id
        or branch_report["saved_audit_id"] != v2_report["report_id"]
        or branch_report["execution_id"] != ctx["execution_id"]
    ):
        raise ValueError("The saved combat evidence is from a different execution")
    for store in (qualification, branches):
        handle = locks.enter_context((store.workspace / "session.lock").open("rb"))
        fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
    sources = {}
    for case in cfg["controls"]:
        if case["source"] == "qualification":
            store, key = qualification, case["world"]
            original = next(w for w in ctx["reward_config"]["worlds"] if w["key"] == key)
            seals = v2_report["seals"]
            trace = store.path(key) / "boss" / TRACE
        else:
            store, key = branches, case["source"]
            original = next(w for w in branch_cfg["cases"] if w["key"] == key)
            seals = branch_report["seals"]
            trace = store.path(key) / TRACE
        seal = store.completed(key, original)
        if seal is None or seal["report_id"] != seals[key] or original["seed"] != case["seed"]:
            raise ValueError("Tactical control requires the exact sealed source")
        name = trace.relative_to(root).as_posix()
        sources[case["key"]] = (trace, {name: seal["sources"][name]})
    return sources


def saved_checks(
    cfg: dict[str, Any], sources: dict[str, tuple[Path, dict[str, str]]]
) -> list[dict[str, Any]]:
    result = []
    for case in cfg["controls"]:
        with closing(decisions(sources[case["key"]][0])) as rows:
            frame = next((f for line, f, a in rows if line == case["line"] and a is not None), None)
        if frame is None or frame["input_digest"] != case["input_digest"]:
            raise ValueError("Saved tactical menu digest differs")
        public = frame["public_input"]
        combat = public["context"]["interaction"]["content"]["context"]
        candidates = public["candidates"]
        indices = list(range(len(candidates)))
        choice = tactical_choice(public, indices)
        if choice is None or [candidates[choice[0]]["label"], choice[1]] != case["expected"]:
            raise ValueError("Tactical planner missed the declared saved menu decision")
        plan = [candidates[i]["label"] for i in lethal_plan(public, indices, combat)]
        if plan != case["expected_lethal_sequence"]:
            raise ValueError("Tactical planner missed the complete legal saved lethal sequence")
        result.append(
            {
                "key": case["key"],
                "input_digest": frame["input_digest"],
                "decision": case["expected"],
                "lethal_sequence": plan,
            }
        )
    return result


def boundary(
    root: Path, ctx: dict[str, Any], before: dict[str, Any], profile: dict[str, Any]
) -> None:
    if (
        frozen(root, ctx) != before
        or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile
        or _running_games()
    ):
        raise ValueError("Frozen inputs, native shutdown or the shared profile differ")


def control(root: Path, ctx: dict[str, Any], deadline: float) -> dict[str, Any]:
    cfg = ctx["tactical_config"]
    store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]})
    with ExitStack() as locks:
        sources = checked_sources(root, ctx, locks)
        saved = saved_checks(cfg, sources)
        locks.enter_context(store.lock())
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
        cases = [*cfg["controls"], cfg["smoke"]]
        rows, seals = {}, {}
        for case in cases:
            key = case["key"]
            source, hashes = sources.get(key, (None, {}))
            target = store.begin(key, case)
            row = play(ctx, case, target, deadline, trace=source)
            if row["cap"]:
                raise ValueError("A capped short tactical control remains incomplete")
            boundary(root, ctx, before, profile)
            seal = store.commit(key, case, row, hashes)
            rows[key], seals[key] = row, seal["report_id"]
            print(f"{key} {row['outcome']} with {row['final_hp']} HP", flush=True)
        eel = rows["eel-lethal"]
        early = [rows["giant-early"], rows["giant-round-three"]]
        late = rows["giant-transition"]
        gate = {
            "eel_native_three_attack_kill": eel["outcome"] == "fight_win"
            and [s["action"] for s in eel["diagnostic"]["steps"]]
            == cfg["controls"][0]["expected_lethal_sequence"],
            "giant_earlier_block_delivered": all(
                row["tactical_deliveries"].get("giant_preserve_hp", 0) > 0 for row in early
            ),
            "giant_earlier_branch_survived": any(row["outcome"] == "fight_win" for row in early),
            "giant_triggered_before_eruption_growth": (late["diagnostic"]["death_blow"] or {}).get(
                "damage"
            )
            == 30
            and late["tactical_deliveries"].get("giant_trigger_death_blow", 0) >= 3,
            "fresh_normal_start_complete": rows[cfg["smoke"]["key"]]["outcome"]
            in {"act1_clear", "act1_loss"},
        }
        return write(
            store.workspace / "report.json",
            {
                "schema_version": "native-a8-tactical-short-check-v1",
                "status": "tactical_short_checks_verified"
                if all(gate.values())
                else "tactical_short_gate_blocked",
                "config_id": manifest_identifier(cfg),
                "execution_id": ctx["tactical_execution_id"],
                "saved_checks": saved,
                "gate": gate,
                "cases": rows,
                "seals": seals,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                **NO_UPDATES,
            },
        )


def require_control(root: Path, ctx: dict[str, Any], *, diagnostic: bool = False) -> dict[str, Any]:
    cfg = ctx["tactical_config"]
    store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]})
    report = identified(store.workspace / "report.json")
    resources = identified(root / cfg["control_resource"])
    blocked = {name for name, passed in report["gate"].items() if not passed}
    diagnostic_only = diagnostic and blocked == {"giant_earlier_branch_survived"}
    if (
        report["status"]
        != ("tactical_short_gate_blocked" if diagnostic_only else "tactical_short_checks_verified")
        or report["config_id"] != manifest_identifier(cfg)
        or report["execution_id"] != ctx["tactical_execution_id"]
        or (blocked and not diagnostic_only)
        or resources["exit_code"] != (2 if diagnostic_only else 0)
        or resources["cap"] is not None
        or resources["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
        or resources["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Fresh qualification requires the passing sealed tactical short checks")
    for case in [*cfg["controls"], cfg["smoke"]]:
        seal = store.completed(case["key"], case)
        if seal is None or seal["report_id"] != report["seals"][case["key"]]:
            raise ValueError("Tactical short evidence changed")
    return report


def play_world(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    episodes = {
        name: play_reference(
            ctx, case, "boss" if name == "boss_v2" else name, target / name, deadline
        )
        for name in REFERENCES
    }
    episodes["boss"] = play(ctx, case, target / "boss", deadline)
    if len({row["initial_public_input_id"] for row in episodes.values()}) != 1:
        raise ValueError("Tactical panel arms did not start from exact matching public menus")
    outcomes = {arm: row["outcome"] for arm, row in episodes.items()}
    changed = first_change(target / "boss_v2" / TRACE, target / "boss" / TRACE)
    if (
        outcomes["boss"] != outcomes["boss_v2"]
        and "capped" not in (outcomes["boss"], outcomes["boss_v2"])
        and changed is None
    ):
        raise ValueError("A differing tactical outcome requires a verified same-menu change")
    confirmed = outcomes["boss"] == "act1_clear"
    if confirmed:
        replay = play(ctx, case, target / "confirmation", deadline)
        if (
            replay["outcome"] != "act1_clear"
            or replay["semantic_trajectory_sha256"]
            != episodes["boss"]["semantic_trajectory_sha256"]
        ):
            raise ValueError("The tactical clear did not reproduce from a fresh normal start")
        episodes["confirmation"] = replay
    return {
        "case": case,
        "outcomes": outcomes,
        "episodes": episodes,
        "first_different_teacher_action": changed,
        "confirmed_clear": confirmed,
        "strict_rescue_confirmed": confirmed
        and all(outcomes[name] == "act1_loss" for name in REFERENCES),
    }


def run(
    root: Path, ctx: dict[str, Any], attempt: int, deadline: float, *, diagnostic: bool = False
) -> dict[str, Any]:
    cfg = ctx["tactical_config"]
    if diagnostic:
        cfg = {**cfg, "workspace": cfg["diagnostic_workspace"], "worlds": cfg["diagnostic_worlds"]}
    store = ChunkJournal(root, cfg)
    with store.lock():
        short = require_control(root, ctx, diagnostic=diagnostic)
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        before, profile = frozen(root, ctx), _shared_snapshot(Path.home() / SHARED_PROFILE)
        launch = write(
            store.workspace / f"launch-{attempt}.json",
            {
                "config_id": store.config_id,
                "execution_id": ctx["tactical_execution_id"],
                "objective": cfg["objective"],
                "frozen_checks": before,
                "checkpoints": ctx["states"],
                "short_report_id": short["report_id"],
                "shared_profile": profile,
            },
        )
        rows, stop = [], None
        for case in cfg["worlds"]:
            key = case["key"]
            seal = store.completed(key, case)
            if seal is None:
                if time.monotonic() + WORLD_BUFFER > deadline:
                    stop = {"world": key, "reason": "wall_reserve"}
                    break
                target = store.begin(key, case)
                try:
                    row = play_world(ctx, case, target, deadline)
                    boundary(root, ctx, before, profile)
                    seal = store.commit(key, case, row)
                except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    stop = {"world": key, "reason": "unsealed_world", "error": str(exc)}
                    break
            rows.append(seal["result"])
            print(f"{key} {rows[-1]['outcomes']}", flush=True)
        boundary(root, ctx, before, profile)
        result = qualify(len(cfg["worlds"]), cfg["gate"], rows)
        v2 = Counter(row["outcomes"]["boss_v2"] for row in rows)
        result["outcomes_by_arm"]["boss_v2"] = {
            k: v2[k] for k in ("act1_clear", "act1_loss", "capped")
        }
        result["boss_encounters_reached_by_arm"]["boss_v2"] = sum(
            row["episodes"]["boss_v2"]["actual_boss_combat_observed"] for row in rows
        )
        result["checks"]["no_capped_arms"] &= not v2["capped"]
        result["checks"]["tactical_teacher_cleared_more_than_v2"] = (
            result["outcomes_by_arm"]["boss"]["act1_clear"] > v2["act1_clear"]
        )
        result["passed"] = all(result["checks"].values()) and stop is None
        complete = result["checks"]["all_worlds_sealed"] and result["checks"]["no_capped_arms"]
        status = (
            "tactical_teacher_qualified"
            if result["passed"]
            else "tactical_teacher_qualification_blocked"
        )
        if diagnostic:
            status = (
                "tactical_diagnostic_complete" if complete else "tactical_diagnostic_incomplete"
            )
        return write(
            store.workspace / f"attempt-{attempt}.json",
            {
                "schema_version": "native-a8-act1-tactical-result-v1",
                "status": status,
                "config_id": store.config_id,
                "execution_id": ctx["tactical_execution_id"],
                "launch_id": launch["report_id"],
                "qualification": None if diagnostic else result,
                "diagnostic": {
                    key: result[key]
                    for key in (
                        "planned_worlds",
                        "sealed_worlds",
                        "outcomes_by_arm",
                        "boss_encounters_reached_by_arm",
                        "confirmed_clears",
                    )
                }
                if diagnostic
                else None,
                "stop": stop,
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "lessons_admitted": 0,
                **NO_UPDATES,
            },
        )


def tracked(root: Path, cfg: dict[str, Any], *, short: bool, diagnostic: bool = False) -> int:
    attempt = str(time.time_ns())
    child = ["uv", "run", "--no-sync", "python", "-m", MODULE]
    if short:
        child += ["--control"]
        report, workspace, limits = (
            cfg["control_resource"],
            cfg["control_workspace"],
            CONTROL_LIMITS,
        )
    else:
        child += ["--run-diagnostic" if diagnostic else "--run", "--attempt", attempt]
        prefix = cfg["diagnostic_resource_prefix" if diagnostic else "resource_prefix"]
        report, workspace, limits = (
            f"{prefix}-{attempt}.json",
            cfg["diagnostic_workspace" if diagnostic else "workspace"],
            SESSION_LIMITS,
        )
    result = run_tracked_command(
        command=child,
        experiment_kind=ExperimentKind.OTHER,
        report_path=root / report,
        artifact_roots=[root / workspace],
        working_directory=root,
        limits=ResourceLimits(**limits),
    )
    print(json.dumps(result.report, indent=2))
    return 0 if result.exit_code == 0 and result.status == "completed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    for mode in ("preflight", "short", "control", "run", "diagnostic", "run-diagnostic"):
        modes.add_argument(f"--{mode}", dest="mode", const=mode, action="store_const")
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread tactical launcher")
        cfg = json.loads((root / RECIPE).read_text())
        ctx = context(root, cfg)
        before = frozen(root, ctx)
        if args.mode == "preflight":
            with ExitStack() as locks:
                saved = saved_checks(cfg, checked_sources(root, ctx, locks))
            result = {
                "status": "tactical_saved_menus_verified",
                "saved_checks": saved,
                "frozen_checks": before,
            }
        elif args.mode == "short":
            return tracked(root, cfg, short=True)
        elif args.mode == "control":
            result = control(root, ctx, started + CONTROL_LIMITS["wall_seconds"] - 15)
        elif args.mode in {"run", "run-diagnostic"}:
            if args.attempt is None or args.attempt < 1:
                raise ValueError("Use the resource-tracked owner launcher")
            result = run(
                root,
                ctx,
                args.attempt,
                started + SESSION_LIMITS["wall_seconds"] - 45,
                diagnostic=args.mode == "run-diagnostic",
            )
        else:
            diagnostic = args.mode == "diagnostic"
            require_control(root, ctx, diagnostic=diagnostic)
            if _running_games():
                raise ValueError("Close STS2 before the fresh tactical qualification")
            print(
                "Eight fresh Ironclad/A8 worlds with four references and the tactical teacher.\n"
                "Allow about 6–15 minutes. Zero optimizer updates.\n"
                + ("Diagnostic comparison only." if diagnostic else "Qualification only."),
                flush=True,
            )
            return tracked(root, cfg, short=False, diagnostic=diagnostic)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "frozen_checks",
                    "saved_checks",
                    "gate",
                    "qualification",
                    "diagnostic",
                    "stop",
                    "report_id",
                )
                if key in result
            }
        )
    )
    return (
        0
        if result["status"]
        in {
            "tactical_saved_menus_verified",
            "tactical_short_checks_verified",
            "tactical_teacher_qualified",
            "tactical_diagnostic_complete",
        }
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
