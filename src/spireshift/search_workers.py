from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.adapters.tactical_mock import TacticalHandoffMockEnvironment
from spireshift.agents.baseline import TerminalVictoryPolicy
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import LegalAction, Observation
from spireshift.mechanics import PublicMechanicsService
from spireshift.rollouts import sha256_file, write_exclusive_json

SEARCH_TASK_SCHEMA_VERSION = "search-simulation-task-v1"
SEARCH_WORKER_RESULT_SCHEMA_VERSION = "search-worker-result-v1"
SEARCH_WORKER_BATCH_SCHEMA_VERSION = "search-worker-batch-v1"
SEARCH_WORKER_METHOD = "isolated-public-world-rollout-v1"


class SearchWorkerStatus(StrEnum):
    COMPLETED = "completed"
    WORKER_ERROR = "worker_error"
    CRASHED = "crashed"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class SearchBackendSpec:
    kind: str
    upstream_root: str | None = None
    manifest_path: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"mock", "tactical_mock", "evangambit"}:
            raise ValueError(f"Unsupported search backend: {self.kind}")
        if self.kind in {"mock", "tactical_mock"} and (
            self.upstream_root is not None or self.manifest_path is not None
        ):
            raise ValueError("Test search backends do not accept external paths")
        if self.kind == "evangambit" and (self.upstream_root is None or self.manifest_path is None):
            raise ValueError("EvanGambit search backend requires upstream and manifest paths")

    @classmethod
    def mock(cls) -> SearchBackendSpec:
        return cls("mock")

    @classmethod
    def tactical_mock(cls) -> SearchBackendSpec:
        return cls("tactical_mock")

    @classmethod
    def evangambit(cls, upstream_root: Path, manifest_path: Path) -> SearchBackendSpec:
        return cls(
            "evangambit",
            str(upstream_root.expanduser().resolve()),
            str(manifest_path.expanduser().resolve()),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "upstream_root": self.upstream_root,
            "manifest_path": self.manifest_path,
        }

    @classmethod
    def from_mapping(cls, value: object) -> SearchBackendSpec:
        document = _mapping(value, "backend")
        _exact_keys(document, {"kind", "upstream_root", "manifest_path"}, "backend")
        return cls(
            kind=_string(document.get("kind"), "backend.kind"),
            upstream_root=_optional_string(document.get("upstream_root")),
            manifest_path=_optional_string(document.get("manifest_path")),
        )


@dataclass(frozen=True, slots=True)
class PublicStateCheckpoint:
    run_seed: int
    action_prefix: tuple[str, ...]
    patch_id: str
    ruleset_manifest_id: str
    state_hash: str

    def __post_init__(self) -> None:
        if not self.patch_id or not self.ruleset_manifest_id or not self.state_hash:
            raise ValueError("Checkpoint identities must be non-empty")

    def as_dict(self) -> dict[str, object]:
        return {
            "run_seed": self.run_seed,
            "action_prefix": list(self.action_prefix),
            "patch_id": self.patch_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "state_hash": self.state_hash,
        }

    @classmethod
    def from_mapping(cls, value: object) -> PublicStateCheckpoint:
        document = _mapping(value, "checkpoint")
        _exact_keys(
            document,
            {"run_seed", "action_prefix", "patch_id", "ruleset_manifest_id", "state_hash"},
            "checkpoint",
        )
        return cls(
            run_seed=_integer(document.get("run_seed"), "checkpoint.run_seed"),
            action_prefix=tuple(
                _string(item, "checkpoint.action_prefix[]")
                for item in _list(document.get("action_prefix"), "checkpoint.action_prefix")
            ),
            patch_id=_string(document.get("patch_id"), "checkpoint.patch_id"),
            ruleset_manifest_id=_string(
                document.get("ruleset_manifest_id"), "checkpoint.ruleset_manifest_id"
            ),
            state_hash=_string(document.get("state_hash"), "checkpoint.state_hash"),
        )


