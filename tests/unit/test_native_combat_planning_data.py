from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.native_combat_planning import budget_task
from spireshift.native_combat_planning_data import cpu_allowance, evaluation_tasks, select_plan


def proposals() -> list[dict[str, Any]]:
    return [
        {
            "sample": i,
            "plan_id": f"plan-{i}",
            "path": f"plan-{i}.json",
            "combat_survived": i != 0,
            "exit_hp": [0, 20, 28, 28][i],
        }
        for i in range(4)
    ]


def test_tactical_selection_uses_survival_then_hp_then_fixed_proposal_order() -> None:
    p = proposals()
    assert select_plan(p)["sample"] == 2
    p[2]["combat_survived"] = False
    assert select_plan(p)["sample"] == 3
    for v in p:
        v.update(combat_survived=False, exit_hp=0)
    assert select_plan(p)["sample"] == 0


@pytest.mark.parametrize(
    "field",
    ["training_return", "maximum_floor", "victory", "later_deck", "selected_by_final_score"],
)
def test_selector_refuses_later_game_outcomes(field: str) -> None:
    p = proposals()
    p[1][field] = 1
    with pytest.raises(ValueError, match="tactical metrics"):
        select_plan(p)


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), -1])
def test_invalid_search_costs_are_refused(value: Any) -> None:
    with pytest.raises(ValueError):
        cpu_allowance(value, 128.0, False)


def test_search_cost_is_not_amortized_and_every_replay_pays_all_proposals() -> None:
    completed = {
        f"p{i}": {"stage": "search", "item_key": "r0", "execution_cpu_seconds": float(i + 1)}
        for i in range(4)
    }
    bare = {"stage": "search", "item_key": "r0"}
    assert budget_task(bare, completed, 128.0)["cpu_allowance"] == 32
    item = {"key": "r0", "root_id": "root", "reference": True}
    group = {
        "item_key": "r0",
        "blocked": False,
        "selected": select_plan(proposals()),
        "planning_cpu_seconds": 10.0,
    }
    tasks = evaluation_tasks([item], [group], 8, False)
    assert len(tasks) == 8 and all(t["planning_cpu_seconds"] == 10 for t in tasks)
    assert all(budget_task(t, completed, 128.0)["cpu_allowance"] == 118 for t in tasks)
    assert cpu_allowance(63.0, 128.0, True) == 1.0
    with pytest.raises(ValueError, match="exhausted"):
        cpu_allowance(64.0, 128.0, True)


def test_blocked_items_keep_their_place_and_control_repeats_are_explicit() -> None:
    items = [{"key": f"r{i}", "root_id": f"root{i}", "reference": True} for i in range(2)]
    groups = [
        {
            "item_key": i["key"],
            "blocked": False,
            "selected": select_plan(proposals()),
            "planning_cpu_seconds": 10.0,
        }
        for i in items
    ]
    assert len(evaluation_tasks(items, groups, 2, True)) == 8
    changed = copy.deepcopy(groups)
    changed[0]["blocked"] = True
    tasks = evaluation_tasks(items, changed, 2, False)
    assert len(tasks) == 2 and all(t["root_id"] == "root1" for t in tasks)
    with pytest.raises(ValueError, match="denominator"):
        evaluation_tasks(items, list(reversed(groups)), 2, False)
