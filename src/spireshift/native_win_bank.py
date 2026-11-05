"""Win-focused labels with whole-world ownership and explicit missing coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win_plan import ACTS, REQUIRED_FAMILIES


def rank(result: dict[str, Any]) -> tuple[bool, float]:
    return result["status"] == "complete" and result["curriculum_success"], float(
        result["ending_hp"]
    )


def select(reference: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    accepted = [c for c in candidates if c["status"] == "complete" and c["curriculum_success"]]
    if not accepted:
        return None
    if any(c["initial_public_input_id"] != reference["initial_public_input_id"] for c in accepted):
        raise ValueError("Counterfactual teachers did not start from the same exact public state")
    return max(accepted, key=rank)


def lesson(
    case: dict[str, Any],
    start: dict[str, Any],
    reference: dict[str, Any],
    chosen: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    if case["partition"] not in {"fit", "control_fit"}:
        raise ValueError("Held-out worlds never provide fitting or teacher-selection labels")
    if (
        chosen["status"] != "complete"
        or not chosen["curriculum_success"]
        or confirmation["status"] != "complete"
        or not confirmation["curriculum_success"]
        or confirmation["variant"] != chosen["variant"]
        or confirmation["initial_public_input_id"] != chosen["initial_public_input_id"]
    ):
        raise ValueError("Only confirmed successful actual native continuations provide labels")
    rescue = reference["status"] == "complete" and not reference["curriculum_success"]
    body = {
        "scenario": case,
        "start_id": start["report_id"],
        "world": start["seed"],
        "partition": case["partition"],
        "episode_directory": chosen["directory"],
        "episode_id": chosen["report_id"],
        "confirmation_id": confirmation["report_id"],
        "reference_id": reference["report_id"],
        "teacher_variant": chosen["variant"],
        "strict_goal_rescue": rescue,
        "training_start_win": start["kind"] == "prepared_training_only",
        "full_run_win": chosen["full_run_win"],
        "ordinary_PPO_eligible": False,
        "student_inputs_public_only": True,
    }
    return {**body, "lesson_id": manifest_identifier(body)}


def steps(root: Path, value: dict[str, Any]) -> list[dict[str, Any]]:
    frame, index, result = None, 0, []
    for row in records(root / value["episode_directory"] / "shared-public.jsonl.gz"):
        if row["kind"] == "policy_input":
            frame = row["frame"]
        if row["kind"] == "policy_choice":
            if frame is None:
                raise ValueError("Label preceded its public menu")
            choice = row["choice"]
            if not choice["navigation_only"] and len(frame["actions"]) > 1:
                result.append(
                    {
                        "public_input": frame["public_input"],
                        "public_input_id": manifest_identifier(frame["public_input"]),
                        "action_index": choice["action_index"],
                        "family": frame["source_family"],
                        "decision_index": index,
                    }
                )
            index += 1
            frame = None
    return result


def coverage(
    lessons: list[dict[str, Any]],
    meaningful_families: set[str],
    heldout_results: list[dict[str, Any]],
    quality: dict[str, Any],
) -> dict[str, Any]:
    acts = {r["scenario"]["act_definition"] for r in lessons}
    bosses = {r["scenario"]["boss"] for r in lessons if r["scenario"]["entry"] == "boss"}
    rescues = {r["world"] for r in lessons if r["strict_goal_rescue"]}
    final_rescues = {
        r["world"]
        for r in lessons
        if r["strict_goal_rescue"]
        and r["scenario"]["act_definition"] == "GLORY"
        and r["scenario"]["entry"] == "boss"
    }
    heldout_success = sum(
        r["status"] == "complete" and r["curriculum_success"] for r in heldout_results
    )
    checks = {
        "all_act_definitions_with_successful_labels": set(ACTS) <= acts,
        "all_declared_bosses_with_successful_labels": set(quality["boss_definitions"]) <= bosses,
        "all_final_bosses_with_successful_labels": set(ACTS["GLORY"][1]) <= bosses,
        "all_required_meaningful_decision_families": meaningful_families >= REQUIRED_FAMILIES,
        "independent_goal_rescues": len(rescues) >= quality["strict_improvement_worlds"],
        "final_boss_goal_rescue": len(final_rescues) >= quality["final_boss_rescues"],
        "fixed_teacher_heldout_successes": heldout_success >= quality["minimum_heldout_successes"],
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "successful_act_definitions": sorted(acts),
        "successful_boss_definitions": sorted(b for b in bosses if b is not None),
        "meaningful_families": sorted(meaningful_families),
        "missing_families": sorted(REQUIRED_FAMILIES - meaningful_families),
        "missing_bosses": sorted(set(quality["boss_definitions"]) - bosses),
        "goal_rescue_worlds": sorted(rescues),
        "final_boss_rescue_worlds": sorted(final_rescues),
        "heldout_successes": heldout_success,
    }


def matching_confirmation(root: Path, left: dict[str, Any], right: dict[str, Any]) -> bool:
    def ordered(value: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        for row in records(root / value["directory"] / "shared-public.jsonl.gz"):
            if "frame" in row:
                f = row["frame"]
                result.append(
                    {"kind": row["kind"], "public": f["public_input"], "terminal": f["terminal"]}
                )
            elif row["kind"] == "policy_choice":
                c = row["choice"]
                result.append(
                    {
                        "kind": "choice",
                        "action_index": c["action_index"],
                        "navigation_only": c["navigation_only"],
                        "behavior": c["behavior"],
                    }
                )
        return result

    return ordered(left) == ordered(right)