@dataclass(frozen=True, slots=True)
class SearchSimulationTask:
    task_id: str
    backend: SearchBackendSpec
    checkpoint: PublicStateCheckpoint
    action_id: str
    simulation_seed: int
    maximum_rollout_steps: int

    def __post_init__(self) -> None:
        UUID(self.task_id)
        if not self.action_id:
            raise ValueError("Search action_id must be non-empty")
        if self.maximum_rollout_steps <= 0:
            raise ValueError("maximum_rollout_steps must be positive")

    @classmethod
    def create(
        cls,
        *,
        backend: SearchBackendSpec,
        checkpoint: PublicStateCheckpoint,
        action_id: str,
        simulation_seed: int,
        maximum_rollout_steps: int = 4096,
        task_id: str | None = None,
    ) -> SearchSimulationTask:
        return cls(
            str(uuid4()) if task_id is None else str(UUID(task_id)),
            backend,
            checkpoint,
            action_id,
            simulation_seed,
            maximum_rollout_steps,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": SEARCH_TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "backend": self.backend.as_dict(),
            "checkpoint": self.checkpoint.as_dict(),
            "action_id": self.action_id,
            "simulation_seed": self.simulation_seed,
            "maximum_rollout_steps": self.maximum_rollout_steps,
        }

    @classmethod
    def from_mapping(cls, value: object) -> SearchSimulationTask:
        document = _mapping(value, "search task")
        _exact_keys(
            document,
            {
                "schema_version",
                "task_id",
                "backend",
                "checkpoint",
                "action_id",
                "simulation_seed",
                "maximum_rollout_steps",
            },
            "search task",
        )
        if document.get("schema_version") != SEARCH_TASK_SCHEMA_VERSION:
            raise ValueError("Unsupported search task schema")
        return cls(
            task_id=_string(document.get("task_id"), "task_id"),
            backend=SearchBackendSpec.from_mapping(document.get("backend")),
            checkpoint=PublicStateCheckpoint.from_mapping(document.get("checkpoint")),
            action_id=_string(document.get("action_id"), "action_id"),
            simulation_seed=_integer(document.get("simulation_seed"), "simulation_seed"),
            maximum_rollout_steps=_integer(
                document.get("maximum_rollout_steps"), "maximum_rollout_steps"
            ),
        )


@dataclass(frozen=True, slots=True)
class SearchWorkerRequest:
    batch_id: str
    task: SearchSimulationTask
    batch_directory: Path
    request_path: Path
    result_path: Path
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class SearchWorkerEvidence:
    task_id: str
    status: SearchWorkerStatus
    exit_code: int | None
    worker_pid: int | None
    message: str
    request_path: str
    result_path: str
    request_sha256: str
    result_sha256: str | None
    cpu_seconds: float | None
    wall_seconds: float | None
    output: dict[str, object] | None

    @property
    def completed(self) -> bool:
        return self.status is SearchWorkerStatus.COMPLETED

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "worker_pid": self.worker_pid,
            "message": self.message,
            "request_path": self.request_path,
            "result_path": self.result_path,
            "request_sha256": self.request_sha256,
            "result_sha256": self.result_sha256,
            "cpu_seconds": self.cpu_seconds,
            "wall_seconds": self.wall_seconds,
            "output": self.output,
        }


@dataclass(frozen=True, slots=True)
class SearchWorkerBatchResult:
    successful: bool
    report_path: Path
    report: dict[str, object]


@dataclass(frozen=True, slots=True)
class SearchWorkerBatchVerification:
    valid: bool
    tasks: int
    verified_tasks: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "valid": self.valid,
            "tasks": self.tasks,
            "verified_tasks": self.verified_tasks,
            "errors": list(self.errors),
        }


class SearchTaskRunner(Protocol):
    def __call__(self, request: SearchWorkerRequest) -> SearchWorkerEvidence: ...


def capture_checkpoint(
    *,
    run_seed: int,
    action_prefix: Sequence[str],
    environment: EnvironmentAdapter,
    observation: Observation,
) -> PublicStateCheckpoint:
    if environment.patch_id != observation.patch_id:
        raise ValueError("Checkpoint environment and observation patches differ")
    return PublicStateCheckpoint(
        run_seed=run_seed,
        action_prefix=tuple(action_prefix),
        patch_id=environment.patch_id,
        ruleset_manifest_id=environment.ruleset.manifest_id,
        state_hash=observation.state_hash,
    )


