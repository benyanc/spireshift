from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_turn_teacher_policy import chooser as turn_chooser
from test_native_turn_teacher_policy import next_round, root, selection

from spireshift.core.manifest import manifest_identifier
from spireshift.native_combat_planning_audit import reconstruct
from spireshift.native_combat_planning_policy import (
    CONTRACT,
    FightChooser,
    combat_exit,
    search_seed,
    validate_fight,
)
from spireshift.native_context_cache import cached_model
from spireshift.native_turn_teacher_policy import TurnChooser


def turn_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    r = root()
    c = turn_chooser(r)
    after = next_round(r["public_input"])
    c(r["public_input"])
    c(after)
    assert c.plan is not None
    return r, c.plan, after


def reward(p: dict[str, Any], hp: int = 20) -> dict[str, Any]:
    value = copy.deepcopy(p)
    value["context"]["interaction"] = {
        "kind": "reward_claim",
        "content": {"context": {"kind": "reward_flow"}},
    }
    value["context"]["persistent"]["player"]["hp"] = hp
    return value


def fight(r: dict[str, Any], turn: dict[str, Any], **options: Any) -> FightChooser:
    return FightChooser(
        r,
        turn,
        cached_model(model()),
        score(),
        **{"mode": "search", "sample": 0, "repeat": 0, **options},
    )


