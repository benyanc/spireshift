from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_systematic_audit_v1 import coverage_ledger
from spireshift.native_systematic_live_v1 import (
    ScriptedPolicy,
    compare_frames,
    effects,
    select_action,
)


def frame(value: int = 0, energy: int = 3) -> dict[str, Any]:
    return {
        "binding_id": "binding",
        "observation": {"runtime_instance_id": "runtime", "snapshot_id": "snapshot"},
        "actions": [{"key": "end", "raw_index": 0, "bound_action_id": "bound"}],
        "public_input": {
            "context": {
                "persistent": {
                    "player": {"relics": [{"definition_id": "HAPPY_FLOWER", "counter": value}]}
                },
                "interaction": {"content": {"context": {"player": {"energy": energy}}}},
            },
            "candidates": [
                {"verb": "end_turn", "label": "End turn", "subject": None, "arguments": []}
            ],
        },
    }


def test_inventory_and_runtime_observation_do_not_grant_effect_coverage() -> None:
    rows = coverage_ledger(["rest_site", "combat_turn"], {"rest_site": 22}, {"rest_site": 7})
    assert rows[0]["saved_frames"] == 22
    assert rows[0]["actual_producer_pairs"] == 7
    assert not any(row["live_effects_qualified"] for row in rows)
    assert "actual saved runtime observation" in rows[1]["remaining"]


def test_comparison_collects_every_first_state_gap_without_realigning() -> None:
    first = frame()
    changed = frame(2, 7)
    result = compare_frames([first, first], [changed, first])
    assert not result["equal"]
    assert result["matching_states"] == 0
    assert len(result["first_difference"]["all_difference_paths"]) == 2
    assert not result["later_divergent_states_realigned"]


def test_missing_final_successor_cannot_pass_comparison() -> None:
    assert not compare_frames([frame(), frame()], [frame()])["equal"]


def test_script_requires_current_exact_control_and_delivered_receipt() -> None:
    policy = ScriptedPolicy(["end_turn"])
    policy.choose(frame())
    with pytest.raises(ValueError, match="retry"):
        policy.choose(frame())
    with pytest.raises(ValueError, match="uncertain"):
        policy.acknowledge({"delivery": "not_delivered"})
    assert policy.decisions == 0
    policy.acknowledge(
        {
            "delivery": "delivered",
            "binding_id": "binding",
            "bound_action_id": "bound",
            "runtime_instance_id": "runtime",
            "before_snapshot_id": "snapshot",
            "successor_snapshot_id": "after",
        }
    )
    policy.observe_successor(frame(1))
    assert policy.decisions == 1 and len(policy.frames) == 2


@pytest.mark.parametrize("instruction", ["HEAL", "SMITH", "confirm_card", "proceed"])
def test_script_never_substitutes_a_fallback_action(instruction: str) -> None:
    with pytest.raises(ValueError, match="unavailable"):
        select_action(frame(), instruction)


def test_happy_flower_effect_requires_both_cycle_and_energy() -> None:
    case = {"family": "combat_turn", "instructions": ["end_turn"] * 3}
    rows = [frame(1), frame(2), frame(0, 4), frame(1)]
    assert effects(case, rows)["rollovers"] == 1
    with pytest.raises(ValueError, match="energy"):
        effects(case, [frame(1), frame(2), frame(0, 3), frame(1)])
    with pytest.raises(ValueError, match="settled"):
        effects(case, [frame(1), frame(2), frame(3, 4), frame(1)])
    with pytest.raises(ValueError, match="final"):
        effects(case, rows[:-1])
