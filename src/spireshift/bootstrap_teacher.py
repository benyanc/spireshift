from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from spireshift.agents.baseline import ProgressBootstrapPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.mechanics import PublicMechanicsService
from spireshift.representations import model_input_from_mapping
from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.search_workers import (
    PublicStateCheckpoint,
    SearchBackendSpec,
    capture_checkpoint,
    load_search_environment,
    restore_search_checkpoint,
)
from spireshift.splits import SplitManifest, SplitName

BOOTSTRAP_STATE_SET_SCHEMA_VERSION = "bootstrap-state-set-v1"
BOOTSTRAP_TASK_SCHEMA_VERSION = "bootstrap-simulation-task-v1"
BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION = "bootstrap-worker-result-v1"
BOOTSTRAP_BATCH_SCHEMA_VERSION = "bootstrap-worker-batch-v1"
BOOTSTRAP_DATASET_SCHEMA_VERSION = "bootstrap-teacher-dataset-v1"
BOOTSTRAP_VERIFICATION_SCHEMA_VERSION = "bootstrap-teacher-verification-v1"
BOOTSTRAP_TEACHER_ID = "paired-terminal-dominant-progress-teacher-v1"
BOOTSTRAP_UTILITY_ID = "terminal-dominant-floor-act-hp-v1"
BOOTSTRAP_SEED_PROTOCOL_ID = "sha256-paired-bootstrap-v1"
MILESTONE_FLOORS = (1, 8, 16, 24, 32, 40, 48, 56, 64)


@dataclass(frozen=True, slots=True)
class BootstrapStateCase:
    state_id: str
    run_seed: int
    combat_state_index: int
    expected_state_hash: str
    expected_legal_actions: int

    def as_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "run_seed": self.run_seed,
            "combat_state_index": self.combat_state_index,
            "expected_state_hash": self.expected_state_hash,
            "expected_legal_actions": self.expected_legal_actions,
        }


@dataclass(frozen=True, slots=True)
class BootstrapStateSet:
    state_set_id: str
    split_manifest_id: str
    ruleset_manifest_id: str
    objective_id: str
    capture_policy_id: str
    partition: str
    selection_policy: str
    cases: tuple[BootstrapStateCase, ...]

    def __post_init__(self) -> None:
        if self.partition != SplitName.TRAIN.value:
            raise ValueError("Bootstrap state sets must use the train partition")
        if self.capture_policy_id != ProgressBootstrapPolicy.policy_id:
            raise ValueError("Bootstrap state set uses an unsupported capture policy")
        if not self.cases:
            raise ValueError("Bootstrap state set must contain at least one case")
        ids = [case.state_id for case in self.cases]
        coordinates = [(case.run_seed, case.combat_state_index) for case in self.cases]
        if len(ids) != len(set(ids)) or len(coordinates) != len(set(coordinates)):
            raise ValueError("Bootstrap cases must have unique IDs and coordinates")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": BOOTSTRAP_STATE_SET_SCHEMA_VERSION,
            "state_set_id": self.state_set_id,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "capture_policy_id": self.capture_policy_id,
            "partition": self.partition,
            "selection_policy": self.selection_policy,
            "cases": [case.as_dict() for case in self.cases],
        }


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    samples_per_candidate: int = 16
    sampling_seed: int = 0
    maximum_prefix_steps: int = 4096
    maximum_rollout_steps: int = 4096
    workers: int = 8
    worker_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        for name, value in (
            ("samples_per_candidate", self.samples_per_candidate),
            ("maximum_prefix_steps", self.maximum_prefix_steps),
            ("maximum_rollout_steps", self.maximum_rollout_steps),
            ("workers", self.workers),
        ):
            if isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if isinstance(self.sampling_seed, bool) or self.sampling_seed < 0:
            raise ValueError("sampling_seed must be non-negative")
        if not math.isfinite(self.worker_timeout_seconds) or self.worker_timeout_seconds <= 0.0:
            raise ValueError("worker_timeout_seconds must be finite and positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "samples_per_candidate": self.samples_per_candidate,
            "sampling_seed": self.sampling_seed,
            "maximum_prefix_steps": self.maximum_prefix_steps,
            "maximum_rollout_steps": self.maximum_rollout_steps,
            "workers": self.workers,
            "worker_timeout_seconds": self.worker_timeout_seconds,
        }


@dataclass(frozen=True, slots=True)
class BootstrapSimulationTask:
    task_id: str
    backend: SearchBackendSpec
    checkpoint: PublicStateCheckpoint
    action_id: str
    simulation_seed: int
    maximum_rollout_steps: int

    def __post_init__(self) -> None:
        UUID(self.task_id)
        if not self.action_id:
            raise ValueError("Bootstrap action ID must be non-empty")
        if isinstance(self.simulation_seed, bool) or self.simulation_seed < 0:
            raise ValueError("Bootstrap simulation seed must be non-negative")
        if self.maximum_rollout_steps <= 0:
            raise ValueError("Bootstrap rollout limit must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": BOOTSTRAP_TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "backend": self.backend.as_dict(),
            "checkpoint": self.checkpoint.as_dict(),
            "action_id": self.action_id,
            "simulation_seed": self.simulation_seed,
            "maximum_rollout_steps": self.maximum_rollout_steps,
            "continuation_policy_id": ProgressBootstrapPolicy.policy_id,
        }

    @classmethod
    def from_mapping(cls, value: object) -> BootstrapSimulationTask:
        document = _mapping(value, "bootstrap task")
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
                "continuation_policy_id",
            },
            "bootstrap task",
        )
        if document.get("schema_version") != BOOTSTRAP_TASK_SCHEMA_VERSION:
            raise ValueError("Unsupported bootstrap task schema")
        if document.get("continuation_policy_id") != ProgressBootstrapPolicy.policy_id:
            raise ValueError("Unsupported bootstrap continuation policy")
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
class BootstrapTaskEvidence:
    task_id: str
    status: str
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
        return self.status == "completed" and self.output is not None

    def as_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "status": self.status,
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
class BootstrapDatasetResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class BootstrapVerification:
    valid: bool
    dataset_id: str | None
    cases: int
    verified_cases: int
    replayed_cases: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": BOOTSTRAP_VERIFICATION_SCHEMA_VERSION,
            "valid": self.valid,
            "dataset_id": self.dataset_id,
            "cases": self.cases,
            "verified_cases": self.verified_cases,
            "replayed_cases": self.replayed_cases,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class _CapturedBootstrapState:
    checkpoint: PublicStateCheckpoint
    observation: Observation
    legal_actions: tuple[LegalAction, ...]