def example(
    mode: str = "search", sample: int = 0
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    r, turn, after = turn_fixture()
    c = fight(r, turn, mode=mode, sample=sample)
    rows = [r["public_input"], after, selection(after), next_round(after), reward(after)]
    decisions = [{"public_input": p, "choice": c(p)} for p in rows]
    assert c.plan is not None
    case = {
        "status": "terminal",
        "seed": r["native_seed"],
        "policy_contract": CONTRACT,
        "ordinary_PPO_eligible": False,
        "privileged_fixed_world_teacher": True,
        "student_inputs_public_only": True,
        "native_ending_evidence_agrees": True,
        "privileged_fixture": False,
        "recovered": False,
        "victory": False,
        "terminal_public_key": "later-death",
        "decisions": decisions,
    }
    return r, turn, c.plan, case, {"stage": mode, "sample": sample, "repeat": 0}


def test_plans_include_later_turns_and_nested_selections_and_freeze_before_future() -> None:
    r, turn, after = turn_fixture()
    saved = []
    c = fight(r, turn, on_plan=lambda p: saved.append(p))
    c(r["public_input"])
    assert c(after)["combat_phase"] == "combat_proposal"
    c(selection(after))
    c(next_round(after))
    assert not saved and c.plan is None
    selected = c(reward(after))
    assert selected["combat_phase"] == "postcombat_continuation" and len(saved) == 1
    assert c.plan is not None and len(c.plan["steps"]) == 3
    validate_fight(c.plan, r, turn)
    frozen = copy.deepcopy(c.plan)
    c.finish({"status": "terminal", "victory": True, "terminal_public_key": "later-victory"})
    assert c.plan == frozen


@pytest.mark.parametrize("mode,sample", [("search", 0), ("search", 2), ("baseline", 0)])
def test_saved_choices_probabilities_boundaries_and_scope_reconstruct(
    mode: str, sample: int
) -> None:
    r, turn, plan, case, task = example(mode, sample)
    assert reconstruct(case, r, turn, task, cached_model(model()), score(), plan) == 5
    case["decisions"][-1]["choice"]["log_probability"] += 0.1
    with pytest.raises(ValueError, match="probability"):
        reconstruct(case, r, turn, task, cached_model(model()), score(), plan)


def test_forced_combat_plan_exactly_replays_and_retains_postcombat_actions() -> None:
    r, turn, plan, case, _ = example(sample=1)
    c = fight(r, turn, mode="evaluation", plan=plan)
    for row in case["decisions"]:
        chosen = c(row["public_input"])
        if chosen["combat_phase"] != "postcombat_continuation":
            assert chosen["action_index"] == row["choice"]["action_index"]
    assert c.plan == plan


def test_baseline_has_exact_old_continuation_actions_and_probabilities() -> None:
    r, turn, after = turn_fixture()
    old = TurnChooser(
        r,
        cached_model(model()),
        score(),
        first_action=None,
        repeat=3,
        temperature=0.8,
        proposal_temperature=1.2,
        plan=turn,
    )
    new = fight(r, turn, mode="baseline", repeat=3)
    for p in [
        r["public_input"],
        after,
        selection(after),
        next_round(after),
        reward(after),
        reward(after, hp=19),
    ]:
        a, b = old(p), new(p)
        assert a["action_index"] == b["action_index"]
        if "log_probability" in a:
            assert a["log_probability"] == b["log_probability"]


def test_proposal_stream_is_independent_of_scoring_repeat() -> None:
    r, turn, after = turn_fixture()
    plans = []
    for repeat in (0, 1):
        c = fight(r, turn, sample=3, repeat=repeat)
        for p in [r["public_input"], after, selection(after), next_round(after), reward(after)]:
            c(p)
        plans.append(c.plan)
    assert plans[0] == plans[1]
    assert search_seed("r", "a", 1) != search_seed("r", "b", 1)
    with pytest.raises(ValueError):
        search_seed("r", "a", True)


@pytest.mark.parametrize("fault", ["observation", "target", "short", "exit", "private"])
def test_replay_never_falls_back_on_changed_or_truncated_plans(fault: str) -> None:
    r, turn, plan, case, _ = example()
    if fault == "short":
        plan["steps"].pop()
    elif fault == "exit":
        plan["exit"]["exit_hp"] -= 1
    elif fault == "private":
        plan["steps"][0]["public_input"]["context"]["native_seed"] = "hidden"
    plan["plan_id"] = manifest_identifier({k: v for k, v in plan.items() if k != "plan_id"})
    with pytest.raises(ValueError):
        c = fight(r, turn, mode="evaluation", plan=plan)
        for i, row in enumerate(case["decisions"]):
            p = copy.deepcopy(row["public_input"])
            if i == 1 and fault in {"observation", "target"}:
                p["candidates"][0]["label"] = "changed current cost or target"
            c(p)


def test_terminal_loss_and_initial_turn_kill_do_not_require_fake_actions() -> None:
    r, turn, after = turn_fixture()
    c = fight(r, turn)
    c(r["public_input"])
    c(after)
    c.finish({"status": "terminal", "victory": False, "terminal_public_key": "dead"})
    assert c.plan is not None and c.plan["exit"]["exit_hp"] is None
    assert not c.plan["exit"]["combat_survived"]
    end = reward(after)
    turn["boundary"] = {
        "kind": "public_postcombat_menu",
        "public_input_id": manifest_identifier(end),
    }
    turn["plan_id"] = manifest_identifier({k: v for k, v in turn.items() if k != "plan_id"})
    c = fight(r, turn)
    c(r["public_input"])
    c(end)
    assert c.plan is not None and c.plan["steps"] == []


def test_unknown_ownership_and_incomplete_attempt_never_create_a_plan() -> None:
    r, turn, after = turn_fixture()
    c = fight(r, turn)
    c(r["public_input"])
    c(after)
    unknown = copy.deepcopy(after)
    unknown["context"]["interaction"] = {"kind": "unknown_modal", "content": {}}
    with pytest.raises(ValueError, match="ownership"):
        c(unknown)
    c.finish({"status": "failed"})
    assert c.plan is None


def test_combat_cap_and_public_exit_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    from spireshift import native_combat_planning_policy as module

    monkeypatch.setattr(module, "MAX_STEPS", 1)
    r, turn, after = turn_fixture()
    c = fight(r, turn)
    c(r["public_input"])
    c(after)
    with pytest.raises(ValueError, match="decision cap"):
        c(next_round(after))
    assert c.plan is None
    assert combat_exit(r["public_input"], selection(after)) is None
    assert combat_exit(r["public_input"], next_round(after)) is None
    observed = combat_exit(r["public_input"], reward(after))
    assert observed is not None and observed["combat_survived"]


def test_fixed_world_experience_cannot_be_mislabeled_as_public_belief_or_PPO() -> None:
    r, turn, plan, case, task = example()
    case["ordinary_PPO_eligible"] = True
    with pytest.raises(ValueError, match="counterfactuals"):
        reconstruct(case, r, turn, task, cached_model(model()), score(), plan)
