from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from test_native_a8_card_display_model import parent

from spireshift import native_qualified_learning_session_v1 as session_v1
from spireshift import native_qualified_learning_worker_v2 as worker
from spireshift import native_win4_game
from spireshift.native_a8_card_display_model import extend
from spireshift.native_combat_intent_model import copy_with_intents
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_qualified_learning_recovery_v1 import FAILED, task
from spireshift.native_qualified_learning_session_v3 import (
    ContinuationJournal,
    Session,
    excluded_game,
)
from spireshift.native_qualified_learning_verification_v2 import verify_episode


def test_current_saved_answer_domain_and_tamper_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to verify the saved answer domain")
    result = subprocess.run(
        [node, "--test", "scripts/engine-card-answer-verify-v2.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_imported_games_and_complete_adam_updates_are_never_replayed(tmp_path: Path) -> None:
    parent = {"workspace": "artifacts/parent"}
    old = ChunkJournal(tmp_path, parent)
    request = {"behavior_state_id": "exact-full-state"}
    with old.lock():
        old.begin("fit-p2-r001", request)
        seal = old.commit("fit-p2-r001", request, {"optimizer_updates": 57})
    current = ContinuationJournal(
        tmp_path,
        {"workspace": "artifacts/current"},
        parent,
        {"inherited_units": {"fit-p2-r001": seal["report_id"]}},
    )
    assert current.completed("fit-p2-r001", request) == seal
    assert current.path("fit-p2-r001") == old.path("fit-p2-r001")
    assert (
        current.path("train-0572-p3-learner")
        == tmp_path / "artifacts/current/chunks/train-0572-p3-learner"
    )
    with pytest.raises(ValueError, match="Never replay"):
        current.begin("fit-p2-r001", request)
    (old.path("fit-p2-r001") / "done.json").unlink()
    with pytest.raises(FileExistsError, match="Preserve uncommitted"):
        current.completed("fit-p2-r001", request)
    with pytest.raises(ValueError, match="Never replay"):
        current.completed(FAILED, request)
    with pytest.raises(ValueError, match="diagnostic"):
        current.path(FAILED)


def test_the_failed_cell_keeps_its_denominator_and_supplies_no_fit_label() -> None:
    game_task = task("exact-world", 571, 3, 36)
    state = cast(Any, (SimpleNamespace(model=SimpleNamespace(model_id="model")), "full-state"))
    proof = {
        "failed_request": {"task": game_task, "behavior_state_id": "full-state"},
        "report_id": "saved-audit",
    }
    result = excluded_game(proof, game_task, state)
    assert result["outcome"] == "failed"
    assert result["training_excluded"] is True
    assert result["outcome"] not in {"win", "loss"}
    assert [r for r in [result] if r["outcome"] in {"win", "loss"}] == []
    with pytest.raises(ValueError, match="behavior state"):
        excluded_game(proof, {**game_task, "seed": "different-world"}, state)


def test_continuation_fits_only_the_fifteen_complete_games_in_the_affected_round(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = copy_with_intents(extend(parent(), ("block", "damage")))
    session = Session.__new__(Session)
    session.root, session.control, session.deadline = tmp_path, False, math.inf
    session.cfg = {"plan": {"minimum_terminal_training_worlds": 12}, "credit": {}, "settings": {}}
    session.ctx = {"score": None}
    session.training = []
    target = tmp_path / "new-fit"
    target.mkdir()
    session.store = cast(Any, SimpleNamespace(path=lambda key: target))
    monkeypatch.setattr(session, "unchanged", lambda: None)
    monkeypatch.setattr(session, "unit", lambda key, request, reserve, action: action(target))
    seen: list[str] = []

    def fit(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
        seen.extend(row["task"]["key"] for _, row in args[1])
        return state, {"optimizer_updates": 0}

    monkeypatch.setattr(session_v1, "fit", fit)
    rows = [
        {
            "task": {"key": f"game-{i}"},
            "seal_id": f"seal-{i}",
            "outcome": "loss",
            "completed_acts": 0,
        }
        for i in range(15)
    ]
    rows.append({"task": {"key": FAILED}, "seal_id": "diagnostic-proof", "outcome": "failed"})
    restored, _ = session.learn(3, 36, rows, (state, "prior-full-state"))
    assert restored == state
    assert len(seen) == 15 and FAILED not in seen
    assert session.training[0]["eligible_terminal_worlds"] == 15
    assert session.training[0]["outcomes"] == {"loss": 15, "failed": 1}


def test_updated_worker_binds_saved_verification_and_preserves_subprocess_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = native_win4_game.verify_episode

    def stopped(*_: Any) -> dict[str, Any]:
        assert native_win4_game.verify_episode is verify_episode
        raise subprocess.CalledProcessError(1, ["saved-verifier"])

    monkeypatch.setattr(worker, "original_play", stopped)
    with pytest.raises(ValueError, match="verification did not complete"):
        worker.play({}, {}, tmp_path, cast(Any, None), 123.0)
    assert native_win4_game.verify_episode is original


def test_fixtures_and_missing_models_cannot_use_normal_start_verification(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="model-owned normal start"):
        verify_episode(
            {}, {"kind": "prepared_training_only"}, "own_policy", tmp_path, tmp_path, 123.0
        )
