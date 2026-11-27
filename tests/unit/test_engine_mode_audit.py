"""Static coverage must not be mistaken for fully reviewed, qualified game behavior."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.engine_mode_audit import TARGETS, assess_reviews, review_key, validate_inventory


def site(token: int = 0x06000001, offset: int = 0) -> dict[str, Any]:
    return {
        "method_token": token,
        "il_offset": offset,
        "declaring_type": "Synthetic.Owner+<Choose>d__2",
        "method": "MoveNext",
        "method_il_sha256": "a" * 64,
        "signature_sha256": "b" * 64,
        "target_type": sorted(TARGETS)[0],
        "target_member": "get_IsActive",
        "opcode": "call",
    }


def inventory() -> dict[str, Any]:
    return {
        "schema_version": "managed-mode-reference-inventory-v1",
        "assembly_sha256": "c" * 64,
        "target_types": sorted(TARGETS),
        "game_assembly_executed": False,
        "undecoded_bodies": 0,
        "method_bodies": 2,
        "methods": 3,
        "decoded_instructions": 20,
        "sites": [site()],
    }


def review() -> dict[str, Any]:
    return {
        "method": "Synthetic.Owner.Choose",
        "method_il_sha256": ["a" * 64],
        "classification": "choice_or_lifecycle_seam",
        "rationale": "Test mode selects a choice without asking the policy.",
    }


def test_async_method_review_preserves_its_owner_and_unknown_methods() -> None:
    assert review_key(site()) == "Synthetic.Owner.Choose"
    other = {**site(0x06000002), "declaring_type": "Synthetic.Other", "method": "Create"}
    report = assess_reviews([site(), other], [review()])
    assert report["references"] == 2 and report["reviewed_references"] == 1
    assert report["unreviewed_method_groups"] == ["Synthetic.Other.Create"]
    assert report["semantic_review_complete"] is False
    assert len(report["findings"]) == 1
    assert report["training_allowed"] is report["mechanics_qualified"] is False


def test_fully_reviewed_static_inventory_still_cannot_admit_training() -> None:
    report = assess_reviews([site()], [review()])
    assert report["semantic_review_complete"] is True
    assert report["training_allowed"] is report["mechanics_qualified"] is False


@pytest.mark.parametrize("change", ["hash", "reason", "classification", "unknown", "duplicate"])
def test_unbound_stale_or_blank_reviews_fail(change: str) -> None:
    value = review()
    if change == "hash":
        value["method_il_sha256"] = ["d" * 64]
    elif change == "reason":
        value["rationale"] = " "
    elif change == "classification":
        value["classification"] = "probably_safe"
    elif change == "unknown":
        value["method"] = "Unknown.Owner.Choose"
    with pytest.raises(ValueError):
        assess_reviews([site()], [value, value] if change == "duplicate" else [value])


@pytest.mark.parametrize("change", ["assembly", "partial", "executed", "duplicate", "operand"])
def test_wrong_assembly_partial_or_malformed_reference_inventory_fails(change: str) -> None:
    value = copy.deepcopy(inventory())
    assert validate_inventory(value, "c" * 64) == value["sites"]
    if change == "assembly":
        value["assembly_sha256"] = "d" * 64
    elif change == "partial":
        value["undecoded_bodies"] = 1
    elif change == "executed":
        value["game_assembly_executed"] = True
    elif change == "duplicate":
        value["sites"].append(site())
    else:
        value["sites"][0]["method_token"] = 0x02000001
    with pytest.raises(ValueError):
        validate_inventory(value, "c" * 64)
