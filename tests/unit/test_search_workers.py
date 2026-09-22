from __future__ import annotations

from pathlib import Path

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.search_workers import (
    PublicStateCheckpoint,
    SearchBackendSpec,
    SearchSimulationTask,
    SearchWorkerEvidence,
    SearchWorkerRequest,
    SearchWorkerStatus,
    capture_checkpoint,
    run_search_worker_batch,
    run_subprocess_search_task,
    verify_search_worker_batch,
)

CHECKED_REPORT = Path("tests/fixtures/search-workers/mock-batch-v1/search-worker-report.json")


def _root_checkpoint() -> PublicStateCheckpoint:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)
    return capture_checkpoint(
        run_seed=7,
        action_prefix=(),
        environment=environment,
        observation=observation,
    )


def _task(index: int, *, checkpoint: PublicStateCheckpoint | None = None) -> SearchSimulationTask:
    return SearchSimulationTask.create(
        backend=SearchBackendSpec.mock(),
        checkpoint=checkpoint or _root_checkpoint(),
        action_id="elite_path",
        simulation_seed=index,
        maximum_rollout_steps=4,
        task_id=f"00000000-0000-4000-8000-{index:012d}",
    )


def test_isolated_workers_restore_checkpoint_and_sample_independent_worlds(tmp_path: Path) -> None:
    result = run_search_worker_batch(
        tasks=tuple(_task(index) for index in range(4)),
        workers=2,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
        batch_id="00000000-0000-4000-8000-000000000099",
    )

    assert result.successful
    summary = result.report["summary"]
    assert isinstance(summary, dict)
    assert summary["requested_tasks"] == 4
    assert summary["completed_tasks"] == 4
    assert summary["failed_tasks"] == 0
    assert summary["worker_crashes"] == 0
    assert summary["sampled_worlds"] == 4
    assert summary["transitions"] >= 4
    assert summary["wall_seconds"] > 0.0
    assert summary["worker_cpu_seconds"] >= 0.0
    assert summary["tasks_per_wall_second"] > 0.0
    tasks = result.report["tasks"]
    assert isinstance(tasks, list)
    pids = {item["worker_pid"] for item in tasks}
    assert None not in pids
    assert len(pids) == 4
    for item in tasks:
        assert item["status"] == "completed"
        output = item["output"]
        assert output["checkpoint_verified"] is True
        assert output["sampled_worlds"] == 1
        assert output["source_state_hash"] == _root_checkpoint().state_hash
        request_path = result.report_path.parent / item["request_path"]
        result_path = result.report_path.parent / item["result_path"]
        assert request_path.is_file()
        assert result_path.is_file()


def test_worker_restores_action_prefix_before_sampling(tmp_path: Path) -> None:
    environment = MockSpireEnvironment()
    environment.reset(7)
    transition = environment.step(environment.legal_actions()[0])
    checkpoint = capture_checkpoint(
        run_seed=7,
        action_prefix=("safe_path",),
        environment=environment,
        observation=transition.next_observation,
    )
    task = SearchSimulationTask.create(
        backend=SearchBackendSpec.mock(),
        checkpoint=checkpoint,
        action_id="face_boss",
        simulation_seed=9,
        maximum_rollout_steps=1,
        task_id="00000000-0000-4000-8000-000000000009",
    )

    result = run_search_worker_batch(
        tasks=(task,),
        workers=1,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
    )

    assert result.successful
    tasks = result.report["tasks"]
    assert isinstance(tasks, list)
    output = tasks[0]["output"]
    assert output["source_state_hash"] == transition.next_observation.state_hash
    assert output["action_id"] == "face_boss"
    assert output["terminal"] is True
    assert output["truncated"] is False


def test_stale_checkpoint_fails_closed_in_its_own_process(tmp_path: Path) -> None:
    checkpoint = _root_checkpoint()
    stale = PublicStateCheckpoint(
        checkpoint.run_seed,
        checkpoint.action_prefix,
        checkpoint.patch_id,
        checkpoint.ruleset_manifest_id,
        "0" * 64,
    )

    result = run_search_worker_batch(
        tasks=(_task(1, checkpoint=stale),),
        workers=1,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
    )

    assert not result.successful
    tasks = result.report["tasks"]
    assert isinstance(tasks, list)
    assert tasks[0]["status"] == "worker_error"
    assert "public state hash mismatch" in tasks[0]["message"]


def test_coordinator_keeps_crash_in_search_denominator(tmp_path: Path) -> None:
    def crash(request: SearchWorkerRequest) -> SearchWorkerEvidence:
        return SearchWorkerEvidence(
            task_id=request.task.task_id,
            status=SearchWorkerStatus.CRASHED,
            exit_code=137,
            worker_pid=None,
            message="injected crash",
            request_path=str(request.request_path.relative_to(request.batch_directory)),
            result_path=str(request.result_path.relative_to(request.batch_directory)),
            request_sha256="0" * 64,
            result_sha256=None,
            cpu_seconds=None,
            wall_seconds=None,
            output=None,
        )

    result = run_search_worker_batch(
        tasks=(_task(1), _task(2)),
        workers=2,
        worker_timeout_seconds=30.0,
        output_directory=tmp_path / "batch",
        task_runner=crash,
    )

    assert not result.successful
    summary = result.report["summary"]
    assert isinstance(summary, dict)
    assert summary["requested_tasks"] == 2
    assert summary["completed_tasks"] == 0
    assert summary["failed_tasks"] == 2
    assert summary["worker_crashes"] == 2


def test_subprocess_worker_refuses_to_replace_result(tmp_path: Path) -> None:
    task = _task(3)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    write_exclusive_json(request_path, task.as_dict())
    request = SearchWorkerRequest(
        batch_id="00000000-0000-4000-8000-000000000099",
        task=task,
        batch_directory=tmp_path,
        request_path=request_path,
        result_path=result_path,
        timeout_seconds=30.0,
    )

    first = run_subprocess_search_task(request)
    first_digest = sha256_file(result_path)
    second = run_subprocess_search_task(request)

    assert first.completed
    assert second.status is SearchWorkerStatus.WORKER_ERROR
    assert second.message == "completed worker returned exit code 1"
    assert sha256_file(result_path) == first_digest


def test_checked_search_worker_batch_replays_every_task() -> None:
    verification = verify_search_worker_batch(CHECKED_REPORT)

    assert verification.valid, verification.errors
    assert verification.tasks == 2
    assert verification.verified_tasks == 2


def test_batch_verification_rejects_tampered_request_path(tmp_path: Path) -> None:
    import json
    import shutil

    batch = tmp_path / "batch"
    shutil.copytree(CHECKED_REPORT.parent, batch)
    report_path = batch / CHECKED_REPORT.name
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["tasks"][0]["request_path"] = "../escape.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    verification = verify_search_worker_batch(report_path)

    assert not verification.valid
    assert any("escapes" in error for error in verification.errors)
