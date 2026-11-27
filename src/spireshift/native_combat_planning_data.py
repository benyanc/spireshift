"""Frozen sampled combat search, explicit CPU charging and paired outcome summaries."""

from __future__ import annotations

import math
import statistics
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_turn_teacher_data import turn_lesson

SAMPLES = 4
SEARCH_CPU_CAP = 64.0
SEARCH_CALL_CPU_CAP = 32.0


def cpu_allowance(spent: float, whole_run: float, search: bool) -> float:
    if (
        any(type(v) not in (int, float) or not math.isfinite(v) for v in (spent, whole_run))
        or spent < 0
        or whole_run < SEARCH_CPU_CAP
    ):
        raise ValueError("Keep finite nonnegative planning costs and the declared run budget")
    remaining = min(SEARCH_CPU_CAP, whole_run) - spent if search else whole_run - spent
    if remaining <= 0:
        raise ValueError("Planning exhausted its budget; do not start another native attempt")
    return min(SEARCH_CALL_CPU_CAP, remaining) if search else remaining


def select_plan(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    """The selector cannot receive final return, maximum floor, wins or closure outcomes."""
    expected = {"sample", "plan_id", "path", "combat_survived", "exit_hp"}
    if (
        len(proposals) != SAMPLES
        or [p["sample"] for p in proposals] != list(range(SAMPLES))
        or any(set(p) != expected for p in proposals)
    ):
        raise ValueError("Resolve four ordered combat proposals with public tactical metrics only")
    for p in proposals:
        if (
            type(p["sample"]) is not int
            or type(p["combat_survived"]) is not bool
            or (p["exit_hp"] is not None and type(p["exit_hp"]) is not int)
        ):
            raise ValueError("Invalid public combat selection metrics")
    return dict(
        max(
            proposals,
            key=lambda p: (
                p["combat_survived"],
                (p["exit_hp"] or 0) if p["combat_survived"] else 0,
                -p["sample"],
            ),
        )
    )


def search_tasks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "key": f"search-{item['key']}-s{sample:02d}",
            "stage": "search",
            "item_key": item["key"],
            "root_id": item["root_id"],
            "sample": sample,
            "repeat": 0,
            "duplicate": False,
        }
        for item in items
        for sample in range(SAMPLES)
    ]


def evaluation_tasks(
    items: list[dict[str, Any]], groups: list[dict[str, Any]], repeats: int, control: bool
) -> list[dict[str, Any]]:
    if (
        type(repeats) is not int
        or repeats not in {2, 8}
        or [g["item_key"] for g in groups] != [i["key"] for i in items]
    ):
        raise ValueError("Preserve every initial turn and its declared continuation denominator")
    tasks = []
    for item, group in zip(items, groups, strict=True):
        if group["blocked"]:
            continue
        for repeat in range(repeats):
            tasks.append(
                {
                    "key": f"evaluate-{item['key']}-r{repeat:02d}",
                    "stage": "evaluation",
                    "item_key": item["key"],
                    "root_id": item["root_id"],
                    "sample": 0,
                    "repeat": repeat,
                    "duplicate": False,
                    "selected": group["selected"],
                    "planning_cpu_seconds": group["planning_cpu_seconds"],
                }
            )
        if control and item["reference"]:
            tasks.append({**tasks[-repeats], "key": f"duplicate-{item['key']}", "duplicate": True})
    if control:
        tasks.extend(
            {
                "key": f"baseline-{i['key']}",
                "stage": "baseline",
                "item_key": i["key"],
                "root_id": i["root_id"],
                "sample": 0,
                "repeat": 0,
                "duplicate": False,
            }
            for i in items
            if i["reference"]
        )
    return tasks


def feedback_table(
    root: dict[str, Any],
    items: list[dict[str, Any]],
    rows: dict[str, list[dict[str, Any]]],
    repeats: int,
) -> dict[str, Any]:
    candidates = [
        {"plan_id": i["turn_plan_id"], "path": i["turn_plan_path"], "reference": i["reference"]}
        for i in items
    ]
    values = [
        {**v, "plan_id": i["turn_plan_id"], "duplicate_control": False, "turn_complete": True}
        for i in items
        for v in rows[i["key"]]
    ]
    return turn_lesson(root, candidates, values, repeats)