def freeze_bootstrap_state_set(
    specification: object,
    *,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    document = _mapping(specification, "bootstrap state-set specification")
    _exact_keys(
        document,
        {
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "capture_policy_id",
            "partition",
            "selection_policy",
            "cases",
        },
        "bootstrap state-set specification",
    )
    body: dict[str, Any] = {
        "schema_version": BOOTSTRAP_STATE_SET_SCHEMA_VERSION,
        "split_manifest_id": _string(document.get("split_manifest_id"), "split_manifest_id"),
        "ruleset_manifest_id": _string(document.get("ruleset_manifest_id"), "ruleset_manifest_id"),
        "objective_id": _string(document.get("objective_id"), "objective_id"),
        "capture_policy_id": _string(document.get("capture_policy_id"), "capture_policy_id"),
        "partition": _string(document.get("partition"), "partition"),
        "selection_policy": _string(document.get("selection_policy"), "selection_policy"),
        "cases": [
            _state_case(value).as_dict()
            for value in _list(document.get("cases"), "bootstrap cases")
        ],
    }
    frozen = {**body, "state_set_id": manifest_identifier(body)}
    state_set = load_bootstrap_state_set_document(frozen)
    _validate_bootstrap_split(state_set, split_manifest)
    return frozen


def load_bootstrap_state_set(path: Path) -> BootstrapStateSet:
    return load_bootstrap_state_set_document(_load_object(path))


def load_bootstrap_state_set_document(value: object) -> BootstrapStateSet:
    document = _mapping(value, "bootstrap state set")
    _exact_keys(
        document,
        {
            "schema_version",
            "state_set_id",
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "capture_policy_id",
            "partition",
            "selection_policy",
            "cases",
        },
        "bootstrap state set",
    )
    if document.get("schema_version") != BOOTSTRAP_STATE_SET_SCHEMA_VERSION:
        raise ValueError("Unsupported bootstrap state-set schema")
    state_set_id = _string(document.get("state_set_id"), "state_set_id")
    body = {key: item for key, item in document.items() if key != "state_set_id"}
    if state_set_id != manifest_identifier(body):
        raise ValueError("Bootstrap state-set identity mismatch")
    return BootstrapStateSet(
        state_set_id=state_set_id,
        split_manifest_id=_string(document.get("split_manifest_id"), "split_manifest_id"),
        ruleset_manifest_id=_string(document.get("ruleset_manifest_id"), "ruleset_manifest_id"),
        objective_id=_string(document.get("objective_id"), "objective_id"),
        capture_policy_id=_string(document.get("capture_policy_id"), "capture_policy_id"),
        partition=_string(document.get("partition"), "partition"),
        selection_policy=_string(document.get("selection_policy"), "selection_policy"),
        cases=tuple(
            _state_case(value) for value in _list(document.get("cases"), "bootstrap cases")
        ),
    )


def write_bootstrap_state_set(document: object, path: Path) -> None:
    write_exclusive_json(path, load_bootstrap_state_set_document(document).as_dict())


def capture_bootstrap_combat_state(
    *,
    backend: SearchBackendSpec,
    run_seed: int,
    combat_state_index: int,
    maximum_prefix_steps: int,
) -> _CapturedBootstrapState:
    environment = load_search_environment(backend)
    try:
        observation = environment.reset(run_seed)
        policy = ProgressBootstrapPolicy()
        prefix: list[str] = []
        seen = 0
        for _ in range(maximum_prefix_steps + 1):
            if observation.decision_type in {DecisionType.COMBAT, DecisionType.COMBAT_SELECTION}:
                if seen == combat_state_index:
                    actions = tuple(environment.legal_actions())
                    if not actions:
                        raise RuntimeError("Captured bootstrap state has no legal actions")
                    return _CapturedBootstrapState(
                        capture_checkpoint(
                            run_seed=run_seed,
                            action_prefix=prefix,
                            environment=environment,
                            observation=observation,
                        ),
                        observation,
                        actions,
                    )
                seen += 1
            if bool(observation.public_state.get("terminal")):
                break
            action = policy.choose_action(observation, tuple(environment.legal_actions()))
            prefix.append(action.action_id)
            observation = environment.step(action).next_observation
    finally:
        _close_environment(environment)
    raise RuntimeError(
        f"Run seed {run_seed} did not reach combat state {combat_state_index} "
        f"within {maximum_prefix_steps} decisions"
    )


def execute_bootstrap_task(task: BootstrapSimulationTask) -> dict[str, object]:
    environment, source = restore_search_checkpoint(task.backend, task.checkpoint)
    sampled: object | None = None
    try:
        mechanics = PublicMechanicsService()
        source_snapshot = mechanics.snapshot(environment, source)
        source_action = _action_by_id(source_snapshot.legal_actions, task.action_id)
        sampled = environment.clone(resample_hidden=True, seed=task.simulation_seed)
        policy = ProgressBootstrapPolicy()
        source_floor = _public_integer(source, ("floor",), ("run", "floor"))
        source_act = _public_act(source)
        maximum_floor = source_floor
        decisions = 0
        sampled_snapshot = mechanics.snapshot(sampled, source)
        if sampled_snapshot.legal_actions != source_snapshot.legal_actions:
            raise RuntimeError("Hidden-world clone changed public legal actions")
        action = _action_by_id(sampled_snapshot.legal_actions, source_action.action_id)
        transition = sampled.step(action)
        if transition.observation != source:
            raise RuntimeError("Hidden-world clone changed the source public observation")
        decisions = 1
        observation = transition.next_observation
        maximum_floor = _maximum_optional(
            maximum_floor, _public_integer(observation, ("floor",), ("run", "floor"))
        )
        while not transition.terminal and decisions < task.maximum_rollout_steps:
            continuation = policy.choose_action(observation, tuple(sampled.legal_actions()))
            transition = sampled.step(continuation)
            decisions += 1
            observation = transition.next_observation
            maximum_floor = _maximum_optional(
                maximum_floor,
                _public_integer(observation, ("floor",), ("run", "floor")),
            )
        final_floor = _public_integer(observation, ("floor",), ("run", "floor"))
        final_hp = _public_integer(observation, ("player_hp",), ("player", "hp"))
        final_max_hp = _public_integer(observation, ("player_max_hp",), ("player", "max_hp"))
        final_gold = _public_integer(observation, ("gold",), ("player", "gold"))
        final_potion_count = _public_sequence_length(
            observation, ("potions",), ("player", "potions")
        )
        final_relic_count = _public_sequence_length(observation, ("relics",), ("player", "relics"))
        final_act = _public_act(observation)
        act_completed = (
            None
            if source_act is None or final_act is None
            else final_act != source_act or bool(transition.victory)
        )
        output: dict[str, object] = {
            "method": "paired-public-progress-rollout-v1",
            "patch_id": environment.patch_id,
            "ruleset_manifest_id": environment.ruleset.manifest_id,
            "source_state_hash": task.checkpoint.state_hash,
            "action_id": task.action_id,
            "simulation_seed": task.simulation_seed,
            "continuation_policy_id": policy.policy_id,
            "transitions": decisions,
            "terminal": transition.terminal,
            "truncated": not transition.terminal,
            "victory": transition.victory,
            "terminal_reward": (
                1.0 if transition.victory else 0.0 if transition.terminal else None
            ),
            "final_state_hash": observation.state_hash,
            "source_floor": source_floor,
            "maximum_floor": maximum_floor,
            "final_floor": final_floor,
            "source_act": source_act,
            "final_act": final_act,
            "act_completed": act_completed,
            "final_hp": final_hp,
            "final_max_hp": final_max_hp,
            "final_gold": final_gold,
            "final_potion_count": final_potion_count,
            "final_relic_count": final_relic_count,
        }
        output["bootstrap_utility"] = bootstrap_utility(output)
        return output
    finally:
        if sampled is not None:
            _close_environment(sampled)
        _close_environment(environment)


def bootstrap_utility(output: dict[str, object]) -> float:
    if output.get("terminal") is True and output.get("victory") is True:
        return 1.0
    floor = output.get("maximum_floor")
    floor_value = float(floor) if isinstance(floor, int) and not isinstance(floor, bool) else 0.0
    act_bonus = 0.5 if output.get("act_completed") is True else 0.0
    hp = output.get("final_hp")
    maximum_hp = output.get("final_max_hp")
    hp_fraction = (
        min(max(float(hp) / float(maximum_hp), 0.0), 1.0)
        if isinstance(hp, int)
        and not isinstance(hp, bool)
        and isinstance(maximum_hp, int)
        and not isinstance(maximum_hp, bool)
        and maximum_hp > 0
        else 0.0
    )
    # One additional floor always outweighs the act/HP tie breakers, and every loss remains below
    # a terminal victory. This score is a curriculum label, never environment reward.
    progress = min(max(floor_value + act_bonus + 0.49 * hp_fraction, 0.0), 64.99)
    return 0.99 * progress / 65.0


def run_bootstrap_worker_batch(
    *,
    tasks: Sequence[BootstrapSimulationTask],
    workers: int,
    worker_timeout_seconds: float,
    output_directory: Path,
    task_runner: Callable[[BootstrapSimulationTask], dict[str, object]] | None = None,
    batch_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    canonical = tuple(tasks)
    if not canonical:
        raise ValueError("At least one bootstrap task is required")
    if len({task.task_id for task in canonical}) != len(canonical):
        raise ValueError("Bootstrap task IDs must be unique")
    if workers <= 0 or worker_timeout_seconds <= 0.0:
        raise ValueError("Bootstrap worker settings must be positive")
    canonical_batch_id = str(uuid5(NAMESPACE_URL, "|".join(task.task_id for task in canonical)))
    if batch_id is not None and str(UUID(batch_id)) != canonical_batch_id:
        raise ValueError("Bootstrap batch ID differs from its task identities")
    output_directory.mkdir(parents=True, exist_ok=False)
    output_directory = output_directory.resolve()
    requests = [
        _write_bootstrap_request(canonical_batch_id, task, output_directory) for task in canonical
    ]
    started_at = _utc_now()
    started = time.perf_counter()

    def run(request: tuple[BootstrapSimulationTask, Path, Path]) -> BootstrapTaskEvidence:
        if task_runner is None:
            return _run_bootstrap_subprocess(
                canonical_batch_id,
                request,
                output_directory,
                worker_timeout_seconds,
            )
        task, request_path, result_path = request
        began = time.perf_counter()
        try:
            output = task_runner(task)
            return BootstrapTaskEvidence(
                task.task_id,
                "completed",
                0,
                None,
                "completed by injected runner",
                str(request_path.relative_to(output_directory)),
                str(result_path.relative_to(output_directory)),
                sha256_file(request_path),
                None,
                None,
                time.perf_counter() - began,
                output,
            )
        except Exception as error:  # noqa: BLE001 - failure remains in the denominator.
            return BootstrapTaskEvidence(
                task.task_id,
                "worker_error",
                1,
                None,
                f"{type(error).__name__}: {error}",
                str(request_path.relative_to(output_directory)),
                str(result_path.relative_to(output_directory)),
                sha256_file(request_path),
                None,
                None,
                time.perf_counter() - began,
                None,
            )

    evidence: list[BootstrapTaskEvidence] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(requests))) as executor:
        futures: dict[Future[BootstrapTaskEvidence], tuple[BootstrapSimulationTask, Path, Path]] = {
            executor.submit(run, request): request for request in requests
        }
        for future in as_completed(futures):
            request = futures[future]
            try:
                item = future.result()
            except Exception as error:  # noqa: BLE001
                task, request_path, result_path = request
                item = BootstrapTaskEvidence(
                    task.task_id,
                    "crashed",
                    None,
                    None,
                    f"coordinator error: {type(error).__name__}: {error}",
                    str(request_path.relative_to(output_directory)),
                    str(result_path.relative_to(output_directory)),
                    sha256_file(request_path),
                    None,
                    None,
                    None,
                    None,
                )
            evidence.append(item)
    ordered = sorted(evidence, key=lambda item: item.task_id)
    completed = [item for item in ordered if item.completed]
    wall_seconds = time.perf_counter() - started
    report_body: dict[str, Any] = {
        "schema_version": BOOTSTRAP_BATCH_SCHEMA_VERSION,
        "batch_id": canonical_batch_id,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "configuration": {
            "workers": workers,
            "worker_timeout_seconds": worker_timeout_seconds,
            "task_ids": sorted(task.task_id for task in canonical),
        },
        "summary": {
            "requested_tasks": len(canonical),
            "completed_tasks": len(completed),
            "failed_tasks": len(canonical) - len(completed),
            "transitions": sum(
                _integer(item.output.get("transitions"), "transitions")
                for item in completed
                if item.output is not None
            ),
            "worker_cpu_seconds": sum(item.cpu_seconds or 0.0 for item in ordered),
            "wall_seconds": wall_seconds,
        },
        "tasks": [item.as_dict() for item in ordered],
    }
    report = {**report_body, "batch_report_id": manifest_identifier(report_body)}
    report_path = output_directory / "bootstrap-worker-report.json"
    write_exclusive_json(report_path, report)
    return report_path, report


