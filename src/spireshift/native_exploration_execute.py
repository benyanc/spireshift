"""Execute one owned rest-exploration chunk with preserved model/Adam state."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_resume import ordered_paths
from spireshift.native_exploration_admission import inputs as launch_inputs
from spireshift.native_exploration_collector import collect_panel
from spireshift.native_exploration_math import fit_round
from spireshift.native_exploration_training import prepare_compact
from spireshift.native_optimizer_trial import arm_settings
from spireshift.training_objective import TrainingScoreSpec


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
    launched = {}
    if task["kind"] == "collect":
        if _running_games() or not node.is_file():
            raise ValueError("Close STS2 before collection")
        launched = launch_inputs(q, cfg, parent)
    target = store.begin(task["key"], req)
    sources: dict[str, str] = {}
    if task["kind"] == "restore":
        r = task["player"]
        model, optimizer, state_id = load_state(q.root / r["path"])
        if state_id != r["state_id"] or optimizer.steps != r["optimizer_steps"]:
            raise ValueError("Original full state changed")
        save_state(target / "state.json", model, optimizer)
        _, _, copied = load_state(target / "state.json")
        if copied != state_id:
            raise ValueError("Import changed weights or Adam moments")
        result = {
            "state_path": str((target / "state.json").relative_to(q.root)),
            "state_id": state_id,
            "model_id": model.model_id,
            "optimizer_steps": optimizer.steps,
            "new_optimizer_steps": 0,
            "games_recorded": 0,
        }
    else:
        before = completed[task["state"]]["result"]
        model, optimizer, state_id = load_state(q.root / before["state_path"])
        if state_id != req["before_state_id"] or optimizer.steps != before["optimizer_steps"]:
            raise ValueError("Continue exact predecessor state")
        settings = arm_settings(
            parent, {"name": "standard", "batch_games": cfg["batch_games"], "epoch_multiplier": 1}
        )
        if task["kind"] == "collect":
            shared = Path.home() / "Library/Application Support/SlayTheSpire2"
            snapshot = _shared_snapshot(shared)
            worker_parent = {**parent, "helpers_sha256": cfg["worker_helpers_sha256"]}
            paths, summary, sources = collect_panel(
                q,
                cfg,
                worker_parent,
                launched,
                task["seeds"],
                node,
                target / "games",
                model,
                score,
                task["numerical_seed"],
                task["panel"],
                task["training"],
                deadline,
                task["uniform_weight"],
            )
            checks = immutable_checks(q, launched)
            checks["account_profile_unchanged"] = _shared_snapshot(shared) == snapshot
            if not all(checks.values()):
                raise ValueError("Shared native inputs/account changed")
            previous = sum(
                r["result"].get("summary", {}).get("failed_games", 0)
                for r in completed.values()
                if r["result"].get("failure_group") == task["failure_group"]
            )
            if previous + summary["failed_games"] > (
                0 if cfg["stage"] == "short_bridge_control" else 2
            ):
                raise ValueError("Frozen group failure allowance exceeded")
            result = {
                "paths": [str(p.relative_to(q.root)) for p in paths],
                "summary": summary,
                "state_id": state_id,
                "model_id": model.model_id,
                "checks": checks,
                "failure_group": task["failure_group"],
                "games_recorded": len(paths),
            }
        elif task["kind"] == "fit":
            paths = ordered_paths(
                [q.root / p for k in task["collections"] for p in completed[k]["result"]["paths"]],
                task["round_seed_ids"],
            )
            samples, credit = prepare_compact(
                paths,
                model,
                score,
                settings,
                parent["learning"]["credit_assignment"],
                task["round"],
                task["arm"]["uniform_weight"],
            )
            after, ao, work = fit_round(
                cast(Any, model), optimizer, samples, settings, task["round"]
            )
            if time.monotonic() > deadline:
                raise TimeoutError("Fit reached its bounded chunk cap; preserve evidence")
            if not isinstance(after, CachedContextModel):
                raise ValueError("Fit lost model identity")
            save_state(target / "state.json", after, ao)
            _, _, after_id = load_state(target / "state.json")
            atomic_json(target / "credit.json", credit)
            atomic_json(target / "work.json", work)
            batch = [completed[k]["result"]["summary"] for k in task["collections"]]
            result = {
                "state_path": str((target / "state.json").relative_to(q.root)),
                "state_id": after_id,
                "model_id": after.model_id,
                "optimizer_steps": ao.steps,
                "new_optimizer_steps": work["optimizer_steps"],
                "games_recorded": 0,
                "source_games": len(paths),
                "clean_training_games": credit["clean_complete_training_games"],
                "rest_choices": {},
                "best_floor": max(b["best_floor"] for b in batch),
                "wins": sum(b["wins"] for b in batch),
            }
            for b in batch:
                for k, v in b["rest_choices"].items():
                    result["rest_choices"][k] = result["rest_choices"].get(k, 0) + v
            print(
                f"{task['arm']['name']}, player {task['numerical_seed']}, round {task['round']}: "
                f"Adam {optimizer.steps}→{ao.steps}; best floor {result['best_floor']}; "
                f"wins {result['wins']}/{len(paths)}; rest choices {result['rest_choices']}.",
                flush=True,
            )
            del samples
        else:
            raise ValueError("Unknown bounded exploration task")
    return store.commit(task["key"], req, result, sources)
