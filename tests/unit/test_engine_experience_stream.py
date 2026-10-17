from __future__ import annotations

import copy
import gzip
import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_engine_experience_audit import fixture, retired_fixture

from spireshift.engine_experience import read_native_episode, save_native_episode
from spireshift.engine_experience_audit import audit_worker_experience
from spireshift.engine_experience_stream import audit_worker_streaming, stopped_worker_evidence


def seal(path: Path, cases: list[dict[str, Any]]) -> list[Path]:
    result = []
    for i, case in enumerate(cases):
        case.update(completed_acts=0, maximum_floor=2, cpu_seconds=1.0, worker_workspace="worker")
        destination = path / f"case-{i}.json"
        save_native_episode(destination, case, {"seed_id": i})
        result.append(destination)
    return result


@pytest.mark.parametrize("retired", [False, True])
def test_streaming_matches_frozen_auditor_on_clean_and_retired_workers(
    tmp_path: Path, retired: bool
) -> None:
    cases = retired_fixture(tmp_path) if retired else fixture(tmp_path)
    expected = audit_worker_experience(tmp_path, cases)
    result = audit_worker_streaming(tmp_path, seal(tmp_path, cases), deadline=time.monotonic() + 10)
    assert result["valid"]
    for key in ("games", "decisions", "excluded_failed_games"):
        assert result[key] == expected[key]
    assert result["maximum_retained_episode_histories"] == 1
    assert not result["ordinary_training_admission"]


@pytest.mark.parametrize(
    "change", ["different_target", "unknown", "broken_successor", "hidden", "fixture", "missing"]
)
def test_streaming_rejects_the_same_corruption_as_the_frozen_auditor(
    tmp_path: Path, change: str
) -> None:
    paths = seal(tmp_path, fixture(tmp_path, change))
    with pytest.raises(ValueError):
        audit_worker_streaming(tmp_path, paths, deadline=time.monotonic() + 10)


def test_interrupted_prefix_is_explicit_diagnostic_evidence_and_preserves_every_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = seal(tmp_path, fixture(tmp_path))
    (tmp_path / "closed.json").unlink()
    (tmp_path / "active.json").write_text('{"owner_process":123}')
    (tmp_path / "identity.json").write_text('{"runtime_identity":{"process_id":456}}')
    raw = tmp_path / "private-transcript.jsonl.gz"
    with gzip.open(raw, "at") as stream:
        stream.write(
            json.dumps({"request": {"cmd": "reset_run", "seed": "UNFINISHED"}, "response": {}})
            + "\n"
        )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    monkeypatch.setattr("spireshift.engine_experience_stream.psutil.pid_exists", lambda _: False)
    monkeypatch.setattr("spireshift.engine_experience_stream.psutil.process_iter", lambda _: [])
    result = audit_worker_streaming(
        tmp_path, paths, interrupted=True, deadline=time.monotonic() + 10
    )
    assert result["games"] == 1 and result["interrupted_diagnostic_prefix"]
    assert result["unfinished_native_seeds"] == ["UNFINISHED"]
    assert not result["ordinary_training_admission"]
    assert result["process_evidence"]["processes_signalled"] == 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before
    with pytest.raises(FileNotFoundError):
        audit_worker_streaming(tmp_path, paths, deadline=time.monotonic() + 10)


def test_live_interrupted_process_blocks_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "active.json").write_text('{"owner_process":123}')
    (tmp_path / "identity.json").write_text('{"runtime_identity":{"process_id":456}}')
    monkeypatch.setattr("spireshift.engine_experience_stream.psutil.pid_exists", lambda _: True)
    with pytest.raises(ValueError, match="still exists"):
        stopped_worker_evidence(tmp_path)


def test_streaming_retains_only_the_current_episode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.engine_experience_stream as module

    cases = fixture(tmp_path)
    rows = {}
    for filename in module.JOURNALS:
        with gzip.open(tmp_path / filename, "rt") as stream:
            rows[filename] = [json.loads(line) for line in stream]
    count = 20
    paths = []
    for i in range(count):
        c = copy.deepcopy(cases[0])
        c["seed"] = f"SEED{i}"
        target = tmp_path / f"case-{i}.json"
        c.update(completed_acts=0, maximum_floor=2, cpu_seconds=1.0, worker_workspace="worker")
        save_native_episode(target, c, {"seed_id": i})
        paths.append(target)
    for filename, source in rows.items():
        with gzip.open(tmp_path / filename, "wt") as stream:
            for i in range(count):
                for original in source:
                    row = copy.deepcopy(original)
                    if filename == module.JOURNALS[0]:
                        if row["request"]["cmd"] == "quit":
                            continue
                        if row["request"]["cmd"] == "start_run":
                            row["request"]["seed"] = f"SEED{i}"
                    else:
                        row["episode"] = i + 1
                    stream.write(json.dumps(row) + "\n")
    (tmp_path / "closed.json").write_text(json.dumps({"clean_exit": True, "episodes": count}))
    live = 0
    peak = 0

    class Counted(dict[str, Any]):
        def __init__(self, value: dict[str, Any]) -> None:
            nonlocal live, peak
            super().__init__(value)
            live += 1
            peak = max(peak, live)

        def __del__(self) -> None:
            nonlocal live
            live -= 1

    original = read_native_episode
    monkeypatch.setattr(module, "read_native_episode", lambda *args: Counted(original(*args)))
    result = module.audit_worker_streaming(tmp_path, paths, deadline=time.monotonic() + 10)
    assert result["games"] == count and peak == 1 and live == 0


def test_truncated_gzip_or_expired_deadline_cannot_be_silently_accepted(tmp_path: Path) -> None:
    paths = seal(tmp_path, fixture(tmp_path))
    with pytest.raises(TimeoutError):
        audit_worker_streaming(tmp_path, paths, deadline=time.monotonic() - 1)
    f = tmp_path / "public-receipts.jsonl.gz"
    f.write_bytes(f.read_bytes()[:-5])
    with pytest.raises((EOFError, OSError)):
        audit_worker_streaming(tmp_path, paths, deadline=time.monotonic() + 10)
