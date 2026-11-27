from __future__ import annotations

from pathlib import Path

import pytest

from spireshift.native_context_journal import ChunkJournal
from spireshift.native_qualified_learning_inputs_v2 import IMPORTS
from spireshift.native_qualified_learning_session_v2 import AdoptedJournal, canonical_partition


def test_all_production_phase_keys_are_valid_and_reload_is_never_a_training_partition(
    tmp_path: Path,
) -> None:
    journal = ChunkJournal(tmp_path, {"workspace": "artifacts/test"})
    for phase in ("control", "train", "development", "reload_control"):
        normalized = canonical_partition(phase)
        assert journal.path(f"{normalized}-0001-p2-learner").name == f"{normalized}-0001-p2-learner"
    assert canonical_partition("reload_control") not in {"control", "train"}
    with pytest.raises(ValueError, match="Invalid chunk key"):
        journal.path("unrecognized_partition-1")


def test_adoption_reuses_exact_predecessor_units_and_never_replays_a_missing_one(
    tmp_path: Path,
) -> None:
    parent = {"workspace": "artifacts/old-study", "control_workspace": "artifacts/old-control"}
    current = AdoptedJournal(tmp_path, {"workspace": "artifacts/new-control"}, parent)
    assert len(IMPORTS) == 8
    assert current.path(IMPORTS[0]) == tmp_path / "artifacts/old-control/chunks" / IMPORTS[0]
    assert (
        current.path("reload-control-0001-p2-learner")
        == tmp_path / "artifacts/new-control/chunks/reload-control-0001-p2-learner"
    )
    with pytest.raises(ValueError, match="Never replay"):
        current.completed(IMPORTS[0], {})
