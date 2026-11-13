"""One sealed delayed diagnostic unit, using unchanged production PPO settings."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_delayed_data import qualify
from spireshift.native_delayed_evaluate import coverage, evaluate, passes
from spireshift.native_delayed_learning import batch
from spireshift.native_policy_updates import qualify as qualify_optimizer
from spireshift.native_policy_updates import update
from spireshift.native_structured_state import load, save


def trees(root: Path, done: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in done.values():
        if row["kind"] != "delayed_tree":
            continue
        tree = json.loads((root / row["tree_path"]).read_text())
        if manifest_identifier(tree) != row["tree_id"] or qualify(tree) != row["qualification"]:
            raise ValueError("Native tree identities or delayed labels changed")
        result.append(tree)
    fitting = {t["task"]["seed"]["id"] for t in result if t["task"]["seed"]["partition"] == "fit"}
    held = {t["task"]["seed"]["id"] for t in result if t["task"]["seed"]["partition"] == "heldout"}
    if fitting & held:
        raise ValueError("Related cases from one native world cannot span fitting and held-out")
    return result


def execute(
    root: Path,
    context: dict[str, Any],
    task: dict[str, Any],
    done: dict[str, dict[str, Any]],
    target: Path,
    deadline: float,
) -> dict[str, Any]:
    p, score, cfg = task["player"], context["score"], context["config"]
    if task["kind"] == "import":
        model = context["models"][p]
        adam = Adam.from_mapping(context["adams"][p].as_dict(), model.parameter_count)
        checks = qualify_optimizer(model, adam)
        atomic_json(target / "optimizer-checks.json", checks)
        result: dict[str, Any] = {
            "kind": "import",
            "player": p,
            "optimizer_checks_passed": checks["passed"],
        }
    else:
        parent = done[task["state"]]
        model, adam, sid = load(root / parent["state_path"])
        if (
            sid != parent["state_id"]
            or model.model_id != parent["model_id"]
            or adam.steps != parent["optimizer_steps"]
        ):
            raise ValueError("Restore the exact predecessor full model and every Adam moment")
        bank = trees(root, done)
        fitting = [t for t in bank if t["task"]["seed"]["partition"] == "fit"]
        result = {"kind": task["kind"], "player": p, "arm": task["arm"]}
        if task["kind"] == "evaluate":
            held = [t for t in bank if t["task"]["seed"]["partition"] == "heldout"]
            fit_result, held_result = evaluate(model, fitting, score), evaluate(model, held, score)
            novelty = coverage(fitting, held)
            unseen = set(novelty["unseen_heldout_cases"])
            unseen_trees = [t for t in held if t["task"]["key"] in unseen]
            return {
                **result,
                "model_id": model.model_id,
                "optimizer_steps": adam.steps,
                "fitting": fit_result,
                "heldout": held_result,
                "coverage": novelty,
                "unseen_heldout": evaluate(model, unseen_trees, score) if unseen_trees else None,
                "fitting_criterion_passed": passes(fit_result),
                "heldout_criterion_passed": held_result["minimum_success_probability"] >= 0.75
                and held_result["greedy_accuracy"] == 1.0,
                "ordinary_PPO_eligible": False,
                "checkpoint_promoted": False,
            }
        steps = adam.steps
        curves: list[dict[str, Any]] = []
        initial = evaluate(model, fitting, score) if task["start_round"] == 1 else None
        first_trace = None
        for index in range(task["start_round"], task["end_round"] + 1):
            if time.monotonic() >= deadline - 15:
                raise TimeoutError(
                    "Preserve unfinished fit; never replay an uncertain optimizer unit"
                )
            samples, credit = batch(model, fitting, score, cfg["credit"], task["arm"], p, index)
            if first_trace is None:
                first_trace = credit["sampled_trace_id"]
            model, adam, work = update(model, adam, samples, index)
            measured = evaluate(model, fitting, score)
            curves.append(
                {"round": index, "credit": credit, "production_update": work, "fitting": measured}
            )
            del samples
        atomic_json(target / "rounds.json", {"initial_fitting": initial, "rounds": curves})
        result.update(
            start_round=task["start_round"],
            end_round=task["end_round"],
            new_optimizer_steps=adam.steps - steps,
            first_batch_trace_id=first_trace,
            final_fitting=curves[-1]["fitting"],
            initial_fitting=initial,
            sampled_episodes=32 * len(curves),
        )
        print(
            f"Delayed player {p} / {task['arm']} / round {task['end_round']}: "
            f"fitting success {curves[-1]['fitting']['mean_success_probability']:.1%}; "
            f"{adam.steps - steps} updates on an experimental copy.",
            flush=True,
        )
    saved = save(target / "state.json", model, adam)
    return {
        **result,
        "state_path": str((target / "state.json").relative_to(root)),
        "state_id": saved["state_id"],
        "model_id": model.model_id,
        "optimizer_steps": adam.steps,
    }