def run_bootstrap_teacher_dataset(
    *,
    backend: SearchBackendSpec,
    state_set: BootstrapStateSet,
    split_manifest: SplitManifest,
    objective: ObjectiveSpec,
    config: BootstrapConfig,
    output_directory: Path,
    task_runner: Callable[[BootstrapSimulationTask], dict[str, object]] | None = None,
    resume: bool = False,
) -> BootstrapDatasetResult:
    _validate_bootstrap_split(state_set, split_manifest)
    if objective.objective_id != state_set.objective_id:
        raise ValueError("Bootstrap objective differs from frozen state set")
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists() and not resume:
        raise FileExistsError(output_directory)
    output_directory.mkdir(parents=True, exist_ok=resume)
    report_path = output_directory / "bootstrap-teacher-dataset.json"
    if report_path.exists():
        raise FileExistsError(report_path)
    started_at = _utc_now()
    case_documents: list[dict[str, Any]] = []
    for case in state_set.cases:
        case_root = output_directory / "cases" / case.state_id
        completed_case_path = case_root / "case.json"
        if resume and completed_case_path.is_file():
            existing = _load_object(completed_case_path)
            if existing.get("status") == "completed":
                case_documents.append(existing)
                continue
            _preserve_failed_case(completed_case_path)
        case_root.mkdir(parents=True, exist_ok=True)
        try:
            captured = capture_bootstrap_combat_state(
                backend=backend,
                run_seed=case.run_seed,
                combat_state_index=case.combat_state_index,
                maximum_prefix_steps=config.maximum_prefix_steps,
            )
            if captured.checkpoint.state_hash != case.expected_state_hash:
                raise RuntimeError("Captured state hash differs from frozen bootstrap state")
            if len(captured.legal_actions) != case.expected_legal_actions:
                raise RuntimeError(
                    "Captured legal-action count differs from frozen bootstrap state"
                )
            model_input = _model_input_at_checkpoint(backend, captured.checkpoint)
            attempt_directory = _next_attempt_directory(case_root)
            tasks = _bootstrap_tasks(backend, captured, config)
            batch_path, batch_report = run_bootstrap_worker_batch(
                tasks=tasks,
                workers=config.workers,
                worker_timeout_seconds=config.worker_timeout_seconds,
                output_directory=attempt_directory,
                task_runner=task_runner,
            )
            if _mapping(batch_report.get("summary"), "batch summary").get("failed_tasks") != 0:
                raise RuntimeError("One or more bootstrap simulations failed")
            target = _build_bootstrap_target(
                captured.legal_actions,
                _list(batch_report.get("tasks"), "bootstrap task evidence"),
                config.samples_per_candidate,
            )
            record_body: dict[str, Any] = {
                "schema_version": "bootstrap-teacher-record-v1",
                "state_id": case.state_id,
                "run_seed": case.run_seed,
                "combat_state_index": case.combat_state_index,
                "source_state_hash": captured.checkpoint.state_hash,
                "model_input": model_input.as_dict(),
                "target": target,
            }
            record = {**record_body, "record_id": manifest_identifier(record_body)}
            case_body: dict[str, Any] = {
                "state_id": case.state_id,
                "status": "completed",
                "failure": None,
                "batch": {
                    "path": str(batch_path.relative_to(output_directory)),
                    "sha256": sha256_file(batch_path),
                    "batch_report_id": batch_report["batch_report_id"],
                },
                "record": record,
            }
        except Exception as error:  # noqa: BLE001 - cases remain in the denominator.
            case_body = {
                "state_id": case.state_id,
                "status": "failed",
                "failure": {"type": type(error).__name__, "message": str(error)},
                "batch": None,
                "record": None,
            }
        case_document = {**case_body, "case_id": manifest_identifier(case_body)}
        write_exclusive_json(completed_case_path, case_document)
        case_documents.append(case_document)
    summary = _dataset_summary(case_documents)
    body: dict[str, Any] = {
        "schema_version": BOOTSTRAP_DATASET_SCHEMA_VERSION,
        "teacher_id": BOOTSTRAP_TEACHER_ID,
        "utility_id": BOOTSTRAP_UTILITY_ID,
        "seed_protocol_id": BOOTSTRAP_SEED_PROTOCOL_ID,
        "objective_id": state_set.objective_id,
        "objective": objective.as_dict(),
        "auxiliary_reward_allowed": False,
        "backend": backend.as_dict(),
        "state_set": state_set.as_dict(),
        "configuration": config.as_dict(),
        "started_at": started_at,
        "completed_at": _utc_now(),
        "cases": [
            {
                "state_id": case["state_id"],
                "path": str(
                    (output_directory / "cases" / case["state_id"] / "case.json").relative_to(
                        output_directory
                    )
                ),
                "sha256": sha256_file(output_directory / "cases" / case["state_id"] / "case.json"),
                "case_id": case["case_id"],
            }
            for case in case_documents
        ],
        "summary": summary,
        "claim_scope": "train_curriculum_only",
    }
    report = {**body, "dataset_id": manifest_identifier(body)}
    write_exclusive_json(report_path, report)
    return BootstrapDatasetResult(summary["failed_cases"] == 0, report_path, report)


