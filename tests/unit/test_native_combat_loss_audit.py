from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.native_combat_loss_audit import combat, inspect_case
from spireshift.native_shop_policy import CONTRACT


def public() -> dict[str, Any]:
    return {
        "candidates": [
            {
                "verb": "play",
                "label": "Free block card",
                "subject": {"properties": {"stats": {"block": 5}}},
            },
            {"verb": "end_turn", "label": "End turn"},
            {"verb": "use", "label": "Potion"},
        ],
        "context": {
            "persistent": {
                "player": {"hp": 5, "max_hp": 80, "potions": ["potion"]},
                "run": {"act": 1, "floor": 7},
            },
            "interaction": {
                "kind": "combat_turn",
                "content": {
                    "context": {
                        "encounter_type": "elite",
                        "round": 3,
                        "enemies": [{"definition_id": "ENEMY"}],
                        "player": {"block": 0, "energy": 0},
                    }
                },
            },
        },
    }


def case() -> dict[str, Any]:
    p = public()
    return {
        "status": "terminal",
        "victory": False,
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "maximum_act": 1,
        "maximum_floor": 7,
        "completed_acts": 0,
        "decisions": [
            {
                "public_input": p,
                "choice": {
                    "action_index": 1,
                    "policy_contract": CONTRACT,
                    "public_input_id": manifest_identifier(p),
                },
            }
        ],
    }


def test_public_opportunity_counts_are_not_counterfactual_mistake_labels() -> None:
    r = inspect_case(case())
    assert r["counts"]["end_with_play_available"] == 1
    assert r["counts"]["end_low_health_with_block_available"] == 1
    assert r["last_combat_decision"]["energy"] == 0  # Includes free legal actions.
    assert r["last_combat_is_death_cause_proven"] is False
    p = public()
    p["context"]["interaction"]["kind"] = "rest_site"
    assert combat(p, 0) is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("status", "failed"),
        ("privileged_fixture", True),
        ("recovered", True),
        ("native_ending_evidence_agrees", False),
    ],
)
def test_failed_privileged_recovered_or_unverified_games_rejected(key: str, value: Any) -> None:
    c = case()
    c[key] = value
    with pytest.raises(ValueError):
        inspect_case(c)


def test_behavior_and_public_input_seals_are_required() -> None:
    c = case()
    c["decisions"][0]["choice"]["policy_contract"] = "old-policy"
    with pytest.raises(ValueError):
        inspect_case(c)
    c = copy.deepcopy(case())
    c["decisions"][0]["public_input"]["context"]["persistent"]["player"]["hp"] = 80
    with pytest.raises(ValueError):
        inspect_case(c)
