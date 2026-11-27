from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.native_render_inputs import verify_plan


def plan() -> dict[str, Any]:
    return {
        "schema_version": "native-render-context-config-v1",
        "stage": "source_saved_checks",
        "training_allowed": False,
        "automatic_follow_up": False,
        "whole_run_cpu_seconds": 128,
        "maximum_decisions": 384,
        "maximum_pair_wall_seconds": 600,
        "implementation": {"a": "pin"},
        "resource_limits": {
            "wall_seconds": 290,
            "cpu_seconds": 900,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 4000000000,
        },
    }


def test_render_plan_keeps_fixed_gameplay_and_short_limits() -> None:
    verify_plan(plan(), {"a": "pin"})


@pytest.mark.parametrize(
    "field,value",
    [
        ("training_allowed", True),
        ("automatic_follow_up", True),
        ("whole_run_cpu_seconds", 129),
        ("maximum_decisions", 385),
        ("maximum_pair_wall_seconds", 601),
    ],
)
def test_render_plan_rejects_silent_budget_or_admission_change(field: str, value: Any) -> None:
    cfg = plan()
    cfg[field] = value
    with pytest.raises(ValueError):
        verify_plan(cfg, {"a": "pin"})


def test_render_plan_rejects_unpinned_source_or_changed_cap() -> None:
    cfg = plan()
    with pytest.raises(ValueError):
        verify_plan(cfg, {"a": "different"})
    cfg = copy.deepcopy(cfg)
    cfg["resource_limits"]["wall_seconds"] = 300
    with pytest.raises(ValueError):
        verify_plan(cfg, {"a": "pin"})
