from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_turn_teacher_policy import root

from spireshift.native_turn_teacher_data import (
    comparison_tasks,
    freeze_candidates,
    proposal_tasks,
    turn_lesson,
)


def references() -> list[dict[str, Any]]:
    return [
        {
            "first_action": a,
            "plan_id": p,
            "plan_path": f"artifacts/{p}.json",
            "proposal_key": f"proposal-{i}",
        }
        for i, (a, p) in enumerate(
            ((None, "reference"), (0, "reference"), (1, "better"), (2, "end"))
        )
    ]


def outcomes(repeats: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "stage": "comparison",
            "plan_id": p,
            "repeat": r,
            "duplicate_control": False,
            "status": "terminal",
            "root_reached": True,
            "turn_complete": True,
            "native_audit_valid": True,
            "training_return": value,
            "victory": False,
            "maximum_floor": floor,
        }
        for r in range(repeats)
        for p, value, floor in (("reference", 0.03, 8), ("better", 0.04, 10), ("end", 0.02, 6))
    ]


def test_every_first_action_is_proposed_and_reference_aliases_are_not_extra_samples() -> None:
    r = root()
    tasks = proposal_tasks([r])
    assert [t["first_action"] for t in tasks] == [None, 0, 1, 2]
    candidates = freeze_candidates(r, references())
    assert len(candidates) == 3 and candidates[0]["reference"]
    assert candidates[0]["proposal_keys"] == ["proposal-0", "proposal-1"]
    groups = [{"root_id": r["root_id"], "blocked": False, "candidates": candidates}]
    tasks = comparison_tasks([r], groups, 8, False)
    assert len(tasks) == 24 and len({x["key"] for x in tasks}) == 24
    assert len(comparison_tasks([r], groups, 2, True)) == 7


def test_outcomes_cannot_be_smuggled_into_candidate_selection() -> None:
    r, props = root(), references()
    before = copy.deepcopy(props)
    assert freeze_candidates(r, props) == freeze_candidates(r, before)
    props[2]["training_return"] = 1.0
    with pytest.raises(ValueError, match="outcome-based"):
        freeze_candidates(r, props)
    with pytest.raises(ValueError):
        freeze_candidates(r, before[:-1])


def test_complete_turn_tables_keep_uncertainty_and_the_original_improvement_gate() -> None:
    r = root()
    candidates = freeze_candidates(r, references())
    table = turn_lesson(r, candidates, outcomes(), 8)
    assert table["comparison_complete"] and table["eligible_for_experimental_value_supervision"]
    assert table["preferences"][0]["positive_pairs"] == 8
    assert table["preferences"][0]["one_sided_sign_p"] == 1 / 256
    assert table["preferences"][0]["within_root_threshold"] == 0.025
    assert table["preferences"][0]["admitted_exploratory_preference"]
    assert not table["preferences"][1]["admitted_exploratory_preference"]
    assert all(t["independent_hidden_worlds"] == 1 for t in table["plans"])
    assert table["privileged_fixed_world_teacher"] and table["student_inputs_public_only"]
    assert not table["ordinary_PPO_eligible"] and not table["public_belief_search_eligible"]
    control = turn_lesson(r, candidates, outcomes(2), 2)
    assert not any(p["admitted_exploratory_preference"] for p in control["preferences"])


@pytest.mark.parametrize(
    "fault", ["missing", "failed", "partial_turn", "no_audit", "duplicate", "stream", "nan"]
)
def test_missing_or_false_turn_evidence_cannot_become_a_complete_lesson(fault: str) -> None:
    r, values = root(), outcomes()
    if fault == "missing":
        values.pop()
    elif fault == "failed":
        values[0]["status"] = "failed"
    elif fault == "partial_turn":
        values[0]["turn_complete"] = False
    elif fault == "no_audit":
        values[0]["native_audit_valid"] = False
    elif fault == "duplicate":
        values.append(values[0])
    elif fault == "stream":
        values[0]["repeat"] = 8
    else:
        values[0]["training_return"] = float("nan")
    if fault in {"duplicate", "stream", "nan"}:
        with pytest.raises(ValueError):
            turn_lesson(r, freeze_candidates(r, references()), values, 8)
    else:
        assert not turn_lesson(r, freeze_candidates(r, references()), values, 8)[
            "comparison_complete"
        ]


def test_blocked_world_remains_an_incomplete_source_comparison() -> None:
    r = root()
    group = {"root_id": r["root_id"], "blocked": True, "candidates": []}
    assert not comparison_tasks([r], [group], 8, False)
    assert not turn_lesson(r, [], [], 8)["comparison_complete"]