def verify_bootstrap_teacher_dataset(
    report_path: Path,
    *,
    split_manifest: SplitManifest,
    replay_cases: int = 0,
) -> BootstrapVerification:
    errors: list[str] = []
    dataset_id: str | None = None
    verified_cases = 0
    replayed_cases = 0
    raw_cases: list[Any] = []
    try:
        report = _load_object(report_path)
        raw_id = report.get("dataset_id")
        dataset_id = raw_id if isinstance(raw_id, str) else None
        body = {key: value for key, value in report.items() if key != "dataset_id"}
        if dataset_id != manifest_identifier(body):
            errors.append("bootstrap dataset identity mismatch")
        if report.get("schema_version") != BOOTSTRAP_DATASET_SCHEMA_VERSION:
            errors.append("unsupported bootstrap dataset schema")
        if report.get("teacher_id") != BOOTSTRAP_TEACHER_ID:
            errors.append("bootstrap teacher identity mismatch")
        if report.get("utility_id") != BOOTSTRAP_UTILITY_ID:
            errors.append("bootstrap utility identity mismatch")
        if report.get("seed_protocol_id") != BOOTSTRAP_SEED_PROTOCOL_ID:
            errors.append("bootstrap seed protocol identity mismatch")
        objective = ObjectiveSpec.from_mapping(
            _mapping(report.get("objective"), "bootstrap objective")
        )
        if (
            report.get("objective_id") != split_manifest.objective_id
            or objective.objective_id != split_manifest.objective_id
        ):
            errors.append("bootstrap objective differs from split manifest")
        if report.get("auxiliary_reward_allowed") is not False:
            errors.append("bootstrap dataset permits auxiliary environment reward")
        if report.get("claim_scope") != "train_curriculum_only":
            errors.append("bootstrap dataset claim scope is not train-only curriculum")
        state_set = load_bootstrap_state_set_document(report.get("state_set"))
        _validate_bootstrap_split(state_set, split_manifest)
        raw_cases = _list(report.get("cases"), "dataset cases")
        if len(raw_cases) != len(state_set.cases):
            errors.append("bootstrap dataset case count differs from frozen state set")
        root = report_path.parent.resolve()
        regenerated: list[dict[str, Any]] = []
        for index, expected in enumerate(state_set.cases):
            if index >= len(raw_cases):
                break
            reference = _mapping(raw_cases[index], f"cases[{index}]")
            if reference.get("state_id") != expected.state_id:
                errors.append(f"case {expected.state_id}: state ID mismatch")
                continue
            case_path = _safe_child(root, _string(reference.get("path"), "case path"))
            if sha256_file(case_path) != reference.get("sha256"):
                errors.append(f"case {expected.state_id}: case digest mismatch")
                continue
            case_document = _load_object(case_path)
            case_body = {key: value for key, value in case_document.items() if key != "case_id"}
            if case_document.get("case_id") != manifest_identifier(case_body):
                errors.append(f"case {expected.state_id}: case identity mismatch")
                continue
            if reference.get("case_id") != case_document.get("case_id"):
                errors.append(f"case {expected.state_id}: referenced case identity mismatch")
            regenerated.append(case_document)
            if case_document.get("status") != "completed":
                verified_cases += 1
                continue
            batch = _mapping(case_document.get("batch"), "case batch")
            batch_path = _safe_child(root, _string(batch.get("path"), "batch path"))
            if sha256_file(batch_path) != batch.get("sha256"):
                errors.append(f"case {expected.state_id}: batch digest mismatch")
                continue
            batch_report = _load_object(batch_path)
            if batch_report.get("batch_report_id") != batch.get("batch_report_id"):
                errors.append(f"case {expected.state_id}: batch identity mismatch")
            batch_errors = _verify_bootstrap_batch(
                batch_path,
                exact_replay=replayed_cases < replay_cases,
            )
            errors.extend(f"case {expected.state_id}: {error}" for error in batch_errors)
            if replayed_cases < replay_cases:
                replayed_cases += 1
            record = _mapping(case_document.get("record"), "case record")
            record_body = {key: value for key, value in record.items() if key != "record_id"}
            if record.get("record_id") != manifest_identifier(record_body):
                errors.append(f"case {expected.state_id}: record identity mismatch")
            if record.get("state_id") != expected.state_id:
                errors.append(f"case {expected.state_id}: record state ID mismatch")
            if record.get("run_seed") != expected.run_seed:
                errors.append(f"case {expected.state_id}: record run seed mismatch")
            if record.get("combat_state_index") != expected.combat_state_index:
                errors.append(f"case {expected.state_id}: record combat index mismatch")
            if record.get("source_state_hash") != expected.expected_state_hash:
                errors.append(f"case {expected.state_id}: record source hash mismatch")
            model_input = model_input_from_mapping(record.get("model_input"))
            if model_input.source_state_hash != expected.expected_state_hash:
                errors.append(f"case {expected.state_id}: model-input source hash mismatch")
            if model_input.ruleset_manifest_id != state_set.ruleset_manifest_id:
                errors.append(f"case {expected.state_id}: model-input ruleset mismatch")
            if len(model_input.candidates) != expected.expected_legal_actions:
                errors.append(f"case {expected.state_id}: model-input candidate count mismatch")
            reconstructed_actions = tuple(
                LegalAction(candidate.source_action_id, candidate.action_kind, {})
                for candidate in model_input.candidates
            )
            configuration = _mapping(report.get("configuration"), "dataset configuration")
            samples = _integer(configuration.get("samples_per_candidate"), "samples_per_candidate")
            batch_tasks = _list(batch_report.get("tasks"), "batch tasks")
            reconstructed_target = _build_bootstrap_target(
                reconstructed_actions,
                batch_tasks,
                samples,
            )
            if record.get("target") != reconstructed_target:
                errors.append(f"case {expected.state_id}: target differs from worker evidence")
            _verify_case_task_domain(
                batch_report,
                batch_path=batch_path,
                backend=_mapping(report.get("backend"), "dataset backend"),
                state_hash=expected.expected_state_hash,
                run_seed=expected.run_seed,
                ruleset_manifest_id=state_set.ruleset_manifest_id,
                action_ids={action.action_id for action in reconstructed_actions},
                samples_per_candidate=samples,
                maximum_rollout_steps=_integer(
                    configuration.get("maximum_rollout_steps"), "maximum_rollout_steps"
                ),
            )
            if not batch_errors:
                verified_cases += 1
        if _dataset_summary(regenerated) != report.get("summary"):
            errors.append("bootstrap dataset summary differs from case evidence")
    except (OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return BootstrapVerification(
        not errors,
        dataset_id,
        len(raw_cases),
        verified_cases,
        replayed_cases,
        tuple(errors),
    )


def write_bootstrap_worker_result(
    *,
    batch_id: str,
    task: BootstrapSimulationTask,
    request_path: Path,
    result_path: Path,
) -> int:
    started = time.perf_counter()
    started_cpu = time.process_time()
    try:
        output = execute_bootstrap_task(task)
        status = "completed"
        message = "bootstrap simulation completed"
        exit_code = 0
    except Exception as error:  # noqa: BLE001 - immutable worker failure evidence.
        output = None
        status = "worker_error"
        message = f"{type(error).__name__}: {error}"
        exit_code = 1
    body: dict[str, object] = {
        "schema_version": BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION,
        "batch_id": batch_id,
        "task_id": task.task_id,
        "status": status,
        "worker_pid": os.getpid(),
        "message": message,
        "request_sha256": sha256_file(request_path),
        "cpu_seconds": time.process_time() - started_cpu,
        "wall_seconds": time.perf_counter() - started,
        "output": output,
    }
    write_exclusive_json(result_path, body)
    return exit_code


def load_bootstrap_task(path: Path) -> BootstrapSimulationTask:
    return BootstrapSimulationTask.from_mapping(_load_object(path))


def _run_bootstrap_subprocess(
    batch_id: str,
    request: tuple[BootstrapSimulationTask, Path, Path],
    batch_directory: Path,
    timeout_seconds: float,
) -> BootstrapTaskEvidence:
    task, request_path, result_path = request
    command = [
        sys.executable,
        "-m",
        "spireshift.bootstrap_worker",
        "--batch-id",
        batch_id,
        "--request",
        str(request_path),
        "--result",
        str(result_path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return _failed_bootstrap_evidence(
            task,
            request_path,
            result_path,
            batch_directory,
            "timeout",
            None,
            f"worker exceeded {timeout_seconds:g}s timeout",
        )
    if not result_path.is_file():
        detail = completed.stderr.strip()
        return _failed_bootstrap_evidence(
            task,
            request_path,
            result_path,
            batch_directory,
            "crashed",
            completed.returncode,
            "worker exited without a result" + (f": {detail[-1000:]}" if detail else ""),
        )
    try:
        result = _load_object(result_path)
        output_value = result.get("output")
        output = None if output_value is None else _mapping(output_value, "worker output")
        status = _string(result.get("status"), "worker status")
        worker_pid = _optional_integer(result.get("worker_pid"))
        cpu_seconds = _optional_number(result.get("cpu_seconds"))
        wall_seconds = _optional_number(result.get("wall_seconds"))
        message = _string(result.get("message"), "worker message")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _failed_bootstrap_evidence(
            task,
            request_path,
            result_path,
            batch_directory,
            "crashed",
            completed.returncode,
            f"invalid worker result: {error}",
        )
    request_digest = sha256_file(request_path)
    if (
        result.get("schema_version") != BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION
        or result.get("batch_id") != batch_id
        or result.get("task_id") != task.task_id
        or result.get("request_sha256") != request_digest
    ):
        status = "crashed"
        message = "worker result identity mismatch"
        output = None
    elif status == "completed":
        if completed.returncode != 0 or output is None:
            status = "worker_error"
            message = "completed worker returned incomplete evidence"
            output = None
        else:
            try:
                _validate_bootstrap_output(task, output)
            except ValueError as error:
                status = "worker_error"
                message = f"invalid completed output: {error}"
                output = None
    return BootstrapTaskEvidence(
        task.task_id,
        status,
        completed.returncode,
        worker_pid,
        message,
        str(request_path.relative_to(batch_directory)),
        str(result_path.relative_to(batch_directory)),
        request_digest,
        sha256_file(result_path),
        cpu_seconds,
        wall_seconds,
        output,
    )


def _write_bootstrap_request(
    batch_id: str,
    task: BootstrapSimulationTask,
    output_directory: Path,
) -> tuple[BootstrapSimulationTask, Path, Path]:
    task_directory = output_directory / "tasks" / task.task_id
    task_directory.mkdir(parents=True, exist_ok=False)
    request_path = task_directory / "request.json"
    write_exclusive_json(request_path, task.as_dict())
    return task, request_path, task_directory / "result.json"


def _failed_bootstrap_evidence(
    task: BootstrapSimulationTask,
    request_path: Path,
    result_path: Path,
    batch_directory: Path,
    status: str,
    exit_code: int | None,
    message: str,
) -> BootstrapTaskEvidence:
    return BootstrapTaskEvidence(
        task.task_id,
        status,
        exit_code,
        None,
        message,
        str(request_path.relative_to(batch_directory)),
        str(result_path.relative_to(batch_directory)),
        sha256_file(request_path),
        sha256_file(result_path) if result_path.is_file() else None,
        None,
        None,
        None,
    )


def _bootstrap_tasks(
    backend: SearchBackendSpec,
    captured: _CapturedBootstrapState,
    config: BootstrapConfig,
) -> tuple[BootstrapSimulationTask, ...]:
    tasks: list[BootstrapSimulationTask] = []
    for sample_index in range(config.samples_per_candidate):
        seed = _bootstrap_seed(config.sampling_seed, captured.checkpoint.state_hash, sample_index)
        for action in captured.legal_actions:
            task_id = str(
                uuid5(
                    NAMESPACE_URL,
                    "|".join(
                        (
                            BOOTSTRAP_TEACHER_ID,
                            captured.checkpoint.state_hash,
                            action.action_id,
                            str(seed),
                        )
                    ),
                )
            )
            tasks.append(
                BootstrapSimulationTask(
                    task_id,
                    backend,
                    captured.checkpoint,
                    action.action_id,
                    seed,
                    config.maximum_rollout_steps,
                )
            )
    return tuple(tasks)


def _build_bootstrap_target(
    actions: Sequence[LegalAction],
    raw_evidence: Sequence[Any],
    samples_per_candidate: int,
) -> dict[str, Any]:
    by_action: dict[str, list[dict[str, object]]] = {action.action_id: [] for action in actions}
    for raw_item in raw_evidence:
        item = _mapping(raw_item, "bootstrap evidence")
        if item.get("status") != "completed":
            continue
        output = _mapping(item.get("output"), "bootstrap output")
        action_id = _string(output.get("action_id"), "action_id")
        if action_id in by_action:
            by_action[action_id].append(output)
    candidates: list[dict[str, Any]] = []
    seed_sets: list[set[int]] = []
    for index, action in enumerate(actions):
        outcomes = sorted(
            by_action[action.action_id],
            key=lambda output: _integer(output.get("simulation_seed"), "simulation_seed"),
        )
        if len(outcomes) != samples_per_candidate:
            raise RuntimeError(f"Action {action.action_id} has incomplete bootstrap outcomes")
        seed_sets.append(
            {_integer(output.get("simulation_seed"), "simulation_seed") for output in outcomes}
        )
        utilities = [
            _number(output.get("bootstrap_utility"), "bootstrap utility") for output in outcomes
        ]
        floors = [_optional_integer(output.get("maximum_floor")) or 0 for output in outcomes]
        victories = sum(
            output.get("terminal") is True and output.get("victory") is True for output in outcomes
        )
        act_known = [
            output.get("act_completed")
            for output in outcomes
            if isinstance(output.get("act_completed"), bool)
        ]
        final_hps = [
            value
            for output in outcomes
            for value in [_optional_integer(output.get("final_hp"))]
            if value is not None
        ]
        final_gold = _known_integers(outcomes, "final_gold")
        final_potions = _known_integers(outcomes, "final_potion_count")
        final_relics = _known_integers(outcomes, "final_relic_count")
        histogram = {str(floor): floors.count(floor) for floor in sorted(set(floors))}
        candidates.append(
            {
                "candidate_index": index,
                "source_action_id": action.action_id,
                "action_kind": action.kind,
                "sample_count": len(outcomes),
                "terminal_value": victories / len(outcomes),
                "mean_progress_utility": sum(utilities) / len(utilities),
                "progress_utility_variance": _variance(utilities),
                "mean_maximum_floor": sum(floors) / len(floors),
                "maximum_floor_histogram": histogram,
                "milestone_reach_probability": {
                    str(milestone): sum(floor >= milestone for floor in floors) / len(floors)
                    for milestone in MILESTONE_FLOORS
                },
                "act_completion_rate": (
                    sum(value is True for value in act_known) / len(act_known)
                    if act_known
                    else None
                ),
                "mean_final_hp": sum(final_hps) / len(final_hps) if final_hps else None,
                "mean_final_gold": (sum(final_gold) / len(final_gold) if final_gold else None),
                "mean_final_potion_count": (
                    sum(final_potions) / len(final_potions) if final_potions else None
                ),
                "mean_final_relic_count": (
                    sum(final_relics) / len(final_relics) if final_relics else None
                ),
                "outcomes": outcomes,
            }
        )
    if any(seeds != seed_sets[0] for seeds in seed_sets[1:]):
        raise RuntimeError("Bootstrap candidates do not use paired simulation seeds")
    selected = max(
        range(len(candidates)),
        key=lambda index: (
            candidates[index]["terminal_value"],
            candidates[index]["mean_maximum_floor"],
            candidates[index]["act_completion_rate"] or 0.0,
            candidates[index]["mean_final_hp"] or 0.0,
            -index,
        ),
    )
    value_spread = max(
        cast(float, candidate["mean_progress_utility"]) for candidate in candidates
    ) - min(cast(float, candidate["mean_progress_utility"]) for candidate in candidates)
    return {
        "teacher_id": BOOTSTRAP_TEACHER_ID,
        "utility_id": BOOTSTRAP_UTILITY_ID,
        "seed_protocol_id": BOOTSTRAP_SEED_PROTOCOL_ID,
        "samples_per_candidate": samples_per_candidate,
        "milestone_floors": list(MILESTONE_FLOORS),
        "candidates": candidates,
        "selected_candidate_index": selected,
        "selected_action_id": candidates[selected]["source_action_id"],
        "one_hot_policy_target": [float(index == selected) for index in range(len(candidates))],
        "candidate_progress_utility_spread": value_spread,
        "terminal_reward_is_primary": True,
        "progress_utility_is_auxiliary": True,
    }


def _verify_bootstrap_batch(report_path: Path, *, exact_replay: bool) -> tuple[str, ...]:
    errors: list[str] = []
    report = _load_object(report_path)
    body = {key: value for key, value in report.items() if key != "batch_report_id"}
    if report.get("batch_report_id") != manifest_identifier(body):
        errors.append("batch report identity mismatch")
    if report.get("schema_version") != BOOTSTRAP_BATCH_SCHEMA_VERSION:
        errors.append("unsupported bootstrap batch schema")
        return tuple(errors)
    root = report_path.parent.resolve()
    configured = _mapping(report.get("configuration"), "batch configuration")
    task_ids = {
        _string(value, "task ID") for value in _list(configured.get("task_ids"), "task IDs")
    }
    seen: set[str] = set()
    completed = 0
    transitions = 0
    cpu_seconds = 0.0
    for raw_item in _list(report.get("tasks"), "batch tasks"):
        item = _mapping(raw_item, "batch task")
        task_id = _string(item.get("task_id"), "task_id")
        seen.add(task_id)
        request_path = _safe_child(root, _string(item.get("request_path"), "request path"))
        if sha256_file(request_path) != item.get("request_sha256"):
            errors.append(f"task {task_id}: request digest mismatch")
            continue
        task = load_bootstrap_task(request_path)
        if task.task_id != task_id:
            errors.append(f"task {task_id}: request identity mismatch")
        if item.get("status") != "completed":
            continue
        completed += 1
        output = _mapping(item.get("output"), "task output")
        try:
            _validate_bootstrap_output(task, output)
            transitions += _integer(output.get("transitions"), "transitions")
            if exact_replay and execute_bootstrap_task(task) != output:
                errors.append(f"task {task_id}: exact replay differs")
        except ValueError as error:
            errors.append(f"task {task_id}: {error}")
        result_value = item.get("result_path")
        result_digest = item.get("result_sha256")
        if isinstance(result_value, str) and isinstance(result_digest, str):
            result_path = _safe_child(root, result_value)
            if sha256_file(result_path) != result_digest:
                errors.append(f"task {task_id}: result digest mismatch")
            else:
                result = _load_object(result_path)
                expected_result = {
                    "schema_version": BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION,
                    "batch_id": report.get("batch_id"),
                    "task_id": task_id,
                    "status": item.get("status"),
                    "worker_pid": item.get("worker_pid"),
                    "message": item.get("message"),
                    "request_sha256": item.get("request_sha256"),
                    "cpu_seconds": item.get("cpu_seconds"),
                    "wall_seconds": item.get("wall_seconds"),
                    "output": item.get("output"),
                }
                if result != expected_result:
                    errors.append(f"task {task_id}: result differs from batch evidence")
        cpu = item.get("cpu_seconds")
        if isinstance(cpu, (int, float)) and not isinstance(cpu, bool):
            cpu_seconds += float(cpu)
    if seen != task_ids:
        errors.append("configured and recorded task IDs differ")
    summary = _mapping(report.get("summary"), "batch summary")
    expected = {
        "requested_tasks": len(task_ids),
        "completed_tasks": completed,
        "failed_tasks": len(task_ids) - completed,
        "transitions": transitions,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"batch summary {key} mismatch")
    actual_cpu = summary.get("worker_cpu_seconds")
    if not isinstance(actual_cpu, (int, float)) or not math.isclose(float(actual_cpu), cpu_seconds):
        errors.append("batch summary worker_cpu_seconds mismatch")
    return tuple(errors)


def _verify_case_task_domain(
    batch_report: dict[str, Any],
    *,
    batch_path: Path,
    backend: dict[str, Any],
    state_hash: str,
    run_seed: int,
    ruleset_manifest_id: str,
    action_ids: set[str],
    samples_per_candidate: int,
    maximum_rollout_steps: int,
) -> None:
    root = batch_path.parent.resolve()
    by_action: dict[str, set[int]] = {action_id: set() for action_id in action_ids}
    for raw_item in _list(batch_report.get("tasks"), "batch tasks"):
        item = _mapping(raw_item, "batch task")
        request_path = _safe_child(root, _string(item.get("request_path"), "request path"))
        task = load_bootstrap_task(request_path)
        if task.backend.as_dict() != backend:
            raise ValueError("bootstrap task backend differs from dataset backend")
        if task.checkpoint.state_hash != state_hash:
            raise ValueError("bootstrap task checkpoint differs from case state")
        if task.checkpoint.run_seed != run_seed:
            raise ValueError("bootstrap task run seed differs from case seed")
        if task.checkpoint.ruleset_manifest_id != ruleset_manifest_id:
            raise ValueError("bootstrap task ruleset differs from state set")
        if task.maximum_rollout_steps != maximum_rollout_steps:
            raise ValueError("bootstrap task rollout limit differs from dataset configuration")
        seeds = by_action.get(task.action_id)
        if seeds is None:
            raise ValueError("bootstrap task action is absent from model input")
        if task.simulation_seed in seeds:
            raise ValueError("bootstrap task repeats an action/seed pair")
        seeds.add(task.simulation_seed)
    if any(len(seeds) != samples_per_candidate for seeds in by_action.values()):
        raise ValueError("bootstrap task count differs from declared samples per candidate")
    seed_sets = list(by_action.values())
    if any(seeds != seed_sets[0] for seeds in seed_sets[1:]):
        raise ValueError("bootstrap task candidates do not use paired seeds")


def _validate_bootstrap_output(
    task: BootstrapSimulationTask,
    output: dict[str, object],
) -> None:
    expected_keys = {
        "method",
        "patch_id",
        "ruleset_manifest_id",
        "source_state_hash",
        "action_id",
        "simulation_seed",
        "continuation_policy_id",
        "transitions",
        "terminal",
        "truncated",
        "victory",
        "terminal_reward",
        "final_state_hash",
        "source_floor",
        "maximum_floor",
        "final_floor",
        "source_act",
        "final_act",
        "act_completed",
        "final_hp",
        "final_max_hp",
        "final_gold",
        "final_potion_count",
        "final_relic_count",
        "bootstrap_utility",
    }
    _exact_keys(output, expected_keys, "bootstrap output")
    expected = {
        "method": "paired-public-progress-rollout-v1",
        "patch_id": task.checkpoint.patch_id,
        "ruleset_manifest_id": task.checkpoint.ruleset_manifest_id,
        "source_state_hash": task.checkpoint.state_hash,
        "action_id": task.action_id,
        "simulation_seed": task.simulation_seed,
        "continuation_policy_id": ProgressBootstrapPolicy.policy_id,
    }
    if any(output.get(key) != value for key, value in expected.items()):
        raise ValueError("bootstrap output identity mismatch")
    transitions = _integer(output.get("transitions"), "transitions")
    if not 1 <= transitions <= task.maximum_rollout_steps:
        raise ValueError("bootstrap transitions exceed the declared limit")
    terminal = _boolean(output.get("terminal"), "terminal")
    truncated = _boolean(output.get("truncated"), "truncated")
    victory = _boolean(output.get("victory"), "victory")
    if terminal == truncated:
        raise ValueError("bootstrap terminal and truncated flags are inconsistent")
    if victory and not terminal:
        raise ValueError("bootstrap victory is not terminal")
    reward = output.get("terminal_reward")
    if terminal:
        expected_reward = 1.0 if output.get("victory") is True else 0.0
        if _number(reward, "terminal reward") != expected_reward:
            raise ValueError("bootstrap terminal reward is not binary victory")
    elif reward is not None:
        raise ValueError("truncated bootstrap output has terminal reward")
    state_hash = _string(output.get("final_state_hash"), "final_state_hash")
    if len(state_hash) != 64 or any(
        character not in "0123456789abcdef" for character in state_hash
    ):
        raise ValueError("bootstrap final state hash is not a lowercase SHA-256 digest")
    for field in (
        "source_floor",
        "maximum_floor",
        "final_floor",
        "final_hp",
        "final_max_hp",
        "final_gold",
        "final_potion_count",
        "final_relic_count",
    ):
        value = output.get(field)
        if value is not None and _optional_integer(value) is None:
            raise ValueError(f"bootstrap {field} must be an integer or null")
    for field in ("source_act", "final_act"):
        value = output.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, str))):
            raise ValueError(f"bootstrap {field} must be an integer, string, or null")
    act_completed = output.get("act_completed")
    if act_completed is not None:
        _boolean(act_completed, "act_completed")
    if not math.isclose(
        _number(output.get("bootstrap_utility"), "bootstrap utility"),
        bootstrap_utility(output),
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise ValueError("bootstrap utility differs from diagnostics")


def _dataset_summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case.get("status") == "completed"]
    records = [
        _mapping(case.get("record"), "case record")
        for case in completed
        if isinstance(case.get("record"), dict)
    ]
    targets = [_mapping(record.get("target"), "record target") for record in records]
    candidates = [
        _mapping(candidate, "candidate")
        for target in targets
        for candidate in _list(target.get("candidates"), "target candidates")
    ]
    terminal_victories = sum(
        output.get("terminal") is True and output.get("victory") is True
        for candidate in candidates
        for output in map(_as_mapping, _list(candidate.get("outcomes"), "candidate outcomes"))
    )
    bins = {
        floor
        for candidate in candidates
        for floor, count in _mapping(
            candidate.get("maximum_floor_histogram"), "floor histogram"
        ).items()
        if _integer(count, "floor count") > 0
    }
    varied = sum(
        _number(target.get("candidate_progress_utility_spread"), "utility spread") > 0.0
        for target in targets
    )
    simulations = sum(
        _integer(candidate.get("sample_count"), "sample count") for candidate in candidates
    )
    transitions = sum(
        _integer(output.get("transitions"), "transitions")
        for candidate in candidates
        for output in map(_as_mapping, _list(candidate.get("outcomes"), "candidate outcomes"))
    )
    return {
        "benchmark_denominator": len(cases),
        "completed_cases": len(completed),
        "failed_cases": len(cases) - len(completed),
        "records": len(records),
        "candidates": len(candidates),
        "simulations": simulations,
        "transitions": transitions,
        "terminal_victories": terminal_victories,
        "states_with_candidate_progress_variation": varied,
        "occupied_maximum_floor_bins": len(bins),
        "completion_rate": len(completed) / len(cases) if cases else 0.0,
    }


