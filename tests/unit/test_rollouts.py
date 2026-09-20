from __future__ import annotations

import json
from pathlib import Path

import pytest

from spireshift.recording.jsonl import ImmutableJsonlRecorder
from spireshift.rollouts import (
    AttemptEvidence,
    AttemptStatus,
    WorkerRequest,
    run_mock_rollout_batch,
    run_subprocess_attempt,
    verify_rollout_batch,
)

OBJECTIVE_CONFIG = Path("configs/default.toml")


def test_parallel_workers_write_and_replay_immutable_runs(tmp_path: Path) -> None:
    output = tmp_path / "batch"
    result = run_mock_rollout_batch(
        seeds=(0, 1, 2, 3),
        workers=2,
        maximum_attempts=2,
        worker_timeout_seconds=30.0,
        output_directory=output,
        objective_config=OBJECTIVE_CONFIG,
        batch_id="00000000-0000-4000-8000-000000000019",
    )

    assert result.successful
    assert result.report["summary"] == {
        "requested_runs": 4,
        "benchmark_denominator": 4,
        "completed_runs": 4,
        "verified_runs": 4,
        "victories": 1,
        "defeats": 3,
        "failed_runs": 0,
        "attempts": 4,
        "failed_attempts": 0,
        "worker_crashes": 0,
        "recovered_runs": 0,
        "victory_rate": 0.25,
        "completion_rate": 1.0,
    }
    replay = verify_rollout_batch(result.report_path)
    assert replay.valid, replay.errors
    assert replay.runs == 4
    assert replay.verified_runs == 4
    attempts = [_mapping(item) for item in _list(result.report["attempts"])]
    worker_pids = {attempt["worker_pid"] for attempt in attempts}
    assert None not in worker_pids
    assert len(worker_pids) >= 2

    with pytest.raises(FileExistsError):
        run_mock_rollout_batch(
            seeds=(0,),
            workers=1,
            maximum_attempts=1,
            worker_timeout_seconds=30.0,
            output_directory=output,
            objective_config=OBJECTIVE_CONFIG,
        )


def test_failed_attempt_is_retried_and_preserved(tmp_path: Path) -> None:
    def crash_once(request: WorkerRequest) -> AttemptEvidence:
        if request.attempt == 1:
            return _crash(request)
        return run_subprocess_attempt(request)

    result = run_mock_rollout_batch(
        seeds=(0,),
        workers=1,
        maximum_attempts=2,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
        objective_config=OBJECTIVE_CONFIG,
        attempt_runner=crash_once,
    )

    summary = _mapping(result.report["summary"])
    assert result.successful
    assert summary["attempts"] == 2
    assert summary["failed_attempts"] == 1
    assert summary["worker_crashes"] == 1
    assert summary["recovered_runs"] == 1
    assert verify_rollout_batch(result.report_path).valid


def test_crashed_seed_remains_in_benchmark_denominator(tmp_path: Path) -> None:
    result = run_mock_rollout_batch(
        seeds=(5, 6),
        workers=2,
        maximum_attempts=2,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
        objective_config=OBJECTIVE_CONFIG,
        attempt_runner=_crash,
    )

    summary = _mapping(result.report["summary"])
    assert not result.successful
    assert summary["requested_runs"] == 2
    assert summary["benchmark_denominator"] == 2
    assert summary["completed_runs"] == 0
    assert summary["failed_runs"] == 2
    assert summary["worker_crashes"] == 4
    assert summary["victory_rate"] == 0.0
    assert summary["completion_rate"] == 0.0
    assert verify_rollout_batch(result.report_path).valid


def test_batch_replay_rejects_tampered_run(tmp_path: Path) -> None:
    result = run_mock_rollout_batch(
        seeds=(0,),
        workers=1,
        maximum_attempts=1,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
        objective_config=OBJECTIVE_CONFIG,
    )
    outcome = _mapping(_list(result.report["outcomes"])[0])
    record_path = result.report_path.parent / str(outcome["record_path"])
    record_path.write_text(record_path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

    replay = verify_rollout_batch(result.report_path)
    assert not replay.valid
    assert any("digest mismatch" in error for error in replay.errors)


def test_immutable_recorder_refuses_to_replace_a_run(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    recorder = ImmutableJsonlRecorder(path)
    recorder.close()
    with pytest.raises(FileExistsError):
        ImmutableJsonlRecorder(path)


def test_worker_result_identity_is_checked(tmp_path: Path) -> None:
    request = WorkerRequest(
        batch_id="00000000-0000-4000-8000-000000000019",
        seed=7,
        attempt=1,
        objective_config=OBJECTIVE_CONFIG.resolve(),
        batch_directory=tmp_path,
        record_path=tmp_path / "run.jsonl",
        result_path=tmp_path / "worker-result.json",
        timeout_seconds=30.0,
    )
    result = run_subprocess_attempt(request)
    assert result.completed
    document = json.loads(request.result_path.read_text(encoding="utf-8"))
    assert document["batch_id"] == request.batch_id
    assert isinstance(document["worker_pid"], int)


def _crash(request: WorkerRequest) -> AttemptEvidence:
    return AttemptEvidence(
        seed=request.seed,
        attempt=request.attempt,
        status=AttemptStatus.CRASHED,
        exit_code=137,
        worker_pid=None,
        message="injected worker crash",
        record_path=str(request.record_path.relative_to(request.batch_directory)),
        result_path=str(request.result_path.relative_to(request.batch_directory)),
        record_sha256=None,
        victory=None,
        decisions=None,
        compute_used=None,
        replay_verified=False,
    )


def _mapping(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return value


def _list(value: object) -> list[object]:
    assert isinstance(value, list)
    return value
