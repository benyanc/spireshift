"""Fixed matched cloning work, then withheld fights and genuinely fresh whole games."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker_qualification import immutable_checks
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_combat_behavior_data import intervals
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_experience_game import game
from spireshift.native_natural_branch import branch
from spireshift.native_natural_data import ARMS, CONTRACT, admit
from spireshift.native_natural_inputs import snapshot
from spireshift.native_natural_learning import epoch, lessons
from spireshift.native_structured_state import load, save


def schedule(cfg: dict[str, Any], roots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = [{"key": f"initial-p{p}", "kind": "import", "player": p} for p in (2, 3)]
    states = {(p, a): f"initial-p{p}" for p in (2, 3) for a in ARMS}
    for index in range(1, cfg["learning"]["epochs"] + 1):
        for p in (2, 3):
            for arm in ARMS:
                key = f"fit-p{p}-{arm.replace('_', '-')}-e{index:02d}"
                tasks.append(
                    {
                        "key": key,
                        "kind": "fit",
                        "player": p,
                        "arm": arm,
                        "epoch": index,
                        "state": states[p, arm],
                    }
                )
                states[p, arm] = key
    # All four final states precede every evaluation, including withheld-fight checks.
    variants = ("initial", *ARMS)
    for i, r in enumerate(x for x in roots if x["partition"] == "heldout"):
        for p in (2, 3):
            for arm in variants:
                tasks.append(
                    {
                        "key": f"held-{i:02d}-p{p}-{arm.replace('_', '-')}",
                        "kind": "held",
                        "player": p,
                        "arm": arm,
                        "root_id": r["root_id"],
                        "state": f"initial-p{p}" if arm == "initial" else states[p, arm],
                    }
                )
    for i, seed in enumerate(cfg["evaluation_seeds"]):
        for p in (2, 3):
            offset = (i + p) % len(variants)
            for arm in variants[offset:] + variants[:offset]:
                tasks.append(
                    {
                        "key": f"fresh-{seed['id']}-p{p}-{arm.replace('_', '-')}",
                        "kind": "fresh",
                        "player": p,
                        "arm": arm,
                        "seed": seed,
                        "state": f"initial-p{p}" if arm == "initial" else states[p, arm],
                    }
                )
    return tasks


def summary(cfg: dict[str, Any], done: dict[str, Any]) -> dict[str, Any]:
    cells = {
        (r["player"], r["arm"], r["seed_id"]): r for r in done.values() if r["kind"] == "fresh"
    }
    columns = ("victory", "completed_acts", "maximum_floor", "training_return")
    arms, comparisons = {}, {}
    for arm in ("initial", *ARMS):
        observed = [r for r in cells.values() if r["arm"] == arm]
        arms[arm] = {
            "denominator": len(cfg["evaluation_seeds"]) * 2,
            "recorded": len(observed),
            "failed_games": sum(r["status"] != "terminal" for r in observed),
            "wins": sum(r["victory"] for r in observed if r["status"] == "terminal"),
            "mean_floor": sum(r["maximum_floor"] for r in observed if r["status"] == "terminal")
            / (len(cfg["evaluation_seeds"]) * 2),
        }
    if len(cells) == len(cfg["evaluation_seeds"]) * 6:
        for a, b in ((ARMS[1], ARMS[0]), (ARMS[1], "initial"), (ARMS[0], "initial")):
            differences = []
            for seed in cfg["evaluation_seeds"]:
                differences.append(
                    [
                        sum(
                            (
                                float(cells[p, a, seed["id"]][k])
                                if cells[p, a, seed["id"]]["status"] == "terminal"
                                else 0
                            )
                            - (
                                float(cells[p, b, seed["id"]][k])
                                if cells[p, b, seed["id"]]["status"] == "terminal"
                                else 0
                            )
                            for p in (2, 3)
                        )
                        / 2
                        for k in columns
                    ]
                )
            ci = intervals(differences) if cfg["stage"] != "short_control" else [None] * 4
            comparisons[f"{a}_minus_{b}"] = {
                k: {"mean": sum(x[j] for x in differences) / len(differences), "interval95": ci[j]}
                for j, k in enumerate(columns)
            }
    return {
        "arms": arms,
        "paired": comparisons,
        "terminal_victory_primary": True,
        "interval_unit": "whole_world_cluster_jointly_across_two_fixed_parents",
        "primary_comparison": "teacher_clone_minus_reference_clone",
        "unchanged_original_comparisons_required": True,
    }


def run(
    root: Path,
    context: dict[str, Any],
    native: Any,
    *,
    max_units: int | None = None,
    launch_deadline: float | None = None,
) -> dict[str, Any]:
    cfg = context["config"]
    teacher_path = root / cfg["workspace"] / "teacher/report.json"
    teacher = identified(teacher_path)
    check_sources(root, teacher["sources"])
    if (
        teacher["status"] != "natural_teacher_complete"
        or teacher["config_id"]
        != manifest_identifier({**cfg, "workspace": cfg["workspace"] + "/teacher"})
        or teacher["gate"] != admit(context["roots"], teacher["summaries"])
        or cfg["stage"] != "short_control"
        and not teacher["gate"]["passed"]
    ):
        raise ValueError(
            "Complete the declared TRAIN-only teacher quality gate before curriculum fitting"
        )
    examples = lessons(root, context, teacher)
    store = ChunkJournal(root, {**cfg, "workspace": cfg["workspace"] + "/curriculum"})
    final = store.workspace / "report.json"
    if final.exists():
        cached = identified(final)
        check_sources(root, cached["sources"])
        return cached
    sources = {
        **context["sources"],
        **teacher["sources"],
        str(teacher_path.relative_to(root)): _sha_file(teacher_path),
    }
    started = time.monotonic()
    deadline = launch_deadline or started + cfg["session_limits"]["wall_seconds"] - 15
    tasks, new = schedule(cfg, context["roots"]), 0
    done: dict[str, Any] = {}
    q, inputs = native
    by_id = {r["root_id"]: r for r in context["roots"]}
    with store.lock():
        sources.update(snapshot(root, cfg, store.workspace))
        for task in tasks:
            request = {"contract": CONTRACT, "task": task, "teacher_id": teacher["report_id"]}
            if "state" in task:
                request["predecessor_state_id"] = done[task["state"]]["state_id"]
            receipt = store.completed(task["key"], request)
            if receipt is None:
                if deadline - time.monotonic() < 90 or max_units is not None and new >= max_units:
                    break
                if task["kind"] in {"held", "fresh"} and _running_games():
                    raise ValueError("Close STS2 before another isolated curriculum evaluation")
                target = store.begin(task["key"], request)
                p = task["player"]
                if task["kind"] == "import":
                    model = context["models"][p]
                    adam = Adam.from_mapping(context["adams"][p].as_dict(), model.parameter_count)
                else:
                    parent = done[task["state"]]
                    model, adam, sid = load(root / parent["state_path"])
                    if sid != parent["state_id"] or adam.steps != parent["optimizer_steps"]:
                        raise ValueError(
                            "Restore exact inherited numerical weights and all Adam state"
                        )
                result = {"kind": task["kind"], "player": p, "arm": task.get("arm", "initial")}
                if task["kind"] in {"fit", "import"}:
                    if task["kind"] == "fit":
                        model, adam, work = epoch(
                            model,
                            adam,
                            examples[task["arm"]],
                            context["score"],
                            cfg["learning"],
                            task["epoch"],
                            p,
                            target,
                        )
                        result.update(work=work, epoch=task["epoch"])
                    saved = save(target / "state.json", model, adam)
                    result.update(
                        state_path=str((target / "state.json").relative_to(root)),
                        state_id=saved["state_id"],
                        model_id=model.model_id,
                        optimizer_steps=adam.steps,
                    )
                else:
                    account = Path.home() / "Library/Application Support/SlayTheSpire2"
                    before = _shared_snapshot(account)
                    if task["kind"] == "held":
                        value = branch(
                            q,
                            inputs,
                            cfg,
                            by_id[task["root_id"]],
                            {},
                            model,
                            context["score"],
                            target,
                            deadline,
                        )
                        result.update(
                            outcome=value["outcome"],
                            status=value["status"],
                            root_id=task["root_id"],
                            fight_id=value["fight_id"],
                        )
                    else:
                        result.update(
                            game(
                                q,
                                cfg,
                                inputs,
                                target,
                                task["seed"],
                                model,
                                context["score"],
                                False,
                                deadline,
                            )
                        )
                    checks = immutable_checks(q, inputs)
                    checks["account_profile_unchanged"] = _shared_snapshot(account) == before
                    if not all(checks.values()):
                        raise ValueError(
                            "Curriculum evaluation changed a frozen input or real profile"
                        )
                    result["checks"] = checks
                store.commit(task["key"], request, result)
                receipt = store.completed(task["key"], request)
                assert receipt is not None
                new += 1
                print(f"Natural curriculum: {task['key']} sealed.", flush=True)
            done[task["key"]] = receipt["result"]
            sources.update(receipt["sources"])
            sources[str((store.path(task["key"]) / "done.json").relative_to(root))] = _sha_file(
                store.path(task["key"]) / "done.json"
            )
        complete = len(done) == len(tasks)
        check_sources(root, sources)
        checks = {
            "evaluations_clean": complete
            and all(
                r["status"] in {"terminal", "complete"}
                for r in done.values()
                if r["kind"] in {"fresh", "held"}
            )
        }
        for p in (2, 3):
            for arm in ARMS:
                fitted = [
                    r
                    for r in done.values()
                    if r["kind"] == "fit" and r["player"] == p and r["arm"] == arm
                ]
                checks[f"p{p}_{arm}_fixed_work"] = sum(
                    r["work"]["new_optimizer_steps"] for r in fitted
                ) == (cfg["learning"]["epochs"] * cfg["learning"]["steps_per_epoch"])
                checks[f"p{p}_{arm}_fitting_loss_decreased"] = bool(fitted) and (
                    fitted[-1]["work"]["final"]["root_equal_cross_entropy"]
                    < fitted[0]["work"]["initial"]["root_equal_cross_entropy"]
                )
        body = {
            "schema_version": "natural-native-curriculum-v1",
            "config_id": store.config_id,
            "status": "natural_curriculum_complete"
            if complete
            else "natural_curriculum_clean_pause",
            "completed_units": len(done),
            "planned_units": len(tasks),
            "new_units_this_session": new,
            "sources": sources,
            "teacher_report_id": teacher["report_id"],
            "teacher_gate": teacher["gate"],
            "full_games": summary(cfg, done),
            "held_fights": [r for r in done.values() if r["kind"] == "held"],
            "optimizer_steps_on_copies": sum(
                r.get("work", {}).get("new_optimizer_steps", 0) for r in done.values()
            ),
            "control_checks": checks,
            "control_checks_passed": complete and all(checks.values()),
            "all_final_states_frozen_before_evaluation": complete,
            "final_players": [
                r
                for r in done.values()
                if r["kind"] == "fit" and r["epoch"] == cfg["learning"]["epochs"]
            ],
            "original_weights_and_Adam_unchanged": True,
            "critic_and_credit_predictor_unchanged": True,
            "full_run_objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "loss": "categorical_imitation_not_return_regression_or_PPO",
            "ordinary_PPO_eligible": False,
            "heldout_selects_epoch": False,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "game_apps_created": 0,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        i = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{i:03d}.json", report)
        if complete:
            atomic_json(final, report)
        return report
