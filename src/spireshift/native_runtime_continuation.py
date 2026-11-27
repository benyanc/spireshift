"""Bounded native repair continuation from both round-48 full Adam states.

The qualified collector, compact experience and numerical kernel stay unchanged.
Only fresh TRAIN games enter fitting. Development controls stopping, never the
checkpoint chosen; a separate holdout opens only after both current players stop.
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.full_run_experience import atomic_json
from spireshift.native_confirmation_metrics import compare
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_resume import request_for
from spireshift.native_context_reuse import check_sources
from spireshift.native_runtime_execute import execute as execute_qualified
from spireshift.native_runtime_plan import decide, final_plan, panels, training_plan, validate
from spireshift.native_shop_continuation import SOURCES as PRIOR_SOURCES
from spireshift.native_shop_continuation import load_continuation as load_prior
from spireshift.native_shop_policy import CONTRACT
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = (
    *PRIOR_SOURCES,
    "engine_runtime_gaps.py",
    "native_runtime_admission.py",
    "native_runtime_execute.py",
    "native_runtime_plan.py",
    "native_runtime_continuation.py",
)
COMPLETE = "native_runtime_continuation_complete"
CONTROL = "native_runtime_continuation_control_pass"


def load_continuation(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    from spireshift.native_runtime_admission import require_effects

    cfg = json.loads(path.read_text())
    old_path = q.root / cfg["source_continuation"]["path"]
    old, parent, _, _ = load_prior(q, old_path)
    result_path = q.root / cfg["source_report"]["path"]
    result = identified(result_path)
    if (
        cfg["source_continuation"]["id"] != manifest_identifier(old)
        or cfg["source_report"]["id"] != result["report_id"]
        or result["config_id"] != manifest_identifier(old)
        or result["status"] != "native_shop_continuation_complete"
        or result["ending"]["milestone"] != 1536
        or not result["original_states_unchanged"]
        or cfg.get("policy_contract") != CONTRACT
        or cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("entry_sha256") != _sha_file(q.root / "scripts/runtime-continuation-v1.py")
    ):
        raise ValueError(
            "Bind completed source result, current players and exact continuation code"
        )
    check_sources(q.root, result["sources"])
    expected_players = []
    for n in (2, 3):
        key = result["ending"]["states"][str(n)]
        done_path = result_path.parent / "chunks" / key / "done.json"
        done = identified(done_path)["result"]
        state_path = q.root / done["state_path"]
        model, optimizer, state_id = load_state(state_path)
        if state_id != done["state_id"] or optimizer.steps != done["optimizer_steps"]:
            raise ValueError("Latest complete source weights/Adam state changed")
        expected_players.append(
            {
                "numerical_seed": n,
                "version": "trained",
                "path": done["state_path"],
                "sha256": _sha_file(state_path),
                "state_id": state_id,
                "model_id": model.model_id,
                "optimizer_steps": optimizer.steps,
                "round": 48,
                "scheduled_training_games": 1536,
            }
        )
    if cfg["players"] != expected_players:
        raise ValueError("Continue both current round-48 states, not an earlier best or reset")
    repair = require_effects(q.root, cfg)
    sources = {
        **result["sources"],
        **{f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()},
        str(path.relative_to(q.root)): _sha_file(path),
        cfg["source_continuation"]["path"]: _sha_file(old_path),
        cfg["source_report"]["path"]: _sha_file(result_path),
        cfg["runtime_repair"]["path"]: _sha_file(q.root / cfg["runtime_repair"]["path"]),
        cfg["runtime_effects"]["path"]: _sha_file(q.root / cfg["runtime_effects"]["path"]),
        "scripts/runtime-continuation-v1.py": cfg["entry_sha256"],
    }
    effects = identified(q.root / cfg["runtime_effects"]["path"])
    sources.update(effects["sources"])
    # The native numerical environment/rules ID remains stable; the changed host
    # and additional Crystal screen are explicit recipe/worker/experience identities.
    for ref in (repair["old_run"], repair["new_run"]):
        sources[ref["path"]] = _sha_file(q.root / ref["path"])
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    if (
        seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != parent["environment_manifest"]["id"]
    ):
        raise ValueError("Runtime continuation seeds bind another environment")
    validate(cfg, seeds)
    required = {old["seed_manifest"]["path"], *[r["path"] for r in old["excluded_seed_manifests"]]}
    if not required <= {r["path"] for r in cfg["excluded_seed_manifests"]}:
        raise ValueError("Exclude all old consumed/reserved seeds, including old holdouts")
    for ref in cfg["excluded_seed_manifests"]:
        previous = identified(q.root / ref["path"], "manifest_id")
        if (
            previous["manifest_id"] != ref["id"]
            or ({s["id"] for s in seeds["seeds"]} & {s["id"] for s in previous["seeds"]})
            or ({s["seed"] for s in seeds["seeds"]} & {s["seed"] for s in previous["seeds"]})
        ):
            raise ValueError("New runtime continuation seeds overlap old reservations")
        sources[ref["path"]] = _sha_file(q.root / ref["path"])
    if cfg["stage"] != "short_bridge_control":
        control_path = q.root / cfg["control_report"]["path"]
        control = identified(control_path)
        cc = json.loads((q.root / control["recipe_path"]).read_text())
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != CONTROL
            or control["games_recorded"] != 12
            or control["config_id"] != manifest_identifier(cc)
            or cc["stage"] != "short_bridge_control"
            or any(
                cc[k] != cfg[k]
                for k in (
                    "players",
                    "implementation_sha256",
                    "entry_sha256",
                    "source_report",
                    "runtime_repair",
                    "runtime_effects",
                    "policy_contract",
                )
            )
            or cc["seed_manifest"] not in cfg["excluded_seed_manifests"]
            or control["fit_rounds"] != [49, 49]
            or not control["original_states_unchanged"]
        ):
            raise ValueError("Fresh native-runtime/full-Adam continuation control must pass first")
        check_sources(q.root, control["sources"])
        sources.update(control["sources"])
        sources[cfg["control_report"]["path"]] = _sha_file(control_path)
    sources[cfg["seed_manifest"]["path"]] = _sha_file(q.root / cfg["seed_manifest"]["path"])
    return cfg, parent, seeds, sources


def request(task: dict[str, Any], completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = request_for(task, completed)
    if task["kind"] == "decide":
        result["evaluation_ids"] = [completed[k]["report_id"] for k in task["evaluations"]]
        result["initial_evaluation_ids"] = [
            completed[k]["report_id"] for k in task["initial_evaluations"]
        ]
        result["prior_decision_ids"] = [completed[k]["report_id"] for k in task["prior_decisions"]]
        result["state_ids"] = {
            n: completed[k]["result"]["state_id"] for n, k in task["states"].items()
        }
    return result


def execute(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    score: TrainingScoreSpec,
    node: Path,
    store: ChunkJournal,
    task: dict[str, Any],
    req: dict[str, Any],
    completed: dict[str, dict[str, Any]],
    deadline: float,
) -> dict[str, Any]:
    if task["kind"] in {"collect", "fit"}:
        # Same collector, ordering, credit and kernel as the confirmed standard arm.
        return execute_qualified(q, cfg, parent, score, node, store, task, req, completed, deadline)
    target = store.begin(task["key"], req)
    if task["kind"] == "restore":
        ref = task["player"]
        model, optimizer, state_id = load_state(q.root / ref["path"])
        if state_id != ref["state_id"] or model.model_id != ref["model_id"] or optimizer.steps < 1:
            raise ValueError("Restore the trained model and full nonzero Adam state, never reset")
        check_sources(q.root, {ref["path"]: ref["sha256"]})
        p = target / "state.json"
        save_state(p, model, optimizer)
        _, _, copied = load_state(p)
        if copied != state_id:
            raise ValueError("Continuation changed the starting model or Adam moments")
        result = {
            "state_path": str(p.relative_to(q.root)),
            "state_id": copied,
            "model_id": model.model_id,
            "optimizer_steps": optimizer.steps,
            "new_optimizer_steps": 0,
            "games_recorded": 0,
            "source_round": cfg["starting_round"],
            "source_training_games": 1536,
        }
    else:
        result = decide(cfg, task, completed)
        print(
            f"After {task['milestone']} training games/player: pooled development wins "
            f"{result['current']['wins']}/{result['current']['denominator']}; "
            f"average floor {result['current']['mean_floor']:.2f}; "
            f"stale checks {result['stale_checks']}; {result['reason']}.",
            flush=True,
        )
    return store.commit(task["key"], req, result)


def verify_state(
    q: EngineQualificationConfig,
    task: dict[str, Any],
    receipt: dict[str, Any],
    completed: dict[str, dict[str, Any]],
) -> None:
    if task["kind"] not in {"restore", "fit"}:
        return
    r = receipt["result"]
    model, optimizer, state_id = load_state(q.root / r["state_path"])
    if (
        state_id != r["state_id"]
        or model.model_id != r["model_id"]
        or optimizer.steps != r["optimizer_steps"]
    ):
        raise ValueError("Saved continuation state or optimizer counter changed")
    if task["kind"] == "restore":
        if state_id != task["player"]["state_id"]:
            raise ValueError("Restored state differs from original weights/Adam")
    else:
        before = completed[task["state"]]["result"]
        if (
            optimizer.steps != before["optimizer_steps"] + r["new_optimizer_steps"]
            or r["new_optimizer_steps"] < 1
        ):
            raise ValueError("Continuation reset or skipped its accumulated optimizer state")


def maximum_plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = training_plan(cfg, seeds)
    return tasks + final_plan(
        cfg, seeds, {"milestone": cfg["milestones"][-1], "states": tasks[-1]["states"]}
    )


def session(
    q: EngineQualificationConfig,
    path: Path,
    node: Path,
    *,
    status_only: bool = False,
    maximum_steps: int | None = None,
    wall_seconds: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    cfg, parent, seeds, sources = load_continuation(q, path)
    store = ChunkJournal(q.root, cfg)
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    wall = cfg["session_limits"]["wall_seconds"] if wall_seconds is None else wall_seconds
    if (
        not 30 <= wall <= cfg["session_limits"]["wall_seconds"]
        or maximum_steps is not None
        and maximum_steps < 1
    ):
        raise ValueError("Use a positive step limit and a session within its declared cap")
    deadline, executed = started + wall - 15, 0
    completed: dict[str, dict[str, Any]] = {}
    visited: list[dict[str, Any]] = []
    ending: dict[str, Any] | None = None

    def run_task(task: dict[str, Any]) -> bool:
        nonlocal executed
        req = request(task, completed)
        receipt = store.completed(task["key"], req)
        if receipt is None:
            short = cfg["stage"] == "short_bridge_control"
            allowance = (
                (60 if short else 300)
                if task["kind"] == "collect"
                else (45 if short else 240)
                if task["kind"] == "fit"
                else 5
            )
            if (
                status_only
                or maximum_steps is not None
                and executed >= maximum_steps
                or deadline - time.monotonic() < allowance + 15
            ):
                return False
            receipt = execute(
                q,
                cfg,
                parent,
                score,
                node,
                store,
                task,
                req,
                completed,
                min(deadline, time.monotonic() + allowance),
            )
            executed += 1
            if task["kind"] == "fit":
                s = receipt["result"]["training_summary"]
                earlier = [
                    c["result"]["training_summary"]
                    for c in completed.values()
                    if "training_summary" in c["result"]
                ]
                best = max(
                    [*earlier, s],
                    key=lambda r: (r["best_victory"], r["best_completed_acts"], r["best_floor"]),
                )
                print(
                    f"Best sampled training game so far: floor {best['best_floor']}, "
                    f"{best['best_completed_acts']} acts; victory {best['best_victory']}.",
                    flush=True,
                )
        verify_state(q, task, receipt, completed)
        if task["kind"] == "decide" and receipt["result"] != decide(cfg, task, completed):
            raise ValueError(
                "Saved plateau decision does not reconstruct from its development panels"
            )
        completed[task["key"]] = receipt
        visited.append(task)
        return True

    with nullcontext() if status_only else store.lock():
        tasks = training_plan(cfg, seeds)
        for task in tasks:
            if not run_task(task):
                break
            if task["kind"] == "decide" and completed[task["key"]]["result"]["stop"]:
                ending = completed[task["key"]]["result"]
                break
        tests = final_plan(cfg, seeds, ending) if ending else []
        if ending:
            for task in tests:
                if not run_task(task):
                    break
        done = ending is not None and all(t["key"] in completed for t in tests)
        all_possible = maximum_plan(cfg, seeds)
        scheduled_games = (
            (
                sum(len(t.get("seeds", [])) for t in visited if t not in tests)
                + sum(len(t.get("seeds", [])) for t in tests)
            )
            if ending
            else None
        )
        development = panels(cfg, tasks, completed)
        holdout = panels(cfg, tests, completed, holdout=True)
        fit_tasks = [t for t in visited if t["kind"] == "fit"]
        for task in visited:
            receipt = completed[task["key"]]
            sources.update(receipt["sources"])
            p = store.path(task["key"]) / "done.json"
            sources[str(p.relative_to(q.root))] = _sha_file(p)
        launch = store.workspace / "config-at-launch.json"
        if launch.exists():
            if json.loads(launch.read_text()) != cfg:
                raise ValueError("Saved continuation launch recipe changed")
            sources[str(launch.relative_to(q.root))] = _sha_file(launch)
        original_sources = {r["path"]: r["sha256"] for r in cfg["players"]}
        check_sources(q.root, original_sources)
        body = {
            "schema_version": "native-runtime-continuation-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(q.root)),
            "status": (CONTROL if cfg["stage"] == "short_bridge_control" else COMPLETE)
            if done
            else "paused_between_committed_chunks",
            "completed_units": len(completed),
            "maximum_planned_units": len(all_possible),
            "games_recorded": sum(c["result"].get("games_recorded", 0) for c in completed.values()),
            "maximum_planned_games": sum(len(t.get("seeds", [])) for t in all_possible),
            "scheduled_games_at_stop": scheduled_games,
            "new_units_this_session": executed,
            "optimizer_steps": sum(
                c["result"].get("new_optimizer_steps", 0) for c in completed.values()
            ),
            "fit_rounds": [t["round"] for t in fit_tasks],
            "starting_optimizer_steps": {
                str(n): completed[f"seed-{n}-restore"]["result"]["optimizer_steps"]
                for n in cfg["training_seeds"]
                if f"seed-{n}-restore" in completed
            },
            "ending_optimizer_steps": {
                n: completed[key]["result"]["optimizer_steps"]
                for n, key in ending["states"].items()
            }
            if ending
            else None,
            "ending": ending,
            "development": development,
            "holdout": holdout,
            "final_holdout_comparison": compare(
                {"training_seeds": cfg["training_seeds"], "stage": "fresh_frozen_confirmation"},
                holdout,
                {"seeds": [s for s in seeds["seeds"] if s["partition"] == "holdout"]},
            )
            if done and cfg["holdout_games"]
            else None,
            "starting_training_games_per_player": 1536,
            "initial_comparison_player_is_round_48_under_repaired_runtime": True,
            "policy_contract": CONTRACT,
            "navigation_steps": sum(
                c["result"].get("summary", {}).get("navigation_steps", 0)
                for c in completed.values()
            ),
            "original_states_unchanged": True,
            "sources": sources,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_extension_follows": False,
            "wall_seconds": time.monotonic() - started,
            "claim_scope": "finite_A8_runtime_repair_full_Adam_continuation",
        }
        final = store.workspace / "report.json"
        if final.exists():
            saved = identified(final)
            check_sources(q.root, saved["sources"])
            if (
                saved["config_id"] != store.config_id
                or not done
                or saved["ending"] != ending
                or saved["final_holdout_comparison"] != body["final_holdout_comparison"]
            ):
                raise ValueError("Completed continuation does not reconstruct")
            return saved
        result = {**body, "report_id": manifest_identifier(body)}
        if not status_only:
            check_sources(q.root, sources)
            n = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
            atomic_json(store.workspace / f"sessions/session-{n:03d}.json", result)
            if done:
                atomic_json(final, result)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("qualification", type=Path)
    p.add_argument("config", type=Path)
    p.add_argument("--node", type=Path, required=True)
    p.add_argument("--status", action="store_true")
    p.add_argument("--maximum-steps", type=int)
    p.add_argument("--wall-seconds", type=int)
    a = p.parse_args()
    q = load_engine_qualification_config(a.qualification)
    try:
        result = session(
            q,
            q.root / a.config,
            a.node,
            status_only=a.status,
            maximum_steps=a.maximum_steps,
            wall_seconds=a.wall_seconds,
        )
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "development", "holdout", "fit_rounds"}
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
