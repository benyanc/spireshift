"""Fixed-game-budget native learning curves for standard and larger-batch PPO.

Fresh whole games, public crossed inputs, identical paired initializers and draws.
Sealed units restore model/Adam state. No final-panel selection or promotion.
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified, summarize
from spireshift.engine_native import (
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _sha_file,
    load_engine_qualification_config,
)
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam, fit_round
from spireshift.native_action_context import CROSSED, initialize
from spireshift.native_compact_training import prepare_compact
from spireshift.native_context_cache import CachedContextModel, cached_model
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_resume import ordered_paths, request_for
from spireshift.native_context_reuse import check_sources
from spireshift.native_context_trial import collect_panel, launch_inputs
from spireshift.native_optimizer_probe import SOURCES as PROBE_SOURCES
from spireshift.native_optimizer_probe import load_probe
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = (*PROBE_SOURCES, "native_compact_training.py", "native_optimizer_trial.py")
ARMS = (
    {"name": "standard", "batch_games": 32, "epoch_multiplier": 1},
    {"name": "larger-batch", "batch_games": 128, "epoch_multiplier": 3},
)


def load_trial(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = json.loads(path.read_text())
    probe_cfg, parent = load_probe(q, q.root / cfg["probe_config"]["path"])
    probe = identified(q.root / probe_cfg["workspace"] / "report.json")
    standards = [r for r in probe["results"] if r["variant"] == "standard"]
    short = cfg.get("stage") == "short_bridge_control"
    if (
        cfg.get("schema_version") != "native-optimizer-learning-curve-config-v1"
        or cfg.get("stage") not in {"short_bridge_control", "bounded_optimizer_learning_curve"}
        or cfg["probe_config"]["id"] != manifest_identifier(probe_cfg)
        or cfg["probe_report_id"] != probe["report_id"]
        or probe["status"] != "train_only_optimizer_probe_complete"
        or len(standards) != 2
        or {r["cohort"] for r in standards} != {0, 1}
        or probe["source_unique_games"] != 64
        or not all(
            r["standard_reconstructs_saved_model"]
            for r in probe["results"]
            if r["variant"] == "standard"
        )
        or cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg.get("arms") != list(ARMS)
        or cfg.get("training_seeds") != ([2] if short else [2, 3])
        or cfg.get("games_per_player") != (2 if short else 512)
        or cfg.get("evaluation_games") != (2 if short else 16)
        or cfg.get("milestones") != ([2] if short else [128, 256, 384, 512])
        or cfg.get("chunk_games") != (2 if short else 8)
        or cfg.get("invocation_wall_seconds") != (180 if short else 10800)
        or cfg.get("checkpoint_selection") != "final_only_no_promotion"
        or cfg.get("row_storage") != "readonly_sparse_uint16_float64_v1"
        or len(cfg.get("excluded_seed_manifests", [])) < 3
        or cfg.get("session_limits")
        != {
            "wall_seconds": 180 if short else 900,
            "cpu_seconds": 360 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 6000000000,
        }
    ):
        raise ValueError(
            "Freeze finite paired A8 learning curves, candidate bundle and exact sources"
        )
    check_sources(q.root, probe["sources"])
    compact = identified(q.root / cfg["compact_check"]["path"])
    if (
        compact["report_id"] != cfg["compact_check"]["id"]
        or not compact["baseline_model_reproduced"]
    ):
        raise ValueError("Exact saved-batch compact training parity must pass first")
    check_sources(q.root, compact["source_files"])
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    train = [s for s in seeds["seeds"] if s["partition"] == ("control" if short else "train")]
    dev = [
        s for s in seeds["seeds"] if s["partition"] == ("control_eval" if short else "development")
    ]
    if (
        seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != parent["environment_manifest"]["id"]
        or len(train) != len(cfg["training_seeds"]) * cfg["games_per_player"]
        or len(dev) != len(cfg["training_seeds"]) * cfg["evaluation_games"]
        or len(seeds["seeds"]) != len(train) + len(dev)
        or len({s["id"] for s in seeds["seeds"]}) != len(seeds["seeds"])
        or len({s["seed"] for s in seeds["seeds"]}) != len(seeds["seeds"])
        or any(type(s["id"]) is not int or not isinstance(s["seed"], str) for s in seeds["seeds"])
    ):
        raise ValueError("Optimizer experiment seeds repeat or cross complete-run ownership")
    # The new development set is reserved before either learner sees a game.
    for ref in cfg["excluded_seed_manifests"]:
        old = identified(q.root / ref["path"], "manifest_id")
        if (
            old["manifest_id"] != ref["id"]
            or {s["seed"] for s in seeds["seeds"]} & {s["seed"] for s in old["seeds"]}
            or {s["id"] for s in seeds["seeds"]} & {s["id"] for s in old["seeds"]}
        ):
            raise ValueError("Fresh optimizer seeds overlap a prior/control experiment")
    if not short:
        control = identified(q.root / cfg["control_report"]["path"])
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != "native_optimizer_control_pass"
            or control["implementation_sha256"] != cfg["implementation_sha256"]
            or control["games_recorded"] != 8
        ):
            raise ValueError("The compact optimizer worker/fit control must pass first")
        check_sources(q.root, control["sources"])
        control_cfg = json.loads((q.root / control["recipe_path"]).read_text())
        control_seeds = identified(q.root / control_cfg["seed_manifest"]["path"], "manifest_id")
        if (
            control["config_id"] != manifest_identifier(control_cfg)
            or control_cfg["stage"] != "short_bridge_control"
            or {s["seed"] for s in seeds["seeds"]} & {s["seed"] for s in control_seeds["seeds"]}
            or {s["id"] for s in seeds["seeds"]} & {s["id"] for s in control_seeds["seeds"]}
        ):
            raise ValueError("Long optimizer trial cannot reuse its control games")
    return cfg, parent, seeds


def plan(cfg: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    short = cfg["stage"] == "short_bridge_control"
    train = [s for s in seeds["seeds"] if s["partition"] == ("control" if short else "train")]
    dev = [
        s for s in seeds["seeds"] if s["partition"] == ("control_eval" if short else "development")
    ]
    result = []
    for rep, number in enumerate(cfg["training_seeds"]):
        own = train[rep * cfg["games_per_player"] : (rep + 1) * cfg["games_per_player"]]
        evaluation = dev[rep * cfg["evaluation_games"] : (rep + 1) * cfg["evaluation_games"]]
        states = {}
        for arm in cfg["arms"]:
            key = f"seed-{number}-{arm['name']}-initial"
            states[arm["name"]] = key
            result.append(
                {
                    "key": key,
                    "kind": "initialize",
                    "arm": arm,
                    "numerical_seed": number,
                    "mode": CROSSED,
                    "round": 0,
                }
            )
        for milestone in ([0] if not short else []) + cfg["milestones"]:
            for arm in cfg["arms"]:
                prefix = f"seed-{number}-{arm['name']}"
                size = 2 if short else arm["batch_games"]
                if milestone:
                    first = 0 if short else milestone - 128
                    for offset in range(first, milestone, size):
                        rows = own[offset : offset + size]
                        index = offset // size + 1
                        collected = []
                        for i in range(0, len(rows), cfg["chunk_games"]):
                            key = (
                                f"{prefix}-stage-{milestone:04d}-batch-{index:03d}"
                                f"-collect-{i // cfg['chunk_games']:02d}"
                            )
                            collected.append(key)
                            result.append(
                                {
                                    "key": key,
                                    "kind": "collect",
                                    "state": states[arm["name"]],
                                    "arm": arm,
                                    "numerical_seed": number,
                                    "mode": CROSSED,
                                    "round": index,
                                    "milestone": milestone,
                                    "training": True,
                                    "seeds": rows[i : i + cfg["chunk_games"]],
                                    "panel": "train",
                                    "failure_group": f"{prefix}-train-stage-{milestone}",
                                }
                            )
                        key = f"{prefix}-batch-{index:03d}-fit"
                        result.append(
                            {
                                "key": key,
                                "kind": "fit",
                                "state": states[arm["name"]],
                                "arm": arm,
                                "numerical_seed": number,
                                "mode": CROSSED,
                                "round": index,
                                "milestone": milestone,
                                "collections": collected,
                                "round_seed_ids": [r["id"] for r in rows],
                            }
                        )
                        states[arm["name"]] = key
                for i in range(0, len(evaluation), cfg["chunk_games"]):
                    result.append(
                        {
                            "key": (
                                f"{prefix}-eval-{milestone:04d}"
                                f"-collect-{i // cfg['chunk_games']:02d}"
                            ),
                            "kind": "collect",
                            "state": states[arm["name"]],
                            "arm": arm,
                            "numerical_seed": number,
                            "mode": CROSSED,
                            "round": milestone // size,
                            "milestone": milestone,
                            "training": False,
                            "seeds": evaluation[i : i + cfg["chunk_games"]],
                            "panel": f"development-at-{milestone:04d}",
                            "failure_group": f"{prefix}-eval-{milestone}",
                        }
                    )
    return result


def arm_settings(parent: dict[str, Any], arm: dict[str, Any]) -> dict[str, Any]:
    return {
        **parent["learning"]["ppo"],
        "epochs": parent["learning"]["ppo"]["epochs"] * arm["epoch_multiplier"],
    }


def execute(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    parent: dict[str, Any],
    score: TrainingScoreSpec,
    node: Path,
    store: ChunkJournal,
    task: dict[str, Any],
    request: dict[str, Any],
    completed: dict[str, dict[str, Any]],
    deadline: float,
) -> dict[str, Any]:
    inputs = {}
    if task["kind"] == "collect":
        _require_native_launch_support()
        if _running_games() or not node.is_file():
            raise ValueError("Close the game and select the local Node runtime before collection")
        inputs = launch_inputs(q, parent)
    target = store.begin(task["key"], request)
    sources: dict[str, str] = {}
    if task["kind"] == "initialize":
        m = cached_model(
            initialize(
                parent["environment_manifest"]["id"], score.spec_id, task["numerical_seed"], CROSSED
            )
        )
        o = Adam.zero(m.parameter_count)
        save_state(target / "state.json", m, o)
        _, _, state_id = load_state(target / "state.json")
        result = {
            "state_path": str((target / "state.json").relative_to(q.root)),
            "state_id": state_id,
            "model_id": m.model_id,
            "optimizer_steps": 0,
            "new_optimizer_steps": 0,
            "games_recorded": 0,
        }
    else:
        before = completed[task["state"]]["result"]
        m, o, state_id = load_state(q.root / before["state_path"])
        if state_id != request["before_state_id"] or m.mode != CROSSED:
            raise ValueError("Optimizer trial model/Adam predecessor changed")
        settings = arm_settings(parent, task["arm"])
        if task["kind"] == "fit":
            paths = ordered_paths(
                [q.root / p for k in task["collections"] for p in completed[k]["result"]["paths"]],
                task["round_seed_ids"],
            )
            samples, credit = prepare_compact(
                paths, m, score, settings, parent["learning"]["credit_assignment"], task["round"]
            )
            after, ao, work = fit_round(cast(Any, m), o, samples, settings, task["round"])
            if not isinstance(after, CachedContextModel):
                raise ValueError("Optimizer trial lost encoding identity")
            save_state(target / "state.json", after, ao)
            _, _, after_id = load_state(target / "state.json")
            atomic_json(target / "credit.json", credit)
            atomic_json(target / "work.json", work)
            outcomes = [
                c
                for k in task["collections"]
                for c in completed[k]["result"]["summary"]["outcomes"]
            ]
            batch = summarize(
                [{**c, "decisions": range(c["decision_count"])} for c in outcomes],
                len(task["round_seed_ids"]),
            )
            result = {
                "state_path": str((target / "state.json").relative_to(q.root)),
                "state_id": after_id,
                "model_id": after.model_id,
                "optimizer_steps": ao.steps,
                "new_optimizer_steps": work["optimizer_steps"],
                "games_recorded": 0,
                "training_summary": batch,
                "row_storage": credit["row_storage"],
                "source_games": len(paths),
            }
            print(
                f"{task['arm']['name']}, seed {task['numerical_seed']}, "
                f"{task['milestone']} training games: batch {len(paths)}, "
                f"{work['epochs_completed']} passes, Adam {o.steps}→{ao.steps}; "
                f"average floor {batch['mean_floor']:.2f}, best {batch['best_floor']}, "
                f"wins {batch['wins']}/{len(paths)}.",
                flush=True,
            )
            del samples
        else:
            print(
                f"{task['arm']['name']}, seed {task['numerical_seed']}: "
                f"collecting {len(task['seeds'])} games for {task['panel']}.",
                flush=True,
            )
            shared = Path.home() / "Library/Application Support/SlayTheSpire2"
            snapshot = _shared_snapshot(shared)
            paths, summary, sources = collect_panel(
                q,
                cfg,
                parent,
                inputs,
                task["seeds"],
                node,
                target / "games",
                m,
                score,
                task["numerical_seed"],
                task["panel"],
                task["training"],
                deadline,
            )
            checks = immutable_checks(q, inputs)
            checks["account_profile_unchanged"] = _shared_snapshot(shared) == snapshot
            if not all(checks.values()):
                raise ValueError("Shared inputs/account changed during optimizer trial")
            previous = sum(
                c["result"].get("summary", {}).get("failed_games", 0)
                for c in completed.values()
                if c["result"].get("failure_group") == task["failure_group"]
            )
            if previous + summary["failed_games"] > (
                0 if cfg["stage"] == "short_bridge_control" else 2
            ):
                raise ValueError("Aggregate 128-game stage/evaluation failure allowance exceeded")
            result = {
                "paths": [str(p.relative_to(q.root)) for p in paths],
                "summary": summary,
                "checks": checks,
                "state_id": state_id,
                "model_id": m.model_id,
                "games_recorded": len(paths),
                "failure_group": task["failure_group"],
            }
    return store.commit(task["key"], request, result, sources)


def curves(
    cfg: dict[str, Any], tasks: list[dict[str, Any]], completed: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    result = []
    for number in cfg["training_seeds"]:
        for arm in cfg["arms"]:
            for milestone in ([0] if cfg["stage"] != "short_bridge_control" else []) + cfg[
                "milestones"
            ]:
                selected = [
                    t
                    for t in tasks
                    if t["kind"] == "collect"
                    and not t["training"]
                    and t["numerical_seed"] == number
                    and t["arm"] == arm
                    and t["milestone"] == milestone
                ]
                if any(t["key"] not in completed for t in selected):
                    continue
                outcomes = [
                    o
                    for t in selected
                    for o in completed[t["key"]]["result"]["summary"]["outcomes"]
                ]
                summary = summarize(
                    [{**c, "decisions": range(c["decision_count"])} for c in outcomes],
                    cfg["evaluation_games"],
                )
                result.append(
                    {
                        "arm": arm["name"],
                        "numerical_seed": number,
                        "training_games": milestone,
                        "model_id": completed[selected[0]["key"]]["result"]["model_id"],
                        "summary": summary,
                        "outcomes": outcomes,
                    }
                )
    return result


def compare_final(cfg: dict[str, Any], evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    players = []
    for number in cfg["training_seeds"]:
        for arm in cfg["arms"]:
            start = next(
                p
                for p in evaluations
                if p["numerical_seed"] == number
                and p["arm"] == arm["name"]
                and p["training_games"] == 0
            )
            final = next(
                p
                for p in evaluations
                if p["numerical_seed"] == number
                and p["arm"] == arm["name"]
                and p["training_games"] == cfg["games_per_player"]
            )
            a = {o["seed_id"]: o for o in start["outcomes"]}
            b = {o["seed_id"]: o for o in final["outcomes"]}
            if len(a) != cfg["evaluation_games"] or a.keys() != b.keys():
                raise ValueError("Final optimizer comparison requires every paired evaluation seed")
            players.append(
                {
                    "arm": arm["name"],
                    "numerical_seed": number,
                    "initial_mean_floor": start["summary"]["mean_floor"],
                    "final_mean_floor": final["summary"]["mean_floor"],
                    "mean_floor_change": final["summary"]["mean_floor"]
                    - start["summary"]["mean_floor"],
                    "initial_wins": start["summary"]["wins"],
                    "final_wins": final["summary"]["wins"],
                    "final_failed_games": final["summary"]["failed_games"],
                    "denominator": cfg["evaluation_games"],
                }
            )
    methods = []
    for arm in cfg["arms"]:
        rows = [p for p in players if p["arm"] == arm["name"]]
        methods.append(
            {
                "arm": arm["name"],
                "final_mean_floor": sum(p["final_mean_floor"] for p in rows) / len(rows),
                "mean_floor_change": sum(p["mean_floor_change"] for p in rows) / len(rows),
                "wins": sum(p["final_wins"] for p in rows),
                "failed_games": sum(p["final_failed_games"] for p in rows),
                "denominator": sum(p["denominator"] for p in rows),
            }
        )
    return {
        "players": players,
        "methods": methods,
        "independent_training_replicates": len(cfg["training_seeds"]),
        "terminal_victory_primary": True,
        "development_only_no_untouched_test_claim": True,
        "automatic_promotion": False,
    }


def session(
    q: EngineQualificationConfig,
    path: Path,
    node: Path,
    *,
    maximum_steps: int | None = None,
    status_only: bool = False,
    wall_seconds: int | None = None,
) -> dict[str, Any]:
    cfg, parent, seeds = load_trial(q, path)
    store = ChunkJournal(q.root, cfg)
    tasks = plan(cfg, seeds)
    if maximum_steps is not None and maximum_steps < 1:
        raise ValueError("Maximum steps must be positive")
    wall = cfg["session_limits"]["wall_seconds"] if wall_seconds is None else wall_seconds
    if not 30 <= wall <= cfg["session_limits"]["wall_seconds"]:
        raise ValueError("Session wall cap must not exceed the frozen limit")
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    started = time.monotonic()
    deadline = started + wall - 15
    completed: dict[str, dict[str, Any]] = {}
    executed = 0
    with nullcontext() if status_only else store.lock():
        if (store.workspace / "report.json").exists():
            saved = identified(store.workspace / "report.json")
            if saved["config_id"] != store.config_id:
                raise ValueError("Completed optimizer trial config changed")
            check_sources(q.root, saved["sources"])
            return saved
        for task in tasks:
            if "state" in task and task["state"] not in completed:
                break
            request = request_for(task, completed)
            cached = store.completed(task["key"], request)
            if cached is not None:
                completed[task["key"]] = cached
                continue
            short = cfg["stage"] == "short_bridge_control"
            allowance = (
                (120 if short else 300)
                if task["kind"] == "collect"
                else ((60 if short else 240) if task["kind"] == "fit" else 5)
            )
            if (
                status_only
                or (maximum_steps is not None and executed >= maximum_steps)
                or deadline - time.monotonic() < allowance + 15
            ):
                break
            completed[task["key"]] = execute(
                q,
                cfg,
                parent,
                score,
                node,
                store,
                task,
                request,
                completed,
                min(deadline, time.monotonic() + allowance),
            )
            executed += 1
            print(
                f"Saved {len(completed)}/{len(tasks)} units; all committed work will be reused.",
                flush=True,
            )
            if task["kind"] == "collect" and not task["training"]:
                for e in curves(cfg, tasks, completed):
                    if (
                        e["arm"] == task["arm"]["name"]
                        and e["numerical_seed"] == task["numerical_seed"]
                        and e["training_games"] == task["milestone"]
                    ):
                        s = e["summary"]
                        print(
                            f"Frozen {e['arm']}, seed {e['numerical_seed']}, "
                            f"after {e['training_games']} training games: "
                            f"wins {s['wins']}/{s['planned_games']}; "
                            f"mean floor {s['mean_floor']:.2f}; best {s['best_floor']}.",
                            flush=True,
                        )
        done = len(completed) == len(tasks)
        sources = {
            str(path.relative_to(q.root)): _sha_file(path),
            **{f"src/spireshift/{n}": s for n, s in cfg["implementation_sha256"].items()},
        }
        refs = [cfg["seed_manifest"], cfg["probe_config"], cfg["compact_check"]]
        if cfg["stage"] != "short_bridge_control":
            refs.append(cfg["control_report"])
        for ref in refs:
            p = q.root / ref["path"]
            sources[str(p.relative_to(q.root))] = _sha_file(p)
        for c in completed.values():
            sources.update(c["sources"])
        for t in tasks[: len(completed)]:
            p = store.path(t["key"]) / "done.json"
            sources[str(p.relative_to(q.root))] = _sha_file(p)
        cfgpath = store.workspace / "config-at-launch.json"
        if cfgpath.exists():
            sources[str(cfgpath.relative_to(q.root))] = _sha_file(cfgpath)
        body = {
            "schema_version": "native-optimizer-learning-curve-v1",
            "config_id": store.config_id,
            "recipe_path": str(path.relative_to(q.root)),
            "status": (
                "native_optimizer_control_pass"
                if cfg["stage"] == "short_bridge_control"
                else "native_optimizer_learning_curve_complete"
            )
            if done
            else "paused_between_committed_chunks",
            "completed_units": len(completed),
            "planned_units": len(tasks),
            "games_recorded": sum(c["result"].get("games_recorded", 0) for c in completed.values()),
            "planned_games": sum(len(t.get("seeds", [])) for t in tasks),
            "new_units_this_session": executed,
            "new_games_this_session": sum(
                c["result"].get("games_recorded", 0) for c in list(completed.values())[-executed:]
            )
            if executed
            else 0,
            "optimizer_steps": sum(
                c["result"].get("new_optimizer_steps", 0) for c in completed.values()
            ),
            "learning_curves": curves(cfg, tasks, completed),
            "implementation_sha256": cfg["implementation_sha256"],
            "sources": sources,
            "wall_seconds": time.monotonic() - started,
            "session_wall_cap": wall,
            "same_game_budget_different_training_compute": True,
            "candidate_changes_batch_size_and_reuse_together": True,
            "row_storage": cfg["row_storage"],
            "checkpoint_selection": "final_only_no_promotion",
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "claim_scope": "fixed_A8_development_learning_curves_not_automatic_readiness",
        }
        report = {**body, "report_id": manifest_identifier(body)}
        if done and cfg["stage"] != "short_bridge_control":
            body["final_comparison"] = compare_final(cfg, body["learning_curves"])
            report = {**body, "report_id": manifest_identifier(body)}
        if not status_only:
            sessions = store.workspace / "sessions"
            n = len(list(sessions.glob("session-*.json"))) + 1
            atomic_json(sessions / f"session-{n:03d}.json", report)
            if done:
                atomic_json(store.workspace / "report.json", report)
        return report


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
        r = session(
            q,
            q.root / a.config,
            a.node,
            maximum_steps=a.maximum_steps,
            status_only=a.status,
            wall_seconds=a.wall_seconds,
        )
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                k: v
                for k, v in r.items()
                if k not in {"sources", "implementation_sha256", "learning_curves"}
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