def execute_search_task(task: SearchSimulationTask) -> dict[str, object]:
    environment, observation = restore_search_checkpoint(task.backend, task.checkpoint)
    mechanics = PublicMechanicsService()
    source_snapshot = mechanics.snapshot(environment, observation)
    source_action = _action_by_id(source_snapshot.legal_actions, task.action_id)
    sampled = environment.clone(resample_hidden=True, seed=task.simulation_seed)
    sampled_snapshot = mechanics.snapshot(sampled, observation)
    if sampled_snapshot.legal_actions != source_snapshot.legal_actions:
        raise RuntimeError("Hidden-world clone changed public legal actions")
    action = _action_by_id(sampled_snapshot.legal_actions, source_action.action_id)
    policy = TerminalVictoryPolicy()
    decisions = 0
    transition = sampled.step(action)
    if transition.observation != observation:
        raise RuntimeError("Hidden-world clone changed the source public observation")
    decisions += 1
    observation = transition.next_observation
    while not transition.terminal and decisions < task.maximum_rollout_steps:
        continuation = mechanics.snapshot(sampled, observation)
        next_action = policy.choose_action(observation, continuation.legal_actions)
        transition = sampled.step(next_action)
        decisions += 1
        observation = transition.next_observation
    return {
        "method": SEARCH_WORKER_METHOD,
        "patch_id": environment.patch_id,
        "ruleset_manifest_id": environment.ruleset.manifest_id,
        "source_state_hash": task.checkpoint.state_hash,
        "action_id": task.action_id,
        "simulation_seed": task.simulation_seed,
        "checkpoint_verified": True,
        "sampled_worlds": 1,
        "transitions": decisions,
        "terminal": transition.terminal,
        "victory": transition.victory,
        "terminal_reward": transition.reward if transition.terminal else None,
        "truncated": not transition.terminal,
        "final_state_hash": observation.state_hash,
    }


def run_search_worker_batch(
    *,
    tasks: Sequence[SearchSimulationTask],
    workers: int,
    worker_timeout_seconds: float,
    output_directory: Path,
    task_runner: SearchTaskRunner | None = None,
    batch_id: str | None = None,
    now: Callable[[], str] | None = None,
) -> SearchWorkerBatchResult:
    canonical_tasks = tuple(tasks)
    if not canonical_tasks:
        raise ValueError("At least one search task is required")
    task_ids = [task.task_id for task in canonical_tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError("Search task IDs must be unique")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if worker_timeout_seconds <= 0.0:
        raise ValueError("worker_timeout_seconds must be positive")
    canonical_batch_id = str(uuid4()) if batch_id is None else str(UUID(batch_id))
    clock_now = _utc_now if now is None else now
    started_at = clock_now()
    started = time.perf_counter()
    output_directory.mkdir(parents=True, exist_ok=False)
    output_directory = output_directory.resolve()
    runner = run_subprocess_search_task if task_runner is None else task_runner
    requests = tuple(
        _write_task_request(
            canonical_batch_id,
            task,
            output_directory,
            worker_timeout_seconds,
        )
        for task in canonical_tasks
    )
    evidence: list[SearchWorkerEvidence] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(requests))) as executor:
        futures: dict[Future[SearchWorkerEvidence], SearchWorkerRequest] = {
            executor.submit(runner, request): request for request in requests
        }
        for future in as_completed(futures):
            request = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = _failed_evidence(
                    request,
                    SearchWorkerStatus.CRASHED,
                    None,
                    f"task runner raised {type(error).__name__}: {error}",
                )
            if result.task_id != request.task.task_id:
                result = _failed_evidence(
                    request,
                    SearchWorkerStatus.CRASHED,
                    None,
                    "task runner returned evidence for a different task",
                )
            evidence.append(result)
    wall_seconds = time.perf_counter() - started
    ordered = tuple(sorted(evidence, key=lambda item: item.task_id))
    completed = tuple(item for item in ordered if item.completed)
    worker_cpu_seconds = sum(item.cpu_seconds or 0.0 for item in ordered)
    transitions = sum(
        _integer(item.output.get("transitions"), "worker output transitions")
        for item in completed
        if item.output is not None
    )
    worker_crashes = sum(
        item.status in {SearchWorkerStatus.CRASHED, SearchWorkerStatus.TIMEOUT} for item in ordered
    )
    report: dict[str, object] = {
        "schema_version": SEARCH_WORKER_BATCH_SCHEMA_VERSION,
        "batch_id": canonical_batch_id,
        "started_at": started_at,
        "completed_at": clock_now(),
        "configuration": {
            "workers": workers,
            "worker_timeout_seconds": worker_timeout_seconds,
            "task_ids": sorted(task_ids),
        },
        "summary": {
            "requested_tasks": len(canonical_tasks),
            "completed_tasks": len(completed),
            "failed_tasks": len(canonical_tasks) - len(completed),
            "worker_crashes": worker_crashes,
            "transitions": transitions,
            "sampled_worlds": len(completed),
            "wall_seconds": wall_seconds,
            "worker_cpu_seconds": worker_cpu_seconds,
            "tasks_per_wall_second": len(completed) / wall_seconds,
            "transitions_per_wall_second": transitions / wall_seconds,
        },
        "tasks": [item.as_dict() for item in ordered],
    }
    report_path = output_directory / "search-worker-report.json"
    write_exclusive_json(report_path, report)
    return SearchWorkerBatchResult(len(completed) == len(canonical_tasks), report_path, report)


