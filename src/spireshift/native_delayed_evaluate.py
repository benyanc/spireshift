"""Exact current-policy values on verified diagnostic trees, never optimal action values."""

from __future__ import annotations

import math
from typing import Any, cast

from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_delayed_data import FAMILIES
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_structured_model import encode
from spireshift.training_objective import TrainingScoreSpec


def predictions(
    model: CachedContextModel, tree: dict[str, Any], score: TrainingScoreSpec
) -> tuple[dict[str, float], dict[str, tuple[float, ...]]]:
    values: dict[str, float] = {}
    probabilities: dict[str, tuple[float, ...]] = {}

    def visit(name: str) -> float:
        node = tree["nodes"][name]
        if node["terminal"]:
            value = float(node["outcome"])
        else:
            rows, _ = encode(node["public_input"], model, score)
            logs = log_softmax(
                score_features(cast(Any, model.actor), rows), SETTINGS["temperature"]
            )
            backwards = log_softmax(
                score_features(cast(Any, model.actor), rows[::-1]), SETTINGS["temperature"]
            )
            if any(abs(a - b) > 1e-10 for a, b in zip(logs, backwards[::-1], strict=True)):
                raise ValueError("Diagnostic policy changed under candidate permutation")
            probabilities[name] = tuple(math.exp(v) for v in logs)
            value = math.fsum(
                p * visit(child)
                for p, child in zip(probabilities[name], node["children"], strict=True)
            )
        values[name] = value
        return value

    visit("root")
    return values, probabilities


def evaluate(
    model: CachedContextModel, trees: list[dict[str, Any]], score: TrainingScoreSpec
) -> dict[str, Any]:
    if not trees or any(t["family"] not in FAMILIES for t in trees):
        raise ValueError("Evaluate a nonempty declared delayed-task partition")
    rows = []
    for tree in trees:
        values, probabilities = predictions(model, tree, score)
        name = "root"
        while not tree["nodes"][name]["terminal"]:
            p = probabilities[name]
            selected = max(range(len(p)), key=lambda i: (p[i], -i))
            name = tree["nodes"][name]["children"][selected]
        rows.append(
            {
                "case": tree["task"]["key"],
                "family": tree["family"],
                "world": tree["task"]["seed"]["id"],
                "public_root_id": tree["nodes"]["root"]["public_input_id"],
                "success_probability": values["root"],
                "greedy_success": bool(tree["nodes"][name]["outcome"]),
            }
        )
    families = {}
    for family in sorted({r["family"] for r in rows}):
        family_rows = [r for r in rows if r["family"] == family]
        families[family] = {
            "cases": len(family_rows),
            "mean_success_probability": math.fsum(r["success_probability"] for r in family_rows)
            / len(family_rows),
            "greedy_accuracy": sum(r["greedy_success"] for r in family_rows) / len(family_rows),
        }
    return {
        "cases": len(rows),
        "worlds": len({r["world"] for r in rows}),
        "mean_success_probability": math.fsum(r["success_probability"] for r in rows) / len(rows),
        "minimum_success_probability": min(r["success_probability"] for r in rows),
        "greedy_accuracy": sum(r["greedy_success"] for r in rows) / len(rows),
        "families": families,
        "rows": rows,
        "exact_expected_success_not_full_run_win_probability": True,
    }


def coverage(fitting: list[dict[str, Any]], held: list[dict[str, Any]]) -> dict[str, Any]:
    fit_ids = {t["nodes"]["root"]["public_input_id"] for t in fitting}
    held_ids = {t["nodes"]["root"]["public_input_id"] for t in held}
    return {
        "distinct_fitting_public_roots": len(fit_ids),
        "distinct_heldout_public_roots": len(held_ids),
        "heldout_roots_already_seen_in_fitting": len(held_ids & fit_ids),
        "genuinely_unseen_heldout_public_roots": len(held_ids - fit_ids),
        "unseen_heldout_cases": [
            t["task"]["key"] for t in held if t["nodes"]["root"]["public_input_id"] not in fit_ids
        ],
        "broad_generalization_established": False,
    }


def passes(result: dict[str, Any]) -> bool:
    return bool(result["minimum_success_probability"] >= 0.8 and result["greedy_accuracy"] == 1.0)
