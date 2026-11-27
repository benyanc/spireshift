"""Versioned, bounded work sessions of sealed collection and model/Adam chunks.

Completed chunks are checked and skipped. Session limits stop between chunks;
uncertain interrupted collection is never replayed or admitted as PPO data.
Historical trial files and worker profiles remain read-only inputs.
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
from spireshift.native_action_context import CROSSED, ORIGINAL, initialize
from spireshift.native_context_cache import CachedContextModel, cached_model
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_reuse import check_sources
from spireshift.native_context_trial import SOURCES as LEGACY_SOURCES
from spireshift.native_context_trial import collect_panel, launch_inputs, load_trial, prepare
from spireshift.training_objective import TrainingScoreSpec, load_training_score_spec

SOURCES = (
    *LEGACY_SOURCES,
    "native_context_cache.py",
    "native_context_journal.py",
    "native_context_resume.py",
    "native_context_reuse.py",
)


def load_resume(
    q: EngineQualificationConfig, path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cfg = json.loads(path.read_text())
    old, parent, old_seeds = load_trial(q, q.root / cfg["legacy_recipe"]["path"])
    short = cfg.get("stage") == "short_bridge_control"
    if (
        cfg.get("schema_version") != "native-context-chunked-comparison-config-v2"
        or cfg.get("stage") not in {"short_bridge_control", "bounded_native_comparison"}
        or cfg.get("cache") != "immutable_identity_compatible_model_id_v1"
        or cfg.get("implementation_sha256")
        != {n: _sha_file(q.root / "src/spireshift" / n) for n in SOURCES}
        or cfg["legacy_recipe"]["id"] != manifest_identifier(old)
        or cfg.get("checkpoint_selection") != "final_only"
        or cfg.get("modes") != [ORIGINAL, CROSSED]
        or cfg.get("training_seed") != (0 if short else 1)
        or cfg.get("recovery") != ("control_only" if short else "fresh_matched_pair")
        or cfg.get("rounds") != (1 if short else 4)
        or cfg.get("games_per_round") != (2 if short else 32)
        or cfg.get("chunk_games") != (2 if short else 8)
        or cfg.get("evaluation_games") != (2 if short else 16)
        or cfg.get("session_limits")
        != {
            "wall_seconds": 180 if short else 900,
            "cpu_seconds": 360 if short else 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 4000000000,
        }
    ):
        raise ValueError("Freeze the chunked comparison sources, cache, scope and bounded sessions")
    seeds = identified(q.root / cfg["seed_manifest"]["path"], "manifest_id")
    if (
        seeds["manifest_id"] != cfg["seed_manifest"]["id"]
        or seeds["environment_id"] != parent["environment_manifest"]["id"]
    ):
        raise ValueError("Chunked seeds bind a different manifest/environment")
    train = [s for s in seeds["seeds"] if s["partition"] == ("control" if short else "train")]
    evaluation = [
        s for s in seeds["seeds"] if s["partition"] == ("control_eval" if short else "development")
    ]
    if (
        len(train) != cfg["rounds"] * cfg["games_per_round"]
        or len(evaluation) != cfg["evaluation_games"]
        or len(seeds["seeds"]) != len(train) + len(evaluation)
        or len({s["id"] for s in seeds["seeds"]}) != len(seeds["seeds"])
        or len({s["seed"] for s in seeds["seeds"]}) != len(seeds["seeds"])
        or any(type(s["id"]) is not int or not isinstance(s["seed"], str) for s in seeds["seeds"])
        or {s["seed"] for s in train} & {s["seed"] for s in old_seeds["seeds"]}
        or {s["id"] for s in train} & {s["id"] for s in old_seeds["seeds"]}
    ):
        raise ValueError("Chunked comparison seeds repeat or cross complete-run ownership")
    if not short:
        legacy = identified(q.root / cfg["legacy_import"]["path"])
        if (
            legacy["report_id"] != cfg["legacy_import"]["id"]
            or legacy["original_config_id"] != manifest_identifier(old)
            or legacy["replacement_protocol"] != "fresh_matched_pair_training_seed_1"
            or legacy["interrupted_prefix_admitted_for_training"] is not False
            or evaluation
            != [s for s in old_seeds["seeds"] if s["partition"] == "development"][16:32]
        ):
            raise ValueError(
                "Bind the chosen fresh pair and verified reserved starting evaluations"
            )
        check_sources(q.root, legacy["sources"])
        control = identified(q.root / cfg["control_report"]["path"])
        if (
            control["report_id"] != cfg["control_report"]["id"]
            or control["status"] != "chunked_native_control_pass"
            or control["implementation_sha256"] != cfg["implementation_sha256"]
        ):
            raise ValueError("The cached chunked collector/fit control must pass first")
        check_sources(q.root, control["sources"])
        control_cfg = json.loads((q.root / control["recipe_path"]).read_text())
        if (
            control["config_id"] != manifest_identifier(control_cfg)
            or control_cfg["stage"] != "short_bridge_control"
            or control_cfg["legacy_recipe"] != cfg["legacy_recipe"]
            or control["games_recorded"] != 8
        ):
            raise ValueError("Short control scope or shared legacy inputs differ")
        control_seeds = identified(q.root / control_cfg["seed_manifest"]["path"], "manifest_id")
        if {s["seed"] for s in seeds["seeds"]} & {s["seed"] for s in control_seeds["seeds"]}:
            raise ValueError("Comparison must not reuse its short control games")
    return cfg, parent, seeds


def tasks(cfg: dict[str, Any], seeds: dict[str, Any]) -> list[dict[str, Any]]:
    short = cfg["stage"] == "short_bridge_control"
    train = [s for s in seeds["seeds"] if s["partition"] == ("control" if short else "train")]
    evaluation = [
        s for s in seeds["seeds"] if s["partition"] == ("control_eval" if short else "development")
    ]
    result = []
    for mode in cfg["modes"]:
        prefix = "base" if mode == ORIGINAL else "cross"
        state = f"{prefix}-initial"
        result.append({"key": state, "kind": "initialize", "mode": mode, "round": 0})
        for index in range(1, cfg["rounds"] + 1):
            rows = train[(index - 1) * cfg["games_per_round"] : index * cfg["games_per_round"]]
            collected = []
            for start in range(0, len(rows), cfg["chunk_games"]):
                key = f"{prefix}-round-{index:03d}-collect-{start // cfg['chunk_games']:02d}"
                collected.append(key)
                result.append(
                    {
                        "key": key,
                        "kind": "collect",
                        "mode": mode,
                        "round": index,
                        "state": state,
                        "seeds": rows[start : start + cfg["chunk_games"]],
                        "training": True,
                    }
                )
            key = f"{prefix}-round-{index:03d}-fit"
            result.append(
                {
                    "key": key,
                    "kind": "fit",
                    "mode": mode,
                    "round": index,
                    "state": state,
                    "collections": collected,
                    "round_seed_ids": [r["id"] for r in rows],
                }
            )
            state = key
        for start in range(0, len(evaluation), cfg["chunk_games"]):
            result.append(
                {
                    "key": f"{prefix}-final-collect-{start // cfg['chunk_games']:02d}",
                    "kind": "collect",
                    "mode": mode,
                    "round": cfg["rounds"],
                    "state": state,
                    "seeds": evaluation[start : start + cfg["chunk_games"]],
                    "training": False,
                }
            )
    return result


def request_for(task: dict[str, Any], completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    request = dict(task)
    if "state" in task:
        request["before_state_id"] = completed[task["state"]]["result"]["state_id"]
    if task["kind"] == "fit":
        request["collection_ids"] = [completed[k]["report_id"] for k in task["collections"]]
    return request


def ordered_paths(paths: list[Path], seed_ids: list[int]) -> list[Path]:
    # Retain the historical two-lane order across separately collected chunks.
    order = {s: (i % 2, i // 2) for i, s in enumerate(seed_ids)}
    ids = [json.loads(p.read_text())["binding"]["seed_id"] for p in paths]
    if len(set(ids)) != len(ids) or set(ids) != set(seed_ids):
        raise ValueError("Chunked training paths repeat or cross the round seed plan")
    return sorted(paths, key=lambda p: order[json.loads(p.read_text())["binding"]["seed_id"]])


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
    inputs: dict[str, Any] = {}
    if task["kind"] == "collect":
        _require_native_launch_support()
        if _running_games() or not node.is_file():
            raise ValueError("Close the game before starting another native chunk")
        inputs = launch_inputs(q, parent)
    target = store.begin(task["key"], request)
    sources: dict[str, str] = {}
    if task["kind"] == "initialize":
        model = cached_model(
            initialize(
                parent["environment_manifest"]["id"],
                score.spec_id,
                cfg["training_seed"],
                task["mode"],
            )
        )
        optimizer = Adam.zero(model.parameter_count)
        if cfg["stage"] != "short_bridge_control":
            imported = identified(q.root / cfg["legacy_import"]["path"])
            if imported["reused_initial_panels"][task["mode"]]["model_id"] != model.model_id:
                raise ValueError("Reused starting evaluation belongs to another initializer")
        state = target / "state.json"
        save_state(state, model, optimizer)
        _, _, state_id = load_state(state)
        result = {
            "state_path": str(state.relative_to(q.root)),
            "state_id": state_id,
            "model_id": model.model_id,
            "optimizer_steps": 0,
            "games_recorded": 0,
        }
    else:
        before = completed[task["state"]]["result"]
        model, optimizer, state_id = load_state(q.root / before["state_path"])
        if state_id != request["before_state_id"] or model.mode != task["mode"]:
            raise ValueError("Chunked model/Adam predecessor differs")
        if task["kind"] == "fit":
            paths = [
                q.root / p for k in task["collections"] for p in completed[k]["result"]["paths"]
            ]
            paths = ordered_paths(paths, task["round_seed_ids"])
            samples, credit = prepare(
                paths,
                model,
                score,
                parent["learning"]["ppo"],
                parent["learning"]["credit_assignment"],
                task["round"],
            )
            fitted, opt, work = fit_round(
                cast(Any, model), optimizer, samples, parent["learning"]["ppo"], task["round"]
            )
            if not isinstance(fitted, CachedContextModel):
                raise ValueError("Chunked PPO lost its immutable ID cache")
            state = target / "state.json"
            save_state(state, fitted, opt)
            _, _, after_id = load_state(state)
            atomic_json(target / "credit.json", credit)
            atomic_json(target / "work.json", work)
            outcomes = [
                o
                for k in task["collections"]
                for o in completed[k]["result"]["summary"]["outcomes"]
            ]
            batch = summarize(
                [{**c, "decisions": range(c["decision_count"])} for c in outcomes],
                len(task["round_seed_ids"]),
            )
            result = {
                "state_path": str(state.relative_to(q.root)),
                "state_id": after_id,
                "model_id": fitted.model_id,
                "optimizer_steps": opt.steps,
                "new_optimizer_steps": work["optimizer_steps"],
                "games_recorded": 0,
                "training_summary": batch,
            }
            print(
                f"{task['mode']}, round {task['round']}: fitted; Adam restored/advanced "
                f"from {optimizer.steps} to {opt.steps} steps.",
                flush=True,
            )
            print(
                f"Whole round: wins {batch['wins']}/{batch['planned_games']}; "
                f"average floor {batch['mean_floor']:.2f}; best floor {batch['best_floor']}, "
                f"{batch['best_completed_acts']} acts; failures {batch['failed_games']}.",
                flush=True,
            )
        else:
            shared = Path.home() / "Library/Application Support/SlayTheSpire2"
            before_account = _shared_snapshot(shared)
            label = f"round-{task['round']:03d}" if task["training"] else "development-final"
            paths, summary, sources = collect_panel(
                q,
                cfg,
                parent,
                inputs,
                task["seeds"],
                node,
                target / "games",
                model,
                score,
                cfg["training_seed"],
                label,
                task["training"],
                deadline,
            )
            checks = immutable_checks(q, inputs)
            checks["account_profile_unchanged"] = _shared_snapshot(shared) == before_account
            if not all(checks.values()):
                raise ValueError("Shared native inputs/profile changed during a chunk")
            prior_failed = sum(
                c["result"].get("summary", {}).get("failed_games", 0)
                for k, c in completed.items()
                if k.startswith(task["key"].rsplit("-collect-", 1)[0] + "-collect-")
            )
            allowance = 0 if cfg["stage"] == "short_bridge_control" else 2
            if prior_failed + summary["failed_games"] > allowance:
                raise ValueError("Aggregate round/evaluation failed-game allowance exceeded")
            result = {
                "paths": [str(p.relative_to(q.root)) for p in paths],
                "summary": summary,
                "checks": checks,
                "games_recorded": len(paths),
                "state_id": state_id,
            }
    return store.commit(task["key"], request, result, sources)


def comparison(
    q: EngineQualificationConfig, cfg: dict[str, Any], completed: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Compare every planned evaluation seed, retaining failed games in the denominator."""
    imported = identified(q.root / cfg["legacy_import"]["path"])
    pairs: list[dict[str, Any]] = []
    for mode, prefix in ((ORIGINAL, "base"), (CROSSED, "cross")):
        old = next(
            a for a in imported["completed_arms"] if a["mode"] == mode and a["training_seed"] == 0
        )
        initial = next(p for p in old["panels"] if p["label"] == "development-initial")
        final = next(p for p in old["panels"] if p["label"] == "development-final")
        pairs.append(
            evaluation_change(
                mode, 0, initial["outcomes"], final["outcomes"], "preserved_legacy_pair"
            )
        )
        start = imported["reused_initial_panels"][mode]["summary"]["outcomes"]
        finish = [
            o
            for k, c in completed.items()
            if k.startswith(f"{prefix}-final-collect-")
            for o in c["result"]["summary"]["outcomes"]
        ]
        pairs.append(evaluation_change(mode, 1, start, finish, "fresh_matched_training_seeds"))
    effects = []
    for seed in (0, 1):
        a = next(p for p in pairs if p["mode"] == ORIGINAL and p["training_seed"] == seed)
        b = next(p for p in pairs if p["mode"] == CROSSED and p["training_seed"] == seed)
        effects.append(
            {
                "training_seed": seed,
                "cross_minus_original_floor_gain": b["mean_floor_change"] - a["mean_floor_change"],
                "cross_minus_original_win_gain": b["wins_change"] - a["wins_change"],
            }
        )
    return {
        "players": pairs,
        "paired_encoding_effects": effects,
        "independent_training_replicates_per_method": 2,
        "training_seeds_matched_within_each_replicate": True,
        "replicates_use_different_training_seed_sets": True,
        "extra_legacy_baseline_retained_as_diagnostic": True,
        "terminal_victory_primary": True,
        "evaluation_selection": "final_only",
        "stronger_play_not_automatically_established": True,
    }