def run_subprocess_search_task(request: SearchWorkerRequest) -> SearchWorkerEvidence:
    command = [
        sys.executable,
        "-m",
        "spireshift.search_worker",
        "--batch-id",
        request.batch_id,
        "--request",
        str(request.request_path),
        "--result",
        str(request.result_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _failed_evidence(
            request,
            SearchWorkerStatus.TIMEOUT,
            None,
            f"worker exceeded {request.timeout_seconds:g}s timeout",
        )
    if not request.result_path.is_file():
        detail = completed.stderr.strip()
        message = "worker exited without an immutable result"
        if detail:
            message = f"{message}: {detail[-1000:]}"
        return _failed_evidence(
            request,
            SearchWorkerStatus.CRASHED,
            completed.returncode,
            message,
        )
    try:
        result = _load_object(request.result_path)
        status = SearchWorkerStatus(_string(result.get("status"), "worker status"))
        output_value = result.get("output")
        output = None if output_value is None else _mapping(output_value, "worker output")
        worker_pid = _optional_integer(result.get("worker_pid"))
        cpu_seconds = _optional_number(result.get("cpu_seconds"))
        wall_seconds = _optional_number(result.get("wall_seconds"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _failed_evidence(
            request,
            SearchWorkerStatus.CRASHED,
            completed.returncode,
            f"invalid worker result: {error}",
        )
    request_digest = sha256_file(request.request_path)
    if (
        result.get("schema_version") != SEARCH_WORKER_RESULT_SCHEMA_VERSION
        or result.get("batch_id") != request.batch_id
        or result.get("task_id") != request.task.task_id
        or result.get("request_sha256") != request_digest
    ):
        return _failed_evidence(
            request,
            SearchWorkerStatus.CRASHED,
            completed.returncode,
            "worker result identity mismatch",
        )
    message = _string(result.get("message"), "worker message")
    if status is SearchWorkerStatus.COMPLETED:
        if completed.returncode != 0:
            status = SearchWorkerStatus.WORKER_ERROR
            message = f"completed worker returned exit code {completed.returncode}"
        elif worker_pid is None or cpu_seconds is None or wall_seconds is None or output is None:
            status = SearchWorkerStatus.WORKER_ERROR
            message = "completed worker omitted required evidence"
        else:
            _validate_completed_output(request.task, output)
    return SearchWorkerEvidence(
        task_id=request.task.task_id,
        status=status,
        exit_code=completed.returncode,
        worker_pid=worker_pid,
        message=message,
        request_path=_relative_path(request.request_path, request.batch_directory),
        result_path=_relative_path(request.result_path, request.batch_directory),
        request_sha256=request_digest,
        result_sha256=sha256_file(request.result_path),
        cpu_seconds=cpu_seconds,
        wall_seconds=wall_seconds,
        output=output,
    )


def verify_search_worker_batch(report_path: Path) -> SearchWorkerBatchVerification:
    errors: list[str] = []
    try:
        report = _load_object(report_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return SearchWorkerBatchVerification(False, 0, 0, (str(error),))
    if report.get("schema_version") != SEARCH_WORKER_BATCH_SCHEMA_VERSION:
        return SearchWorkerBatchVerification(False, 0, 0, ("unsupported batch schema",))
    raw_tasks = report.get("tasks")
    configuration = report.get("configuration")
    summary = report.get("summary")
    if not isinstance(raw_tasks, list) or not isinstance(configuration, dict):
        return SearchWorkerBatchVerification(False, 0, 0, ("invalid batch structure",))
    if not isinstance(summary, dict):
        return SearchWorkerBatchVerification(False, len(raw_tasks), 0, ("invalid summary",))
    configured_ids = configuration.get("task_ids")
    if not isinstance(configured_ids, list) or any(
        not isinstance(task_id, str) for task_id in configured_ids
    ):
        errors.append("configuration task IDs must be strings")
        configured_ids = []
    batch_directory = report_path.parent.resolve()
    seen_ids: set[str] = set()
    completed = 0
    verified = 0
    crashes = 0
    transitions = 0
    worker_cpu_seconds = 0.0
    for index, raw_evidence in enumerate(raw_tasks):
        if not isinstance(raw_evidence, dict):
            errors.append(f"tasks[{index}] must be an object")
            continue
        task_id = raw_evidence.get("task_id")
        if not isinstance(task_id, str):
            errors.append(f"tasks[{index}] has invalid task ID")
            continue
        if task_id in seen_ids:
            errors.append(f"duplicate task ID {task_id}")
        seen_ids.add(task_id)
        status = raw_evidence.get("status")
        crashes += status in {SearchWorkerStatus.CRASHED.value, SearchWorkerStatus.TIMEOUT.value}
        cpu_seconds = raw_evidence.get("cpu_seconds")
        if isinstance(cpu_seconds, (int, float)) and not isinstance(cpu_seconds, bool):
            worker_cpu_seconds += float(cpu_seconds)
        try:
            request_path = _safe_child(
                batch_directory,
                _string(raw_evidence.get("request_path"), "request path"),
            )
            expected_request_digest = _string(raw_evidence.get("request_sha256"), "request digest")
            if sha256_file(request_path) != expected_request_digest:
                raise ValueError("request digest mismatch")
            task = load_search_task(request_path)
            if task.task_id != task_id:
                raise ValueError("request task identity mismatch")
            if status != SearchWorkerStatus.COMPLETED.value:
                continue
            completed += 1
            result_path = _safe_child(
                batch_directory,
                _string(raw_evidence.get("result_path"), "result path"),
            )
            expected_result_digest = _string(raw_evidence.get("result_sha256"), "result digest")
            if sha256_file(result_path) != expected_result_digest:
                raise ValueError("result digest mismatch")
            result = _load_object(result_path)
            if (
                result.get("schema_version") != SEARCH_WORKER_RESULT_SCHEMA_VERSION
                or result.get("batch_id") != report.get("batch_id")
                or result.get("task_id") != task_id
                or result.get("status") != SearchWorkerStatus.COMPLETED.value
                or result.get("request_sha256") != expected_request_digest
            ):
                raise ValueError("worker result identity mismatch")
            recorded_output = _mapping(raw_evidence.get("output"), "recorded output")
            if result.get("output") != recorded_output:
                raise ValueError("batch and worker outputs differ")
            regenerated_output = execute_search_task(task)
            if regenerated_output != recorded_output:
                raise ValueError("deterministic task replay differs")
            task_transitions = _integer(recorded_output.get("transitions"), "recorded transitions")
            transitions += task_transitions
            verified += 1
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"task {task_id}: {error}")
    if seen_ids != set(configured_ids):
        errors.append("configured and recorded task IDs differ")
    expected_counts: dict[str, int | float] = {
        "requested_tasks": len(configured_ids),
        "completed_tasks": completed,
        "failed_tasks": len(configured_ids) - completed,
        "worker_crashes": crashes,
        "transitions": transitions,
        "sampled_worlds": completed,
        "worker_cpu_seconds": worker_cpu_seconds,
    }
    for key, expected in expected_counts.items():
        actual = summary.get(key)
        if isinstance(expected, float):
            if (
                not isinstance(actual, (int, float))
                or isinstance(actual, bool)
                or not math.isclose(float(actual), expected, rel_tol=1e-12, abs_tol=1e-12)
            ):
                errors.append(f"summary {key} mismatch")
        elif actual != expected:
            errors.append(f"summary {key} mismatch")
    wall_seconds = summary.get("wall_seconds")
    if isinstance(wall_seconds, (int, float)) and not isinstance(wall_seconds, bool):
        wall = float(wall_seconds)
        if wall <= 0.0:
            errors.append("summary wall_seconds must be positive")
        else:
            rates = {
                "tasks_per_wall_second": completed / wall,
                "transitions_per_wall_second": transitions / wall,
            }
            for key, expected in rates.items():
                actual = summary.get(key)
                if (
                    not isinstance(actual, (int, float))
                    or isinstance(actual, bool)
                    or not math.isclose(float(actual), expected, rel_tol=1e-12, abs_tol=1e-12)
                ):
                    errors.append(f"summary {key} mismatch")
    else:
        errors.append("summary wall_seconds is invalid")
    return SearchWorkerBatchVerification(not errors, len(configured_ids), verified, tuple(errors))


def load_search_task(path: Path) -> SearchSimulationTask:
    return SearchSimulationTask.from_mapping(_load_object(path))


def load_search_environment(specification: SearchBackendSpec) -> EnvironmentAdapter:
    if specification.kind == "mock":
        return MockSpireEnvironment()
    if specification.kind == "tactical_mock":
        return TacticalHandoffMockEnvironment()
    from spireshift.adapters.evangambit import load_evangambit_backend

    if specification.upstream_root is None or specification.manifest_path is None:
        raise RuntimeError("EvanGambit backend paths are missing")
    loaded = load_evangambit_backend(
        Path(specification.upstream_root),
        Path(specification.manifest_path),
    )
    return loaded.factory()


def restore_search_checkpoint(
    backend: SearchBackendSpec,
    checkpoint: PublicStateCheckpoint,
) -> tuple[EnvironmentAdapter, Observation]:
    environment = load_search_environment(backend)
    observation = environment.reset(checkpoint.run_seed)
    for action_id in checkpoint.action_prefix:
        action = _action_by_id(environment.legal_actions(), action_id)
        observation = environment.step(action).next_observation
    if environment.patch_id != checkpoint.patch_id:
        raise RuntimeError("Restored checkpoint patch identity mismatch")
    if environment.ruleset.manifest_id != checkpoint.ruleset_manifest_id:
        raise RuntimeError("Restored checkpoint ruleset identity mismatch")
    if observation.state_hash != checkpoint.state_hash:
        raise RuntimeError("Restored checkpoint public state hash mismatch")
    return environment, observation


def _write_task_request(
    batch_id: str,
    task: SearchSimulationTask,
    output_directory: Path,
    timeout_seconds: float,
) -> SearchWorkerRequest:
    task_directory = output_directory / "tasks" / task.task_id
    task_directory.mkdir(parents=True, exist_ok=False)
    request_path = task_directory / "request.json"
    write_exclusive_json(request_path, task.as_dict())
    return SearchWorkerRequest(
        batch_id=batch_id,
        task=task,
        batch_directory=output_directory,
        request_path=request_path,
        result_path=task_directory / "result.json",
        timeout_seconds=timeout_seconds,
    )


def _validate_completed_output(task: SearchSimulationTask, output: dict[str, object]) -> None:
    expected = {
        "method": SEARCH_WORKER_METHOD,
        "patch_id": task.checkpoint.patch_id,
        "ruleset_manifest_id": task.checkpoint.ruleset_manifest_id,
        "source_state_hash": task.checkpoint.state_hash,
        "action_id": task.action_id,
        "simulation_seed": task.simulation_seed,
        "checkpoint_verified": True,
        "sampled_worlds": 1,
    }
    if any(output.get(key) != value for key, value in expected.items()):
        raise ValueError("Completed worker output identity mismatch")
    transitions = _integer(output.get("transitions"), "worker output transitions")
    if not 1 <= transitions <= task.maximum_rollout_steps:
        raise ValueError("Completed worker transition count is outside its declared limit")
    terminal = _boolean(output.get("terminal"), "worker output terminal")
    truncated = _boolean(output.get("truncated"), "worker output truncated")
    if terminal == truncated:
        raise ValueError("Worker output terminal and truncated flags are inconsistent")


def _failed_evidence(
    request: SearchWorkerRequest,
    status: SearchWorkerStatus,
    exit_code: int | None,
    message: str,
) -> SearchWorkerEvidence:
    return SearchWorkerEvidence(
        task_id=request.task.task_id,
        status=status,
        exit_code=exit_code,
        worker_pid=None,
        message=message,
        request_path=_relative_path(request.request_path, request.batch_directory),
        result_path=_relative_path(request.result_path, request.batch_directory),
        request_sha256=sha256_file(request.request_path),
        result_sha256=(sha256_file(request.result_path) if request.result_path.is_file() else None),
        cpu_seconds=None,
        wall_seconds=None,
        output=None,
    )


def _action_by_id(actions: Sequence[LegalAction], action_id: str) -> LegalAction:
    matches = [action for action in actions if action.action_id == action_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one legal action {action_id!r}, found {len(matches)}")
    return matches[0]


def _relative_path(path: Path, directory: Path) -> str:
    return str(path.resolve().relative_to(directory.resolve()))


def _safe_child(directory: Path, relative: str) -> Path:
    candidate = (directory / relative).resolve()
    if candidate == directory or directory not in candidate.parents:
        raise ValueError("evidence path escapes the batch directory")
    if not candidate.is_file():
        raise ValueError("evidence file is missing")
    return candidate


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value, "optional string")


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _optional_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _optional_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if result >= 0.0 else None


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