def _model_input_at_checkpoint(
    backend: SearchBackendSpec,
    checkpoint: PublicStateCheckpoint,
) -> Any:
    environment, observation = restore_search_checkpoint(backend, checkpoint)
    try:
        return PublicMechanicsService().snapshot(environment, observation).model_input
    finally:
        _close_environment(environment)


def _next_attempt_directory(case_root: Path) -> Path:
    index = 1
    while (candidate := case_root / f"attempt-{index:04d}").exists():
        index += 1
    return candidate


def _preserve_failed_case(path: Path) -> None:
    index = 1
    while (candidate := path.with_name(f"failed-case-{index:04d}.json")).exists():
        index += 1
    path.replace(candidate)


def _validate_bootstrap_split(
    state_set: BootstrapStateSet,
    split_manifest: SplitManifest,
) -> None:
    if state_set.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Bootstrap state set references a different split manifest")
    if state_set.ruleset_manifest_id != split_manifest.ruleset_manifest_id:
        raise ValueError("Bootstrap state-set ruleset differs from split manifest")
    if state_set.objective_id != split_manifest.objective_id:
        raise ValueError("Bootstrap state-set objective differs from split manifest")
    for case in state_set.cases:
        if split_manifest.split_for_seed(case.run_seed) is not SplitName.TRAIN:
            raise ValueError(f"Bootstrap seed {case.run_seed} is outside the train partition")


