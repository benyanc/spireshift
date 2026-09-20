from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import UUID, uuid4

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import PolicyOnlyBudgetController, TerminalVictoryPolicy
from spireshift.core.objective import load_objective
from spireshift.replay import verify_mock_replay

ROLLOUT_BATCH_SCHEMA_VERSION = "rollout-batch-v1"
ROLLOUT_WORKER_RESULT_SCHEMA_VERSION = "rollout-worker-result-v1"
ROLLOUT_BATCH_REPLAY_SCHEMA_VERSION = "rollout-batch-replay-v1"


class AttemptStatus(StrEnum):
    COMPLETED = "completed"
    WORKER_ERROR = "worker_error"
    REPLAY_FAILED = "replay_failed"
    CRASHED = "crashed"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class WorkerRequest:
    batch_id: str
    seed: int
    attempt: int
    objective_config: Path
    batch_directory: Path
    record_path: Path
    result_path: Path
    timeout_seconds: float


@dataclass(frozen=True, slots=True)
class AttemptEvidence:
    seed: int
    attempt: int
    status: AttemptStatus
    exit_code: int | None
    worker_pid: int | None
    message: str
    record_path: str
    result_path: str
    record_sha256: str | None
    victory: bool | None
    decisions: int | None
    compute_used: int | None
    replay_verified: bool

    @property
    def completed(self) -> bool:
        return self.status is AttemptStatus.COMPLETED and self.replay_verified

    @property
    def crashed(self) -> bool:
        return self.status in {AttemptStatus.CRASHED, AttemptStatus.TIMEOUT}

    def as_dict(self) -> dict[str, object]:
        return {
            "seed": self.seed,
            "attempt": self.attempt,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "worker_pid": self.worker_pid,
            "message": self.message,
            "record_path": self.record_path,
            "result_path": self.result_path,
            "record_sha256": self.record_sha256,
            "victory": self.victory,
            "decisions": self.decisions,
            "compute_used": self.compute_used,
            "replay_verified": self.replay_verified,
        }


@dataclass(frozen=True, slots=True)
class RolloutBatchResult:
    successful: bool
    report_path: Path
    report: dict[str, object]


@dataclass(frozen=True, slots=True)
class BatchReplayResult:
    valid: bool
    runs: int
    verified_runs: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": ROLLOUT_BATCH_REPLAY_SCHEMA_VERSION,
            "valid": self.valid,
            "runs": self.runs,
            "verified_runs": self.verified_runs,
            "errors": list(self.errors),
        }


class AttemptRunner(Protocol):
    def __call__(self, request: WorkerRequest) -> AttemptEvidence: ...


