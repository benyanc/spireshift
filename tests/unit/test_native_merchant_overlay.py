from __future__ import annotations

import copy
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift import native_merchant_overlay_checks_v1 as checks
from spireshift.native_mixed_handoff_inputs_v1 import cases as original_cases
from spireshift.native_mixed_handoff_inputs_v5 import cases
from spireshift.native_selector_lifecycle_trace import Trace


def test_replacement_and_effect_probe_are_fresh_and_leave_unstarted_worlds_fixed() -> None:
    previous = {"cases": original_cases()}
    before = copy.deepcopy(previous)
    current = cases(previous)
    assert previous == before
    assert len(current) == 8
    assert current[2:] == previous["cases"][6:]
    assert {row["seed"] for row in current[:2]}.isdisjoint(row["seed"] for row in previous["cases"])
    assert current[1] == {**previous["cases"][5], "seed": "SP1RESH1FTA8MH5C006"}


def test_map_target_scope_and_native_operands() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for projection checks")
    run = subprocess.run(
        [node, "--test", "scripts/engine-merchant-overlay-surface-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert run.returncode == 0, run.stdout + run.stderr


@pytest.mark.parametrize("fault", [None, "extra_target", "missing_action", "wrong_merchant"])
def test_public_target_checks_reject_conflicting_owners(
    monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    raw: dict[str, Any] = {
        "player": {
            "potions": [
                {
                    "id": "FOUL_POTION",
                    "can_use": True,
                    "valid_target_refs": ["native-current-merchant"],
                }
            ]
        }
    }
    visible = {"definition_id": "FOUL_POTION", "can_use": True, "target_entity_ids": ["merchant"]}
    actions = [{"verb": "use", "subject": {"properties": {"definition_id": "FOUL_POTION"}}}]
    merchant = {"role": "merchant", "referent_id": "merchant"}
    if fault == "extra_target":
        raw["player"]["potions"][0]["valid_target_refs"].append("stale")
    elif fault == "missing_action":
        actions.clear()
    elif fault == "wrong_merchant":
        merchant["referent_id"] = "different-owner"
    trace = cast(
        Trace,
        SimpleNamespace(
            current={
                "snapshot": {
                    "referents": [merchant],
                    "interaction": {"content": {"surface": {"potion_states": [visible]}}},
                }
            },
            frame={"public_input": {"candidates": actions}},
        ),
    )
    monkeypatch.setattr(checks, "native_state", lambda _: raw)
    if fault is None:
        checks.merchant_target(trace, True)
    else:
        with pytest.raises(ValueError, match="current operand"):
            checks.merchant_target(trace, True)
