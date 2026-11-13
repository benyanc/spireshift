from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from spireshift import native_inventory_credit_study as study
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal


def setup(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], list[str], Path]:
    original = root / "original-state.json"
    original.write_text('{"weights":[1,2],"Adam":{"steps":5658,"first":[3],"second":[4]}}')
    context = {
        "config": {"workspace": "artifacts/credit-diagnosis"},
        "source_report": {"report_id": "sha256:original-report"},
        "tasks": {key: {"key": key} for key in study.COHORTS},
        "sources": {"original-state.json": _sha_file(original)},
        "score": SimpleNamespace(
            spec_id="sha256:score",
            evaluation_objective=SimpleNamespace(as_dict=lambda: {"primary": "terminal_victory"}),
        ),
    }
    calls: list[str] = []

    def fake_prepare(root: Path, path: Path) -> dict[str, Any]:
        return context

    def fake_analyze(
        root: Path, context: dict[str, Any], key: str, directory: Path, deadline: float
    ) -> dict[str, Any]:
        calls.append(key)
        result = {
            "cohort": key,
            "forecast": {
                "prediction": {
                    "mse": {
                        "current": 0.02,
                        "deck_relic": 0.01,
                    }
                }
            },
        }
        atomic_json(directory / "result.json", result)
        return result

    monkeypatch.setattr(study, "prepare", fake_prepare)
    monkeypatch.setattr(study, "analyze", fake_analyze)
    monkeypatch.setattr(study, "summarize", lambda rows: {"completed_cohorts": len(rows)})
    return context, calls, original


def test_short_cohorts_resume_without_refitting_sealed_work_or_changing_Adam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, calls, original = setup(tmp_path, monkeypatch)
    before = original.read_bytes()
    first = study.run(tmp_path, tmp_path / "config.json", max_new_cohorts=1, session_seconds=240)
    assert first["status"] == "paused_between_sealed_cohorts"
    assert first["completed_cohorts"] == 1
    second = study.run(tmp_path, tmp_path / "config.json", max_new_cohorts=1, session_seconds=240)
    assert second["completed_cohorts"] == 2
    assert calls == list(study.COHORTS[:2])
    assert original.read_bytes() == before
    assert second["player_Adam_updates"] == 0


def test_completed_run_is_cached_without_new_fitting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, calls, original = setup(tmp_path, monkeypatch)
    before = original.read_bytes()
    first = study.run(tmp_path, tmp_path / "config.json", session_seconds=240)
    assert first["status"] == "native_inventory_credit_diagnosis_complete"
    assert len(calls) == 12
    again = study.run(tmp_path, tmp_path / "config.json", session_seconds=240)
    assert again == first
    assert len(calls) == 12 and original.read_bytes() == before


def test_unsealed_diagnosis_is_preserved_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, calls, _ = setup(tmp_path, monkeypatch)
    store = ChunkJournal(tmp_path, context["config"])
    task = context["tasks"][study.COHORTS[0]]
    with store.lock():
        folder = store.begin(
            study.COHORTS[0],
            {
                "source_report_id": context["source_report"]["report_id"],
                "task": task,
            },
        )
        (folder / "partial.npz").write_bytes(b"preserve partial diagnostic evidence")
    with pytest.raises(FileExistsError, match="uncommitted"):
        study.run(tmp_path, tmp_path / "config.json", max_new_cohorts=1, session_seconds=240)
    assert not calls
    assert (folder / "partial.npz").read_bytes() == b"preserve partial diagnostic evidence"


def test_tampered_completed_cohort_is_detected_before_new_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context, calls, original = setup(tmp_path, monkeypatch)
    study.run(tmp_path, tmp_path / "config.json", max_new_cohorts=1, session_seconds=240)
    store = ChunkJournal(tmp_path, context["config"])
    (store.path(study.COHORTS[0]) / "result.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="evidence changed"):
        study.run(tmp_path, tmp_path / "config.json", max_new_cohorts=1, session_seconds=240)
    assert calls == [study.COHORTS[0]]
    assert '"steps":5658' in original.read_text()
