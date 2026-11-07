from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.native_credit_training import CREDIT_ID
from spireshift.native_input_normalization import QUARTER
from spireshift.native_normalization_comparison import require_matched_recipes


def recipes() -> tuple[dict[str, Any], dict[str, Any]]:
    a: dict[str, Any] = {
        "stage": "bounded_policy_only_pilot",
        "workspace": "artifacts/unscaled",
        "admission": "first",
        "development_comparison": "initial_vs_best_trained",
        "network": {"dimension": 512, "hidden_units": 32, "seed": 0},
        "learning": {"credit_assignment": {"id": CREDIT_ID}, "ppo": {"actor_learning_rate": 0.001}},
    }
    b = copy.deepcopy(a)
    b["workspace"] = "artifacts/normalized"
    b["admission"] = "second"
    b["network"]["input_normalization"] = QUARTER
    b["input_normalization_checks"] = {"path": "checked", "id": "passed"}
    return a, b


def test_normalization_is_the_only_permitted_treatment() -> None:
    a, b = recipes()
    require_matched_recipes(a, b)
    b["network"]["hidden_units"] = 64
    with pytest.raises(ValueError, match="other than"):
        require_matched_recipes(a, b)


@pytest.mark.parametrize(
    "key,value",
    [
        ("seed_manifest", "different"),
        ("resource_limits", {"wall_seconds": 999}),
        ("development_comparison", "initial_vs_incumbent"),
    ],
)
def test_seed_compute_and_evaluation_rules_stay_matched(key: str, value: Any) -> None:
    a, b = recipes()
    b[key] = value
    with pytest.raises(ValueError):
        require_matched_recipes(a, b)


def test_value_credit_and_initial_numeric_weights_cannot_change_with_normalization() -> None:
    for change in ("credit", "seed", "rate"):
        a, b = recipes()
        if change == "credit":
            b["learning"].pop("credit_assignment")
        elif change == "seed":
            b["network"]["seed"] = 1
        else:
            b["learning"]["ppo"]["actor_learning_rate"] = 0.002
        with pytest.raises(ValueError):
            require_matched_recipes(a, b)
