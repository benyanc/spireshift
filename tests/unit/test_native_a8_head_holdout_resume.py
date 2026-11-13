from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from spireshift import native_a8_head_grid_resume as previous
from spireshift import native_a8_head_holdout_resume as resume
from spireshift import native_a8_head_study as head
from spireshift.native_a8_head_policy import ARMS
from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_context_journal import ChunkJournal


def test_only_untouched_worlds_can_launch() -> None:
    worlds = head.world_schedule()["holdout"]
    tasks = list(resume.tasks("holdout", worlds, resume.FIRST_NEW))
    assert len(tasks) == 232
    assert tasks[0]["key"] == "holdout-r064-071-p2-shared"
    assert {task["seed"] for task in tasks} == set(worlds[70:])
    assert {resume.slot(task) for task in tasks} == {
        (seed, player, arm) for seed in worlds[70:] for player in PLAYERS for arm in ARMS
    }


def test_saved_interruption_stays_in_the_planned_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worlds = head.world_schedule()["holdout"]
    history = ChunkJournal(tmp_path, {"workspace": "artifacts/interrupted"})
    refs = {
        player: {arm: {"state_id": f"p{player}-{arm}", "model_id": arm} for arm in ARMS}
        for player in PLAYERS
    }
    task_by_key = {task["key"]: task for task in resume.tasks("holdout", worlds)}
    stopped = task_by_key[resume.STOPPED]
    with history.lock():
        history.begin(resume.STOPPED, previous.game_request(stopped, refs[3]["shared"]))

    def loss(
        store: ChunkJournal, task: dict[str, Any], ref: dict[str, Any], *, full: bool
    ) -> dict[str, Any]:
        assert store is history and full and ref == refs[task["player"]][task["arm"]]
        assert task["seed"] in worlds[:70]
        assert (task["seed"], task["player"]) != (worlds[69], 3)
        return {
            "outcome": "loss",
            "maximum_floor": 9,
            "completed_acts": 0,
            "initial_public_input_id": task["seed"],
        }

    monkeypatch.setattr(previous, "load_game", loss)
    rows = resume.saved_evaluation(history, "holdout", worlds, refs)
    assert rows[worlds[69], 3, "shared"] == {"outcome": "failed"}
    assert (worlds[69], 3, "split") not in rows
    result = head.evaluate(worlds, rows)
    assert result["by_initializer"]["3"]["arms"]["shared"]["failed"] == 1
    assert result["by_initializer"]["3"]["arms"]["split"]["unattempted"] == 59
    assert result["pooled_split_minus_shared_win_rate_bounds"] == [-117 / 256, 117 / 256]
    assert result["comparison"] == "inconclusive"

    sibling = task_by_key["holdout-r064-070-p3-split"]
    with history.lock():
        history.begin(sibling["key"], previous.game_request(sibling, refs[3]["split"]))
    with pytest.raises(ValueError, match="excluded or untouched"):
        resume.saved_evaluation(history, "holdout", worlds, refs)
