"""Finite supervised combat-consequence ablation and fresh full-game evaluation."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_behavior_game import branch
from spireshift.native_consequence_config import (
    evaluation_seeds,
    load_config,
    qualified_control,
)
from spireshift.native_consequence_data import CONTRACT, TARGETS
from spireshift.native_consequence_evaluation import duplicates, matched_draws, summarize, tasks
from spireshift.native_consequence_math import ARMS, fit, mathematical_controls
from spireshift.native_consequence_sources import combine, encode_world, partition, prepare
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal, load_state, save_state
from spireshift.native_context_reuse import check_sources
from spireshift.neural_combat import _numpy


def request(unit: dict[str, Any]) -> dict[str, Any]:
    return {**unit, "consequence_contract": CONTRACT, "scope": "supervised_fixed_world_not_PPO"}


def receipt(
    store: ChunkJournal, unit: dict[str, Any], sources: dict[str, str]
) -> dict[str, Any] | None:
    saved = store.completed(unit["key"], request(unit))
    if saved is None:
        return None
    value = saved["result"]
    if (
        value["stage"] != unit["stage"]
        or (
            unit["stage"] == "data"
            and (
                value["source_seed_id"] != unit["source_seed_id"]
                or value["numerical_seed"] != unit["numerical_seed"]
                or value["directory"] != str(store.path(unit["key"]).relative_to(store.root))
            )
        )
        or (unit["stage"] in {"fit", "game"} and value["numerical_seed"] != unit["numerical_seed"])
        or (
            unit["stage"] == "fit"
            and any(value[k] != unit[k] for k in ("arm", "head_seed", "held_world", "purpose"))
        )
        or (
            unit["stage"] == "game"
            and (value["variant"] != unit["variant"] or value["seed_id"] != unit["seed"]["id"])
        )
    ):
        raise ValueError("Saved consequence unit changed its owner, objective or model arm")
    sources.update(saved["sources"])
    sources[str((store.path(unit["key"]) / "done.json").relative_to(store.root))] = _sha_file(
        store.path(unit["key"]) / "done.json"
    )
    return dict(value)


def fit_units(data: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    control = cfg["stage"] == "short_control"
    units = []
    for player in (2, 3):
        worlds = [d["source_seed_id"] for d in data if d["numerical_seed"] == player]
        for held in worlds[:1] if control else worlds:
            for seed in cfg["cv_head_seeds"]:
                for arm in ARMS:
                    units.append(
                        {
                            "key": f"cv-p{player}-w{held}-h{seed}-{arm.replace('_', '-')}",
                            "stage": "fit",
                            "purpose": "cross_validation",
                            "numerical_seed": player,
                            "held_world": held,
                            "head_seed": seed,
                            "arm": arm,
                        }
                    )
        if control:
            for arm in ("return_only", "consequence"):
                units.append(
                    {
                        "key": f"final-p{player}-{arm.replace('_', '-')}",
                        "stage": "fit",
                        "purpose": "final_fork",
                        "numerical_seed": player,
                        "held_world": None,
                        "head_seed": cfg["deployment_head_seed"],
                        "arm": arm,
                    }
                )
    return units


def fit_unit(
    unit: dict[str, Any],
    arrays: dict[str, Any],
    model: CachedContextModel,
    adam: Any,
    directory: Path,
    root: Path,
    deadline: float,
) -> dict[str, Any]:
    np = _numpy()
    held_mask = (
        arrays["owners"] == unit["held_world"]
        if unit["held_world"] is not None
        else np.zeros(len(arrays["owners"]), dtype=np.bool_)
    )
    fitting, held = partition(arrays, ~held_mask), partition(arrays, held_mask)
    if len(set(fitting["owners"].tolist())) < 2 or (
        unit["held_world"] is not None and set(held["owners"].tolist()) != {unit["held_world"]}
    ):
        raise ValueError("Need at least two fitting worlds and the exact entire held source")
    after, optimizer, heads, result = fit(
        model,
        adam,
        fitting,
        held,
        unit["arm"],
        unit["head_seed"],
        deadline,
        allow_no_held=unit["purpose"] == "final_fork",
    )
    save_state(directory / "state.json", after, optimizer)
    with (directory / "heads-and-calibration.npz").open("xb") as stream:
        np.savez_compressed(stream, **heads)
    body = {
        "schema_version": "native-consequence-fit-v1",
        "unit": unit,
        **result,
        "loss_contract": CONTRACT,
        "full_run_score_or_environment_reward_changed": False,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(directory / "fit-report.json", report)
    return {
        "stage": "fit",
        "purpose": unit["purpose"],
        "numerical_seed": unit["numerical_seed"],
        "arm": unit["arm"],
        "head_seed": unit["head_seed"],
        "held_world": unit["held_world"],
        "report_path": str((directory / "fit-report.json").relative_to(root)),
        "report_id": report["report_id"],
        "state_path": str((directory / "state.json").relative_to(root)),
        "model_id": after.model_id,
        "initial_optimizer_steps": adam.steps,
        "optimizer_steps": optimizer.steps,
    }


def offline_summary(root: Path, completed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Report fixed final epochs; held outcomes never choose epochs, seeds or forks."""
    cells = []
    for v in completed.values():
        if v.get("stage") != "fit" or v["purpose"] != "cross_validation":
            continue
        report = identified(root / v["report_path"])
        if report["report_id"] != v["report_id"]:
            raise ValueError("Changed saved whole-world consequence validation")
        cells.append(
            {
                "numerical_seed": v["numerical_seed"],
                "held_world": v["held_world"],
                "arm": v["arm"],
                "head_seed": v["head_seed"],
                "final_step": report["curves"][-1],
                "constant": report["fitting_constant"],
                "persistence": report["current_state_persistence"],
            }
        )
    players = []
    for player in (2, 3):
        own = [v for v in cells if v["numerical_seed"] == player]
        arms = {}
        for arm in ARMS:
            rows = [v for v in own if v["arm"] == arm]
            heads = {}
            for target in TARGETS:
                valid = [v for v in rows if v["final_step"]["held"][target]["mse"] is not None]
                heads[target] = {
                    "mean_held_mse": sum(v["final_step"]["held"][target]["mse"] for v in valid)
                    / len(valid)
                    if valid
                    else None,
                    "mean_fitting_mse": sum(
                        v["final_step"]["fitting"][target]["mse"] for v in valid
                    )
                    / len(valid)
                    if valid
                    else None,
                    "mean_other_world_constant_mse": sum(
                        v["constant"][target]["mse"] for v in valid
                    )
                    / len(valid)
                    if valid
                    else None,
                    "mean_current_state_persistence_mse": sum(
                        v["persistence"][target]["mse"] for v in valid
                    )
                    / len(valid)
                    if valid
                    else None,
                    "held_source_worlds": len({v["held_world"] for v in valid}),
                    "head_initializers": len({v["head_seed"] for v in valid}),
                }
            arms[arm] = heads
        players.append({"numerical_seed": player, "arms": arms})
    return {
        "players": players,
        "completed_fits": len(cells),
        "fixed_final_epoch_not_selected_on_held_outcomes": True,
        "whole_source_world_is_independent_unit": True,
        "numerical_head_replicates_are_not_new_game_worlds": True,
        "seven_source_worlds_cannot_establish_broad_generalization": True,
        "tactical_prediction_does_not_establish_better_play": True,
    }