def run_mock_rollout_batch(
    *,
    seeds: Sequence[int],
    workers: int,
    maximum_attempts: int,
    worker_timeout_seconds: float,
    output_directory: Path,
    objective_config: Path,
    attempt_runner: AttemptRunner | None = None,
    batch_id: str | None = None,
    now: Callable[[], str] | None = None,
) -> RolloutBatchResult:
    canonical_seeds = tuple(seeds)
    if not canonical_seeds:
        raise ValueError("At least one rollout seed is required")
    if len(canonical_seeds) != len(set(canonical_seeds)):
        raise ValueError("Rollout seeds must be unique")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if maximum_attempts <= 0:
        raise ValueError("maximum_attempts must be positive")
    if worker_timeout_seconds <= 0:
        raise ValueError("worker_timeout_seconds must be positive")
    canonical_batch_id = str(uuid4()) if batch_id is None else str(UUID(batch_id))
    clock_now = _utc_now if now is None else now
    objective_path = objective_config.resolve()
    objective = load_objective(objective_path)
    started_at = clock_now()
    output_directory.mkdir(parents=True, exist_ok=False)
    output_directory = output_directory.resolve()
    runner = run_subprocess_attempt if attempt_runner is None else attempt_runner

    attempts: list[AttemptEvidence] = []
    final_by_seed: dict[int, AttemptEvidence] = {}
    pending: dict[int, int] = {seed: 1 for seed in canonical_seeds}
    with ThreadPoolExecutor(max_workers=min(workers, len(canonical_seeds))) as executor:
        while pending:
            future_to_request: dict[Future[AttemptEvidence], WorkerRequest] = {}
            for seed, attempt in sorted(pending.items()):
                request = _worker_request(
                    batch_id=canonical_batch_id,
                    seed=seed,
                    attempt=attempt,
                    objective_config=objective_path,
                    output_directory=output_directory,
                    timeout_seconds=worker_timeout_seconds,
                )
                future_to_request[executor.submit(runner, request)] = request
            pending = {}
            for future in as_completed(future_to_request):
                request = future_to_request[future]
                try:
                    evidence = future.result()
                except Exception as error:
                    evidence = _coordinator_failure(request, error)
                if evidence.seed != request.seed or evidence.attempt != request.attempt:
                    evidence = _coordinator_failure(
                        request,
                        ValueError("attempt runner returned evidence for a different request"),
                    )
                attempts.append(evidence)
                if evidence.completed or request.attempt >= maximum_attempts:
                    final_by_seed[request.seed] = evidence
                else:
                    pending[request.seed] = request.attempt + 1

    ordered_attempts = tuple(sorted(attempts, key=lambda item: (item.seed, item.attempt)))
    outcomes = [_outcome(seed, ordered_attempts, final_by_seed[seed]) for seed in canonical_seeds]
    completed = [evidence for evidence in final_by_seed.values() if evidence.completed]
    victories = sum(evidence.victory is True for evidence in completed)
    requested_runs = len(canonical_seeds)
    failed_runs = requested_runs - len(completed)
    worker_crashes = sum(evidence.crashed for evidence in ordered_attempts)
    failed_attempts = sum(not evidence.completed for evidence in ordered_attempts)
    recovered_runs = sum(
        final_by_seed[seed].completed
        and any(not attempt.completed for attempt in ordered_attempts if attempt.seed == seed)
        for seed in canonical_seeds
    )
    report: dict[str, object] = {
        "schema_version": ROLLOUT_BATCH_SCHEMA_VERSION,
        "batch_id": canonical_batch_id,
        "backend": "mock",
        "started_at": started_at,
        "completed_at": clock_now(),
        "configuration": {
            "seeds": list(canonical_seeds),
            "workers": workers,
            "maximum_attempts": maximum_attempts,
            "worker_timeout_seconds": worker_timeout_seconds,
        },
        "ruleset": MockSpireEnvironment.ruleset.as_dict(),
        "objective": objective.as_dict(),
        "policy_id": TerminalVictoryPolicy().policy_id,
        "controller_id": PolicyOnlyBudgetController().controller_id,
        "summary": {
            "requested_runs": requested_runs,
            "benchmark_denominator": requested_runs,
            "completed_runs": len(completed),
            "verified_runs": sum(evidence.replay_verified for evidence in completed),
            "victories": victories,
            "defeats": len(completed) - victories,
            "failed_runs": failed_runs,
            "attempts": len(ordered_attempts),
            "failed_attempts": failed_attempts,
            "worker_crashes": worker_crashes,
            "recovered_runs": recovered_runs,
            "victory_rate": victories / requested_runs,
            "completion_rate": len(completed) / requested_runs,
        },
        "outcomes": outcomes,
        "attempts": [attempt.as_dict() for attempt in ordered_attempts],
    }
    report_path = output_directory / "rollout-report.json"
    write_exclusive_json(report_path, report)
    return RolloutBatchResult(failed_runs == 0, report_path, report)


