from __future__ import annotations

from pathlib import Path

import pytest
from test_native_a8_card_display_model import parent

from spireshift.native_capacity_recovery_v1 import game_task
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_normalization_recovery_v1 import FAILED
from spireshift.native_normalization_session_v2 import Session
from spireshift.native_sealed_continuation_v1 import SealedPrefixJournal


def test_imports_are_exact_read_only_and_uncertain_work_cannot_be_reopened(tmp_path: Path) -> None:
    parent_cfg = {"workspace": "artifacts/old", "fixed": "old"}
    original = ChunkJournal(tmp_path, parent_cfg)
    request = {"behavior": "exact", "world": "original"}
    with original.lock():
        original.begin("sealed", request)
        seal = original.commit("sealed", request, {"updates": 7})
    (original.workspace / "chunks/uncertain").mkdir()
    imports = {"sealed": seal["report_id"]}
    next_ = SealedPrefixJournal(
        tmp_path, {"workspace": "artifacts/new"}, parent_cfg, imports, frozenset({"uncertain"})
    )
    before = (original.path("sealed") / "done.json").read_bytes()
    with next_.lock():
        assert next_.completed("sealed", request) == seal
        assert next_.path("sealed") == original.path("sealed")
        with pytest.raises(ValueError, match="predecessor"):
            next_.completed("sealed", {"behavior": "different"})
        for key in ("sealed", "uncertain"):
            with pytest.raises(ValueError, match="Never"):
                next_.begin(key, request)
        with pytest.raises(ValueError, match="Never"):
            next_.path("uncertain")
        assert next_.completed("fresh", request) is None
        assert next_.begin("fresh", request).parent == next_.workspace / "chunks"
    assert (original.path("sealed") / "done.json").read_bytes() == before


def test_exclusion_cannot_alias_an_import(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot also"):
        SealedPrefixJournal(
            tmp_path,
            {"workspace": "artifacts/new"},
            {"workspace": "artifacts/old"},
            {"same": "sha256:x"},
            frozenset({"same"}),
        )


def test_failed_cell_retains_its_original_denominator_and_exact_behavior_identity() -> None:
    state = parent()
    state_id = "sha256:" + "a" * 64
    task = game_task("SP1RESH1FTA8N1T0993", 993, 2, 63, "normalized")
    assert task["key"] == FAILED
    session = object.__new__(Session)
    session.proof = {
        "failed_request": {"task": task, "behavior_state_id": state_id},
        "report_id": "sha256:proof",
    }
    session.cohort_counts = {}
    session.game_counts = {}
    result = session.game(task["seed"], 993, 2, 63, "train", "normalized", (state, state_id))
    assert result["outcome"] == "failed" and result["training_excluded"] is True
    assert result["task"] == task
    assert session.cohort_counts["train-p2-normalized"]["failed"] == 1
    with pytest.raises(ValueError, match="complete behavior state"):
        session.game(task["seed"], 993, 2, 63, "train", "normalized", (state, "different"))
