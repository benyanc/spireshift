"""Check the proven ordinary-fight lethal line and compare it on fresh A8 starts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_ordinary_episode import play, policy
from spireshift.native_a8_ordinary_policy import CONTRACT, REASON
from spireshift.native_a8_rescue_curriculum import first_change
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_a8_rescue_inputs import CONTROL_LIMITS, GAME_LIMITS, SESSION_LIMITS
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_a8_tactical_episode import play as play_tactical
from spireshift.native_a8_tactical_session import RECIPE as PARENT_RECIPE
from spireshift.native_a8_tactical_session import boundary, context, frozen, require_control
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-ordinary-lethal-v1.json"
MODULE = "spireshift.native_a8_ordinary_session"
ARMS = ("tactical", "ordinary")
WORLD_RESERVE = 3 * (GAME_LIMITS["episode_wall_seconds"] + 20) + 40


def load(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    if cfg["parent"]["path"] != PARENT_RECIPE or cfg["teacher"] != CONTRACT:
        raise ValueError("Require the separately pinned ordinary-fight extension")
    parent = json.loads(verified(root, cfg["parent"]).read_text())
    ctx = context(root, parent)
    if cfg["objective"] != parent["objective"] or cfg["game_limits"] != GAME_LIMITS:
        raise ValueError(
            "The ordinary-fight comparison must retain the frozen objective and limits"
        )
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
    for recipe in (ctx["boss_config"], ctx["reward_config"], parent):
        used.update(c["seed"] for c in recipe["worlds"])
    used.update(c["seed"] for c in ctx["reward_config"]["control_worlds"])
    used.update(c["seed"] for c in parent["diagnostic_worlds"])
    used.update(
        (old["control"]["seed"], ctx["boss_config"]["control"]["seed"], parent["smoke"]["seed"])
    )
    starts = [c["seed"] for c in [*cfg["worlds"], cfg["smoke"]]]
    if len(starts) != len(set(starts)) or used.intersection(starts):
        raise ValueError("Use fresh disjoint ordinary-fight comparison and smoke worlds")
    return {
        **ctx,
        "ordinary_config": cfg,
        "ordinary_execution_id": manifest_identifier(
            {"parent_execution_id": ctx["tactical_execution_id"], "config": cfg}
        ),
    }


def verify_sources(root: Path, ctx: dict[str, Any]) -> None:
    cfg = ctx["ordinary_config"]
    if json.loads((root / RECIPE).read_text()) != cfg:
        raise ValueError("Ordinary-fight execution recipe changed")
    verified(root, cfg["parent"])
    check_sources(root, cfg["implementation"])
    for ref in cfg["proof"].values():
        verified(root, ref)


def saved_check(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    cfg = ctx["ordinary_config"]
    verify_sources(root, ctx)
    require_control(root, ctx, diagnostic=True)
    proof = identified(root / cfg["proof"]["report"]["path"])
    resources = identified(root / cfg["proof"]["resources"]["path"])
    source_recipe = json.loads((root / cfg["proof"]["recipe"]["path"]).read_text())
    source = ChunkJournal(root, source_recipe)
    case = source_recipe["case"]
    seal = source.completed(case["key"], case)
    if (
        proof["status"] != "sewer_clam_three_strike_kill_verified"
        or proof["config_id"] != source.config_id
        or proof["frozen_checks"] != frozen(root, ctx)
        or resources["status"] != "completed"
        or resources["exit_code"] != 0
        or resources["cap"] is not None
        or seal is None
        or seal["report_id"] != proof["seal_id"]
        or seal["result"]["report_id"] != proof["result_id"]
        or seal["result"]["outcome"] != "fight_win"
    ):
        raise ValueError("Ordinary-fight planning requires the sealed native Sewer Clam kill")
    actor = policy(ctx, case)
    actions = []
    for _, frame, delivered in decisions(source.path(case["key"]) / TRACE):
        if delivered is None or delivered["choice"].get("stage") != "combat_branch":
            continue
        choice = actor.choose(frame)
        index = choice["action_index"]
        if index != delivered["choice"]["action_index"] or choice.get("tactical_reason") != REASON:
            raise ValueError("Ordinary-fight policy missed the verified Sewer Clam choice")
        actor.acknowledge(delivered["receipt"])
        actions.append(frame["public_input"]["candidates"][index]["label"])
    if actions != ["Play Strike on Sewer Clam"] * 3:
        raise ValueError("Ordinary-fight policy must reproduce all three verified Strikes")
    return {
        "proof_id": proof["report_id"],
        "verified_choices": actions,
        "reward_hp": proof["reward_hp"],
    }


def pair(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    rows = {
        "tactical": play_tactical(ctx, case, target / "tactical", deadline),
        "ordinary": play(ctx, case, target / "ordinary", deadline),
    }
    if rows["tactical"]["initial_public_input_id"] != rows["ordinary"]["initial_public_input_id"]:
        raise ValueError("Ordinary-fight arms started on different public menus")
    outcomes = {arm: row["outcome"] for arm, row in rows.items()}
    changed = first_change(target / "tactical" / TRACE, target / "ordinary" / TRACE)
    if changed is not None and changed["reason"] != REASON:
        raise ValueError("First ordinary-fight difference lacks its verified lethal intervention")
    if "capped" not in outcomes.values() and len(set(outcomes.values())) > 1 and changed is None:
        raise ValueError("Different outcomes require a verified same-menu ordinary-fight change")
    confirmed_rescue = outcomes == {"tactical": "act1_loss", "ordinary": "act1_clear"}
    if confirmed_rescue:
        confirmation = play(ctx, case, target / "confirmation", deadline)
        if (
            confirmation["outcome"] != "act1_clear"
            or confirmation["semantic_trajectory_sha256"]
            != rows["ordinary"]["semantic_trajectory_sha256"]
        ):
            raise ValueError("Ordinary-fight rescue did not reproduce from a fresh start")
        rows["confirmation"] = confirmation
    return {
        "case": case,
        "episodes": rows,
        "outcomes": outcomes,
        "first_change": changed,
        "confirmed_rescue": confirmed_rescue,
    }


def compare(
    root: Path,
    ctx: dict[str, Any],
    saved: dict[str, Any],
    deadline: float,
    *,
    short: bool,
    attempt: int,
) -> dict[str, Any]:
    cfg = ctx["ordinary_config"]
    store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]} if short else cfg)
    cases = [cfg["smoke"]] if short else cfg["worlds"]
    with store.lock():
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        before = frozen(root, ctx)
        profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
        rows, seals, stop = [], {}, None
        for case in cases:
            key = case["key"]
            seal = store.completed(key, case)
            if seal is None:
                if not short and time.monotonic() + WORLD_RESERVE > deadline:
                    stop = {"world": key, "reason": "wall_reserve"}
                    break
                target = store.begin(key, case)
                try:
                    result = pair(ctx, case, target, deadline)
                    boundary(root, ctx, before, profile)
                    verify_sources(root, ctx)
                    seal = store.commit(key, case, result)
                except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
                    stop = {"world": key, "reason": "unsealed_world", "error": str(exc)}
                    break
            rows.append(seal["result"])
            seals[key] = seal["report_id"]
            print(f"{key} {rows[-1]['outcomes']}", flush=True)
        boundary(root, ctx, before, profile)
        verify_sources(root, ctx)
        counts = {arm: Counter(r["outcomes"][arm] for r in rows) for arm in ARMS}
        complete = (
            stop is None
            and len(rows) == len(cases)
            and not any(c["capped"] for c in counts.values())
        )
        verified_choices = sum(
            r["episodes"]["ordinary"]["tactical_deliveries"].get(REASON, 0) for r in rows
        )
        passed = complete and (not short or verified_choices > 0)
        return write(
            store.workspace / ("report.json" if short else f"attempt-{attempt}.json"),
            {
                "schema_version": "native-a8-ordinary-lethal-comparison-v1",
                "status": (
                    "ordinary_lethal_short_verified"
                    if short
                    else "ordinary_lethal_comparison_complete"
                )
                if passed
                else "ordinary_lethal_comparison_incomplete",
                "config_id": store.config_id,
                "execution_id": ctx["ordinary_execution_id"],
                "objective": cfg["objective"],
                "saved_check": saved,
                "seals": seals,
                "planned_worlds": len(cases),
                "sealed_worlds": len(rows),
                "outcomes_by_arm": {
                    arm: {k: count[k] for k in ("act1_clear", "act1_loss", "capped")}
                    for arm, count in counts.items()
                },
                "boss_encounters_reached_by_arm": {
                    arm: sum(r["episodes"][arm]["actual_boss_combat_observed"] for r in rows)
                    for arm in ARMS
                },
                "changed_worlds": [r["case"]["key"] for r in rows if r["first_change"]],
                "confirmed_rescues": [r["case"]["key"] for r in rows if r["confirmed_rescue"]],
                "ordinary_lethal_deliveries": verified_choices,
                "verified_native_deliveries": sum(
                    e["verified_native_deliveries"] for r in rows for e in r["episodes"].values()
                ),
                "frozen_checks": before,
                "shared_profile_unchanged": True,
                "stop": stop,
                "lessons_admitted": 0,
                **NO_UPDATES,
            },
        )


def require_short(root: Path, ctx: dict[str, Any], saved: dict[str, Any]) -> dict[str, Any]:
    cfg = ctx["ordinary_config"]
    store = ChunkJournal(root, {**cfg, "workspace": cfg["control_workspace"]})
    report = identified(store.workspace / "report.json")
    resources = identified(root / cfg["control_resource"])
    case = cfg["smoke"]
    seal = store.completed(case["key"], case)
    if (
        report["status"] != "ordinary_lethal_short_verified"
        or report["config_id"] != store.config_id
        or report["execution_id"] != ctx["ordinary_execution_id"]
        or report["saved_check"] != saved
        or seal is None
        or seal["report_id"] != report["seals"][case["key"]]
        or resources["exit_code"] != 0
        or resources["cap"] is not None
        or resources["command"] != ["uv", "run", "--no-sync", "python", "-m", MODULE, "--control"]
        or resources["artifacts"]["roots"] != [str(store.workspace)]
    ):
        raise ValueError("Fresh comparison requires the exact passing ordinary-fight smoke check")
    return report


def tracked(root: Path, cfg: dict[str, Any], *, short: bool) -> int:
    attempt = time.time_ns()
    mode = ["--control"] if short else ["--run", "--attempt", str(attempt)]
    resources = run_tracked_command(
        command=["uv", "run", "--no-sync", "python", "-m", MODULE, *mode],
        experiment_kind=ExperimentKind.OTHER,
        report_path=root
        / (cfg["control_resource"] if short else f"{cfg['resource_prefix']}-{attempt}.json"),
        artifact_roots=[root / cfg["control_workspace" if short else "workspace"]],
        working_directory=root,
        limits=ResourceLimits(**(CONTROL_LIMITS if short else SESSION_LIMITS)),
    )
    print(json.dumps(resources.report, indent=2))
    return 0 if resources.exit_code == 0 and resources.status == "completed" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    for mode in ("preflight", "short", "control", "run"):
        modes.add_argument(f"--{mode}", dest="mode", action="store_const", const=mode)
    parser.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread ordinary-fight launcher")
        cfg = json.loads((root / RECIPE).read_text())
        ctx = load(root, cfg)
        saved = saved_check(root, ctx)
        if args.mode == "preflight":
            print(json.dumps({"status": "ordinary_lethal_saved_check_verified", **saved}))
            return 0
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")
        if args.mode == "short":
            return tracked(root, cfg, short=True)
        if args.mode != "control":
            require_short(root, ctx, saved)
        if args.mode is None:
            print(
                "Sixteen fresh matched Ironclad/A8 worlds. Allow about 5–10 minutes. "
                "Diagnostic only with zero optimizer updates.",
                flush=True,
            )
            return tracked(root, cfg, short=False)
        short = args.mode == "control"
        if not short and (args.attempt is None or args.attempt < 1):
            raise ValueError("Use the resource-tracked owner launcher")
        limits = CONTROL_LIMITS if short else SESSION_LIMITS
        result = compare(
            root,
            ctx,
            saved,
            started + limits["wall_seconds"] - 20,
            short=short,
            attempt=args.attempt or 0,
        )
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2
    print(json.dumps(result))
    return (
        0
        if result["status"]
        in {"ordinary_lethal_short_verified", "ordinary_lethal_comparison_complete"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