def run_subprocess_attempt(request: WorkerRequest) -> AttemptEvidence:
    command = [
        sys.executable,
        "-m",
        "spireshift.rollout_worker",
        "--batch-id",
        request.batch_id,
        "--seed",
        str(request.seed),
        "--attempt",
        str(request.attempt),
        "--objective-config",
        str(request.objective_config),
        "--record",
        str(request.record_path),
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
        return _failed_attempt(
            request,
            AttemptStatus.TIMEOUT,
            None,
            f"worker exceeded {request.timeout_seconds:g}s timeout",
        )
    if not request.result_path.exists():
        stderr = completed.stderr.strip()
        message = "worker exited without an immutable result"
        if stderr:
            message = f"{message}: {stderr[-1000:]}"
        return _failed_attempt(
            request,
            AttemptStatus.CRASHED,
            completed.returncode,
            message,
        )
    try:
        result = _load_object(request.result_path)
        status = AttemptStatus(str(result["status"]))
    except (KeyError, OSError, ValueError, json.JSONDecodeError) as error:
        return _failed_attempt(
            request,
            AttemptStatus.CRASHED,
            completed.returncode,
            f"invalid worker result: {error}",
        )
    if (
        result.get("schema_version") != ROLLOUT_WORKER_RESULT_SCHEMA_VERSION
        or result.get("batch_id") != request.batch_id
        or result.get("seed") != request.seed
        or result.get("attempt") != request.attempt
    ):
        return _failed_attempt(
            request,
            AttemptStatus.CRASHED,
            completed.returncode,
            "worker result identity mismatch",
        )
    actual_digest = sha256_file(request.record_path) if request.record_path.is_file() else None
    replay_verified = result.get("replay_verified") is True
    message = str(result.get("message", status.value))
    victory = _optional_bool(result.get("victory"))
    decisions = _optional_int(result.get("decisions"))
    compute_used = _optional_int(result.get("compute_used"))
    worker_pid = _optional_int(result.get("worker_pid"))
    if status is AttemptStatus.COMPLETED:
        if completed.returncode != 0:
            status = AttemptStatus.WORKER_ERROR
            message = f"completed worker returned exit code {completed.returncode}"
        elif worker_pid is None:
            status = AttemptStatus.WORKER_ERROR
            message = "completed worker omitted its process identity"
        elif actual_digest is None:
            status = AttemptStatus.REPLAY_FAILED
            message = "completed worker did not produce a run record"
        elif result.get("record_sha256") != actual_digest:
            status = AttemptStatus.REPLAY_FAILED
            message = "worker record digest mismatch"
        else:
            independent_replay = verify_mock_replay(request.record_path)
            if not replay_verified or not independent_replay.valid:
                status = AttemptStatus.REPLAY_FAILED
                replay_verified = False
                message = independent_replay.message
            else:
                records = _load_jsonl_objects(request.record_path)
                summary = records[-1]
                if (
                    victory is not independent_replay.victory
                    or decisions != independent_replay.steps
                    or compute_used != summary.get("compute_used")
                ):
                    status = AttemptStatus.REPLAY_FAILED
                    replay_verified = False
                    message = "worker metrics differ from replayed run"
    return AttemptEvidence(
        seed=request.seed,
        attempt=request.attempt,
        status=status,
        exit_code=completed.returncode,
        worker_pid=worker_pid,
        message=message,
        record_path=_relative_path(request.record_path, request.batch_directory),
        result_path=_relative_path(request.result_path, request.batch_directory),
        record_sha256=actual_digest,
        victory=victory,
        decisions=decisions,
        compute_used=compute_used,
        replay_verified=replay_verified,
    )


def verify_rollout_batch(report_path: Path) -> BatchReplayResult:
    errors: list[str] = []
    try:
        report = _load_object(report_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return BatchReplayResult(False, 0, 0, (str(error),))
    if report.get("schema_version") != ROLLOUT_BATCH_SCHEMA_VERSION:
        return BatchReplayResult(False, 0, 0, ("unsupported rollout report schema",))
    outcomes = report.get("outcomes")
    attempts = report.get("attempts")
    summary = report.get("summary")
    configuration = report.get("configuration")
    if not isinstance(outcomes, list) or not isinstance(attempts, list):
        return BatchReplayResult(False, 0, 0, ("report outcomes and attempts must be arrays",))
    if not isinstance(summary, dict) or not isinstance(configuration, dict):
        return BatchReplayResult(False, 0, 0, ("report summary and configuration must be objects",))
    seeds = configuration.get("seeds")
    if not isinstance(seeds, list) or any(not isinstance(seed, int) for seed in seeds):
        errors.append("configuration seeds must be integers")
        seeds = []
    if len(seeds) != len(set(seeds)):
        errors.append("configuration seeds are not unique")
    if len(outcomes) != len(seeds):
        errors.append("outcome count differs from the benchmark denominator")
    if report.get("backend") != "mock":
        errors.append("unsupported rollout backend")
    if report.get("ruleset") != MockSpireEnvironment.ruleset.as_dict():
        errors.append("batch ruleset identity mismatch")

    valid_statuses = {status.value for status in AttemptStatus}
    attempts_by_seed: dict[int, list[dict[str, Any]]] = {seed: [] for seed in seeds}
    seen_attempts: set[tuple[int, int]] = set()
    failed_attempts = 0
    worker_crashes = 0
    for raw_attempt in attempts:
        if not isinstance(raw_attempt, dict):
            errors.append("attempt must be an object")
            continue
        seed = raw_attempt.get("seed")
        attempt_number = raw_attempt.get("attempt")
        status = raw_attempt.get("status")
        if not isinstance(seed, int) or seed not in attempts_by_seed:
            errors.append(f"attempt has unknown seed {seed!r}")
            continue
        if not isinstance(attempt_number, int) or attempt_number <= 0:
            errors.append(f"seed {seed}: attempt number must be positive")
            continue
        if (seed, attempt_number) in seen_attempts:
            errors.append(f"seed {seed}: duplicate attempt {attempt_number}")
        seen_attempts.add((seed, attempt_number))
        if status not in valid_statuses:
            errors.append(f"seed {seed}: unsupported attempt status {status!r}")
            continue
        attempts_by_seed[seed].append(raw_attempt)
        failed_attempts += status != AttemptStatus.COMPLETED.value
        worker_crashes += status in {AttemptStatus.CRASHED.value, AttemptStatus.TIMEOUT.value}

    for seed, seed_attempts in attempts_by_seed.items():
        numbers = sorted(cast(int, attempt["attempt"]) for attempt in seed_attempts)
        if numbers != list(range(1, len(numbers) + 1)):
            errors.append(f"seed {seed}: attempts are not contiguous from one")

    verified_runs = 0
    completed_outcomes = 0
    victories = 0
    recovered_runs = 0
    seen_outcome_seeds: set[int] = set()
    batch_directory = report_path.parent.resolve()
    for raw_outcome in outcomes:
        if not isinstance(raw_outcome, dict):
            errors.append("outcome must be an object")
            continue
        seed = raw_outcome.get("seed")
        if not isinstance(seed, int) or seed not in attempts_by_seed:
            errors.append(f"outcome has unknown seed {seed!r}")
            continue
        if seed in seen_outcome_seeds:
            errors.append(f"seed {seed}: duplicate outcome")
        seen_outcome_seeds.add(seed)
        seed_attempts = attempts_by_seed[seed]
        if not seed_attempts:
            errors.append(f"seed {seed}: outcome has no attempts")
            continue
        final_attempt = max(seed_attempts, key=lambda item: cast(int, item["attempt"]))
        if raw_outcome.get("attempt_count") != len(seed_attempts):
            errors.append(f"seed {seed}: outcome attempt count mismatch")
        if raw_outcome.get("final_attempt") != final_attempt.get("attempt"):
            errors.append(f"seed {seed}: final attempt mismatch")
        completed = raw_outcome.get("status") == "completed"
        if completed != (final_attempt.get("status") == AttemptStatus.COMPLETED.value):
            errors.append(f"seed {seed}: final attempt status mismatch")
        if not completed:
            if raw_outcome.get("failure_status") != final_attempt.get("status"):
                errors.append(f"seed {seed}: final failure status mismatch")
            continue
        completed_outcomes += 1
        victories += raw_outcome.get("victory") is True
        recovered_runs += any(
            attempt.get("status") != AttemptStatus.COMPLETED.value for attempt in seed_attempts
        )
        for field in (
            "victory",
            "decisions",
            "compute_used",
            "record_path",
            "record_sha256",
            "replay_verified",
        ):
            if raw_outcome.get(field) != final_attempt.get(field):
                errors.append(f"seed {seed}: outcome {field} differs from final attempt")
        record_value = raw_outcome.get("record_path")
        expected_digest = raw_outcome.get("record_sha256")
        if not isinstance(record_value, str) or not isinstance(expected_digest, str):
            errors.append(f"seed {seed}: completed outcome lacks record evidence")
            continue
        try:
            record_path = _safe_child(batch_directory, record_value)
        except ValueError as error:
            errors.append(f"seed {seed}: {error}")
            continue
        if not record_path.is_file():
            errors.append(f"seed {seed}: run record is missing")
            continue
        if sha256_file(record_path) != expected_digest:
            errors.append(f"seed {seed}: run record digest mismatch")
            continue
        replay = verify_mock_replay(record_path)
        if not replay.valid:
            errors.append(f"seed {seed}: {replay.message}")
            continue
        try:
            records = _load_jsonl_objects(record_path)
            result_value = final_attempt.get("result_path")
            if not isinstance(result_value, str):
                raise ValueError("worker result path must be a string")
            worker_result_path = _safe_child(batch_directory, result_value)
            worker_result = _load_object(worker_result_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"seed {seed}: invalid worker evidence: {error}")
            continue
        header = records[0]
        record_summary = records[-1]
        if (
            header.get("objective") != report.get("objective")
            or header.get("policy_id") != report.get("policy_id")
            or header.get("controller_id") != report.get("controller_id")
        ):
            errors.append(f"seed {seed}: run metadata differs from batch metadata")
            continue
        if (
            raw_outcome.get("victory") is not replay.victory
            or raw_outcome.get("decisions") != replay.steps
            or raw_outcome.get("compute_used") != record_summary.get("compute_used")
        ):
            errors.append(f"seed {seed}: outcome metrics differ from replayed run")
            continue
        if not isinstance(final_attempt.get("worker_pid"), int):
            errors.append(f"seed {seed}: completed attempt lacks a worker process ID")
            continue
        expected_worker_fields = {
            "schema_version": ROLLOUT_WORKER_RESULT_SCHEMA_VERSION,
            "batch_id": report.get("batch_id"),
            "seed": seed,
            "attempt": final_attempt.get("attempt"),
            "status": AttemptStatus.COMPLETED.value,
            "worker_pid": final_attempt.get("worker_pid"),
            "record_sha256": expected_digest,
            "victory": raw_outcome.get("victory"),
            "decisions": raw_outcome.get("decisions"),
            "compute_used": raw_outcome.get("compute_used"),
            "replay_verified": True,
        }
        if any(worker_result.get(key) != value for key, value in expected_worker_fields.items()):
            errors.append(f"seed {seed}: worker result differs from batch evidence")
            continue
        verified_runs += 1

    if seen_outcome_seeds != set(seeds):
        errors.append("outcome seeds differ from configured seeds")

    requested = len(seeds)
    expected_counts = {
        "requested_runs": requested,
        "benchmark_denominator": requested,
        "completed_runs": completed_outcomes,
        "verified_runs": verified_runs,
        "victories": victories,
        "defeats": completed_outcomes - victories,
        "failed_runs": requested - completed_outcomes,
        "attempts": len(attempts),
        "failed_attempts": failed_attempts,
        "worker_crashes": worker_crashes,
        "recovered_runs": recovered_runs,
    }
    for key, expected in expected_counts.items():
        if summary.get(key) != expected:
            errors.append(f"summary {key} mismatch: expected {expected}, got {summary.get(key)!r}")
    expected_victory_rate = victories / requested if requested else 0.0
    if summary.get("victory_rate") != expected_victory_rate:
        errors.append("summary victory_rate does not use the requested-run denominator")
    expected_completion_rate = completed_outcomes / requested if requested else 0.0
    if summary.get("completion_rate") != expected_completion_rate:
        errors.append("summary completion_rate does not use the requested-run denominator")
    return BatchReplayResult(not errors, requested, verified_runs, tuple(errors))


def write_exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _worker_request(
    *,
    batch_id: str,
    seed: int,
    attempt: int,
    objective_config: Path,
    output_directory: Path,
    timeout_seconds: float,
) -> WorkerRequest:
    attempt_directory = output_directory / "attempts" / f"seed-{seed}" / f"attempt-{attempt}"
    attempt_directory.mkdir(parents=True, exist_ok=False)
    return WorkerRequest(
        batch_id=batch_id,
        seed=seed,
        attempt=attempt,
        objective_config=objective_config,
        batch_directory=output_directory,
        record_path=attempt_directory / "run.jsonl",
        result_path=attempt_directory / "worker-result.json",
        timeout_seconds=timeout_seconds,
    )


def _failed_attempt(
    request: WorkerRequest,
    status: AttemptStatus,
    exit_code: int | None,
    message: str,
) -> AttemptEvidence:
    return AttemptEvidence(
        seed=request.seed,
        attempt=request.attempt,
        status=status,
        exit_code=exit_code,
        worker_pid=None,
        message=message,
        record_path=_relative_path(request.record_path, request.batch_directory),
        result_path=_relative_path(request.result_path, request.batch_directory),
        record_sha256=(sha256_file(request.record_path) if request.record_path.is_file() else None),
        victory=None,
        decisions=None,
        compute_used=None,
        replay_verified=False,
    )


def _coordinator_failure(request: WorkerRequest, error: Exception) -> AttemptEvidence:
    return _failed_attempt(
        request,
        AttemptStatus.CRASHED,
        None,
        f"attempt runner raised {type(error).__name__}: {error}",
    )


def _outcome(
    seed: int,
    attempts: Sequence[AttemptEvidence],
    final: AttemptEvidence,
) -> dict[str, object]:
    seed_attempts = [attempt for attempt in attempts if attempt.seed == seed]
    return {
        "seed": seed,
        "status": "completed" if final.completed else "failed",
        "attempt_count": len(seed_attempts),
        "final_attempt": final.attempt,
        "victory": final.victory if final.completed else None,
        "decisions": final.decisions if final.completed else None,
        "compute_used": final.compute_used if final.completed else None,
        "record_path": final.record_path if final.completed else None,
        "record_sha256": final.record_sha256 if final.completed else None,
        "replay_verified": final.replay_verified if final.completed else False,
        "failure_status": None if final.completed else final.status.value,
        "failure_message": None if final.completed else final.message,
    }


def _safe_child(directory: Path, relative: str) -> Path:
    candidate = (directory / relative).resolve()
    if candidate == directory or directory not in candidate.parents:
        raise ValueError("record path escapes the batch directory")
    return candidate


def _relative_path(path: Path, directory: Path) -> str:
    return str(path.resolve().relative_to(directory.resolve()))


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def _load_jsonl_objects(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            value: object = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} contains a non-object record")
            values.append(cast(dict[str, Any], value))
    if not values:
        raise ValueError(f"{path} is empty")
    return values


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
