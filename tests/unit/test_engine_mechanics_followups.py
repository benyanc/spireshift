from __future__ import annotations

import argparse
import copy
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_mechanics_followups import assert_completed_sweep
from spireshift.engine_qualification_cli import add_engine_parser


def evidence() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    cfg = {"scope": "frozen-current-sweep"}
    specs = [{"case_id": "one"}, {"case_id": "two"}]
    rows = [
        {"spec": specs[0], "report_id": "case-one", "status": "effect_exercised"},
        {"spec": specs[1], "report_id": "case-two", "status": "observed_prerequisite_blocked"},
    ]
    plan = {"plan_id": "plan", "cases": specs}
    report = {
        "config_id": manifest_identifier(cfg),
        "plan_id": "plan",
        "inventory_complete": True,
        "known_gaps": [],
        "not_attempted_cases": 0,
        "planned_cases": 2,
        "completed_cases": 2,
        "case_reports": ["case-one", "case-two"],
    }
    return cfg, plan, report, rows


def test_actual_sweep_pass_is_required_before_conditional_followups() -> None:
    assert_completed_sweep(*evidence())


@pytest.mark.parametrize(
    "defect",
    [
        "in_flight",
        "failed_case_hidden",
        "wrong_plan",
        "changed_config",
        "wrong_reports",
        "missing_gap_inventory",
        "partial_inventory",
        "wrong_denominator",
        "missing_case",
        "wrong_case",
    ],
)
def test_assumptions_or_relabelled_failures_cannot_unlock_the_next_stage(defect: str) -> None:
    cfg, plan, report, rows = evidence()
    if defect == "in_flight":
        report["not_attempted_cases"] = 1
    elif defect == "failed_case_hidden":
        rows[0]["status"] = "failed"
    elif defect == "wrong_plan":
        report["plan_id"] = "other"
    elif defect == "changed_config":
        cfg["scope"] = "changed"
    elif defect == "wrong_reports":
        report["case_reports"].reverse()
    elif defect == "missing_gap_inventory":
        report.pop("known_gaps")
    elif defect == "partial_inventory":
        report["inventory_complete"] = False
    elif defect == "wrong_denominator":
        report["planned_cases"] = 1
    elif defect == "missing_case":
        rows.pop()
    else:
        rows[0] = copy.deepcopy(rows[0])
        rows[0]["spec"]["case_id"] = "replacement"
    with pytest.raises(ValueError, match="full repaired sweep must finish"):
        assert_completed_sweep(cfg, plan, report, rows)


def test_followup_cli_does_not_need_node_or_allow_launch_for_saved_verification() -> None:
    parser = argparse.ArgumentParser()
    add_engine_parser(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(
        ["engine", "verify-mechanics-followups", "qualification.json", "followup.json"]
    )
    assert args.engine_command == "verify-mechanics-followups"
    assert not hasattr(args, "node")
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["engine", "check-mechanics-followups", "qualification.json", "followup.json"]
        )
