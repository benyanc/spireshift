from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_combat_behavior_policy import noncombat
from test_native_turn_teacher_policy import next_round, public, selection

from spireshift.core.manifest import manifest_identifier
from spireshift.native_action_context import policy
from spireshift.native_context_cache import cached_model
from spireshift.native_greedy_turn_policy import (
    CONTRACT,
    GreedyTurnChooser,
    SourceChooser,
    continuation_seed,
    reconstruct,
)
from spireshift.native_turn_teacher_policy import validate_plan


def seed(n: int = 2) -> dict[str, Any]:
    return {"id": n + 10, "seed": f"FRESH-TRAIN-{n}", "numerical_seed": n}


def root(n: int = 2) -> dict[str, Any]:
    c = SourceChooser(seed(n), cached_model(model()), score())
    c(public())
    assert c.root is not None
    return c.root


def turn(
    r: dict[str, Any], first: int | None = None, repeat: int = 0, **kwargs: Any
) -> GreedyTurnChooser:
    return GreedyTurnChooser(
        r, cached_model(model()), score(), first_action=first, repeat=repeat, **kwargs
    )


def plan(r: dict[str, Any], first: int | None) -> dict[str, Any]:
    c = turn(r, first)
    c(r["public_input"])
    c(next_round(r["public_input"]))
    assert c.plan is not None
    return c.plan


def test_source_root_is_first_public_eligible_and_sealed_before_future_outcomes() -> None:
    frozen: list[dict[str, Any]] = []
    c = SourceChooser(seed(), cached_model(model()), score(), frozen.append)
    earlier = public()
    earlier["context"]["persistent"]["run"]["floor"] = 4
    selected = c(earlier)
    assert c.root is None
    c(public())
    assert c.root is not None and frozen == [c.root]
    assert c.root["decision_index"] == 1
    assert c.root["prefix"] == [
        {"public_input_id": manifest_identifier(earlier), "action_index": selected["action_index"]}
    ]
    original = copy.deepcopy(c.root)
    later = public()
    later["context"]["persistent"]["run"]["floor"] = 12
    c(later)
    assert c.root == original and len(frozen) == 1
    assert not c.root["selection_uses_final_outcomes"]


