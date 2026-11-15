from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from spireshift.native_a8_later_recovery import FAILED, HistoryJournal
from spireshift.native_a8_later_training_resume import Session
from spireshift.native_context_journal import ChunkJournal


def test_carried_units_stay_read_only_and_failed_seed_cannot_start(tmp_path: Path) -> None:
    request = {"task": "saved"}
    old = ChunkJournal(tmp_path, {"workspace": "artifacts/old"})
    with old.lock():
        old.begin("saved", request)
        seal = old.commit("saved", request, {"outcome": "loss"})
    journal = HistoryJournal(old, {"workspace": "artifacts/new"}, {"saved": seal["report_id"]})
    assert journal.completed("saved", request) == seal
    assert journal.path("saved") == old.path("saved")
    with journal.lock():
        for key in ("saved", FAILED):
            with pytest.raises(ValueError, match="Preserve the original"):
                journal.begin(key, request)
            with pytest.raises(ValueError, match="Preserve the original"):
                journal.commit(key, request, {"outcome": "loss"})
        assert journal.completed("untouched", request) is None
        with pytest.raises(ValueError, match="must remain unresolved"):
            journal.completed(FAILED, request)
    assert not (journal.workspace / "chunks").exists()


def test_missing_load_preserves_the_other_players_matched_start() -> None:
    session = object.__new__(Session)
    session.starts = {}
    seed = "TEST123"
    session.matched_start({"key": "verified-p2", "seed": seed}, {"initial_public_input_id": "id"})
    failure = {"outcome": "failed", "native_decisions": 0}
    task = {"key": FAILED, "seed": seed}
    session.matched_start(task, failure)
    assert session.starts == {seed: "id"}
    with pytest.raises(ValueError, match="unresolved load"):
        session.matched_start(task, {**failure, "native_decisions": 1})
    with pytest.raises(ValueError, match="different public start"):
        session.matched_start({"key": "other-p3", "seed": seed}, {"initial_public_input_id": "new"})


def test_prepared_save_file_transport() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to verify the prepared-save transport")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", str(root / "scripts/engine-prepared-save-load-v1.test.mjs")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