def _state_case(value: object) -> BootstrapStateCase:
    document = _mapping(value, "bootstrap state case")
    _exact_keys(
        document,
        {
            "state_id",
            "run_seed",
            "combat_state_index",
            "expected_state_hash",
            "expected_legal_actions",
        },
        "bootstrap state case",
    )
    state_hash = _string(document.get("expected_state_hash"), "expected_state_hash")
    if len(state_hash) != 64 or any(
        character not in "0123456789abcdef" for character in state_hash
    ):
        raise ValueError("Bootstrap expected_state_hash must be a lowercase SHA-256 digest")
    case = BootstrapStateCase(
        state_id=_string(document.get("state_id"), "state_id"),
        run_seed=_integer(document.get("run_seed"), "run_seed"),
        combat_state_index=_integer(document.get("combat_state_index"), "combat_state_index"),
        expected_state_hash=state_hash,
        expected_legal_actions=_integer(
            document.get("expected_legal_actions"), "expected_legal_actions"
        ),
    )
    if case.run_seed < 0 or case.combat_state_index < 0 or case.expected_legal_actions <= 0:
        raise ValueError("Bootstrap case integer fields are outside their allowed range")
    return case


def _bootstrap_seed(sampling_seed: int, state_hash: str, sample_index: int) -> int:
    payload = f"{sampling_seed}|{state_hash}|bootstrap-paired|{sample_index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def _variance(values: Sequence[float]) -> float:
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _known_integers(outputs: Sequence[dict[str, object]], field: str) -> list[int]:
    return [
        value
        for output in outputs
        for value in [_optional_integer(output.get(field))]
        if value is not None
    ]


