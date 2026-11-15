"""Matched outcomes, same-menu divergence and strict Act 1 rescue admission."""

from __future__ import annotations

from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_rescue_game import TRACE, decisions, play
from spireshift.native_a8_rescue_inputs import GATES
from spireshift.native_win4_game import write
from spireshift.native_win_teacher import validate_student_input

ARMS = ("original", "fitted", "teacher")
TARGET_REASONS: frozenset[str] = frozenset(GATES["collect"]["required_reasons"])


def first_change(fitted: Path, teacher: Path) -> dict[str, Any] | None:
    with closing(decisions(fitted)) as baseline, closing(decisions(teacher)) as improved:
        for number, ((_, left, a), (_, right, b)) in enumerate(
            zip(baseline, improved, strict=True)
        ):
            if left["input_digest"] != right["input_digest"]:
                raise ValueError("Public inputs diverged before a different choice was delivered")
            if a is None or b is None:
                return None
            old, new = a["choice"]["action_index"], b["choice"]["action_index"]
            if old == new:
                if a["receipt"]["delivery_domain"] != b["receipt"]["delivery_domain"]:
                    raise ValueError("An identical choice changed delivery domain")
                continue
            if (
                left["public_input"] != right["public_input"]
                or b["choice"].get("reference_action_index") != old
                or not b["choice"].get("intervention")
                or any(r["receipt"]["delivery_domain"] != "native" for r in (a, b))
            ):
                raise ValueError("The first change must be a verified same-menu intervention")
            return {
                "choice_ordinal_including_local_factors": number,
                "public_input_id": manifest_identifier(right["public_input"]),
                "family": right["source_family"],
                "fitted_action_index": old,
                "teacher_action_index": new,
                "reason": b["choice"]["intervention"],
            }
    raise ValueError("Missing final frame in a verified Act 1 trace")


def teaching_labels(trace: Path) -> list[dict[str, Any]]:
    result = []
    native_index = 0
    for _, frame, delivered in decisions(trace):
        if delivered is None or delivered["receipt"]["delivery_domain"] != "native":
            continue
        choice = delivered["choice"]
        reason = choice.get("intervention")
        if reason in TARGET_REASONS:
            public = frame["public_input"]
            selected, proposed = choice["action_index"], choice["reference_action_index"]
            if (
                choice["navigation_only"]
                or choice.get("answer_plan")
                or not 0 <= selected < len(public["candidates"])
                or not 0 <= proposed < len(public["candidates"])
                or selected == proposed
            ):
                raise ValueError("A label requires a real intervention on a legal menu")
            validate_student_input(public)
            result.append(
                {
                    "public_input": public,
                    "public_input_id": manifest_identifier(public),
                    "action_index": selected,
                    "fitted_proposal_action_index": proposed,
                    "reason": reason,
                    "family": frame["source_family"],
                    "decision_index": native_index,
                }
            )
        native_index += 1
    return [{**label, "label_weight": 1.0 / len(result)} for label in result]


def play_case(
    ctx: dict[str, Any], case: dict[str, Any], target: Path, deadline: float
) -> dict[str, Any]:
    episodes = {}
    for arm in ARMS:
        episodes[arm] = play(ctx, case, arm, target / arm, deadline)
        if len({row["initial_public_input_id"] for row in episodes.values()}) != 1:
            raise ValueError("Matched arms started with different public inputs or legal choices")
    outcomes = {arm: row["outcome"] for arm, row in episodes.items()}
    change = first_change(target / "fitted" / TRACE, target / "teacher" / TRACE)
    rescued = outcomes == {"original": "act1_loss", "fitted": "act1_loss", "teacher": "act1_clear"}
    labels, label_file = [], None
    if rescued:
        if change is None:
            raise ValueError("A rescue requires a first different action on an identical menu")
        confirmation = play(ctx, case, "confirmation", target / "confirmation", deadline)
        episodes["confirmation"] = confirmation
        if (
            confirmation["outcome"] != "act1_clear"
            or confirmation["semantic_trajectory_sha256"]
            != episodes["teacher"]["semantic_trajectory_sha256"]
        ):
            raise ValueError("A candidate rescue did not reproduce in a fresh isolated worker")
        if case["phase"] == "collect":
            labels = teaching_labels(target / "teacher" / TRACE)
            if labels:
                path = target / "lessons.json"
                report = write(
                    path,
                    {
                        "schema_version": "native-a8-act1-rescue-world-lessons-v1",
                        "case": case,
                        "teacher_episode_id": episodes["teacher"]["report_id"],
                        "confirmation_episode_id": confirmation["report_id"],
                        "labels": labels,
                    },
                )
                label_file = {
                    "path": str(path.relative_to(ctx["qualification"].root)),
                    "sha256": _sha_file(path),
                    "report_id": report["report_id"],
                }
    return {
        "case": case,
        "outcomes": outcomes,
        "episodes": episodes,
        "strict_rescue_confirmed": rescued,
        "first_change_from_fitted": change,
        "label_file": label_file,
        "targeted_label_count": len(labels),
        "label_reasons": sorted({label["reason"] for label in labels}),
    }


def assess(phase: str, planned: list[dict[str, Any]], rows: list[dict[str, Any]]) -> dict[str, Any]:
    rules = GATES[phase]
    counts = {arm: Counter(row["outcomes"][arm] for row in rows) for arm in ARMS}
    rescues = [row for row in rows if row["strict_rescue_confirmed"]]
    eligible = rescues if phase == "qualify" else [row for row in rescues if row["label_file"]]
    players = sorted({row["case"]["player"] for row in eligible})
    reasons = sorted({reason for row in eligible for reason in row["label_reasons"]})
    checks = {
        "declared_cases_finished": len(rows) == len(planned),
        "minimum_distinct_rescues": len(eligible) >= rules["minimum_rescues"],
        "both_initializers": players == rules["required_players"],
    }
    if phase == "qualify":
        checks.update(
            {
                "no_capped_qualification_arms": all(not c["capped"] for c in counts.values()),
                "teacher_cleared_more_than_each_reference": all(
                    counts["teacher"]["act1_clear"] > counts[ref]["act1_clear"] for ref in ARMS[:2]
                ),
            }
        )
    else:
        checks["all_target_reasons_delivered"] = reasons == rules["required_reasons"]
    return {
        "planned_worlds": len(planned),
        "sealed_worlds": len(rows),
        "outcomes_by_arm": {
            arm: {status: c[status] for status in ("act1_clear", "act1_loss", "capped")}
            for arm, c in counts.items()
        },
        "strict_rescues": [row["case"]["key"] for row in rescues],
        "eligible_rescues": [row["case"]["key"] for row in eligible],
        "eligible_initializers": players,
        "eligible_reasons": reasons,
        "checks": checks,
        "passed": all(checks.values()),
    }
