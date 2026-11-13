"""One isolated public-policy game, delivery/inference audit and compact RNG receipt."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, save_native_episode, score_episode
from spireshift.engine_learning import identified
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file
from spireshift.engine_selection_audit import audit_selection_worker
from spireshift.engine_selection_worker import SCRIPT, SelectionWorker
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_behavior_policy import CONTRACT, RNG, Chooser, reconstruct
from spireshift.native_combat_teacher_data import trace_id
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.training_objective import TrainingScoreSpec


def binding(
    cfg: dict[str, Any], task: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> dict[str, Any]:
    return {
        "environment_id": model.actor.environment_id,
        "config_id": manifest_identifier(cfg),
        "seed_manifest_id": cfg["seed_manifest"]["id"],
        "seed_id": task["seed"]["id"],
        "native_seed": task["seed"]["seed"],
        "partition": "control" if cfg["stage"] == "short_control" else "development",
        "panel_purpose": "fresh_game_combat_behavior_evaluation_not_PPO",
        "model_id": model.model_id,
        "training_spec_id": score.spec_id,
        "policy_contract": CONTRACT,
        "rng_contract": RNG,
        "task": task,
        "information_scope": "current_public_state_only_no_search",
    }


def branch(
    q: EngineQualificationConfig,
    cfg: dict[str, Any],
    inputs: dict[str, Any],
    target: Path,
    node: Path,
    task: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    deadline: float,
) -> dict[str, Any]:
    chooser = Chooser(model, score, task["seed"]["seed"], task["arm"])
    worker = SelectionWorker(
        q, inputs, target / "worker", node, cfg["helpers_sha256"], script=SCRIPT
    )
    try:
        atomic_json(worker.workspace / "selection-verifier.json", {"node": str(node)})
        case = worker.episode(
            task["seed"]["seed"],
            maximum_decisions=cfg["maximum_decisions"],
            wall_seconds=min(cfg["episode_wall_seconds"], deadline - time.monotonic() - 15),
            cpu_seconds=score.evaluation_objective.whole_run_budget,
            chooser=chooser,
        )
        case.update(
            worker_workspace="worker",
            policy_contract=CONTRACT,
            ordinary_PPO_eligible=False,
            privileged_fixed_world_teacher=False,
            student_inputs_public_only=True,
            comparison_experiment=True,
        )
        scored = score_episode(case, task["seed"]["id"], score)
        if not scored["completed"]:
            case.update(
                status="failed", error=case.get("error") or "Outside declared whole-run budget"
            )
        if case["seed"] != task["seed"]["seed"]:
            raise ValueError("Native seed differs from the frozen canonical game seed")
        path = target / "episode.json"
        bound = binding(cfg, task, model, score)
        save_native_episode(path, case, bound)
        if case["status"] == "terminal":
            worker.close()
        else:
            worker.retire(case.get("error") or "Combat behavior game failed")
        digest = trace_id(case)
        outcome = {
            k: case[k]
            for k in ("status", "victory", "maximum_floor", "completed_acts", "cpu_seconds")
        }
        error = case.get("error")
        del case
        native = audit_selection_worker(worker.workspace, [path], deadline=deadline)
        atomic_json(target / "native-audit.json", native)
        case = read_native_episode(path, bound)
        checked = reconstruct(case, model, score, task["seed"]["seed"], task["arm"])
        if trace_id(case) != digest or not native["valid"]:
            raise ValueError("Saved public policy trace or native delivery failed verification")
        rng_body = {"schema_version": "native-combat-behavior-rng-receipt-v1", **checked}
        rng_receipt = {**rng_body, "report_id": manifest_identifier(rng_body)}
        atomic_json(target / "rng-receipt.json", rng_receipt)
        return {
            **outcome,
            "error": error,
            "numerical_seed": task["numerical_seed"],
            "arm": task["arm"],
            "seed_id": task["seed"]["id"],
            "duplicate_of": task["duplicate_of"],
            "trace_id": digest,
            "episode_path": str(path.relative_to(q.root)),
            "rng_receipt_path": str((target / "rng-receipt.json").relative_to(q.root)),
            "rng_receipt_id": rng_receipt["report_id"],
            "counts": checked["counts"],
            "nested_combat_selections": checked["nested_combat_selections"],
            "decisions_reconstructed": checked["decisions_reconstructed"],
            "native_audit_valid": True,
            "inference_audit_valid": True,
            "training_return": scored["training_return"] if scored["completed"] else None,
        }
    finally:
        worker.stop()


def matched_noncombat(root: Path, completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cells = {
        (v["numerical_seed"], v["seed_id"], v["arm"]): v
        for v in completed.values()
        if not v["duplicate_of"] and v["status"] == "terminal"
    }
    shared = same_input = pairs = 0
    for player, seed, arm in cells:
        if arm != "sampled" or (player, seed, "greedy") not in cells:
            continue
        maps = []
        for name in ("sampled", "greedy"):
            value = cells[player, seed, name]
            saved = identified(root / value["rng_receipt_path"])
            if saved["report_id"] != value["rng_receipt_id"]:
                raise ValueError("Saved noncombat randomness receipt differs")
            rows = {r["draw_key"]: r for r in saved["noncombat"]}
            if len(rows) != len(saved["noncombat"]):
                raise ValueError("A noncombat sampling slot was reused")
            maps.append(rows)
        pairs += 1
        for key in maps[0].keys() & maps[1].keys():
            a, b = maps[0][key], maps[1][key]
            if a["draw"] != b["draw"]:
                raise ValueError("Combat action counts shifted a matched noncombat draw")
            shared += 1
            if a["effective_input_id"] == b["effective_input_id"]:
                if a != b:
                    raise ValueError("Identical noncombat observations produced different choices")
                same_input += 1
    return {
        "valid": True,
        "complete_player_seed_pairs": pairs,
        "shared_noncombat_draw_keys": shared,
        "identical_public_inputs_with_identical_choices": same_input,
        "different_public_states_may_legitimately_choose_different_actions": True,
    }


def audit(root: Path, path: Path, deadline: float) -> dict[str, Any]:
    from spireshift.native_combat_behavior import receipt
    from spireshift.native_combat_behavior_config import load
    from spireshift.native_combat_behavior_data import summarize, tasks

    cfg, seeds, models, score, sources = load(root, path)
    store = ChunkJournal(root, cfg)
    report = identified(store.workspace / "report.json")
    if (
        report["config_id"] != store.config_id
        or report["status"] != "native_combat_behavior_complete"
    ):
        raise ValueError("Saved behavior audit needs a complete matching comparison")
    check_sources(root, report["sources"])
    completed: dict[str, dict[str, Any]] = {}
    decisions = 0
    for task in tasks(seeds, cfg["stage"] == "short_control"):
        if time.monotonic() >= deadline:
            raise TimeoutError("Saved combat behavior audit reached its finite cap")
        value = receipt(store, task, sources)
        if value is None or value["status"] != "terminal":
            raise ValueError("Saved inference qualification requires every clean native ending")
        model = models[task["numerical_seed"]]
        case = read_native_episode(root / value["episode_path"], binding(cfg, task, model, score))
        rebuilt = reconstruct(case, model, score, task["seed"]["seed"], task["arm"])
        saved = identified(root / value["rng_receipt_path"])
        if (
            rebuilt != {k: saved[k] for k in rebuilt}
            or saved["report_id"] != value["rng_receipt_id"]
            or trace_id(case) != value["trace_id"]
            or any(
                case[k] != value[k]
                for k in ("status", "victory", "maximum_floor", "completed_acts", "cpu_seconds")
            )
            or score_episode(case, task["seed"]["id"], score)["training_return"]
            != value["training_return"]
        ):
            raise ValueError("Saved choice, RNG, cost, ending or return no longer reconstructs")
        decisions += len(case["decisions"])
        del case
        if (
            task["duplicate_of"]
            and value["trace_id"] != completed[task["duplicate_of"]]["trace_id"]
        ):
            raise ValueError("Repeated behavior trace changed")
        completed[task["key"]] = value
    if (
        summarize(seeds, completed, control=cfg["stage"] == "short_control") != report["summary"]
        or matched_noncombat(root, completed) != report["noncombat_matching"]
    ):
        raise ValueError("Saved paired tables or matched noncombat behavior changed")
    check_sources(root, sources)
    body = {
        "schema_version": "native-combat-behavior-audit-v1",
        "source_report_id": report["report_id"],
        "auditor_sha256": _sha_file(Path(__file__)),
        "episodes_reconstructed": len(completed),
        "public_decisions_reconstructed": decisions,
        "all_choices_reconstructed": True,
        "matched_noncombat_and_tables_reconstructed": True,
        "native_journal_bytes_verified": True,
        "native_delivery_semantically_reaudited": False,
        "full_states_unchanged": True,
        "new_games": 0,
        "optimizer_steps": 0,
    }
    return {**body, "report_id": manifest_identifier(body)}
