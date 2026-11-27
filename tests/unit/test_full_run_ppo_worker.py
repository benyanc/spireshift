from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from test_full_run_public_policy import MenuRun, environment

from spireshift.full_run_ppo_worker import (
    JournalEnvironment,
    execution_evidence,
    run_isolated_episode,
    verify_execution_evidence,
)


def test_real_child_exit_does_not_destroy_sibling_supervisors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_run = subprocess.run

    def child(args: list[str], **kwargs: Any) -> Any:
        request = json.loads(Path(args[-1]).read_text())
        program = (
            "import os; os._exit(23)"
            if request["seed"] == 1
            else "print('Sibling game finished', flush=True)"
        )
        return real_run([sys.executable, "-c", program], **kwargs)

    monkeypatch.setattr("spireshift.full_run_ppo_worker.subprocess.run", child)
    requests = []
    for seed in (1, 2, 3):
        directory = tmp_path / str(seed)
        directory.mkdir()
        requests.append(
            {"seed": seed, "case_path": str(directory / "case.json"), "episode_wall_seconds": 5}
        )
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(run_isolated_episode, request) for request in requests]
        with pytest.raises(RuntimeError, match="code 23"):
            futures[0].result()
        assert futures[1].result() is None
        assert futures[2].result() is None
    assert "Sibling game finished" in (tmp_path / "2" / "worker.log").read_text()
    with pytest.raises(ValueError, match="previous worker request"):
        run_isolated_episode(requests[0])


def test_wall_timeout_kills_child_and_retains_debug_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_run = subprocess.run

    def child(args: list[str], **kwargs: Any) -> Any:
        return real_run([sys.executable, "-c", "import time; time.sleep(10)"], **kwargs)

    monkeypatch.setattr("spireshift.full_run_ppo_worker.subprocess.run", child)
    with pytest.raises(RuntimeError, match="wall-time cap"):
        run_isolated_episode(
            {"case_path": str(tmp_path / "case.json"), "episode_wall_seconds": 0.1}
        )
    assert (tmp_path / "worker.log").exists()
    assert (tmp_path / "worker-request.json").exists()


def test_public_journal_is_written_before_a_failing_step(tmp_path: Path) -> None:
    backend = MenuRun()
    wrapped = JournalEnvironment(environment(backend), tmp_path / "last-public-step.json")
    observation = wrapped.reset(1)
    action = wrapped.legal_actions()[0]

    def failing_step(action: Any) -> Any:
        journal = json.loads(wrapped.journal.read_text())
        assert journal["observation"] == observation.as_dict()
        assert journal["action"] == action.as_dict()
        assert journal["decision_index"] == 0
        assert journal["claim_scope"].startswith("debug_only")
        raise RuntimeError("Synthetic native step failure")

    wrapped.environment.step = failing_step  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="Synthetic native"):
        wrapped.step(action)
    assert wrapped.steps == 0


def test_mutable_debug_journal_tracks_the_latest_step(tmp_path: Path) -> None:
    wrapped = JournalEnvironment(environment(MenuRun()), tmp_path / "last-public-step.json")
    wrapped.reset(1)
    wrapped.step(wrapped.legal_actions()[0])
    second = wrapped.observation
    wrapped.step(wrapped.legal_actions()[0])
    journal = json.loads(wrapped.journal.read_text())
    assert journal["decision_index"] == 1
    assert second is not None and journal["observation"] == second.as_dict()


def test_failure_evidence_rejects_changed_logs_and_path_escape(tmp_path: Path) -> None:
    log = tmp_path / "worker.log"
    log.write_text("Native failure\n")
    evidence = execution_evidence(tmp_path)
    verify_execution_evidence(tmp_path, evidence)
    log.write_text("Changed\n")
    with pytest.raises(ValueError, match="crash evidence differs"):
        verify_execution_evidence(tmp_path, evidence)
    evidence["worker.log"]["path"] = "../worker.log"
    with pytest.raises(ValueError, match="crash evidence differs"):
        verify_execution_evidence(tmp_path, evidence)
