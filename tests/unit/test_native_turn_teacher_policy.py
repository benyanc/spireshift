from __future__ import annotations

import copy
import random
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_later_teacher import public as later_public

from spireshift.core.manifest import manifest_identifier
from spireshift.native_action_context import policy
from spireshift.native_context_cache import cached_model
from spireshift.native_rest_exploration import choose, verified_samples
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_turn_teacher_audit import reconstruct
from spireshift.native_turn_teacher_policy import (
    CONTRACT,
    TurnChooser,
    boundary,
    random_seed,
    validate_plan,
)


def public() -> dict[str, Any]:
    p = later_public()
    p["context"]["persistent"]["run"]["act_definition_id"] = "UNDERDOCKS"
    p["context"]["interaction"]["content"]["context"]["kind"] = "combat"
    p["context"]["interaction"]["content"]["context"]["enemies"][0]["hp"] = 20
    return p


def root() -> dict[str, Any]:
    p = public()
    logs = policy(p, cached_model(model()), score(), 0.8)[2]
    return {
        "root_id": "public-source-root",
        "public_input": p,
        "public_input_id": manifest_identifier(p),
        "prefix": [],
        "native_seed": "FROZEN-TRAIN-WORLD",
        "numerical_seed": 2,
        "reference_action": max(range(len(logs)), key=lambda j: (logs[j], -j)),
    }