def evaluation_change(
    mode: str,
    replicate: int,
    initial: list[dict[str, Any]],
    final: list[dict[str, Any]],
    origin: str,
) -> dict[str, Any]:
    a, b = {c["seed_id"]: c for c in initial}, {c["seed_id"]: c for c in final}
    if len(a) != 16 or len(b) != 16 or a.keys() != b.keys():
        raise ValueError("Final comparison must retain every planned paired evaluation seed")
    differences = [b[s]["maximum_floor"] - a[s]["maximum_floor"] for s in a]
    return {
        "mode": mode,
        "training_seed": replicate,
        "origin": origin,
        "planned_evaluation_games": 16,
        "initial_wins": sum(c["victory"] and c["status"] == "terminal" for c in initial),
        "final_wins": sum(c["victory"] and c["status"] == "terminal" for c in final),
        "wins_change": sum(c["victory"] and c["status"] == "terminal" for c in final)
        - sum(c["victory"] and c["status"] == "terminal" for c in initial),
        "initial_mean_floor": sum(c["maximum_floor"] for c in initial) / 16,
        "final_mean_floor": sum(c["maximum_floor"] for c in final) / 16,
        "mean_floor_change": sum(differences) / 16,
        "better_floor_seeds": sum(d > 0 for d in differences),
        "same_floor_seeds": sum(d == 0 for d in differences),
        "worse_floor_seeds": sum(d < 0 for d in differences),
        "final_failed_games": sum(c["status"] != "terminal" for c in final),
    }