def run(
    root: Path,
    path: Path,
    *,
    node: Path | None = None,
    status_only: bool = False,
    offline_only: bool = False,
    max_units: int | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    cfg = load_config(root, path)
    if max_units is not None and max_units < 1:
        raise ValueError("A bounded session needs a positive unit allowance")
    session_wall = (
        min(cfg["session_limits"]["wall_seconds"], 240)
        if offline_only
        else cfg["session_limits"]["wall_seconds"]
    )
    deadline = started + session_wall - 10
    store = ChunkJournal(root, cfg)
    context, models, adams, score, sources = prepare(root, cfg, deadline)
    if any(
        cfg[k] != context["teacher_config"][k]
        for k in (
            "qualification",
            "qualification_id",
            "native_inputs",
            "node",
            "helpers_sha256",
            "maximum_decisions",
            "episode_wall_seconds",
        )
    ):
        raise ValueError("Preserve the qualified A8 native bridge and actual-engine inputs")
    seeds, seed_sources = evaluation_seeds(
        root, cfg, context["teacher_config"], models[2].actor.environment_id
    )
    sources.update(seed_sources)
    sources[str(path.relative_to(root))] = _sha_file(path)
    sources.update({f"src/spireshift/{n}": h for n, h in cfg["implementation_sha256"].items()})
    sources.update({f"scripts/{n}": h for n, h in cfg["entry_sha256"].items()})
    control = cfg["stage"] == "short_control"
    passed, inherited = (None, {}) if control else qualified_control(root, cfg)
    sources.update(inherited)
    if passed is not None and {
        (d["source_seed_id"], d["numerical_seed"]) for d in passed["data_units"]
    } != {(d["root"]["source_seed_id"], d["root"]["numerical_seed"]) for d in context["units"]}:
        raise ValueError("Qualified data must retain every usable source and its original parent")
    final = store.workspace / "report.json"
    if final.exists():
        report = identified(final)
        if report["config_id"] != store.config_id:
            raise ValueError("Preserve the existing result under its exact original recipe")
        check_sources(root, report["sources"])
        return report
    planned_games = tasks(seeds, control)
    if status_only:
        return {
            "status": "consequence_plan_only",
            "source_world_denominator": len(context["source_world_denominator"]),
            "usable_source_worlds": len(context["units"]),
            "planned_games": len(planned_games),
            "planned_CV_fits": 6 if control else 63,
            "games_launched": 0,
            "optimizer_steps": 0,
        }
    if passed is None:
        proofs = [
            {"numerical_seed": p, **mathematical_controls(models[p], adams[p])} for p in (2, 3)
        ]
        proof = {"passed": all(p["passed"] for p in proofs), "players": proofs}
    else:
        proof = passed["mathematical_controls"]
    completed: dict[str, dict[str, Any]] = {}
    data_units = list(passed["data_units"]) if passed is not None else []
    new = 0
    before_profile = None
    q = inputs = None
    game_models = {}
    with store.lock():
        for unit in context["units"] if control else []:
            compact = {
                "key": unit["key"],
                "stage": "data",
                "source_seed_id": unit["root"]["source_seed_id"],
                "numerical_seed": unit["root"]["numerical_seed"],
            }
            value = receipt(store, compact, sources)
            if value is None:
                if deadline - time.monotonic() < 45 or (max_units is not None and new >= max_units):
                    break
                directory = store.begin(compact["key"], request(compact))
                result = encode_world(
                    root,
                    context,
                    unit,
                    models[unit["root"]["numerical_seed"]],
                    score,
                    directory,
                    deadline - 5,
                )
                value = {**result, "stage": "data", "directory": str(directory.relative_to(root))}
                store.commit(compact["key"], request(compact), value)
                value = receipt(store, compact, sources)
                if value is None:
                    raise ValueError("The new consequence data commit is missing")
                new += 1
                print(
                    f"Saved combat data: world {value['source_seed_id']}, "
                    f"{value['plans']} plans / {value['combat_decisions']} decisions.",
                    flush=True,
                )
            completed[compact["key"]] = value
            data_units.append(value)
        data_ready = len(data_units) == len(context["units"])
        numeric_plan = fit_units(data_units, cfg) if data_ready else []
        data_by_player = {}
        for unit in numeric_plan:
            value = receipt(store, unit, sources)
            if value is None:
                if deadline - time.monotonic() < 45 or (max_units is not None and new >= max_units):
                    break
                player = unit["numerical_seed"]
                if player not in data_by_player:
                    data_by_player[player] = combine(
                        [root / d["directory"] for d in data_units if d["numerical_seed"] == player]
                    )
                directory = store.begin(unit["key"], request(unit))
                value = fit_unit(
                    unit,
                    data_by_player[player],
                    models[player],
                    adams[player],
                    directory,
                    root,
                    deadline - 5,
                )
                store.commit(unit["key"], request(unit), value)
                value = receipt(store, unit, sources)
                if value is None:
                    raise ValueError("The consequence fit commit is missing")
                new += 1
                print(
                    f"Saved learning check: player {player}, {unit['arm']}, "
                    f"held world {unit['held_world']}, head seed {unit['head_seed']}.",
                    flush=True,
                )
            completed[unit["key"]] = value
        numeric_ready = data_ready and all(u["key"] in completed for u in numeric_plan)
        final_forks = (
            [v for v in completed.values() if v.get("purpose") == "final_fork"]
            if control
            else passed["final_forks"]
            if passed
            else []
        )
        if numeric_ready and not offline_only:
            for task in planned_games:
                value = receipt(store, task, sources)
                if value is None:
                    if deadline - time.monotonic() < 135 or (
                        max_units is not None and new >= max_units
                    ):
                        break
                    if q is None:
                        if node != Path(cfg["node"]) or _running_games():
                            raise ValueError(
                                "Close STS2 before the finite native gameplay check; "
                                "saved learning units remain intact"
                            )
                        q = load_engine_qualification_config(root / cfg["qualification"])
                        inputs = _run_inputs(q, root / cfg["native_inputs"]["path"])
                        if (
                            q.config_id != cfg["qualification_id"]
                            or manifest_identifier(inputs["recipe"]) != cfg["native_inputs"]["id"]
                            or inputs["objective"] != score.evaluation_objective.as_dict()
                        ):
                            raise ValueError("Native evaluation objective or frozen inputs changed")
                        before_profile = _shared_snapshot(
                            Path.home() / "Library/Application Support/SlayTheSpire2"
                        )
                        for player in (2, 3):
                            game_models[player, "original"] = models[player]
                        for v in final_forks:
                            model, adam, _ = load_state(root / v["state_path"])
                            if (
                                model.model_id != v["model_id"]
                                or adam.steps != v["optimizer_steps"]
                            ):
                                raise ValueError(
                                    "A frozen supervised fork or its Adam state changed"
                                )
                            game_models[v["numerical_seed"], v["arm"]] = model
                    directory = store.begin(task["key"], request(task))
                    assert inputs is not None and node is not None
                    result = branch(
                        q,
                        cfg,
                        inputs,
                        directory,
                        node,
                        task,
                        game_models[task["numerical_seed"], task["variant"]],
                        score,
                        deadline,
                    )
                    value = {**result, "stage": "game", "variant": task["variant"]}
                    store.commit(task["key"], request(task), value)
                    value = receipt(store, task, sources)
                    if value is None:
                        raise ValueError("The consequence game commit is missing")
                    new += 1
                completed[task["key"]] = value
                recorded = sum(v["stage"] == "game" for v in completed.values())
                if recorded % 8 == 0 or task is planned_games[-1]:
                    terminal = [
                        v
                        for v in completed.values()
                        if v.get("stage") == "game" and v["status"] == "terminal"
                    ]
                    best = max((v["maximum_floor"] for v in terminal), default=0)
                    print(
                        f"Fresh-game check: {recorded}/{len(planned_games)} recorded; "
                        f"best floor {best}; wins {sum(v['victory'] for v in terminal)}.",
                        flush=True,
                    )
                if sum(
                    v.get("stage") == "game" and v["status"] != "terminal"
                    for v in completed.values()
                ) > (0 if control else 2):
                    break
        games = [v for v in completed.values() if v.get("stage") == "game"]
        done = numeric_ready and len(games) == len(planned_games)
        checks = dict(context["report"]["checks"])
        if q is not None and inputs is not None:
            checks = immutable_checks(q, inputs)
            checks["account_profile_unchanged"] = before_profile == _shared_snapshot(
                Path.home() / "Library/Application Support/SlayTheSpire2"
            )
        if not all(checks.values()):
            raise ValueError("A native shared input or account profile changed")
        check_sources(root, sources)
        failure_count = sum(v["status"] != "terminal" for v in games)
        stopped = failure_count > (0 if control else 2)
        body = {
            "schema_version": "native-combat-consequence-study-v1",
            "recipe_path": str(path.relative_to(root)),
            "config_id": store.config_id,
            "status": (
                "native_consequence_control_complete"
                if control
                else "native_consequence_comparison_complete"
            )
            if done
            else "stopped_failed_game_allowance"
            if stopped
            else "offline_units_complete"
            if numeric_ready and offline_only
            else "paused_between_sealed_units",
            "data_units": data_units,
            "final_forks": final_forks,
            "mathematical_controls": proof,
            "offline_validation": offline_summary(root, completed),
            "source_world_denominator": context["source_world_denominator"],
            "parents": context["players"],
            "original_full_states_unchanged": True,
            "summary": summarize(seeds, completed, control),
            "noncombat_matching": matched_draws(root, completed),
            "duplicate_traces_match": duplicates(planned_games, completed),
            "completed_games": len(games),
            "failed_games": failure_count,
            "completed_units": len(completed),
            "new_units_this_session": new,
            "checks": checks,
            "sources": sources,
            "game_apps_created": 0,
            "production_optimizer_steps": 0,
            "ordinary_PPO_eligible": False,
            "training_kind": "supervised_recorded_return_and_auxiliary_consequence_not_PPO",
            "shared_actor_changes_all_current_legal_action_families_remain_available": True,
            "noncombat_rule_and_uniform_draws_matched_not_noncombat_weights": True,
            "parent_PPO_Adam_moments_copied_without_reset": True,
            "deployment_head_seed_fixed_before_any_held_or_gameplay_outcomes": cfg[
                "deployment_head_seed"
            ],
            "information_scope_training": cfg["information_scope"],
            "information_scope_gameplay": (
                "current_public_inputs_only_no_search_or_privileged_state"
            ),
            "full_run_objective": score.evaluation_objective.as_dict(),
            "training_spec_id": score.spec_id,
            "full_run_score_or_environment_reward_changed": False,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
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
    parser.add_argument("--node", type=Path)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--offline-only", action="store_true")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(
            root,
            root / args.recipe,
            node=args.node,
            status_only=args.status,
            offline_only=args.offline_only,
            max_units=args.max_units,
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k
                    not in {
                        "sources",
                        "data_units",
                        "offline_validation",
                        "parents",
                        "source_world_denominator",
                    }
                },
                indent=2,
            )
        )
        return int(result.get("failed_games", 0) > 0)
    except (ValueError, KeyError, OSError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