def selection(p: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(p)
    value["context"]["interaction"] = {
        "kind": "card_selection",
        "content": {
            "context": {"kind": "selection"},
            "surface": {"min_select": 1, "max_select": 1},
        },
    }
    value["candidates"] = [copy.deepcopy(p["candidates"][0])]
    value["candidates"][0]["verb"] = "select"
    return value


def next_round(p: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(p)
    value["context"]["interaction"]["content"]["context"]["round"] += 1
    return value


def chooser(r: dict[str, Any], **kwargs: Any) -> TurnChooser:
    options: dict[str, Any] = {
        "first_action": 0,
        "repeat": 0,
        "temperature": 0.8,
        "proposal_temperature": 1.2,
    }
    options.update(kwargs)
    return TurnChooser(r, cached_model(model()), score(), **options)


def example() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    r = root()
    prefix = copy.deepcopy(r["public_input"])
    prefix["context"]["persistent"]["player"]["gold"] += 1
    r["prefix"] = [{"public_input_id": manifest_identifier(prefix), "action_index": 0}]
    end = copy.deepcopy(r["public_input"])
    end["candidates"] = [end["candidates"][-1]]
    c = chooser(r)
    rows = [prefix, r["public_input"], selection(r["public_input"]), end, next_round(end)]
    decisions = [{"public_input": p, "choice": c(p)} for p in rows]
    assert c.plan is not None
    case = {
        "status": "terminal",
        "seed": r["native_seed"],
        "recovered": False,
        "privileged_fixture": False,
        "native_ending_evidence_agrees": True,
        "policy_contract": CONTRACT,
        "privileged_fixed_world_teacher": True,
        "ordinary_PPO_eligible": False,
        "decisions": decisions,
    }
    return r, c.plan, case, {"stage": "proposal", "first_action": 0, "repeat": 0}


def test_nested_choices_are_part_of_the_turn_and_freeze_precedes_continuation() -> None:
    r = root()
    frozen = []
    c = chooser(r, on_plan=lambda p: frozen.append(p))
    assert c(r["public_input"])["teacher_phase"] == "candidate_turn_generation"
    c(selection(r["public_input"]))
    assert not c.turn_complete and not frozen
    selected = c(next_round(r["public_input"]))
    assert c.turn_complete and frozen == [c.plan]
    assert selected["teacher_phase"] == "public_policy_continuation"
    assert c.plan is not None and len(c.plan["steps"]) == 2
    assert c.plan["boundary"]["kind"] == "native_public_round_changed"
    validate_plan(c.plan, r)


def test_end_turn_triggered_selection_is_resolved_before_the_boundary() -> None:
    r = root()
    c = chooser(r, first_action=2)
    assert c(r["public_input"])["action_index"] == 2
    assert not c.turn_complete
    c(selection(r["public_input"]))
    assert not c.turn_complete
    c(next_round(r["public_input"]))
    assert c.plan is not None and len(c.plan["steps"]) == 2


@pytest.mark.parametrize("ending", ["kill", "terminal", "new_room", "automatic_round"])
def test_native_endings_do_not_require_an_invented_end_turn_action(ending: str) -> None:
    r, c = root(), chooser(root())
    c(r["public_input"])
    if ending == "terminal":
        c.finish({"status": "terminal", "terminal_public_key": "public-end", "victory": False})
    else:
        after = next_round(r["public_input"])
        if ending == "kill":
            after["context"]["interaction"] = {
                "kind": "reward_claim",
                "content": {"context": {"kind": "reward_flow"}},
            }
        elif ending == "new_room":
            after["context"]["persistent"]["run"]["floor"] += 1
        c(after)
    assert c.turn_complete and c.plan is not None
    assert len(c.plan["steps"]) == 1


def test_ambiguous_ownership_and_unknown_round_are_refused() -> None:
    p, changed = public(), public()
    changed["context"]["interaction"] = {"kind": "new_modal", "content": {}}
    with pytest.raises(ValueError, match="ownership"):
        boundary(p, changed)
    p["context"]["interaction"]["content"]["context"]["round"] = None
    with pytest.raises(ValueError, match="public round"):
        chooser({**root(), "public_input": p})


def test_exact_replay_includes_all_choices_targets_and_turn_boundary() -> None:
    r, plan, case, task = example()
    original = copy.deepcopy(case)
    cfg = {"temperature": 0.8, "proposal_temperature": 1.2}
    assert reconstruct(case, r, task, cached_model(model()), score(), cfg, plan) == 5
    replay = chooser(r, plan=plan)
    for row in case["decisions"]:
        actual = replay(row["public_input"])
        if actual["teacher_phase"] != "public_policy_continuation":
            assert actual["action_index"] == row["choice"]["action_index"]
    assert replay.plan == plan and replay.turn_complete
    assert case == original


@pytest.mark.parametrize("fault", ["cost", "target", "root", "short", "boundary", "private"])
def test_changed_or_truncated_frozen_sequences_cannot_silently_fall_back(fault: str) -> None:
    r, plan, case, _ = example()
    if fault == "short":
        plan["steps"] = plan["steps"][:1]
    elif fault == "boundary":
        plan["boundary"]["public_input_id"] = "different"
    elif fault == "private":
        plan["steps"][0]["public_input"]["context"]["native_seed"] = "hidden"
    plan["plan_id"] = manifest_identifier({k: v for k, v in plan.items() if k != "plan_id"})
    with pytest.raises(ValueError):
        c = chooser(r, plan=plan)
        for i, row in enumerate(case["decisions"]):
            value = copy.deepcopy(row["public_input"])
            if (fault in {"cost", "target"} and i == 2) or (fault == "root" and i == 1):
                if fault == "cost":
                    value["candidates"][0]["subject"] = {
                        "public_slot": 1,
                        "role": "playable_card",
                        "properties": {"cost": "0"},
                    }
                elif fault == "target":
                    value["candidates"][0]["arguments"] = [
                        {"role": "target", "entity": {"public_slot": 2, "role": "enemy"}}
                    ]
                else:
                    value["candidates"][0]["label"] = "different root"
            c(value)


def test_turn_cap_never_invents_an_end_or_eligible_partial_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spireshift import native_turn_teacher_policy as module

    monkeypatch.setattr(module, "MAX_STEPS", 2)
    r = root()
    c = chooser(r)
    c(r["public_input"])
    no_end = copy.deepcopy(r["public_input"])
    no_end["candidates"].pop()
    c(no_end)
    with pytest.raises(ValueError, match="decision cap"):
        c(no_end)
    assert not c.turn_complete and c.plan is None
    c.finish({"status": "failed"})
    assert c.plan is None


def test_resolved_end_turn_can_end_at_same_displayed_round() -> None:
    r = root()
    c = chooser(r, first_action=2)
    c(r["public_input"])
    c(selection(r["public_input"]))
    c(r["public_input"])
    assert c.turn_complete and c.plan is not None
    assert c.plan["boundary"]["kind"] == "native_end_turn_returned_to_combat"
    assert len(c.plan["steps"]) == 2


def test_plan_storage_cap_never_leaves_a_partially_admitted_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spireshift import native_turn_teacher_policy as module

    r = root()
    monkeypatch.setattr(module, "MAX_PLAN_BYTES", 20)
    c = chooser(r)
    with pytest.raises(ValueError, match="storage cap"):
        c(r["public_input"])
    assert not c.turn_complete and c.plan is None


def test_continuation_randomness_is_separate_from_proposal_length_and_sampling() -> None:
    r = root()
    c = chooser(r, repeat=3)
    c(r["public_input"])
    c(selection(r["public_input"]))
    after = next_round(r["public_input"])
    actual = c(after)
    expected = choose(
        cached_model(model()),
        score(),
        after,
        ShopNavigation(),
        random.Random(random_seed(r["root_id"], "continuation", 3)),
        0.8,
        0.0,
    )
    assert actual["action_index"] == expected["action_index"]
    assert actual["log_probability"] == expected["log_probability"]
    assert random_seed(r["root_id"], "proposal", 3) != random_seed(r["root_id"], "continuation", 3)


@pytest.mark.parametrize("fault", ["probability", "value", "PPO", "world", "phase"])
def test_saved_behavior_audit_rejects_wrong_streams_and_teacher_relabeling(fault: str) -> None:
    r, plan, case, task = example()
    if fault in {"probability", "value"}:
        key = "log_probability" if fault == "probability" else "value"
        case["decisions"][-1]["choice"][key] += 0.01
    elif fault == "PPO":
        case["ordinary_PPO_eligible"] = True
    elif fault == "world":
        case["seed"] = "different world"
    else:
        case["decisions"][2]["choice"]["teacher_phase"] = "public_policy_continuation"
    with pytest.raises(ValueError):
        reconstruct(
            case,
            r,
            task,
            cached_model(model()),
            score(),
            {"temperature": 0.8, "proposal_temperature": 1.2},
            plan,
        )


def test_forced_complete_turns_cannot_be_used_as_ordinary_PPO_games() -> None:
    _, _, case, _ = example()
    with pytest.raises(ValueError):
        verified_samples(case, cached_model(model()), score(), 0.03, 0.8, 0.0)