def session(
    q: EngineQualificationConfig,
    path: Path,
    node: Path,
    *,
    maximum_steps: int | None = None,
    status_only: bool = False,
) -> dict[str, Any]:
    if maximum_steps is not None and maximum_steps <= 0:
        raise ValueError("Maximum steps must be positive")
    cfg, parent, seeds = load_resume(q, path)
    score = load_training_score_spec(q.root / parent["training_spec"]["path"])
    store = ChunkJournal(q.root, cfg)
    started = time.monotonic()
    deadline = started + cfg["session_limits"]["wall_seconds"] - 15
    completed: dict[str, dict[str, Any]] = {}
    executed = 0
    plan = tasks(cfg, seeds)
    if (
        status_only
        and (store.workspace / "config-at-launch.json").exists()
        and json.loads((store.workspace / "config-at-launch.json").read_text()) != cfg
    ):
        raise ValueError("Saved chunked comparison recipe changed")
    with nullcontext() if status_only else store.lock():
        final_path = store.workspace / "report.json"
        if final_path.exists():
            saved = identified(final_path)
            if saved["config_id"] != store.config_id:
                raise ValueError("Saved final comparison recipe changed")
            check_sources(q.root, saved["sources"])
            print(
                "Comparison already complete. Verified saved result; no new games or fitting.",
                flush=True,
            )
            return saved
        for task in plan:
            if "state" in task and task["state"] not in completed:
                break
            request = request_for(task, completed)
            cached = store.completed(task["key"], request)
            if cached is not None:
                completed[task["key"]] = cached
                continue
            allowance = (
                (120 if cfg["stage"] == "short_bridge_control" else 300)
                if task["kind"] == "collect"
                else (
                    (60 if cfg["stage"] == "short_bridge_control" else 180)
                    if task["kind"] == "fit"
                    else 5
                )
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
                f"Saved {len(completed)}/{len(plan)} chunks; "
                "completed work will be skipped on restart.",
                flush=True,
            )
        done = len(completed) == len(plan)
        sources = {str(path.relative_to(q.root)): _sha_file(path)}
        sources.update(
            {f"src/spireshift/{n}": sha for n, sha in cfg["implementation_sha256"].items()}
        )
        config_path = store.workspace / "config-at-launch.json"
        if config_path.exists():
            sources[str(config_path.relative_to(q.root))] = _sha_file(config_path)
        if cfg["stage"] != "short_bridge_control":
            legacy_path = q.root / cfg["legacy_import"]["path"]
            sources[str(legacy_path.relative_to(q.root))] = _sha_file(legacy_path)
            sources.update(identified(legacy_path)["sources"])
        for c in completed.values():
            sources.update(c["sources"])
        for task in plan[: len(completed)]:
            p = store.path(task["key"]) / "done.json"
            sources[str(p.relative_to(q.root))] = _sha_file(p)
        short = cfg["stage"] == "short_bridge_control"
        body = {
            "schema_version": "native-context-chunked-progress-v2",
            "recipe_path": str(path.relative_to(q.root)),
            "config_id": store.config_id,
            "status": ("chunked_native_control_pass" if short else "chunked_comparison_complete")
            if done
            else "paused_between_committed_chunks",
            "completed_chunks": len(completed),
            "planned_chunks": len(plan),
            "new_chunks_this_session": executed,
            "new_games_this_session": sum(
                c["result"].get("games_recorded", 0) for c in list(completed.values())[-executed:]
            )
            if executed
            else 0,
            "games_recorded": sum(c["result"].get("games_recorded", 0) for c in completed.values()),
            "sources": sources,
            "implementation_sha256": cfg["implementation_sha256"],
            "chunk_ids": [c["report_id"] for c in completed.values()],
            "game_apps_created": 0,
            "all_legal_decision_families_learnable": True,
            "normal_training_batch_unchanged": True,
            "wall_seconds": time.monotonic() - started,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "claim_scope": "versioned_cached_native_chunk_execution_not_learning_quality",
        }
        if done and not short:
            body["comparison"] = comparison(q, cfg, completed)
        if not short:
            body["preserved_original_denominator"] = {
                "planned": 640,
                "sealed": 520,
                "closed_audited": 496,
                "interrupted_prefix_excluded": 24,
                "unsealed_slots": 120,
                "unsealed_attempt_count_unknown": True,
            }
            body["fresh_pair_planned_games"] = 288
            body["saved_initial_evaluations_reused"] = 32
        report = {**body, "report_id": manifest_identifier(body)}
        if not status_only:
            # Session receipts are immutable too; a restart never overwrites progress.
            sessions = store.workspace / "sessions"
            number = len(list(sessions.glob("session-*.json"))) + 1
            atomic_json(sessions / f"session-{number:03d}.json", report)
            if done and not (store.workspace / "report.json").exists():
                atomic_json(store.workspace / "report.json", report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qualification", type=Path)
    parser.add_argument("config", type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--maximum-steps", type=int)
    args = parser.parse_args()
    q = load_engine_qualification_config(args.qualification)
    try:
        report = session(
            q,
            q.root / args.config,
            args.node,
            maximum_steps=args.maximum_steps,
            status_only=args.status,
        )
    except (ValueError, OSError, TimeoutError) as exc:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k
                not in {
                    "sources",
                    "implementation_sha256",
                    "chunk_ids",
                    "new_chunks_this_session",
                    "new_games_this_session",
                }
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
