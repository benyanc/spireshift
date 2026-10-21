from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_combat_planning_policy import reward
from test_native_turn_teacher_policy import public, selection

from spireshift.native_action_context import policy
from spireshift.native_combat_behavior_policy import Chooser, reconstruct
from spireshift.native_context_cache import cached_model


def choose(arm: str = "sampled") -> Chooser:
    return Chooser(cached_model(model()), score(), "FRESH-WORLD", arm)


def noncombat(kind: str = "rest_site", floor: int = 8) -> dict[str, Any]:
    value = reward(public())
    value["context"]["persistent"]["run"]["floor"] = floor
    value["context"]["interaction"]["kind"] = kind
    return value


def test_greedy_is_exact_argmax_without_fake_softmax_behavior_probability() -> None:
    p = public()
    c = choose("greedy")
    logs = policy(p, c.model, c.score, 0.8)[2]
    result = c(p)
    assert result["action_index"] == max(range(len(logs)), key=lambda i: (logs[i], -i))
    assert result["behavior"] == "greedy_combat" and result["log_probability"] == 0.0
    assert result["policy_log_probability"] == logs[result["action_index"]]
    assert not result["draw_used"] and not result["ordinary_PPO_eligible"]


def test_noncombat_is_matched_despite_extra_combat_and_nested_choices() -> None:
    a, b = choose(), choose("greedy")
    a(public())
    for _ in range(7):
        b(public())
        b(selection(public()))
    ra, rb = a(noncombat()), b(noncombat())
    assert {k: v for k, v in ra.items()} == rb
    assert ra["behavior"] == "sampled_noncombat" and not ra["combat_owned"]


def test_noncombat_streams_are_separate_per_room_and_family() -> None:
    a, b = choose(), choose("greedy")
    a(noncombat("reward_claim"))
    a(noncombat("reward_claim"))
    assert a(noncombat()) == b(noncombat())
    a(noncombat())
    assert a(noncombat(floor=9)) == b(noncombat(floor=9))


def test_same_noncombat_draw_does_not_force_same_action_in_different_public_states() -> None:
    a, b = choose(), choose("greedy")
    first, second = noncombat(), noncombat()
    second["context"]["persistent"]["player"]["hp"] = 1
    left, right = a(first), b(second)
    assert left["draw_key"] == right["draw_key"] and left["draw"] == right["draw"]
    assert left["effective_input_id"] != right["effective_input_id"]


def test_combat_nested_choices_end_only_at_observed_exit_or_new_room() -> None:
    c = choose("greedy")
    assert not c(selection(public()))["combat_owned"]
    assert c(public())["combat_owned"]
    assert c(selection(public()))["nested_combat_selection"]
    assert not c(reward(public()))["combat_owned"]
    assert not c(selection(public()))["combat_owned"]
    c(public())
    assert not c(noncombat(floor=20))["combat_owned"]


def test_unknown_active_combat_owner_fails_without_guessing() -> None:
    c = choose()
    c(public())
    p = public()
    p["context"]["interaction"] = {"kind": "unknown_modal", "content": {}}
    with pytest.raises(ValueError, match="ownership"):
        c(p)


def test_shop_navigation_does_not_advance_noncombat_policy_draws() -> None:
    p = noncombat("shop_inventory")
    p["context"]["interaction"]["content"] = {"surface": {"inventory_open": False}}
    p["candidates"] = [
        {
            "verb": "activate",
            "label": "Open inventory",
            "subject": None,
            "arguments": [],
            "history": {"shop_inspected": False},
        },
        {
            "verb": "close",
            "label": "Leave shop",
            "subject": None,
            "arguments": [],
            "history": {"shop_inspected": False},
        },
    ]
    a, b = choose(), choose("greedy")
    result = a(p)
    assert result["navigation_only"] and result["draw"] is None and result["action_index"] == 0
    assert a(noncombat()) == b(noncombat())


@pytest.mark.parametrize("arm", ["sampled", "greedy"])
def test_saved_behavior_reconstructs_all_draws_inputs_and_probabilities(arm: str) -> None:
    c = choose(arm)
    before = c.model.as_dict()
    case: dict[str, Any] = {
        "policy_contract": "public_combat_greedy_vs_sampled_matched_noncombat_v1",
        "ordinary_PPO_eligible": False,
        "privileged_fixture": False,
        "privileged_fixed_world_teacher": False,
        "recovered": False,
        "decisions": [
            {"public_input": p, "choice": c(p)}
            for p in (public(), selection(public()), reward(public()), noncombat())
        ],
    }
    result = reconstruct(case, c.model, c.score, "FRESH-WORLD", arm)
    assert result["decisions_reconstructed"] == 4 and result["nested_combat_selections"] == 1
    assert len(result["noncombat"]) == 2 and c.model.as_dict() == before
    case["decisions"][-1]["choice"]["draw"] += 0.01
    with pytest.raises(ValueError, match="randomness"):
        reconstruct(case, c.model, c.score, "FRESH-WORLD", arm)


@pytest.mark.parametrize("fault", ["private", "probability", "owner", "seed", "ppo", "teacher"])
def test_misbound_or_leaking_behavior_cannot_pass_saved_verification(fault: str) -> None:
    c, p = choose(), public()
    case: dict[str, Any] = {
        "policy_contract": "public_combat_greedy_vs_sampled_matched_noncombat_v1",
        "ordinary_PPO_eligible": False,
        "privileged_fixture": False,
        "privileged_fixed_world_teacher": False,
        "recovered": False,
        "decisions": [{"public_input": copy.deepcopy(p), "choice": c(p)}],
    }
    if fault == "private":
        case["decisions"][0]["public_input"]["context"]["hidden_rng"] = 5
    elif fault == "probability":
        case["decisions"][0]["choice"]["log_probability"] += 0.1
    elif fault == "owner":
        case["decisions"][0]["choice"]["combat_owned"] = False
    elif fault == "ppo":
        case["ordinary_PPO_eligible"] = True
    elif fault == "teacher":
        case["privileged_fixed_world_teacher"] = True
    with pytest.raises(ValueError):
        reconstruct(
            case, c.model, c.score, "OTHER" if fault == "seed" else "FRESH-WORLD", "sampled"
        )
