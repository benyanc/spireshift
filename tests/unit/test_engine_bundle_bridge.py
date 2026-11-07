from copy import deepcopy
from typing import Any

import pytest

from spireshift.engine_bundle_bridge import validate_bundle_cases
from spireshift.engine_connector import _evaluate_connector_checkpoint


def cases() -> dict[str, Any]:
    return {
        "cases": [
            {
                "case_id": f"seed-{seed}-pack-{index}-repeat-{repeat}",
                "seed": f"SEED{seed}",
                "index": index,
            }
            for seed in (1, 2)
            for index in (0, 1)
            for repeat in (1, 2)
        ]
    }


def test_bundle_repeats_are_not_independent_seeds() -> None:
    actual = validate_bundle_cases(cases())
    assert len(actual) == 8
    assert len({row["seed"] for row in actual}) == 2
    assert len({(row["seed"], row["index"]) for row in actual}) == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_id", "../escape"),
        ("seed", "bad seed"),
        ("index", True),
        ("index", "1"),
        ("index", -1),
        ("index", 2),
    ],
)
def test_invalid_bundle_cases_are_refused(field: str, value: Any) -> None:
    document = cases()
    document["cases"][0][field] = value
    with pytest.raises(ValueError):
        validate_bundle_cases(document)


def test_missing_duplicate_or_unbalanced_cases_are_refused() -> None:
    original = cases()
    for change in ("missing", "duplicate", "pack", "seed"):
        document = deepcopy(original)
        if change == "missing":
            document["cases"].pop()
        elif change == "duplicate":
            document["cases"][1] = deepcopy(document["cases"][0])
        elif change == "pack":
            document["cases"][0]["index"] = 1
        else:
            document["cases"][0]["seed"] = "SEED3"
        with pytest.raises(ValueError):
            validate_bundle_cases(document)


def test_bundle_gate_requires_preview_and_award_checks_beyond_menu_loading() -> None:
    normal = _evaluate_connector_checkpoint({})
    checks = {name: True for name in normal["errors"]}
    assert _evaluate_connector_checkpoint(checks)["status"] == "shipped_checkpoint_input_pass"
    bundle = _evaluate_connector_checkpoint(checks, bundle_bridge=True)
    assert bundle["status"] == "shipped_checkpoint_input_incomplete"
    assert set(bundle["errors"]) == {
        "bundle_all_snapshots_match",
        "bundle_all_actions_delivered",
        "bundle_preview_cancel_confirm_verified",
        "bundle_selected_cards_obtained",
    }
    for key in bundle["errors"]:
        checks[key] = True
    assert (
        _evaluate_connector_checkpoint(checks, bundle_bridge=True)["status"]
        == "shipped_checkpoint_input_pass"
    )
    checks["bundle_preview_cancel_confirm_verified"] = False
    assert _evaluate_connector_checkpoint(checks, bundle_bridge=True)["errors"] == [
        "bundle_preview_cancel_confirm_verified"
    ]


def test_bundle_scope_cannot_be_merged_with_unrelated_comparison_gates() -> None:
    with pytest.raises(ValueError):
        _evaluate_connector_checkpoint({}, bundle_bridge=True, journey=True)
