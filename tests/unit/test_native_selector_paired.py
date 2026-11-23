from __future__ import annotations

import copy
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_native import EXE_RELATIVE
from spireshift.native_selector_official_reset import OWNED, validate_inventory
from spireshift.native_selector_paired_contract import PairedPolicy


def frame() -> dict[str, Any]:
    return {
        "binding_id": "current",
        "observation": {"runtime_instance_id": "runtime", "snapshot_id": "before"},
        "public_input": {"hp": 48, "candidates": [{"verb": "cancel"}]},
        "actions": [{"key": "cancel-key", "bound_action_id": "cancel-current"}],
    }


def test_pair_uses_current_official_binding_without_normalizing_a_difference() -> None:
    native, official = frame(), frame()
    official["binding_id"] = "official-binding"
    official["actions"][0]["bound_action_id"] = "official-current"
    policy = PairedPolicy([native, native], [0])
    choice = policy.choose(official)
    assert choice["binding_id"] == "official-binding"
    assert choice["bound_action_id"] == "official-current"
    assert policy.decisions == 0
    with pytest.raises(ValueError, match="Unowned"):
        policy.choose(official)


@pytest.mark.parametrize("change", ["hp", "candidate", "action_key"])
def test_first_public_difference_prevents_delivery(change: str) -> None:
    native, official = frame(), frame()
    if change == "hp":
        official["public_input"]["hp"] = 47
    elif change == "candidate":
        official["public_input"]["candidates"].append({"verb": "skip"})
    else:
        official["actions"][0]["key"] = "other-choice"
    policy = PairedPolicy([native, native], [0])
    with pytest.raises(ValueError, match="differs"):
        policy.choose(official)
    assert policy.pending is None and policy.decisions == 0
    assert policy.difference and policy.difference["decision"] == 0


def acknowledgement() -> dict[str, str]:
    return {
        "delivery": "delivered",
        "binding_id": "current",
        "bound_action_id": "cancel-current",
        "runtime_instance_id": "runtime",
        "before_snapshot_id": "before",
        "successor_snapshot_id": "after",
    }


@pytest.mark.parametrize(
    "key",
    [
        "delivery",
        "binding_id",
        "bound_action_id",
        "runtime_instance_id",
        "before_snapshot_id",
        "successor_snapshot_id",
    ],
)
def test_cross_owner_or_uncertain_receipt_cannot_advance(key: str) -> None:
    value = frame()
    policy = PairedPolicy([value, value], [0])
    policy.choose(value)
    ack = acknowledgement()
    ack[key] = "" if key == "successor_snapshot_id" else "wrong"
    with pytest.raises(ValueError, match="Uncertain"):
        policy.acknowledge(ack)
    assert policy.decisions == 0 and policy.pending is not None


def test_final_difference_is_retained_while_allowing_clean_official_shutdown() -> None:
    value = frame()
    policy = PairedPolicy([value, value], [0])
    policy.choose(value)
    policy.acknowledge(acknowledgement())
    after = copy.deepcopy(value)
    after["public_input"]["hp"] = 47
    policy.observe_successor(after)
    assert policy.difference and policy.difference["decision"] == 1
    assert policy.frames[-1] == after


def inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    baseline: list[dict[str, Any]] = [
        {"path": EXE_RELATIVE, "sha256": "original", "size": 10, "mode": 0o444},
        {"path": "official-data", "sha256": "original-data", "size": 20, "mode": 0o444},
    ]
    current = copy.deepcopy(baseline)
    current[0]["mode"] |= 0o111
    current.extend({"path": name, "sha256": "owned", "size": 1, "mode": 0o600} for name in OWNED)
    return baseline, current


def test_inspected_reset_accepts_only_original_bytes_and_five_declared_additions() -> None:
    baseline, current = inventory()
    before = copy.deepcopy((baseline, current))
    validate_inventory(baseline, current)
    assert (baseline, current) == before


@pytest.mark.parametrize(
    "change",
    [
        "original_bytes",
        "missing_original",
        "unknown_addition",
        "missing_addition",
        "permissions",
        "duplicate",
    ],
)
def test_inspected_reset_cannot_hide_other_game_changes(change: str) -> None:
    baseline, current = inventory()
    if change == "original_bytes":
        current[0]["sha256"] = "changed"
    elif change == "missing_original":
        current.pop(1)
    elif change == "unknown_addition":
        current.append({"path": "unknown", "sha256": "x", "size": 1, "mode": 0o600})
    elif change == "missing_addition":
        current.pop()
    elif change == "permissions":
        current[1]["mode"] |= 0o222
    else:
        current.append(current[0])
    with pytest.raises(ValueError):
        validate_inventory(baseline, current)


def test_official_local_factor_requires_zero_native_inputs() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for official completion evidence")
    result = subprocess.run(
        [node, "--test", "scripts/engine-selector-paired-contract-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
