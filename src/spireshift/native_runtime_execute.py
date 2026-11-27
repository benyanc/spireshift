"""Unchanged PPO kernel under the explicitly qualified native host repair."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from spireshift.engine_learning import summarize
from spireshift.engine_native import (
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam, fit_round
from spireshift.native_action_context import CROSSED, initialize
from spireshift.native_context_cache import CachedContextModel, cached_model
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_resume import ordered_paths
from spireshift.native_optimizer_trial import arm_settings
from spireshift.native_runtime_admission import launch_inputs
from spireshift.native_shop_collector import collect_panel
from spireshift.native_shop_training import prepare_compact
from spireshift.training_objective import TrainingScoreSpec


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
        inputs = launch_inputs(q, cfg, parent)
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
                raise ValueError("Aggregate shop stage/evaluation failure allowance exceeded")
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
