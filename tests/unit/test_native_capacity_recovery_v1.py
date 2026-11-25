from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift.native_a8_head_policy import HeadState
from spireshift.native_capacity_recovery_v1 import FAILED, game_task
from spireshift.native_capacity_session_v2 import ContinuationJournal, excluded
from spireshift.native_context_journal import ChunkJournal


def test_exclusion_binds_world_initializer_round_and_complete_state() -> None:
    task = game_task("DECLAREDWORLD", 154, 3, 10, "expanded")
    state = cast(HeadState, SimpleNamespace(model=SimpleNamespace(model_id="model")))
    proof = {
        "report_id": "proof",
        "failed_request": {"task": task, "behavior_state_id": "full-state"},
    }
    row = excluded(proof, task, (state, "full-state"))
    assert task["key"] == FAILED
    assert row["outcome"] == "failed" and row["training_excluded"]
    assert "completed_acts" not in row
    for changed in ({**task, "seed": "ANOTHERWORLD"}, {**task, "player": 2}, {**task, "round": 11}):
        with pytest.raises(ValueError, match="exclusion changed"):
            excluded(proof, changed, (state, "full-state"))
    with pytest.raises(ValueError, match="complete behavior"):
        excluded(proof, task, (state, "weights-only"))


def test_continuation_never_restarts_historical_or_failed_chunks(tmp_path: Path) -> None:
    original = ChunkJournal(tmp_path, {"workspace": "artifacts/old", "plan": "fixed"})
    request: dict[str, Any] = {"prior_state_id": "weights-and-Adam", "game_seals": ["game"]}
    with original.lock():
        original.begin("fit-p3-expanded-r009", request)
        seal = original.commit("fit-p3-expanded-r009", request, {"optimizer_updates": 60})
    journal = ContinuationJournal(
        tmp_path,
        {"workspace": "artifacts/new"},
        original.recipe,
        {
            "inherited_units": {"fit-p3-expanded-r009": seal["report_id"]},
        },
    )
    assert journal.completed("fit-p3-expanded-r009", request) == seal
    assert journal.path("fit-p3-expanded-r009") == original.path("fit-p3-expanded-r009")
    assert (
        journal.path("train-0155-p3-expanded")
        == tmp_path / "artifacts/new/chunks/train-0155-p3-expanded"
    )
    for key in (FAILED, "fit-p3-expanded-r009"):
        with pytest.raises(ValueError, match="Never"):
            journal.begin(key, request)
    for operation in (lambda: journal.path(FAILED), lambda: journal.completed(FAILED, request)):
        with pytest.raises(ValueError, match="Never"):
            operation()
    with pytest.raises(ValueError, match="predecessor"):
        journal.completed("fit-p3-expanded-r009", {**request, "prior_state_id": "different"})
    original.path("fit-p3-expanded-r009").joinpath("done.json").unlink()
    with pytest.raises(FileExistsError, match="Preserve uncommitted"):
        journal.completed("fit-p3-expanded-r009", request)
