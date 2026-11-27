from __future__ import annotations

import math
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift.native_qualified_learning_readiness_v2 import EXCLUDED
from spireshift.native_qualified_learning_recovery_v1 import task
from spireshift.native_qualified_learning_session_v4 import (
    ContinuationJournal,
    Session,
    excluded_game,
)


def test_both_historical_failed_paths_cannot_be_opened_or_replayed(tmp_path: Path) -> None:
    journal = ContinuationJournal(
        tmp_path,
        {"workspace": "artifacts/current"},
        {"workspace": "artifacts/old"},
        {"inherited_units": {}},
    )
    for key in EXCLUDED:
        for action in (
            partial(journal.path, key),
            partial(journal.begin, key, {}),
            partial(journal.completed, key, {}),
        ):
            with pytest.raises(ValueError, match="failed|excluded"):
                action()
    assert not (tmp_path / "artifacts").exists()


def test_both_exclusions_keep_exact_behavior_and_failed_denominators() -> None:
    state = cast(Any, (SimpleNamespace(model=SimpleNamespace(model_id="model")), "full-state"))
    proof: dict[str, Any] = {"report_id": "audit", "excluded_training_requests": {}}
    for key, index in zip(EXCLUDED, (571, 572), strict=True):
        game_task = task(f"seed-{index}", index, 3, 36)
        proof["excluded_training_requests"][key] = {
            "task": game_task,
            "behavior_state_id": "full-state",
        }
        row = excluded_game(proof, game_task, state)
        assert row["outcome"] == "failed" and row["training_excluded"] is True
        with pytest.raises(ValueError, match="full behavior state"):
            excluded_game(proof, game_task, cast(Any, (state[0], "other-Adam")))


def test_fixed_loop_restores_before_development_and_prints_only_new_fits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = Session.__new__(Session)
    session.starting = cast(Any, {2: ("p2-original", "p2-start"), 3: ("p3-original", "p3-start")})
    session.cfg = {
        "plan": {
            "rounds": 2,
            "worlds_per_round": 2,
            "training": ["t1", "t2", "t3", "t4"],
            "development": ["fresh"],
        }
    }
    session.proof = {"report_id": "audit", "inherited_units": {}, "inherited_optimizer_updates": 0}
    session.training, session.evaluation = [], {}
    session.deadline = math.inf
    session.store = cast(Any, SimpleNamespace(path=lambda key: tmp_path / key))
    for p in (2, 3):
        folder = tmp_path / f"fit-p{p}-r001"
        folder.mkdir()
        (folder / "done.json").write_text("saved")
    calls = []

    def game(
        seed: str, index: int, p: int, r: int, phase: str, arm: str, state: Any
    ) -> dict[str, Any]:
        if phase == "development":
            assert len(session.training) == 4
            assert state[1] == (f"p{p}-start" if arm == "original" else f"p{p}-r2")
        calls.append((seed, p, phase, arm))
        return {"outcome": "loss"}

    def learn(p: int, r: int, rows: list[Any], state: Any) -> Any:
        session.training.append({"act1_clears": 0, "work": {"optimizer_updates": int(r == 2)}})
        return (state[0], f"p{p}-r{r}")

    monkeypatch.setattr(session, "game", game)
    monkeypatch.setattr(session, "learn", learn)
    monkeypatch.setattr(session, "unchanged", lambda: None)
    result = session.run()
    output = capsys.readouterr().out
    assert "New fit round 1" not in output
    assert output.count("New fit round 2") == 2
    assert len([c for c in calls if c[2] == "train"]) == 8
    assert len(session.evaluation) == 4
    assert result["new_optimizer_updates"] == 2
    assert result["final_states"] == {"2": "p2-r2", "3": "p3-r2"}
