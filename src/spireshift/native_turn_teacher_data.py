"""Outcome-blind turn candidates and conditional full-run comparison tables."""

from __future__ import annotations

import math
import statistics
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_combat_teacher_data import INFORMATION, sign_probability


def proposal_tasks(roots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for index, root in enumerate(roots):
        for action in (None, *range(len(root["public_input"]["candidates"]))):
            suffix = "greedy" if action is None else f"a-{action:02d}"
            result.append(
                {
                    "key": f"propose-{index:03d}-{suffix}",
                    "root_id": root["root_id"],
                    "stage": "proposal",
                    "first_action": action,
                    "repeat": 0,
                    "duplicate_control": False,
                }
            )
    return result


def freeze_candidates(
    root: dict[str, Any], proposals: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Accept only plan references; final returns cannot influence selection or ordering."""
    expected = [None, *range(len(root["public_input"]["candidates"]))]
    if (
        [p["first_action"] for p in proposals] != expected
        or any(
            set(p) != {"first_action", "plan_id", "plan_path", "proposal_key"} for p in proposals
        )
        or any(
            p["first_action"] is not None and type(p["first_action"]) is not int for p in proposals
        )
    ):
        raise ValueError("Freeze every planned proposal in order without outcome-based filtering")
    unique: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        identity = proposal["plan_id"]
        if identity not in unique:
            unique[identity] = {
                "plan_id": identity,
                "path": proposal["plan_path"],
                "proposal_keys": [],
                "reference": proposal["first_action"] is None,
            }
        unique[identity]["proposal_keys"].append(proposal["proposal_key"])
    return list(unique.values())


def comparison_tasks(
    roots: list[dict[str, Any]], sets: list[dict[str, Any]], repeats: int, control: bool
) -> list[dict[str, Any]]:
    if type(repeats) is not int or not 1 <= repeats <= 32:
        raise ValueError("Freeze finite continuation stream counts")
    if [s["root_id"] for s in sets] != [r["root_id"] for r in roots]:
        raise ValueError("Keep every source world in the frozen candidate denominator")
    result = []
    for index, group in enumerate(sets):
        if group["blocked"]:
            continue
        for repeat in range(repeats):
            for candidate, value in enumerate(group["candidates"]):
                result.append(
                    {
                        "key": f"compare-{index:03d}-r-{repeat:02d}-p-{candidate:02d}",
                        "stage": "comparison",
                        "root_id": group["root_id"],
                        "plan_id": value["plan_id"],
                        "plan_path": value["path"],
                        "first_action": None,
                        "repeat": repeat,
                        "duplicate_control": False,
                    }
                )
        if control:
            reference = group["candidates"][0]
            result.append(
                {
                    "key": f"compare-{index:03d}-duplicate-reference",
                    "stage": "comparison",
                    "root_id": group["root_id"],
                    "plan_id": reference["plan_id"],
                    "plan_path": reference["path"],
                    "first_action": None,
                    "repeat": 0,
                    "duplicate_control": True,
                }
            )
    return result


def turn_lesson(
    root: dict[str, Any],
    candidates: list[dict[str, Any]],
    results: list[dict[str, Any]],
    repeats: int,
) -> dict[str, Any]:
    if type(repeats) is not int or not 1 <= repeats <= 32:
        raise ValueError("Freeze finite teacher continuation streams")
    identifiers = [p["plan_id"] for p in candidates]
    if len(set(identifiers)) != len(identifiers) or (
        candidates
        and (candidates[0]["reference"] is not True or any(p["reference"] for p in candidates[1:]))
    ):
        raise ValueError("Keep one greedy reference and each unique complete plan exactly once")
    actual = [x for x in results if not x["duplicate_control"]]
    cells = {(x["plan_id"], x["repeat"]): x for x in actual}
    expected = {(p, r) for p in identifiers for r in range(repeats)}
    if len(cells) != len(actual) or any(k not in expected or type(k[1]) is not int for k in cells):
        raise ValueError("Turn teacher repeats a cell or includes an unplanned candidate/stream")
    for value in cells.values():
        if value["status"] == "terminal" and (
            type(value.get("training_return")) not in (int, float)
            or not math.isfinite(value["training_return"])
            or not 0 <= value["training_return"] <= 1
        ):
            raise ValueError("Turn comparison return is outside its declared finite score")
    complete = (
        bool(candidates)
        and set(cells) == expected
        and all(
            v["status"] == "terminal"
            and v["root_reached"]
            and v["turn_complete"]
            and v["native_audit_valid"]
            for v in cells.values()
        )
    )
    tables, preferences = [], []
    if complete:
        reference = identifiers[0]
        for identity in identifiers:
            own = [cells[identity, r] for r in range(repeats)]
            values = [v["training_return"] for v in own]
            wins = sum(v["victory"] for v in own)
            tables.append(
                {
                    "plan_id": identity,
                    "samples": repeats,
                    "full_run_wins": wins,
                    "mean_bootstrap_return": statistics.fmean(values),
                    "return_standard_error": statistics.stdev(values) / math.sqrt(repeats)
                    if repeats > 1
                    else None,
                    "mean_maximum_floor": statistics.fmean(v["maximum_floor"] for v in own),
                    "independent_hidden_worlds": 1,
                }
            )
            if identity == reference:
                continue
            differences = [
                cells[identity, r]["training_return"] - cells[reference, r]["training_return"]
                for r in range(repeats)
            ]
            positive, negative = (
                sum(x > 1e-12 for x in differences),
                sum(x < -1e-12 for x in differences),
            )
            probability = sign_probability(positive, negative)
            threshold = 0.05 / (len(identifiers) - 1)
            reference_wins = sum(cells[reference, r]["victory"] for r in range(repeats))
            preferences.append(
                {
                    "preferred_plan_id": identity,
                    "reference_plan_id": reference,
                    "mean_bootstrap_return_difference": statistics.fmean(differences),
                    "paired_difference_standard_error": statistics.stdev(differences)
                    / math.sqrt(repeats)
                    if repeats > 1
                    else None,
                    "positive_pairs": positive,
                    "negative_pairs": negative,
                    "tied_pairs": repeats - positive - negative,
                    "one_sided_sign_p": probability,
                    "within_root_threshold": threshold,
                    "admitted_exploratory_preference": repeats >= 8
                    and statistics.fmean(differences) > 0
                    and probability <= threshold
                    and wins >= reference_wins,
                    "label_kind": "terminal_victory_evidence"
                    if wins > reference_wins
                    else "auxiliary_bootstrap_only",
                }
            )
    body = {
        "root_id": root["root_id"],
        "public_input": root["public_input"],
        "public_input_id": root["public_input_id"],
        "comparison_complete": complete,
        "candidate_plans": candidates,
        "plans": tables,
        "preferences": preferences,
        "eligible_for_experimental_value_supervision": complete and repeats >= 8,
        "information_scope": INFORMATION,
        "privileged_fixed_world_teacher": True,
        "student_inputs_public_only": True,
        "ordinary_PPO_eligible": False,
        "public_belief_search_eligible": False,
        "optimal_native_turn_established": False,
        "uncertainty_scope": (
            "continuation_policy_sampling_conditional_on_one_original_hidden_world"
        ),
        "preference_test": "paired_outperformance_sign_test_not_expected_return_test",
        "multiple_comparisons": "Bonferroni_alternatives_vs_frozen_reference_within_each_root_only",
        "zero_observed_variance_is_not_hidden_world_certainty": True,
    }
    return {**body, "lesson_id": manifest_identifier(body)}
