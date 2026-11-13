from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from spireshift.native_a8_later_merchant_recovery import FAILED, HistoryJournal
from spireshift.native_a8_later_recovery import FAILED as FAILED_LOAD
from spireshift.native_context_journal import ChunkJournal


def test_merchant_map_observation() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to verify the merchant-map observation")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", str(root / "scripts/engine-merchant-map-observation-v1.test.mjs")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_both_failed_world_slots_stay_reserved(tmp_path: Path) -> None:
    old = ChunkJournal(tmp_path, {"workspace": "artifacts/old"})
    request = {"game": "sealed"}
    with old.lock():
        old.begin("sealed", request)
        seal = old.commit("sealed", request, {"outcome": "loss"})
    journal = HistoryJournal(old, {"workspace": "artifacts/new"}, {"sealed": seal["report_id"]})
    assert journal.completed("sealed", request) == seal
    with journal.lock():
        for key in (FAILED, FAILED_LOAD):
            with pytest.raises(ValueError, match="must remain unresolved"):
                journal.completed(key, request)
            with pytest.raises(ValueError, match="Preserve"):
                journal.begin(key, request)
            with pytest.raises(ValueError, match="Preserve"):
                journal.commit(key, request, {"outcome": "loss"})
        assert journal.completed("untouched", request) is None
    assert not (journal.workspace / "chunks").exists()
