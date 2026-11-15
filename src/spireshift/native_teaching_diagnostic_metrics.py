"""Saved public-choice diagnostics; no optimality labels, fitting or gameplay."""

from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_model import encode
from spireshift.native_teaching_data import ARMS, public_step
from spireshift.native_training_diagnostics import decision_meta
from spireshift.training_objective import TrainingScoreSpec


def remaining(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("Saved teaching diagnosis reached its short wall cap")


def distribution(
    model: CachedContextModel, public: dict[str, Any], score: TrainingScoreSpec
) -> tuple[float, ...]:
    rows, _ = encode(public, model, score)
    logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
    if not logs or not all(math.isfinite(x) for x in logs):
        raise ValueError("A diagnostic needs a finite current legal distribution")
    return logs


def greedy(logs: tuple[float, ...] | list[float]) -> int:
    return max(range(len(logs)), key=lambda i: (logs[i], -i))


def action_label(public: dict[str, Any], index: int) -> str:
    action = public["candidates"][index]
    targets = [
        str(a["entity"]["label"])
        for a in action.get("arguments", [])
        if (a.get("entity") or {}).get("label")
    ]
    return str(action.get("label") or action["verb"]) + (
        " → " + ", ".join(targets) if targets else ""
    )


def target(logs: tuple[float, ...], action: int) -> dict[str, Any]:
    others = [p for i, p in enumerate(logs) if i != action]
    return {
        "probability": math.exp(logs[action]),
        "cross_entropy": -logs[action],
        "greedy_matches": greedy(logs) == action,
        "log_probability_margin_over_best_other": logs[action] - max(others) if others else None,
    }


def lesson_details(
    models: dict[str, CachedContextModel],
    bank: dict[str, Any],
    score: TrainingScoreSpec,
    deadline: float,
) -> dict[str, Any]:
    """Keep full-plan averages separate from each of the three changed targets."""
    worlds = []
    for lesson in bank["lessons"]:
        remaining(deadline)
        if lesson["partition"] != "fit":
            raise ValueError("Lesson diagnosis cannot turn a held-out plan into a label")
        changed = {
            (s["public_input_id"], s["action_index"]) for s in lesson["changed_choices"]["steps"]
        }
        plans = {}
        for arm in ARMS:
            rows = []
            for index, raw in enumerate(lesson["plans"][arm]["steps"]):
                remaining(deadline)
                step = public_step(raw)
                public, chosen = step["public_input"], step["action_index"]
                rows.append(
                    {
                        "position": index,
                        "public_input_id": step["public_input_id"],
                        "target_action": chosen,
                        "target_label": action_label(public, chosen),
                        "changed_target": (step["public_input_id"], chosen) in changed,
                        "versions": {
                            name: target(distribution(model, public, score), chosen)
                            for name, model in models.items()
                        },
                    }
                )
            plans[arm] = rows
        teacher = plans["teacher_clone"]
        worlds.append(
            {
                "world": lesson["world"],
                "root_id": lesson["root_id"],
                "plans": plans,
                "changed_targets": [
                    next(
                        r
                        for r in teacher
                        if (r["public_input_id"], r["target_action"])
                        == (s["public_input_id"], s["action_index"])
                    )
                    for s in lesson["changed_choices"]["steps"]
                ],
                "explicit_changed_choices": len(lesson["changed_choices"]["steps"]),
                "teacher_positions": len(teacher),
                "changed_positions": sum(r["changed_target"] for r in teacher),
                "nominal_changed_position_weight_within_world": sum(
                    r["changed_target"] for r in teacher
                )
                / len(teacher),
            }
        )
    return {
        "worlds": worlds,
        "nominal_changed_position_weight_equal_world": statistics.fmean(
            r["nominal_changed_position_weight_within_world"] for r in worlds
        ),
        "position_weights_are_not_actual_gradient_influence": True,
        "better_target_probabilities_establish_stronger_play": False,
    }


def departure(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare only the exact common prefix; never align different post-edit states."""
    expected = [public_step(s) for s in expected]
    actual = [public_step(s) for s in actual]
    matched = 0
    first = None
    for i, (a, b) in enumerate(zip(expected, actual, strict=False)):
        if a["public_input_id"] != b["public_input_id"]:
            first = {
                "position": i,
                "kind": "public_state_difference",
                "expected_public_input_id": a["public_input_id"],
                "actual_public_input_id": b["public_input_id"],
                "action_comparison_available": False,
            }
            break
        if a["action_index"] != b["action_index"]:
            meta = decision_meta(a["public_input"], a["action_index"])
            first = {
                "position": i,
                "kind": "different_action_on_identical_public_state",
                "public_input_id": a["public_input_id"],
                "family": meta["family"],
                "hp_fraction": meta["hp_fraction"],
                "expected_action": a["action_index"],
                "actual_action": b["action_index"],
                "expected_label": action_label(a["public_input"], a["action_index"]),
                "actual_label": action_label(a["public_input"], b["action_index"]),
                "action_comparison_available": True,
            }
            break
        matched += 1
    if first is None and len(actual) != len(expected):
        first = {
            "position": matched,
            "kind": "executed_trace_ended" if len(actual) < len(expected) else "plan_trace_ended",
            "action_comparison_available": False,
        }
    return {
        "expected_actions": len(expected),
        "executed_actions": len(actual),
        "exact_common_prefix_actions": matched,
        "same_complete_trace": first is None,
        "first_departure": first,
        "departure_is_proven_mistake": False,
        "post_departure_states_compared_by_position": False,
    }


def changed_reach(
    changed: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for s in changed:
        s = public_step(s)
        positions = [
            (i, a["action_index"])
            for i, a in enumerate(actual)
            if a["public_input_id"] == s["public_input_id"]
        ]
        rows.append(
            {
                "public_input_id": s["public_input_id"],
                "target_action": s["action_index"],
                "exact_state_reached": bool(positions),
                "observed_positions_and_actions": positions,
                "target_taken_on_every_visit": all(a == s["action_index"] for _, a in positions)
                if positions
                else None,
            }
        )
    return rows


def movement(before: tuple[float, ...], after: tuple[float, ...]) -> dict[str, Any]:
    if len(before) != len(after) or not before:
        raise ValueError("Compare distributions on the same nonempty ordered menu")
    return {
        "total_variation": sum(
            abs(math.exp(a) - math.exp(b)) for a, b in zip(before, after, strict=True)
        )
        / 2,
        "KL_initial_to_copy": sum(
            math.exp(a) * (a - b) for a, b in zip(before, after, strict=True)
        ),
        "greedy_action_changed": greedy(before) != greedy(after),
    }


def world_mean(rows: list[dict[str, Any]], field: str) -> float:
    by_world: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_world[row["world"]].append(float(row[field]))
    return statistics.fmean(statistics.fmean(v) for v in by_world.values())


def interference(
    models: dict[str, CachedContextModel],
    situations: list[dict[str, Any]],
    score: TrainingScoreSpec,
    deadline: float,
) -> dict[str, Any]:
    comparisons: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    opportunities: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for row in situations:
        remaining(deadline)
        public = row["public_input"]
        logs = {name: distribution(model, public, score) for name, model in models.items()}
        meta = decision_meta(public, 0)  # The recorded historical choice is not a quality label.
        for arm in ARMS:
            change = {
                "world": row["world"],
                "family": meta["family"],
                "public_input_id": manifest_identifier(public),
                "source": row["source"],
                **movement(logs["initial"], logs[arm]),
                "initial_greedy_label": action_label(public, greedy(logs["initial"])),
                "copy_greedy_label": action_label(public, greedy(logs[arm])),
            }
            comparisons[arm].append(change)
            for name, indices in meta["opportunities"].items():
                opportunities[arm].append(
                    {
                        "world": row["world"],
                        "opportunity": name,
                        "probability_change": sum(math.exp(logs[arm][i]) for i in indices)
                        - sum(math.exp(logs["initial"][i]) for i in indices),
                    }
                )
    result = {}
    for arm in ARMS:
        groups = []
        for family in sorted({r["family"] for r in comparisons[arm]}):
            rows = [r for r in comparisons[arm] if r["family"] == family]
            groups.append(
                {
                    "family": family,
                    "states": len(rows),
                    "worlds": len({r["world"] for r in rows}),
                    **{
                        field: world_mean(rows, field)
                        for field in (
                            "total_variation",
                            "KL_initial_to_copy",
                            "greedy_action_changed",
                        )
                    },
                }
            )
        offers = []
        for name in sorted({r["opportunity"] for r in opportunities[arm]}):
            rows = [r for r in opportunities[arm] if r["opportunity"] == name]
            offers.append(
                {
                    "name": name,
                    "states": len(rows),
                    "worlds": len({r["world"] for r in rows}),
                    "mean_probability_change": world_mean(rows, "probability_change"),
                }
            )
        result[arm] = {
            "by_family": groups,
            "opportunities": offers,
            "largest_probability_movements": sorted(
                comparisons[arm], key=lambda r: (-r["total_variation"], r["public_input_id"])
            )[:8],
        }
    return {
        "arms": result,
        "aggregation": "equal_world_within_family_or_opportunity",
        "distribution_temperature": 0.8,
        "combat_greedy_choice_changes_reported_separately": True,
        "changed_behavior_establishes_damage_or_improvement": False,
        "source_actions_used_as_optimal_labels": False,
    }