@pytest.mark.parametrize("index,eligible", [(512, True), (513, False)])
def test_root_prefix_has_an_explicit_bound(
    index: int, eligible: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = SourceChooser(seed(), cached_model(model()), score())
    c.index = index
    c.prefix = [{"public_input_id": "public", "action_index": 0}] * min(index, 512)
    c(public())
    assert (c.root is not None) == eligible
    assert len(c.prefix) <= 512


def test_nested_complete_turn_is_sealed_before_greedy_continuation() -> None:
    r = root()
    frozen: list[dict[str, Any]] = []
    c = turn(r, 0, on_plan=frozen.append)
    c(r["public_input"])
    c(selection(r["public_input"]))
    assert not c.turn_complete and not frozen
    after = next_round(r["public_input"])
    selected = c(after)
    assert c.plan is not None and frozen == [c.plan]
    assert len(c.plan["steps"]) == 2
    validate_plan(c.plan, r)
    logs = policy(after, c.model, c.score, 0.8)[2]
    assert selected["action_index"] == max(range(len(logs)), key=lambda i: (logs[i], -i))
    assert selected["behavior"] == "greedy_combat"
    assert selected["log_probability"] == 0 and not selected["draw_used"]
    assert selected["policy_contract"] == CONTRACT and not selected["ordinary_PPO_eligible"]
    assert c(selection(after))["behavior"] == "greedy_combat"


def test_extra_proposal_and_combat_steps_do_not_shift_noncombat_draws() -> None:
    r = root()
    a, b = turn(r, 0, 2), turn(r, 1, 2)
    a(r["public_input"])
    b(r["public_input"])
    b(selection(r["public_input"]))
    a(next_round(r["public_input"]))
    for _ in range(5):
        b(next_round(r["public_input"]))
        b(selection(next_round(r["public_input"])))
    left, right = a(noncombat()), b(noncombat())
    assert left == right and left["behavior"] == "sampled_noncombat"
    assert left["draw_used"] and left["log_probability"] == left["policy_log_probability"]
    changed = turn(r, 0, 3)
    changed(r["public_input"])
    assert changed(noncombat())["draw_key"] != left["draw_key"]


def test_end_turn_nested_choice_and_same_round_return_are_preserved() -> None:
    r = root()
    c = turn(r, 2)
    c(r["public_input"])
    c(selection(r["public_input"]))
    assert not c.turn_complete
    after = c(r["public_input"])
    assert c.plan is not None and c.plan["boundary"]["kind"] == "native_end_turn_returned_to_combat"
    assert after["behavior"] == "greedy_combat"


@pytest.mark.parametrize("fault", ["root", "target", "short", "boundary", "ownership"])
def test_frozen_turn_refuses_observation_target_and_boundary_drift(fault: str) -> None:
    r = root()
    p = plan(r, 0)
    if fault == "short":
        p["steps"] = []
    elif fault == "boundary":
        p["boundary"]["public_input_id"] = "changed"
    p["plan_id"] = manifest_identifier({k: v for k, v in p.items() if k != "plan_id"})
    with pytest.raises(ValueError):
        c = turn(r, plan=p)
        first, after = copy.deepcopy(r["public_input"]), next_round(r["public_input"])
        if fault == "root":
            first["candidates"][0]["label"] = "changed"
        elif fault == "target":
            first["candidates"][0]["arguments"] = [
                {"role": "target", "entity": {"public_slot": 9, "role": "enemy"}}
            ]
        elif fault == "ownership":
            after["context"]["interaction"] = {"kind": "unknown", "content": {}}
        c(first)
        c(after)


def example(
    source: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    r = root()
    task = {
        "stage": "source" if source else "proposal",
        "seed": seed(),
        "first_action": 0,
        "repeat": 0,
    }
    c: SourceChooser | GreedyTurnChooser = (
        SourceChooser(seed(), cached_model(model()), score()) if source else turn(r, 0)
    )
    rows = [r["public_input"], next_round(r["public_input"]), noncombat()]
    case = {
        "status": "terminal",
        "seed": seed()["seed"],
        "recovered": False,
        "privileged_fixture": False,
        "native_ending_evidence_agrees": True,
        "policy_contract": CONTRACT,
        "privileged_fixed_world_teacher": not source,
        "student_inputs_public_only": True,
        "ordinary_PPO_eligible": False,
        "decisions": [{"public_input": p, "choice": c(p)} for p in rows],
    }
    return (
        case,
        task,
        c.root if isinstance(c, SourceChooser) else r,
        c.plan if isinstance(c, GreedyTurnChooser) else None,
    )


@pytest.mark.parametrize("source", [True, False])
def test_saved_choices_roots_and_probabilities_reconstruct_without_changing_model(
    source: bool,
) -> None:
    case, task, r, p = example(source)
    m = cached_model(model())
    before = m.as_dict()
    result = reconstruct(case, task, m, score(), r, p)
    assert result["decisions_reconstructed"] == 3 and len(result["noncombat"]) == 1
    assert m.as_dict() == before


@pytest.mark.parametrize("fault", ["probability", "root", "world", "PPO", "phase", "hidden"])
def test_saved_audit_rejects_relabeling_and_wrong_continuation(fault: str) -> None:
    case, task, r, p = example(False)
    if fault == "probability":
        case["decisions"][-1]["choice"]["log_probability"] += 0.01
    elif fault == "root":
        assert r is not None
        r["public_input_id"] = "changed"
    elif fault == "world":
        case["seed"] = "different"
    elif fault == "PPO":
        case["ordinary_PPO_eligible"] = True
    elif fault == "hidden":
        case["privileged_fixed_world_teacher"] = False
    else:
        case["decisions"][-1]["choice"]["teacher_phase"] = "ordinary_PPO"
    with pytest.raises(ValueError):
        reconstruct(case, task, cached_model(model()), score(), r, p)


def test_repeat_namespace_is_independent_of_candidate_and_finite() -> None:
    assert continuation_seed("root", 0) != continuation_seed("root", 1)
    for invalid in (-1, 8, True):
        with pytest.raises(ValueError):
            continuation_seed("root", invalid)
