"""Finite saved-record diagnosis and policy-preserving independent prediction fitting."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_consequence_sources import combine, partition
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_outcome_predictor import (
    OutcomePredictor,
    PlayerWithPredictions,
    fit_predictor,
)
from spireshift.native_rank_audit import aggregate, audit_case
from spireshift.native_separation_inputs import load
from spireshift.neural_combat import _numpy


def fit_plan(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan = []
    for player in (2, 3):
        worlds = sorted(d["source_seed_id"] for d in data if d["numerical_seed"] == player)
        if len(worlds) != (4 if player == 2 else 3) or len(set(worlds)) != len(worlds):
            raise ValueError("Keep all seven qualified TRAIN worlds, separately by parent")
        for held in [*worlds, None]:
            plan.append(
                {
                    "key": f"predictor-p{player}-w{held}"
                    if held is not None
                    else f"predictor-p{player}-final",
                    "stage": "prediction_fit",
                    "numerical_seed": player,
                    "held_world": held,
                }
            )
    return plan


def fit_unit(
    context: dict[str, Any], task: dict[str, Any], directory: Path, root: Path, deadline: float
) -> dict[str, Any]:
    np = _numpy()
    player = task["numerical_seed"]
    data = combine(
        [
            root / d["directory"]
            for d in context["report"]["data_units"]
            if d["numerical_seed"] == player
        ]
    )
    held = (
        data["owners"] == task["held_world"]
        if task["held_world"] is not None
        else np.zeros(len(data["owners"]), dtype=np.bool_)
    )
    predictor, optimizer, report = fit_predictor(
        context["models"][player, "original"],
        partition(data, ~held),
        partition(data, held),
        context["config"]["predictor_seed"],
        deadline,
        epochs=context["config"]["predictor_epochs"],
        allow_no_held=task["held_world"] is None,
    )
    state = {
        "schema_version": "native-separated-prediction-state-v1",
        "predictor": predictor.as_dict(),
        "optimizer": optimizer,
    }
    atomic_json(
        directory / "predictor-state.json", {**state, "state_id": manifest_identifier(state)}
    )
    body = {"schema_version": "native-separated-prediction-fit-v1", "task": task, **report}
    atomic_json(directory / "fit-report.json", {**body, "report_id": manifest_identifier(body)})
    return {
        "task": task,
        "report_path": str((directory / "fit-report.json").relative_to(root)),
        "state_path": str((directory / "predictor-state.json").relative_to(root)),
        "predictor_id": predictor.as_dict()["predictor_id"],
    }


def restore(root: Path, result: dict[str, Any], parent: Any) -> PlayerWithPredictions:
    state = identified(root / result["state_path"], "state_id")
    if state["schema_version"] != "native-separated-prediction-state-v1":
        raise ValueError("Do not load prediction checkpoints as policy checkpoints")
    p = OutcomePredictor.from_mapping(state["predictor"])
    optimizer = state["optimizer"]
    np = _numpy()
    if (
        p.as_dict()["predictor_id"] != result["predictor_id"]
        or optimizer.get("schema_version") != "native-independent-predictor-Adam-v1"
        or optimizer.get("steps") != 128
        or optimizer.get("scope") != "new_prediction_parameters_only_not_parent_PPO_Adam"
        or any(
            len(optimizer[k]) != p.parameter_count or not np.isfinite(optimizer[k]).all()
            for k in ("first", "second")
        )
        or np.any(np.asarray(optimizer["second"]) < 0)
    ):
        raise ValueError("Independent predictor or its own optimizer state changed")
    return PlayerWithPredictions(parent, p)


def run(root: Path, path: Path, *, max_cases: int | None = None) -> dict[str, Any]:
    started = time.monotonic()
    if max_cases is not None and (type(max_cases) is not int or max_cases < 1):
        raise ValueError("A saved-only check needs a positive case cap")
    context = load(root, path)
    cfg, r = context["config"], context["report"]
    deadline = started + cfg["session_limits"]["wall_seconds"] - 10
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        cached = identified(final)
        if cached["config_id"] != store.config_id:
            raise ValueError("Preserve an existing result under its exact recipe")
        check_sources(root, cached["sources"])
        return cached
    sources = dict(context["sources"])
    completed = {}
    new = 0
    new_cases = 0
    with store.lock():
        saved: dict[str, Any] | None
        for task in fit_plan(r["data_units"]):
            saved = store.completed(task["key"], task)
            if saved is None:
                if deadline - time.monotonic() < 45:
                    break
                directory = store.begin(task["key"], task)
                value = fit_unit(context, task, directory, root, deadline - 5)
                store.commit(task["key"], task, value)
                saved = store.completed(task["key"], task)
                new += 1
                print(
                    f"Saved independent predictor: player {task['numerical_seed']}, "
                    f"held world {task['held_world']}; policy updates 0.",
                    flush=True,
                )
            assert saved is not None
            if saved["result"]["task"] != task:
                raise ValueError("Saved predictor world or original owner changed")
            sources.update(saved["sources"])
            sources[str((store.path(task["key"]) / "done.json").relative_to(root))] = _sha_file(
                store.path(task["key"]) / "done.json"
            )
            completed[task["key"]] = saved["result"]
        fit_ready = len(completed) == 9
        players = (
            {
                p: restore(
                    root, completed[f"predictor-p{p}-final"], context["models"][p, "original"]
                )
                for p in (2, 3)
            }
            if fit_ready
            else {}
        )
        rank_cases = []
        for task in context["tasks"] if fit_ready else []:
            request = {
                "stage": "saved_menu_rankings",
                "source_task": task,
                "key": "rank-" + task["key"],
            }
            saved = store.completed(request["key"], request)
            if saved is None:
                if deadline - time.monotonic() < 45 or (
                    max_cases is not None and new_cases >= max_cases
                ):
                    break
                directory = store.begin(request["key"], request)
                value = audit_case(context, task, players, root, directory, deadline - 5)
                store.commit(request["key"], request, value)
                saved = store.completed(request["key"], request)
                new += 1
                new_cases += 1
            assert saved is not None
            value = saved["result"]
            if (
                value["source_key"] != task["key"]
                or value["numerical_seed"] != task["numerical_seed"]
                or value["source_variant"] != task["variant"]
            ):
                raise ValueError("Saved ranking belongs to another public case/player")
            rank_cases.append(value)
            sources.update(saved["sources"])
            sources[str((store.path(request["key"]) / "done.json").relative_to(root))] = _sha_file(
                store.path(request["key"]) / "done.json"
            )
            if len(rank_cases) % 16 == 0:
                print(
                    f"Saved menu rankings: {len(rank_cases)}/192 games; "
                    "original policy and PPO optimizer updates 0.",
                    flush=True,
                )
        check_sources(root, sources)
        done = fit_ready and len(rank_cases) == 192
        fits = [identified(root / c["report_path"]) for c in completed.values()]
        body = {
            "schema_version": "native-action-prediction-separation-v1",
            "config_id": store.config_id,
            "status": "native_prediction_separation_complete"
            if done
            else "paused_between_saved_units",
            "source_report_id": r["report_id"],
            "ranking": aggregate(rank_cases),
            "prediction_fits": completed,
            "prediction_validation": [
                {
                    "task": f["task"],
                    "final": f["curves"][-1],
                    "constant_baseline": f["constant_baseline"],
                }
                for f in fits
            ],
            "parents": r["parents"],
            "parent_full_states_and_PPO_Adam_unchanged": True,
            "PPO_Adam_updates": 0,
            "new_prediction_networks_have_their_own_Adam": True,
            "prediction_fitting_does_not_update_original_encoder_readout_or_direct_path": True,
            "fitted_prediction_did_not_change_action_scores_or_probabilities": all(
                c["fitted_prediction_policy_logs_exactly_unchanged"] for c in rank_cases
            )
            if rank_cases
            else None,
            "development_outcomes_or_menus_used_for_prediction_fitting": False,
            "training_source_worlds": 7,
            "game_apps_created": 0,
            "games_launched": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "full_run_objective": r["full_run_objective"],
            "training_spec_id": r["training_spec_id"],
            "ordinary_PPO_eligible": False,
            "sources": sources,
            "new_units_this_session": new,
            "session_wall_seconds": time.monotonic() - started,
        }
        result = {**body, "report_id": manifest_identifier(body)}
        index = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{index:03d}.json", result)
        if done:
            atomic_json(final, result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-cases", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe, max_cases=args.max_cases)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k not in {"sources", "prediction_validation", "prediction_fits", "parents"}
                },
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_saved_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