def _public_integer(
    observation: Observation,
    *paths: tuple[str, ...],
) -> int | None:
    for path in paths:
        value: object = observation.public_state
        for key in path:
            if not isinstance(value, dict) or key not in value:
                break
            value = value[key]
        else:
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def _public_act(observation: Observation) -> int | str | None:
    value: object = observation.public_state
    for path in (("act",), ("run", "act")):
        value = observation.public_state
        for key in path:
            if not isinstance(value, dict) or key not in value:
                break
            value = value[key]
        else:
            if isinstance(value, str) and value:
                return value
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def _public_sequence_length(
    observation: Observation,
    *paths: tuple[str, ...],
) -> int | None:
    for path in paths:
        value: object = observation.public_state
        for key in path:
            if not isinstance(value, dict) or key not in value:
                break
            value = value[key]
        else:
            if isinstance(value, (list, tuple)):
                return len(value)
    return None


def _maximum_optional(left: int | None, right: int | None) -> int | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def _action_by_id(actions: Sequence[LegalAction], action_id: str) -> LegalAction:
    try:
        return next(action for action in actions if action.action_id == action_id)
    except StopIteration as error:
        raise RuntimeError(f"Bootstrap action is no longer legal: {action_id}") from error


def _close_environment(environment: object) -> None:
    close = getattr(environment, "close", None)
    if callable(close):
        close()


def _safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("artifact path escapes its root")
    return candidate


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _exact_keys(document: dict[str, Any], expected: set[str], label: str) -> None:
    if set(document) != expected:
        raise ValueError(f"{label} fields differ: expected {sorted(expected)}")


def _as_mapping(value: object) -> dict[str, Any]:
    return _mapping(value, "value")


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _optional_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    return _number(value, "optional number")


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
