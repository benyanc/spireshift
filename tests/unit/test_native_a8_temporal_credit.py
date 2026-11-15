from __future__ import annotations

from pathlib import Path

from spireshift.native_a8_paired_inputs import PLAYERS
from spireshift.native_a8_temporal_credit import FULL, SHORT
from spireshift.native_a8_temporal_credit_session import ARMS, WORLDS, tasks
from spireshift.native_context_journal import ChunkJournal


def test_fresh_panel_uses_all_references_and_journal_safe_keys(tmp_path: Path) -> None:
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/test-temporal"})
    evaluation = tasks(False)
    control = tasks(True)
    keys = [row["key"] for row in evaluation + control]
    assert len(evaluation) == 64 and len(control) == 4
    assert len(keys) == len(set(keys))
    assert all(store.path(key).name == key for key in keys)
    assert {row["partition"] for row in evaluation} == {"development"}
    assert {row["arm"] for row in control} == {FULL, SHORT}
    assert {row["seed"] for row in control}.isdisjoint(WORLDS)
    for world in WORLDS:
        assert {(r["player"], r["arm"]) for r in evaluation if r["seed"] == world} == {
            (p, arm) for p in PLAYERS for arm in ARMS
        }
