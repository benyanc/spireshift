"""Repaired natural native experience; one raw episode per worker and exact replay."""

from __future__ import annotations

import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_relic_worker import SCRIPT, RelicWorker
from spireshift.engine_selection_audit import audit_selection_worker
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_inventory_credit_features import inventory
from spireshift.native_relic_observation import verify
from spireshift.native_structured_policy import CONTRACT, Chooser, reconstruct
from spireshift.training_objective import TrainingScoreSpec


def game(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    seed: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    training: bool,
    deadline: float,
) -> dict[str, Any]:
    worker = RelicWorker(
        q, inputs, target / "worker", Path(cfg["node"]), cfg["helpers_sha256"], script=SCRIPT
    )
    try:
        atomic_json(worker.workspace / "selection-verifier.json", {"node": cfg["node"]})
        case = worker.episode(
            seed["seed"],
            maximum_decisions=cfg["maximum_decisions"],
            wall_seconds=min(
                45 if cfg["stage"] == "short_control" else cfg["episode_wall_seconds"],
                deadline - time.monotonic() - 15,
            ),
            cpu_seconds=score.evaluation_objective.whole_run_budget,
            chooser=Chooser(model, score, seed["seed"], training),
        )
        case.update(
            worker_workspace="worker",
            policy_contract=CONTRACT,
            privileged_fixed_world_teacher=False,
            student_inputs_public_only=True,
        )
        scored = score_episode(case, seed["id"], score)
        if not scored["completed"]:
            case.update(
                status="failed", error=case.get("error") or "Outside declared full-run budget"
            )
        case["ordinary_PPO_eligible"] = training and case["status"] == "terminal"
        if case["seed"] != seed["seed"]:
            raise ValueError("Native game seed differs from its planned canonical seed")
        bound = {
            "environment_id": model.actor.environment_id,
            "config_id": manifest_identifier(cfg),
            "seed_manifest_id": cfg["seed_manifest"]["id"],
            "seed_id": seed["id"],
            "native_seed": seed["seed"],
            "partition": seed["partition"],
            "panel_purpose": "training" if training else "frozen_policy_evaluation",
            "model_id": model.model_id,
            "training_spec_id": score.spec_id,
            "policy_contract": CONTRACT,
        }
        path = target / "episode.json"
        save_native_episode(path, case, bound)
        outcome = {
            k: case[k]
            for k in ("status", "victory", "maximum_floor", "completed_acts", "cpu_seconds")
        }
        error, decisions = case.get("error"), len(case["decisions"])
        del case
        if outcome["status"] == "terminal":
            worker.close()
        else:
            worker.retire(error or "Structured-comparison game failed; no seed retry")
        audit = audit_selection_worker(worker.workspace, [path], deadline=deadline)
        if not audit["valid"]:
            raise ValueError("Native delivery is not verified")
        atomic_json(target / "native-audit.json", audit)
        saved = read_native_episode(path, bound)
        _, normalized = reconstruct(
            saved, model, score, seed["seed"], training, scored["training_return"]
        )
        families = Counter(r["public_input"]["context"]["interaction"]["kind"] for r in normalized)
        counter_check = (
            verify(worker.workspace, deadline) if outcome["status"] == "terminal" else None
        )
        coverage = [inventory(row["public_input"]) for row in normalized]
        cards = sorted({d for c in coverage for d in c["deck_definitions"]})
        relics = sorted({d for c in coverage for d in c["relic_definitions"]})
        return {
            **outcome,
            "error": error,
            "seed_id": seed["id"],
            "model_id": model.model_id,
            "decisions": decisions,
            "episode_path": str(path.relative_to(q.root)),
            "training_return": scored["training_return"] if scored["completed"] else 0.0,
            "decision_families": dict(families),
            "owned_card_definitions": cards,
            "owned_relic_definitions": relics,
            "combat_counter_check": counter_check,
            "native_delivery_audit_valid": True,
            "all_behavior_probabilities_reconstructed": True,
            "ordinary_PPO_eligible": training and outcome["status"] == "terminal",
        }
    finally:
        worker.stop()


def batch(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    seeds: list[dict[str, Any]],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    training: bool,
    deadline: float,
) -> dict[str, Any]:
    def one(seed: dict[str, Any]) -> dict[str, Any]:
        return game(
            q, cfg, inputs, target / f"game-{seed['id']}", seed, model, score, training, deadline
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(one, seeds))
    clean = [r for r in outcomes if r["status"] == "terminal"]
    result = {
        "outcomes": outcomes,
        "games_recorded": len(outcomes),
        "failed_games": len(outcomes) - len(clean),
        "wins": sum(r["victory"] for r in clean),
        "mean_floor": sum(r["maximum_floor"] if r["status"] == "terminal" else 0 for r in outcomes)
        / len(seeds),
        "best_floor": max((r["maximum_floor"] for r in clean), default=0),
        "best_completed_acts": max((r["completed_acts"] for r in clean), default=0),
        "paths": [r["episode_path"] for r in outcomes],
    }
    atomic_json(target / "batch.json", result)
    print(
        f"Batch: {len(outcomes)}/{len(seeds)} games; wins {result['wins']}; "
        f"average floor {result['mean_floor']:.2f}; best floor {result['best_floor']}, "
        f"{result['best_completed_acts']} acts; failures {result['failed_games']}.",
        flush=True,
    )
    return result
