from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.native_credit_comparison import require_matched_recipes
from spireshift.native_credit_training import CREDIT_ID


def recipes() -> tuple[dict[str, Any], dict[str, Any]]:
    a: dict[str, Any] = {
        "stage": "bounded_policy_only_pilot",
        "workspace": "artifacts/legacy",
        "admission": {"id": "legacy-control"},
        "development_comparison": "initial_vs_best_trained",
        "network": {"dimension": 512},
        "learning": {"temperature": 0.8},
    }
    b = copy.deepcopy(a)
    b["workspace"] = "artifacts/crossfit"
    b["admission"] = {"id": "new-control"}
    b["learning"]["credit_assignment"] = {"id": CREDIT_ID}
    return a, b


def test_matched_comparison_permits_only_baseline_and_evidence_destinations() -> None:
    a, b = recipes()
    require_matched_recipes(a, b)
    b["learning"]["temperature"] = 0.7
    with pytest.raises(ValueError, match="other than"):
        require_matched_recipes(a, b)


@pytest.mark.parametrize(
    "key,value",
    [
        ("network", {"dimension": 1024}),
        ("development_comparison", "initial_vs_incumbent"),
        ("seed_manifest", "different"),
        ("resource_limits", {"wall_seconds": 999}),
    ],
)
def test_actor_evaluation_data_and_compute_cannot_change_with_treatment(
    key: str, value: Any
) -> None:
    a, b = recipes()
    b[key] = value
    with pytest.raises(ValueError):
        require_matched_recipes(a, b)
