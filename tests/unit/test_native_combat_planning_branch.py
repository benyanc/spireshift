from __future__ import annotations

import copy
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_combat_planning_policy import example

from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_planning_branch import branch
from spireshift.native_context_cache import cached_model


@pytest.mark.parametrize("over_budget", [False, True])
def test_full_search_cost_changes_admission_and_never_updates_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, over_budget: bool
) -> None:
    from spireshift import native_combat_planning_branch as module

    r, turn, plan, case, _ = example()
    r["source_seed_id"] = 0
    atomic_json(tmp_path / "turn.json", turn)
    atomic_json(tmp_path / "selected.json", plan)
    closed = []

    class Worker:
        def __init__(
            self, q: Any, inputs: Any, workspace: Path, node: Path, helpers: Any, **kwargs: Any
        ) -> None:
            self.workspace = workspace
            workspace.mkdir(parents=True)

        def episode(
            self, seed: str, *, chooser: Callable[[dict[str, Any]], dict[str, Any]], **kwargs: Any
        ) -> dict[str, Any]:
            decisions = [
                {**row, "choice": chooser(row["public_input"])} for row in case["decisions"]
            ]
            return {
                **copy.deepcopy(case),
                "decisions": decisions,
                "maximum_floor": 8,
                "completed_acts": 0,
                "cpu_seconds": 6.0 if over_budget else 2.0,
                "inference_cpu_seconds": 0.1,
                "game_apps_created": 0,
            }

        def close(self) -> None:
            closed.append("closed")

        def retire(self, reason: str) -> None:
            closed.append("retired")

        def stop(self) -> None:
            closed.append("stopped")

    monkeypatch.setattr(module, "SelectionWorker", Worker)
    monkeypatch.setattr(module, "audit_selection_worker", lambda *a, **k: {"valid": True})
    task = {
        "key": "evaluation",
        "stage": "evaluation",
        "sample": 0,
        "repeat": 0,
        "duplicate": False,
        "selected": {"path": "selected.json", "plan_id": plan["plan_id"]},
        "planning_cpu_seconds": 123.0 if over_budget else 8.0,
        "cpu_allowance": 5.0 if over_budget else 120.0,
    }
    player = cached_model(model())
    before = copy.deepcopy(player.as_dict())
    result = branch(
        cast(EngineQualificationConfig, SimpleNamespace(root=tmp_path)),
        {"helpers_sha256": {}},
        {},
        tmp_path / "attempt",
        tmp_path / "node",
        r,
        {"key": "item", "turn_plan_path": "turn.json", "turn_plan_id": turn["plan_id"]},
        task,
        player,
        score(),
        time.monotonic() + 100,
    )
    assert result["cpu_seconds"] == result["planning_cpu_seconds"] + result["execution_cpu_seconds"]
    assert player.as_dict() == before
    if over_budget:
        assert result["status"] == "failed" and result["training_return"] is None
        assert closed == ["retired", "stopped"]
    else:
        assert result["status"] == "terminal" and result["cpu_seconds"] == 10.0
        assert closed == ["closed", "stopped"]


def test_tactical_hp_does_not_become_an_episode_reward() -> None:
    from spireshift.engine_experience import score_episode

    _, _, _, case, _ = example()
    case.update(maximum_floor=8, completed_acts=0, cpu_seconds=10.0)
    values = []
    for hp in (1, 80):
        modified = copy.deepcopy(case)
        for row in modified["decisions"]:
            row["public_input"]["context"]["persistent"]["player"]["hp"] = hp
        values.append(score_episode(modified, 0, score())["training_return"])
    assert values[0] == values[1]
