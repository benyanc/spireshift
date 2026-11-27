"""Sealed warm-state teaching and a frozen-final evaluation barrier, never another study."""

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
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_context_reuse import check_sources
from spireshift.native_coordinated_branch import branch
from spireshift.native_experience_game import game
from spireshift.native_natural_learning import epoch
from spireshift.native_structured_state import load, save
from spireshift.native_teaching_data import ARMS, CONTRACT
from spireshift.native_teaching_inputs import snapshot
from spireshift.native_teaching_learning import diagnostics
from spireshift.native_teaching_plan import schedule, summary


def execute(
    root: Path,
    context: dict[str, Any],
    native: Any,
    *,
    max_units: int | None = None,
    launch_deadline: float | None = None,
) -> dict[str, Any]:
    cfg, bank = context["config"], context["bank"]
    store = ChunkJournal(root, cfg)
    final = store.workspace / "report.json"
    if final.exists():
        saved = identified(final)
        check_sources(root, saved["sources"])
        return saved
    started = time.monotonic()
    deadline = launch_deadline or started + cfg["session_limits"]["wall_seconds"] - 15
    tasks = schedule(cfg, bank)
    done: dict[str, Any] = {}
    sources = dict(context["sources"])
    q, inputs = native
    new = 0
    roots = {r["root_id"]: r for r in bank["roots"]}
    examples = {arm: [r["plans"][arm] for r in bank["lessons"]] for arm in ARMS}
    with store.lock():
        sources.update(snapshot(root, cfg, store.workspace))
        for task in tasks:
            request = {"contract": CONTRACT, "task": task, "bank_id": bank["bank_id"]}
            if "state" in task:
                request["predecessor_state_id"] = done[task["state"]]["state_id"]
            if task["kind"] == "freeze":
                request["final_state_ids"] = {
                    k: done[v]["state_id"] for k, v in task["states"].items()
                }
            if task["kind"] in {"fresh", "fight"}:
                request["frozen_finals_id"] = done["frozen-finals"]["frozen_finals_id"]
            receipt = store.completed(task["key"], request)
            if receipt is None:
                reserve = (
                    (90 if cfg["stage"] == "short_control" else 180)
                    if task["kind"] in {"fresh", "fight"}
                    else 15
                )
                if (
                    deadline - time.monotonic() < reserve
                    or max_units is not None
                    and new >= max_units
                ):
                    break
                if task["kind"] in {"fresh", "fight"} and _running_games():
                    raise ValueError("Close STS2 before another isolated teaching-test game")
                target = store.begin(task["key"], request)
                result: dict[str, Any] = {"kind": task["kind"]}
                if task["kind"] == "freeze":
                    body = {
                        "bank_id": bank["bank_id"],
                        "final_state_ids": request["final_state_ids"],
                        "no_evaluation_used_for_selection": True,
                    }
                    result.update(body, frozen_finals_id=manifest_identifier(body))
                    atomic_json(target / "frozen-finals.json", result)
                else:
                    p = task["player"]
                    if task["kind"] == "import":
                        model = context["models"][p]
                        adam = Adam.from_mapping(
                            context["adams"][p].as_dict(), model.parameter_count
                        )
                    else:
                        parent = done[task["state"]]
                        model, adam, sid = load(root / parent["state_path"])
                        if sid != parent["state_id"] or adam.steps != parent["optimizer_steps"]:
                            raise ValueError(
                                "Restore exact copied weights and every Adam moment/counter"
                            )
                    result.update(player=p, arm=task.get("arm", "initial"))
                    if task["kind"] in {"import", "fit"}:
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
                        state = save(target / "state.json", model, adam)
                        result.update(
                            state_path=str((target / "state.json").relative_to(root)),
                            state_id=state["state_id"],
                            model_id=model.model_id,
                            optimizer_steps=adam.steps,
                        )
                        if (
                            task["kind"] == "import"
                            or task.get("epoch") == cfg["learning"]["epochs"]
                        ):
                            result["diagnostics"] = diagnostics(model, bank, context["score"])
                    else:
                        account = Path.home() / "Library/Application Support/SlayTheSpire2"
                        before = _shared_snapshot(account)
                        if task["kind"] == "fresh":
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
                        else:
                            r = roots[task["root_id"]]
                            value = branch(
                                q,
                                inputs,
                                cfg,
                                r,
                                {"phase": "reference"},
                                model,
                                context["score"],
                                target,
                                deadline,
                            )
                            result.update(
                                root_id=r["root_id"],
                                world=r["world"],
                                source_player=r["player"],
                                partition=r["partition"],
                                status=value["status"],
                                outcome=value["outcome"],
                                resources=value["resources"],
                                model_id=model.model_id,
                                fight_id=value["fight_id"],
                                error=value["error"],
                            )
                        checks = immutable_checks(q, inputs)
                        checks["account_profile_unchanged"] = before == _shared_snapshot(account)
                        if not all(checks.values()):
                            raise ValueError(
                                "Teaching evaluation changed a frozen input or real profile"
                            )
                        result["checks"] = checks
                store.commit(task["key"], request, result)
                receipt = store.completed(task["key"], request)
                assert receipt is not None
                new += 1
                if task["kind"] == "fight":
                    print(
                        f"Teaching test: {task['key']} saved; {result['status']}; "
                        f"fight {result['outcome']}.",
                        flush=True,
                    )
                elif task["kind"] == "fresh":
                    games = [r for r in done.values() if r["kind"] == "fresh"] + [result]
                    if len(games) % 8 == 0 or len(games) == len(cfg["evaluation_seeds"]) * 6:
                        clean_games = [r for r in games if r["status"] == "terminal"]
                        wins = sum(bool(r["victory"]) for r in clean_games)
                        mean = sum(r["maximum_floor"] for r in clean_games) / len(games)
                        best = max((r["maximum_floor"] for r in clean_games), default=0)
                        print(
                            f"Fresh games: {len(games)}/{len(cfg['evaluation_seeds']) * 6}; "
                            f"wins {wins}; average floor {mean:.2f}; best floor {best}; "
                            f"failures {len(games) - len(clean_games)}.",
                            flush=True,
                        )
                elif task["kind"] == "fit" and task["epoch"] in {1, cfg["learning"]["epochs"]}:
                    print(
                        f"Teaching player {task['player']} / {task['arm']} / "
                        f"epoch {task['epoch']} saved.",
                        flush=True,
                    )
            done[task["key"]] = receipt["result"]
            sources.update(receipt["sources"])
            sources[str((store.path(task["key"]) / "done.json").relative_to(root))] = _sha_file(
                store.path(task["key"]) / "done.json"
            )
            failures = sum(
                r["kind"] in {"fresh", "fight"} and r["status"] not in {"terminal", "complete"}
                for r in done.values()
            )
            if failures > cfg["technical_failure_allowance"]:
                raise ValueError(
                    "Teaching test exceeded its finite failure allowance; all receipts retained"
                )
        complete = len(done) == len(tasks)
        check_sources(root, sources)
        clean = complete and all(
            r["status"] in {"terminal", "complete"}
            for r in done.values()
            if r["kind"] in {"fresh", "fight"}
        )
        expected = cfg["learning"]["epochs"] * cfg["learning"]["steps_per_epoch"]
        checks = {
            "all_evaluations_clean": clean,
            "frozen_final_barrier_present": "frozen-finals" in done,
        }
        for p in (2, 3):
            for arm in ARMS:
                fitted = [
                    r
                    for r in done.values()
                    if r["kind"] == "fit" and r["player"] == p and r["arm"] == arm
                ]
                checks[f"p{p}_{arm}_fixed_work"] = (
                    sum(r["work"]["new_optimizer_steps"] for r in fitted) == expected
                )
        body = {
            "schema_version": "native-plan-teaching-comparison-v1",
            "config_id": store.config_id,
            "recipe_stage": cfg["stage"],
            "status": "native_teaching_complete" if complete else "native_teaching_clean_pause",
            "sources": sources,
            "bank_id": bank["bank_id"],
            "completed_units": len(done),
            "planned_units": len(tasks),
            "new_units_this_session": new,
            "maximum_native_attempts": sum(t["kind"] in {"fight", "fresh"} for t in tasks),
            "fresh_games": summary(cfg, done),
            "natural_fights": [r for r in done.values() if r["kind"] == "fight"],
            "states": {
                k: r
                for k, r in done.items()
                if r["kind"] in {"import", "fit"} and "diagnostics" in r
            },
            "frozen_finals": done.get("frozen-finals"),
            "control_checks": checks,
            "control_checks_passed": cfg["stage"] == "short_control"
            and complete
            and all(checks.values()),
            "optimizer_steps_on_copies": sum(
                r.get("work", {}).get("new_optimizer_steps", 0) for r in done.values()
            ),
            "original_weights_and_all_Adam_unchanged": True,
            "critic_and_credit_predictor_unchanged": True,
            "all_finals_frozen_before_any_evaluation": "frozen-finals" in done,
            "fitting_worlds": 2,
            "fitting_worlds_from_source_player": {"2": 2, "3": 0},
            "heldout_used_for_fitting_or_selection": False,
            "checkpoint_selection": "all_fixed_final_epochs_before_evaluation",
            "evaluation_behavior": "greedy_combat_sampled_noncombat_v1",
            "student_inputs_public_only": True,
            "training_loss": "categorical_imitation_not_PPO_or_return_regression",
            "ordinary_PPO_eligible": False,
            "full_run_objective": context["score"].evaluation_objective.as_dict(),
            "training_spec_id": context["score"].spec_id,
            "game_apps_created": 0,
            "checkpoint_promoted": False,
            "base_readiness_passed": False,
            "adaptive_controller_allowed": False,
            "automatic_training_follows": False,
            "wall_seconds": time.monotonic() - started,
        }
        report = {**body, "report_id": manifest_identifier(body)}
        i = len(list((store.workspace / "sessions").glob("session-*.json"))) + 1
        atomic_json(store.workspace / f"sessions/session-{i:03d}.json", report)
        if complete:
            atomic_json(final, report)
        return report
