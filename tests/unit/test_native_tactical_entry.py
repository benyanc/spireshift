from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json


def entry() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts/check-native-tactical-learning-v1.py"
    spec = importlib.util.spec_from_file_location("tactical_test_entry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_resource(root: Path, command: list[str], status: str = "completed") -> None:
    name = command[command.index("--report") + 1]
    body = {"status": status, "exit_code": 0}
    atomic_json(root / name, {**body, "report_id": manifest_identifier(body)})


def test_failed_check_stops_without_receipt_or_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = entry()
    monkeypatch.setattr(module, "repository_snapshot", lambda _: "unchanged")
    calls = []

    def failed(command: list[str], **kwargs: Any) -> int:
        calls.append(command)
        return 1

    monkeypatch.setattr(module.subprocess, "call", failed)
    assert module.ensure_repository_checks(tmp_path) == 1
    assert len(calls) == 1 and calls[0][-1] == "check"
    assert not list(tmp_path.rglob("passed-*.json"))


def test_capped_result_with_zero_exit_code_still_cannot_admit_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = entry()
    monkeypatch.setattr(module, "repository_snapshot", lambda _: "unchanged")

    def capped(command: list[str], **kwargs: Any) -> int:
        write_resource(tmp_path, command, "capped")
        return 0

    monkeypatch.setattr(module.subprocess, "call", capped)
    with pytest.raises(ValueError, match="Only a complete passing"):
        module.ensure_repository_checks(tmp_path)
    assert not list(tmp_path.rglob("passed-*.json"))


def test_passing_checks_are_reused_only_for_identical_repository_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = entry()
    monkeypatch.setattr(module, "repository_snapshot", lambda _: "unchanged")
    calls = []

    def completed(command: list[str], **kwargs: Any) -> int:
        calls.append(command)
        write_resource(tmp_path, command)
        return 0

    monkeypatch.setattr(module.subprocess, "call", completed)
    assert module.ensure_repository_checks(tmp_path) == 0
    assert module.ensure_repository_checks(tmp_path) == 0
    assert len(calls) == 1
    monkeypatch.setattr(module, "repository_snapshot", lambda _: "changed")
    assert module.ensure_repository_checks(tmp_path) == 0
    assert len(calls) == 2


def test_changing_sources_during_checks_prevents_a_passing_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = entry()
    snapshots = iter(("before", "after"))
    monkeypatch.setattr(module, "repository_snapshot", lambda _: next(snapshots))

    def completed(command: list[str], **kwargs: Any) -> int:
        write_resource(tmp_path, command)
        return 0

    monkeypatch.setattr(module.subprocess, "call", completed)
    with pytest.raises(ValueError, match="changed during checks"):
        module.ensure_repository_checks(tmp_path)
    assert not list(tmp_path.rglob("passed-*.json"))


def test_repository_fingerprint_tracks_new_and_changed_unignored_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = entry()
    (tmp_path / "a.py").write_text("first")
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **kw: b"a.py\x00")
    before = module.repository_snapshot(tmp_path)
    (tmp_path / "a.py").write_text("second")
    assert module.repository_snapshot(tmp_path) != before
