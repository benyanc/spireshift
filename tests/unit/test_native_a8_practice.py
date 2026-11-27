from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_a8_practice_goal import BOSS_ROOM, KIND, TWO_ROOMS, PracticeGoal
from spireshift.native_a8_practice_session import TEMPLATES, schedule, status

START = {"kind": KIND}


def frame(floor: int, kind: str, *, hp: int = 20, **facts: str) -> dict[str, Any]:
    return {
        "terminal": False,
        "public_input": {
            "context": {
                "persistent": {"run": {"act": 2, "floor": floor}, "player": {"hp": hp}},
                "interaction": {"kind": kind, "content": {"context": facts}},
            },
        },
    }


def test_practice_requires_two_distinct_delivered_combat_rewards() -> None:
    goal = PracticeGoal(TWO_ROOMS, 2)
    reward = frame(2, "reward_claim", reward_kind="room_rewards")
    assert goal(reward, START) == (False, False)
    assert goal(frame(2, "combat_turn", encounter_type="normal"), START) == (False, False)
    assert goal(frame(2, "card_selection", reward_kind="room_rewards"), START) == (False, False)
    assert goal(reward, START) == (False, False)
    assert goal(reward, START) == (False, False)
    assert goal(frame(4, "combat_turn", encounter_type="elite"), START) == (False, False)
    assert goal(frame(5, "reward_claim", reward_kind="room_rewards"), START) == (False, False)
    assert goal(frame(6, "combat_turn", encounter_type="normal"), START) == (False, False)
    assert goal(frame(6, "reward_claim", reward_kind="room_rewards"), START) == (True, True)
    assert goal.completed == {2: "normal", 6: "normal"}


def test_preboss_practice_requires_a_living_reward_from_observed_boss_combat() -> None:
    goal = PracticeGoal(BOSS_ROOM, 2)
    assert goal(frame(3, "combat_turn", encounter_type="normal"), START) == (False, False)
    assert goal(frame(3, "reward_claim", reward_kind="room_rewards"), START) == (False, False)
    assert goal(frame(17, "combat_turn", encounter_type="boss"), START) == (False, False)
    assert goal(frame(17, "reward_claim", reward_kind="room_rewards", hp=0), START) == (
        False,
        False,
    )
    assert goal(frame(17, "reward_claim", reward_kind="room_rewards"), START) == (True, True)
    assert goal({"terminal": True, "ending": {"victory": False}}, START) == (True, False)
    with pytest.raises(ValueError, match="full-run victory"):
        goal({"terminal": True, "ending": {"victory": True}}, START)


def test_practice_plan_keeps_control_separate_and_retains_missing_segments() -> None:
    plan = {
        "fit": [
            {
                "key": key,
                "act_definition": definition,
                "entry": "preboss" if i == 2 else "act_start",
            }
            for definition, keys in TEMPLATES.items()
            for i, key in enumerate(keys)
        ]
    }
    control, main = schedule(plan, control=True), schedule(plan, control=False)
    assert len(control) == 9
    assert len(main) == 32
    seeds = [seed for c in control + main for seed in c["seed_pool"]]
    assert len(set(seeds)) == len(seeds)
    assert {c["partition"] for c in control} == {"practice_control"}
    assert {c["partition"] for c in main} == {"practice_train"}
    summary = status(main, {"m-001-p2": {"outcome": "capped"}}, control=False)
    assert summary["room_coverage_candidate"] is False
    counts = summary["by_act_definition_and_tier"]
    assert counts["OVERGROWTH"]["healthy"] == {"capped": 1, "unattempted": 5}