def summarize(
    roots: list[dict[str, Any]],
    items: list[dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    repeats: int,
) -> dict[str, Any]:
    actual = {
        (v["item_key"], v["repeat"]): v
        for v in completed.values()
        if v["stage"] == "evaluation" and not v["duplicate"]
    }
    expected = {(i["key"], rep) for i in items for rep in range(repeats)}
    if not set(actual).issubset(expected) or len(actual) != sum(
        v["stage"] == "evaluation" and not v["duplicate"] for v in completed.values()
    ):
        raise ValueError("Repeated combat evaluation cell")
    own_rows, base_rows, cases = {}, {}, []
    for item in items:
        pairs = []
        for rep in range(repeats):
            b = baseline[f"{item['key']}-r{rep:02d}"]
            v = actual.get((item["key"], rep))
            valid = (
                v is not None
                and v["status"] == "terminal"
                and v["root_reached"]
                and v["combat_complete"]
                and v["native_audit_valid"]
            )
            pairs.append((b, v, valid))
        difference = [
            (v["training_return"] if valid and v else 0.0) - b["training_return"]
            for b, v, valid in pairs
        ]
        cases.append(
            {
                "item_key": item["key"],
                "root_id": item["root_id"],
                "initial_turn_id": item["turn_plan_id"],
                "denominator": repeats,
                "completed": sum(valid for _, _, valid in pairs),
                "failures_or_unattempted": sum(not valid for _, _, valid in pairs),
                "baseline_wins": sum(b["victory"] for b, _, _ in pairs),
                "planned_wins": sum(v["victory"] for _, v, valid in pairs if valid and v),
                "baseline_mean_floor": statistics.fmean(b["maximum_floor"] for b, _, _ in pairs),
                "planned_mean_floor_failures_zero": statistics.fmean(
                    v["maximum_floor"] if valid and v else 0 for _, v, valid in pairs
                ),
                "baseline_encounter_exits_alive": sum(
                    b["combat_exit"]["combat_survived"] for b, _, _ in pairs
                ),
                "planned_encounter_exits_alive": sum(
                    v["exit"]["combat_survived"] for _, v, valid in pairs if valid and v
                ),
                "mean_bootstrap_return_change_failures_zero": statistics.fmean(difference),
                "paired_standard_error_descriptive": statistics.stdev(difference)
                / math.sqrt(repeats),
                "higher_pairs": sum(v > 1e-12 for v in difference),
                "lower_pairs": sum(v < -1e-12 for v in difference),
                "tied_pairs": sum(abs(v) <= 1e-12 for v in difference),
            }
        )
        base_rows[item["key"]] = [b for b, _, _ in pairs]
        own_rows[item["key"]] = [v for _, v, valid in pairs if valid and v]
    feedback = []
    for r in roots:
        source_items = [i for i in items if i["root_id"] == r["root_id"]]
        feedback.append(
            {
                "root_id": r["root_id"],
                "baseline": feedback_table(r, source_items, base_rows, repeats),
                "planned": feedback_table(r, source_items, own_rows, repeats),
            }
        )

    def counts(kind: str) -> dict[str, int]:
        return {
            k: sum(p[k] for row in feedback for p in row[kind]["preferences"])
            for k in ("positive_pairs", "negative_pairs", "tied_pairs")
        }

    body = {
        "schema_version": "native-bounded-combat-comparison-summary-v1",
        "cases": cases,
        "turn_feedback": feedback,
        "baseline_alternative_pair_counts": counts("baseline"),
        "planned_alternative_pair_counts": counts("planned"),
        "independent_source_worlds": len(roots),
        "conditional_streams_not_independent_worlds": True,
        "denominator": len(items) * repeats,
        "completed": sum(c["completed"] for c in cases),
        "failed_or_unattempted": sum(c["failures_or_unattempted"] for c in cases),
        "baseline_full_run_wins": sum(c["baseline_wins"] for c in cases),
        "planned_full_run_wins": sum(c["planned_wins"] for c in cases),
        "baseline_encounter_exits_alive": sum(c["baseline_encounter_exits_alive"] for c in cases),
        "planned_encounter_exits_alive": sum(c["planned_encounter_exits_alive"] for c in cases),
        "readiness_passed": False,
        "checkpoint_promoted": False,
        "ordinary_PPO_eligible": False,
    }
    return {**body, "report_id": manifest_identifier(body)}
