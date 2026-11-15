from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_combat_behavior_policy import noncombat
from test_native_greedy_turn_policy import plan, root, seed
from test_native_turn_teacher_policy import next_round

from spireshift import native_greedy_turn_branch as module
from spireshift.engine_experience import read_native_episode
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_cache import cached_model
from spireshift.native_greedy_turn_data import budget_task, proposal_tasks, source_tasks


@pytest.mark.parametrize("stage", ["source", "proposal", "comparison"])
def test_native_branch_seals_reconstructs_and_charges_without_fitting(
    stage: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r, m, spec = root(), cached_model(model()), score()
    original = m.as_dict()
    stopped: list[bool] = []

    class Worker:
        def __init__(
            self, _q: Any, _inputs: Any, workspace: Path, *_args: Any, **_kwargs: Any
        ) -> None:
            self.workspace = workspace
            workspace.mkdir(parents=True)

        def episode(self, native_seed: str, **kwargs: Any) -> dict[str, Any]:
            chooser = kwargs["chooser"]
            rows = [r["public_input"], next_round(r["public_input"]), noncombat()]
            return {
                "status": "terminal",
                "seed": native_seed,
                "victory": False,
                "completed_acts": 0,
                "maximum_floor": 8,
                "cpu_seconds": 2.0,
                "native_ending_evidence_agrees": True,
                "recovered": False,
                "privileged_fixture": False,
                "terminal_public_key": "native-end",
                "decisions": [{"public_input": p, "choice": chooser(p)} for p in rows],
            }

        def close(self) -> None:
            pass

        def retire(self, _error: str) -> None:
            pytest.fail("Clean native branch must not retire")

        def stop(self) -> None:
            stopped.append(True)

    monkeypatch.setattr(module, "SelectionWorker", Worker)
    monkeypatch.setattr(module, "audit_selection_worker", lambda *_a, **_k: {"valid": True})
    cfg = {
        "stage": "short_control",
        "helpers_sha256": {},
        "maximum_decisions": 4096,
        "episode_wall_seconds": 120,
    }
    task = source_tasks([seed()])[0] if stage == "source" else proposal_tasks([r], False)[1]
    if stage == "comparison":
        p = plan(r, 0)
        atomic_json(tmp_path / "original-plan.json", p)
        task.update(
            stage="comparison",
            plan_id=p["plan_id"],
            plan_path="original-plan.json",
            reference=False,
            planning_cpu_seconds=4.0,
        )
    task = budget_task(task, {})
    target = tmp_path / "attempt"
    target.mkdir()
    value = module.branch(
        cast(EngineQualificationConfig, SimpleNamespace(root=tmp_path)),
        cfg,
        {},
        target,
        Path("node"),
        task,
        m,
        spec,
        None if stage == "source" else r,
        time.monotonic() + 150,
    )
    assert (
        value["status"] == "terminal"
        and value["native_audit_valid"]
        and value["inference_audit_valid"]
    )
    assert value["execution_cpu_seconds"] == 2.0
    assert value["cpu_seconds"] == (6.0 if stage == "comparison" else 2.0)
    saved = read_native_episode(
        tmp_path / value["episode_path"], module.binding(cfg, task, m, spec)
    )
    assert saved["privileged_fixed_world_teacher"] == (stage != "source")
    assert not saved["ordinary_PPO_eligible"] and stopped == [True]
    assert m.as_dict() == original
