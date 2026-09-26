from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from spireshift.agents.baseline import ProgressBootstrapPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.protocols import EnvironmentAdapter, Policy
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.mechanics import PublicMechanicsService
from spireshift.representations import CompositionalModelInput, model_input_from_mapping
from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.search_workers import (
    PublicStateCheckpoint,
    SearchBackendSpec,
    capture_checkpoint,
    load_search_environment,
    restore_search_checkpoint,
)
from spireshift.splits import SplitManifest, SplitName

if TYPE_CHECKING:
    from spireshift.agents.combat_advancement import CombatAdvancementConfig

BOOTSTRAP_STATE_SET_SCHEMA_VERSION = "bootstrap-state-set-v1"
CURRICULUM_STATE_SET_SCHEMA_VERSION = "bootstrap-state-set-v2"
LEARNED_CURRICULUM_STATE_SET_SCHEMA_VERSION = "bootstrap-state-set-v3"
TERMINAL_FRONTIER_STATE_SET_SCHEMA_VERSION = "bootstrap-state-set-v4"
COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION = "bootstrap-state-set-v5"
BOOTSTRAP_TASK_SCHEMA_VERSION = "bootstrap-simulation-task-v1"
LEARNED_BOOTSTRAP_TASK_SCHEMA_VERSION = "bootstrap-simulation-task-v2"
COMBAT_ADVANCEMENT_BOOTSTRAP_TASK_SCHEMA_VERSION = "bootstrap-simulation-task-v3"
BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION = "bootstrap-worker-result-v1"
LEARNED_BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION = "bootstrap-worker-result-v2"
COMBAT_ADVANCEMENT_WORKER_RESULT_SCHEMA_VERSION = "bootstrap-worker-result-v3"
BOOTSTRAP_BATCH_SCHEMA_VERSION = "bootstrap-worker-batch-v1"
BOOTSTRAP_DATASET_SCHEMA_VERSION = "bootstrap-teacher-dataset-v1"
CURRICULUM_DATASET_SCHEMA_VERSION = "bootstrap-teacher-dataset-v2"
LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION = "bootstrap-teacher-dataset-v3"
TERMINAL_FRONTIER_DATASET_SCHEMA_VERSION = "bootstrap-teacher-dataset-v4"
COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION = "bootstrap-teacher-dataset-v5"
BOOTSTRAP_VERIFICATION_SCHEMA_VERSION = "bootstrap-teacher-verification-v1"
BOOTSTRAP_TEACHER_ID = "paired-terminal-dominant-progress-teacher-v1"
CURRICULUM_TEACHER_ID = "paired-preference-curriculum-teacher-v2"
BOOTSTRAP_UTILITY_ID = "terminal-dominant-floor-act-hp-v1"
BOOTSTRAP_SEED_PROTOCOL_ID = "sha256-paired-bootstrap-v1"
MILESTONE_FLOORS = (1, 8, 16, 24, 32, 40, 48, 56, 64)


@dataclass(frozen=True, slots=True)
class BootstrapPolicyArtifacts:
    """Verified local artifacts for an admitted learned continuation policy."""

    checkpoint_path: Path
    training_report_path: Path
    policy_id: str
    model_id: str
    training_report_id: str
    split_manifest_id: str
    ruleset_manifest_id: str
    combat_advancement_config: CombatAdvancementConfig | None = None

    @classmethod
    def from_paths(
        cls,
        checkpoint_path: Path,
        training_report_path: Path,
        *,
        combat_advancement_config: CombatAdvancementConfig | None = None,
    ) -> BootstrapPolicyArtifacts:
        resolved_checkpoint = checkpoint_path.expanduser().resolve()
        resolved_report = training_report_path.expanduser().resolve()
        checkpoint_stat = resolved_checkpoint.stat()
        report_stat = resolved_report.stat()
        (
            model_id,
            training_report_id,
            split_manifest_id,
            ruleset_manifest_id,
        ) = _cached_bootstrap_policy_metadata(
            str(resolved_checkpoint),
            checkpoint_stat.st_mtime_ns,
            checkpoint_stat.st_size,
            str(resolved_report),
            report_stat.st_mtime_ns,
            report_stat.st_size,
        )
        policy_id = f"production-checkpoint-policy-v1:{model_id}"
        if combat_advancement_config is not None:
            from spireshift.agents.combat_advancement import combat_advancement_policy_id

            policy_id = combat_advancement_policy_id(model_id, combat_advancement_config)
        return cls(
            checkpoint_path=resolved_checkpoint,
            training_report_path=resolved_report,
            policy_id=policy_id,
            model_id=model_id,
            training_report_id=training_report_id,
            split_manifest_id=split_manifest_id,
            ruleset_manifest_id=ruleset_manifest_id,
            combat_advancement_config=combat_advancement_config,
        )

    def provenance(self) -> dict[str, str]:
        provenance = {
            "kind": (
                "combat_advancement_checkpoint"
                if self.combat_advancement_config is not None
                else "production_checkpoint"
            ),
            "policy_id": self.policy_id,
            "model_id": self.model_id,
            "training_report_id": self.training_report_id,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
        }
        if self.combat_advancement_config is not None:
            provenance["combat_advancement_config_id"] = self.combat_advancement_config.config_id
        return provenance

    def task_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            **self.provenance(),
            "checkpoint_path": str(self.checkpoint_path),
            "training_report_path": str(self.training_report_path),
        }
        if self.combat_advancement_config is not None:
            document["combat_advancement_config"] = self.combat_advancement_config.as_dict()
        return document

    def load_policy(
        self,
        ruleset: object,
        *,
        environment: EnvironmentAdapter | None = None,
    ) -> Policy:
        # ProductionCheckpointPolicy owns the gate and ruleset checks.
        from spireshift.agents.learned import ProductionCheckpointPolicy

        base_policy = ProductionCheckpointPolicy.from_paths(
            self.checkpoint_path,
            self.training_report_path,
            ruleset=cast(Any, ruleset),
        )
        if self.combat_advancement_config is None:
            return base_policy
        if environment is None:
            raise ValueError("Combat-advancement policy requires its current environment")
        from spireshift.agents.combat_advancement import CombatAdvancementPolicy

        return CombatAdvancementPolicy(
            environment=environment,
            base_policy=base_policy,
            config=self.combat_advancement_config,
        )

    def validate_for(self, *, split_manifest_id: str, ruleset_manifest_id: str) -> None:
        if self.split_manifest_id != split_manifest_id:
            raise ValueError("Learned bootstrap policy references a different split manifest")
        if self.ruleset_manifest_id != ruleset_manifest_id:
            raise ValueError("Learned bootstrap policy references a different ruleset")

    @classmethod
    def from_task_mapping(cls, value: object) -> BootstrapPolicyArtifacts:
        document = _mapping(value, "bootstrap continuation policy")
        kind = document.get("kind")
        combat_advancement = kind == "combat_advancement_checkpoint"
        expected_keys = {
            "kind",
            "policy_id",
            "model_id",
            "training_report_id",
            "split_manifest_id",
            "ruleset_manifest_id",
            "checkpoint_path",
            "training_report_path",
        }
        if combat_advancement:
            expected_keys.update({"combat_advancement_config_id", "combat_advancement_config"})
        _exact_keys(
            document,
            expected_keys,
            "bootstrap continuation policy",
        )
        if kind not in {"production_checkpoint", "combat_advancement_checkpoint"}:
            raise ValueError("Unsupported bootstrap continuation policy kind")
        config = None
        if combat_advancement:
            from spireshift.agents.combat_advancement import CombatAdvancementConfig

            config = CombatAdvancementConfig.from_mapping(document.get("combat_advancement_config"))
            if document.get("combat_advancement_config_id") != config.config_id:
                raise ValueError("Bootstrap combat-advancement config identity mismatch")
        artifacts = cls.from_paths(
            Path(_string(document.get("checkpoint_path"), "checkpoint_path")),
            Path(_string(document.get("training_report_path"), "training_report_path")),
            combat_advancement_config=config,
        )
        if artifacts.task_dict() != document:
            raise ValueError("Bootstrap continuation policy artifact identity mismatch")
        return artifacts


@lru_cache(maxsize=16)
def _cached_bootstrap_policy_metadata(
    checkpoint_path: str,
    checkpoint_mtime_ns: int,
    checkpoint_size: int,
    training_report_path: str,
    training_report_mtime_ns: int,
    training_report_size: int,
) -> tuple[str, str, str, str]:
    """Validate immutable policy artifacts once for each observed file version."""
    del checkpoint_mtime_ns, checkpoint_size, training_report_mtime_ns, training_report_size
    from spireshift.production_models import (  # Avoid a bootstrap/model import cycle.
        load_production_model_checkpoint,
        load_production_training_report,
    )

    checkpoint = load_production_model_checkpoint(Path(checkpoint_path))
    report = load_production_training_report(Path(training_report_path), checkpoint=checkpoint)
    return (
        _string(checkpoint.get("model_id"), "model_id"),
        _string(report.get("report_id"), "report_id"),
        _string(checkpoint.get("split_manifest_id"), "split_manifest_id"),
        _string(checkpoint.get("ruleset_manifest_id"), "ruleset_manifest_id"),
    )


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
class CurriculumStateCase:
    state_id: str
    run_seed: int
    decision_type: DecisionType
    decision_index: int
    expected_state_hash: str
    expected_legal_actions: int
    expected_source_floor: int | None
    expected_source_act: int | str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "run_seed": self.run_seed,
            "decision_type": self.decision_type.value,
            "decision_index": self.decision_index,
            "expected_state_hash": self.expected_state_hash,
            "expected_legal_actions": self.expected_legal_actions,
            "expected_source_floor": self.expected_source_floor,
            "expected_source_act": self.expected_source_act,
        }


@dataclass(frozen=True, slots=True)
class CurriculumSignalSpec:
    minimum_states: int
    minimum_source_floors: int
    minimum_decision_types: int
    minimum_effective_labeled_states: float
    minimum_half_split_agreement: float
    minimum_occupied_maximum_floor_bins: int
    minimum_terminal_victories: int | None = None
    minimum_terminal_defeats: int | None = None
    minimum_states_with_candidate_terminal_variation: int | None = None

    def __post_init__(self) -> None:
        integer_values = (
            self.minimum_states,
            self.minimum_source_floors,
            self.minimum_decision_types,
            self.minimum_occupied_maximum_floor_bins,
        )
        if any(isinstance(value, bool) or value <= 0 for value in integer_values):
            raise ValueError("Curriculum signal integer thresholds must be positive")
        if (
            not math.isfinite(self.minimum_effective_labeled_states)
            or self.minimum_effective_labeled_states <= 0.0
        ):
            raise ValueError("minimum_effective_labeled_states must be finite and positive")
        if not 0.0 <= self.minimum_half_split_agreement <= 1.0:
            raise ValueError("minimum_half_split_agreement must be between zero and one")
        terminal_thresholds = (
            self.minimum_terminal_victories,
            self.minimum_terminal_defeats,
            self.minimum_states_with_candidate_terminal_variation,
        )
        if any(value is None for value in terminal_thresholds) and not all(
            value is None for value in terminal_thresholds
        ):
            raise ValueError("Terminal signal thresholds must be supplied together")
        if any(
            isinstance(value, bool) or value <= 0
            for value in terminal_thresholds
            if value is not None
        ):
            raise ValueError("Terminal signal thresholds must be positive integers")

    @property
    def requires_terminal_signal(self) -> bool:
        return self.minimum_terminal_victories is not None

    def as_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "minimum_states": self.minimum_states,
            "minimum_source_floors": self.minimum_source_floors,
            "minimum_decision_types": self.minimum_decision_types,
            "minimum_effective_labeled_states": self.minimum_effective_labeled_states,
            "minimum_half_split_agreement": self.minimum_half_split_agreement,
            "minimum_occupied_maximum_floor_bins": (self.minimum_occupied_maximum_floor_bins),
        }
        if self.requires_terminal_signal:
            document.update(
                {
                    "minimum_terminal_victories": self.minimum_terminal_victories,
                    "minimum_terminal_defeats": self.minimum_terminal_defeats,
                    "minimum_states_with_candidate_terminal_variation": (
                        self.minimum_states_with_candidate_terminal_variation
                    ),
                }
            )
        return document


@dataclass(frozen=True, slots=True)
class CurriculumStateSet:
    state_set_id: str
    split_manifest_id: str
    ruleset_manifest_id: str
    objective_id: str
    capture_policy_id: str
    partition: str
    selection_policy: str
    discovery: dict[str, Any]
    signal_spec: CurriculumSignalSpec
    cases: tuple[CurriculumStateCase, ...]
    capture_policy: dict[str, str] | None = None

    def __post_init__(self) -> None:
        if self.partition not in {SplitName.TRAIN.value, SplitName.VALIDATION.value}:
            raise ValueError("Curriculum state sets must use train or validation")
        if self.capture_policy is None:
            if self.capture_policy_id != ProgressBootstrapPolicy.policy_id:
                raise ValueError("Curriculum state set omits learned capture-policy provenance")
        else:
            _validate_policy_provenance(
                self.capture_policy,
                policy_id=self.capture_policy_id,
                split_manifest_id=self.split_manifest_id,
                ruleset_manifest_id=self.ruleset_manifest_id,
            )
        if not self.cases:
            raise ValueError("Curriculum state set must contain at least one reachable case")
        ids = [case.state_id for case in self.cases]
        coordinates = [
            (case.run_seed, case.decision_type, case.decision_index) for case in self.cases
        ]
        if len(ids) != len(set(ids)) or len(coordinates) != len(set(coordinates)):
            raise ValueError("Curriculum cases must have unique IDs and coordinates")

    def as_dict(self) -> dict[str, object]:
        frontier = self.discovery.get("schema_version") in {
            "bootstrap-curriculum-discovery-v3",
            "bootstrap-curriculum-discovery-v4",
        }
        combat_advancement = (
            self.capture_policy is not None
            and self.capture_policy.get("kind") == "combat_advancement_checkpoint"
        )
        document: dict[str, object] = {
            "schema_version": (
                COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION
                if combat_advancement
                else (
                    TERMINAL_FRONTIER_STATE_SET_SCHEMA_VERSION
                    if frontier
                    else (
                        LEARNED_CURRICULUM_STATE_SET_SCHEMA_VERSION
                        if self.capture_policy is not None
                        else CURRICULUM_STATE_SET_SCHEMA_VERSION
                    )
                )
            ),
            "state_set_id": self.state_set_id,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "capture_policy_id": self.capture_policy_id,
            "partition": self.partition,
            "selection_policy": self.selection_policy,
            "discovery": self.discovery,
            "signal_spec": self.signal_spec.as_dict(),
            "cases": [case.as_dict() for case in self.cases],
        }
        if self.capture_policy is not None:
            document["capture_policy"] = self.capture_policy
        return document


BootstrapStateSetLike = BootstrapStateSet | CurriculumStateSet


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
    continuation_policy: BootstrapPolicyArtifacts | None = None

    def __post_init__(self) -> None:
        UUID(self.task_id)
        if not self.action_id:
            raise ValueError("Bootstrap action ID must be non-empty")
        if isinstance(self.simulation_seed, bool) or self.simulation_seed < 0:
            raise ValueError("Bootstrap simulation seed must be non-negative")
        if self.maximum_rollout_steps <= 0:
            raise ValueError("Bootstrap rollout limit must be positive")

    def as_dict(self) -> dict[str, object]:
        if (
            self.continuation_policy is not None
            and self.continuation_policy.combat_advancement_config is not None
        ):
            schema_version = COMBAT_ADVANCEMENT_BOOTSTRAP_TASK_SCHEMA_VERSION
        elif self.continuation_policy is not None:
            schema_version = LEARNED_BOOTSTRAP_TASK_SCHEMA_VERSION
        else:
            schema_version = BOOTSTRAP_TASK_SCHEMA_VERSION
        document: dict[str, object] = {
            "schema_version": schema_version,
            "task_id": self.task_id,
            "backend": self.backend.as_dict(),
            "checkpoint": self.checkpoint.as_dict(),
            "action_id": self.action_id,
            "simulation_seed": self.simulation_seed,
            "maximum_rollout_steps": self.maximum_rollout_steps,
            "continuation_policy_id": self.continuation_policy_id,
        }
        if self.continuation_policy is not None:
            document["continuation_policy"] = self.continuation_policy.task_dict()
        return document

    @property
    def continuation_policy_id(self) -> str:
        return (
            self.continuation_policy.policy_id
            if self.continuation_policy is not None
            else ProgressBootstrapPolicy.policy_id
        )

    @classmethod
    def from_mapping(cls, value: object) -> BootstrapSimulationTask:
        document = _mapping(value, "bootstrap task")
        schema_version = document.get("schema_version")
        learned = schema_version in {
            LEARNED_BOOTSTRAP_TASK_SCHEMA_VERSION,
            COMBAT_ADVANCEMENT_BOOTSTRAP_TASK_SCHEMA_VERSION,
        }
        expected_keys = {
            "schema_version",
            "task_id",
            "backend",
            "checkpoint",
            "action_id",
            "simulation_seed",
            "maximum_rollout_steps",
            "continuation_policy_id",
        }
        if learned:
            expected_keys.add("continuation_policy")
        _exact_keys(
            document,
            expected_keys,
            "bootstrap task",
        )
        if schema_version not in {
            BOOTSTRAP_TASK_SCHEMA_VERSION,
            LEARNED_BOOTSTRAP_TASK_SCHEMA_VERSION,
            COMBAT_ADVANCEMENT_BOOTSTRAP_TASK_SCHEMA_VERSION,
        }:
            raise ValueError("Unsupported bootstrap task schema")
        policy = (
            BootstrapPolicyArtifacts.from_task_mapping(document.get("continuation_policy"))
            if learned
            else None
        )
        if (schema_version == COMBAT_ADVANCEMENT_BOOTSTRAP_TASK_SCHEMA_VERSION) != (
            policy is not None and policy.combat_advancement_config is not None
        ):
            raise ValueError("Bootstrap task policy generation differs from its schema")
        expected_policy_id = (
            policy.policy_id if policy is not None else ProgressBootstrapPolicy.policy_id
        )
        if document.get("continuation_policy_id") != expected_policy_id:
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
            continuation_policy=policy,
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
class CurriculumPolicyExample:
    state_id: str
    model_input: CompositionalModelInput
    policy_target: tuple[float, ...]
    policy_target_weight: float
    paired_preference_matrix: tuple[tuple[float, ...], ...]
    hard_target_eligible: bool


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


def load_bootstrap_state_set(path: Path) -> BootstrapStateSetLike:
    return load_bootstrap_state_set_document(_load_object(path))


def load_bootstrap_state_set_document(value: object) -> BootstrapStateSetLike:
    document = _mapping(value, "bootstrap state set")
    if document.get("schema_version") in {
        CURRICULUM_STATE_SET_SCHEMA_VERSION,
        LEARNED_CURRICULUM_STATE_SET_SCHEMA_VERSION,
        TERMINAL_FRONTIER_STATE_SET_SCHEMA_VERSION,
        COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION,
    }:
        return _load_curriculum_state_set_document(document)
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


def discover_curriculum_state_set(
    specification: object,
    *,
    backend: SearchBackendSpec,
    split_manifest: SplitManifest,
    policy_artifacts: BootstrapPolicyArtifacts | None = None,
    run_offset: int = 0,
) -> dict[str, Any]:
    document = _mapping(specification, "curriculum discovery specification")
    schema_version = document.get("schema_version")
    frontier = schema_version in {
        "bootstrap-curriculum-discovery-spec-v3",
        "bootstrap-curriculum-discovery-spec-v4",
    }
    _exact_keys(
        document,
        {
            "schema_version",
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "capture_policy_id",
            "partition",
            "selection_policy",
            "run_count",
            "frontier_selection" if frontier else "decision_occurrences",
            "maximum_steps_per_run",
            "signal_spec",
        },
        "curriculum discovery specification",
    )
    if schema_version not in {
        "bootstrap-curriculum-discovery-spec-v1",
        "bootstrap-curriculum-discovery-spec-v2",
        "bootstrap-curriculum-discovery-spec-v3",
        "bootstrap-curriculum-discovery-spec-v4",
    }:
        raise ValueError("Unsupported curriculum discovery specification")
    partition = SplitName(_string(document.get("partition"), "partition"))
    if partition is SplitName.TEST:
        raise ValueError("Curriculum discovery may not inspect the sealed test partition")
    if document.get("split_manifest_id") != split_manifest.manifest_id:
        raise ValueError("Curriculum discovery references a different split manifest")
    if document.get("ruleset_manifest_id") != split_manifest.ruleset_manifest_id:
        raise ValueError("Curriculum discovery ruleset differs from split manifest")
    if document.get("objective_id") != split_manifest.objective_id:
        raise ValueError("Curriculum discovery objective differs from split manifest")
    expected_policy_id = (
        policy_artifacts.policy_id
        if policy_artifacts is not None
        else ProgressBootstrapPolicy.policy_id
    )
    if document.get("capture_policy_id") != expected_policy_id:
        raise ValueError("Curriculum discovery capture policy differs from supplied artifacts")
    if policy_artifacts is None and schema_version != "bootstrap-curriculum-discovery-spec-v1":
        raise ValueError("Learned curriculum discovery requires checkpoint artifacts")
    if policy_artifacts is not None:
        if schema_version not in {
            "bootstrap-curriculum-discovery-spec-v2",
            "bootstrap-curriculum-discovery-spec-v3",
            "bootstrap-curriculum-discovery-spec-v4",
        }:
            raise ValueError("Learned curriculum discovery requires a v2, v3, or v4 specification")
        policy_artifacts.validate_for(
            split_manifest_id=split_manifest.manifest_id,
            ruleset_manifest_id=split_manifest.ruleset_manifest_id,
        )
        if (policy_artifacts.combat_advancement_config is not None) != (
            schema_version == "bootstrap-curriculum-discovery-spec-v4"
        ):
            raise ValueError(
                "Combat-advancement discovery requires a v4 specification and vice versa"
            )
    run_count = _integer(document.get("run_count"), "run_count")
    maximum_steps = _integer(document.get("maximum_steps_per_run"), "maximum_steps_per_run")
    if run_count <= 0 or maximum_steps <= 0:
        raise ValueError("Curriculum discovery limits must be positive")
    if isinstance(run_offset, bool) or run_offset < 0:
        raise ValueError("Curriculum discovery run_offset must be non-negative")
    partition_seeds = split_manifest.seeds(partition)
    if run_offset + run_count > len(partition_seeds):
        raise ValueError("Curriculum discovery run range exceeds the partition")
    signal_spec = _curriculum_signal_spec(document.get("signal_spec"))
    if frontier:
        if not signal_spec.requires_terminal_signal:
            raise ValueError("Terminal-frontier discovery requires terminal signal thresholds")
        return _discover_terminal_frontier_state_set(
            document,
            backend=backend,
            split_manifest=split_manifest,
            policy_artifacts=cast(BootstrapPolicyArtifacts, policy_artifacts),
            partition=partition,
            partition_seeds=partition_seeds,
            run_offset=run_offset,
            run_count=run_count,
            maximum_steps=maximum_steps,
            signal_spec=signal_spec,
        )
    raw_occurrences = _mapping(document.get("decision_occurrences"), "decision_occurrences")
    if not raw_occurrences:
        raise ValueError("Curriculum discovery requires decision occurrences")
    decision_occurrences: dict[DecisionType, tuple[int, ...]] = {}
    for raw_type, raw_indices in raw_occurrences.items():
        decision_type = DecisionType(raw_type)
        if decision_type in {DecisionType.MENU, DecisionType.TERMINAL, DecisionType.UNKNOWN}:
            raise ValueError(f"Unsupported curriculum decision type: {decision_type.value}")
        indices = tuple(
            _integer(value, f"decision_occurrences.{raw_type}")
            for value in _list(raw_indices, f"decision_occurrences.{raw_type}")
        )
        if not indices or any(index < 0 for index in indices) or len(indices) != len(set(indices)):
            raise ValueError("Decision occurrences must be unique non-negative indices")
        decision_occurrences[decision_type] = indices
    cases: list[dict[str, object]] = []
    unreachable: list[dict[str, object]] = []
    terminal_runs = 0
    truncated_runs = 0
    for run_seed in partition_seeds[run_offset : run_offset + run_count]:
        environment = load_search_environment(backend)
        try:
            observation = environment.reset(run_seed)
            policy = _load_bootstrap_policy(policy_artifacts, environment)
            prefix: list[str] = []
            seen = {decision_type: 0 for decision_type in decision_occurrences}
            found: set[tuple[DecisionType, int]] = set()
            for _ in range(maximum_steps + 1):
                decision_type = observation.decision_type
                if decision_type in decision_occurrences:
                    occurrence = seen[decision_type]
                    if occurrence in decision_occurrences[decision_type]:
                        actions = tuple(environment.legal_actions())
                        if actions:
                            checkpoint = capture_checkpoint(
                                run_seed=run_seed,
                                action_prefix=prefix,
                                environment=environment,
                                observation=observation,
                            )
                            cases.append(
                                CurriculumStateCase(
                                    state_id=(
                                        f"{partition.value}-seed-{run_seed:06d}-"
                                        f"{decision_type.value}-{occurrence:03d}"
                                    ),
                                    run_seed=run_seed,
                                    decision_type=decision_type,
                                    decision_index=occurrence,
                                    expected_state_hash=checkpoint.state_hash,
                                    expected_legal_actions=len(actions),
                                    expected_source_floor=_public_integer(
                                        observation, ("floor",), ("run", "floor")
                                    ),
                                    expected_source_act=_public_act(observation),
                                ).as_dict()
                            )
                            found.add((decision_type, occurrence))
                    seen[decision_type] += 1
                if bool(observation.public_state.get("terminal")):
                    terminal_runs += 1
                    break
                action = policy.choose_action(observation, tuple(environment.legal_actions()))
                prefix.append(action.action_id)
                observation = environment.step(action).next_observation
            else:
                truncated_runs += 1
            for decision_type, indices in decision_occurrences.items():
                for occurrence in indices:
                    if (decision_type, occurrence) not in found:
                        unreachable.append(
                            {
                                "run_seed": run_seed,
                                "decision_type": decision_type.value,
                                "decision_index": occurrence,
                                "reason": "terminal_or_step_limit_before_coordinate",
                            }
                        )
        finally:
            _close_environment(environment)
    requested = run_count * sum(len(indices) for indices in decision_occurrences.values())
    discovery: dict[str, Any] = {
        "schema_version": (
            "bootstrap-curriculum-discovery-v2"
            if policy_artifacts is not None
            else "bootstrap-curriculum-discovery-v1"
        ),
        "requested_runs": run_count,
        "maximum_steps_per_run": maximum_steps,
        "decision_occurrences": {
            decision_type.value: list(indices)
            for decision_type, indices in decision_occurrences.items()
        },
        "requested_coordinates": requested,
        "captured_coordinates": len(cases),
        "unreachable_coordinates": unreachable,
        "terminal_runs": terminal_runs,
        "step_limited_runs": truncated_runs,
    }
    if run_offset:
        discovery["run_offset"] = run_offset
    body: dict[str, Any] = {
        "schema_version": (
            COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION
            if (
                policy_artifacts is not None
                and policy_artifacts.combat_advancement_config is not None
            )
            else CURRICULUM_STATE_SET_SCHEMA_VERSION
            if policy_artifacts is None
            else LEARNED_CURRICULUM_STATE_SET_SCHEMA_VERSION
        ),
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "capture_policy_id": expected_policy_id,
        "partition": partition.value,
        "selection_policy": _string(document.get("selection_policy"), "selection_policy"),
        "discovery": discovery,
        "signal_spec": signal_spec.as_dict(),
        "cases": cases,
    }
    if policy_artifacts is not None:
        body["capture_policy"] = policy_artifacts.provenance()
    frozen = {**body, "state_set_id": manifest_identifier(body)}
    state_set = load_bootstrap_state_set_document(frozen)
    _validate_bootstrap_split(state_set, split_manifest)
    return frozen


def _discover_terminal_frontier_state_set(
    document: dict[str, Any],
    *,
    backend: SearchBackendSpec,
    split_manifest: SplitManifest,
    policy_artifacts: BootstrapPolicyArtifacts,
    partition: SplitName,
    partition_seeds: tuple[int, ...],
    run_offset: int,
    run_count: int,
    maximum_steps: int,
    signal_spec: CurriculumSignalSpec,
) -> dict[str, Any]:
    """Retain each run's deepest actionable states without inspecting sealed test runs."""
    raw_selection = _mapping(document.get("frontier_selection"), "frontier_selection")
    _exact_keys(
        raw_selection,
        {
            "decision_types",
            "minimum_source_floor",
            "minimum_legal_actions",
            "maximum_states_per_run",
        },
        "frontier_selection",
    )
    raw_types = _list(raw_selection.get("decision_types"), "frontier decision types")
    decision_types = tuple(
        DecisionType(_string(value, "frontier decision type")) for value in raw_types
    )
    if not decision_types or len(decision_types) != len(set(decision_types)):
        raise ValueError("Frontier decision types must be non-empty and unique")
    if any(
        decision_type in {DecisionType.MENU, DecisionType.TERMINAL, DecisionType.UNKNOWN}
        for decision_type in decision_types
    ):
        raise ValueError("Frontier selection contains an unsupported decision type")
    minimum_floor = _integer(raw_selection.get("minimum_source_floor"), "minimum_source_floor")
    minimum_actions = _integer(raw_selection.get("minimum_legal_actions"), "minimum_legal_actions")
    maximum_states = _integer(raw_selection.get("maximum_states_per_run"), "maximum_states_per_run")
    if minimum_floor < 0 or minimum_actions <= 0 or maximum_states <= 0:
        raise ValueError("Frontier selection bounds are outside their allowed range")

    cases: list[dict[str, object]] = []
    eligible_coordinates = 0
    runs_with_eligible_coordinates = 0
    terminal_runs = 0
    victorious_runs = 0
    defeated_runs = 0
    step_limited_runs = 0
    maximum_floor_histogram: dict[str, int] = {}
    for run_seed in partition_seeds[run_offset : run_offset + run_count]:
        environment = load_search_environment(backend)
        try:
            observation = environment.reset(run_seed)
            policy = _load_bootstrap_policy(policy_artifacts, environment)
            prefix: list[str] = []
            seen = {decision_type: 0 for decision_type in decision_types}
            eligible: list[tuple[int, int, dict[str, object]]] = []
            maximum_floor: int | None = None
            for global_index in range(maximum_steps + 1):
                source_floor = _public_integer(observation, ("floor",), ("run", "floor"))
                if source_floor is not None:
                    maximum_floor = (
                        source_floor if maximum_floor is None else max(maximum_floor, source_floor)
                    )
                decision_type = observation.decision_type
                if decision_type in seen:
                    occurrence = seen[decision_type]
                    seen[decision_type] += 1
                    actions = tuple(environment.legal_actions())
                    if (
                        source_floor is not None
                        and source_floor >= minimum_floor
                        and len(actions) >= minimum_actions
                    ):
                        checkpoint = capture_checkpoint(
                            run_seed=run_seed,
                            action_prefix=prefix,
                            environment=environment,
                            observation=observation,
                        )
                        case = CurriculumStateCase(
                            state_id=(
                                f"{partition.value}-seed-{run_seed:06d}-"
                                f"{decision_type.value}-{occurrence:03d}"
                            ),
                            run_seed=run_seed,
                            decision_type=decision_type,
                            decision_index=occurrence,
                            expected_state_hash=checkpoint.state_hash,
                            expected_legal_actions=len(actions),
                            expected_source_floor=source_floor,
                            expected_source_act=_public_act(observation),
                        ).as_dict()
                        eligible.append((source_floor, global_index, case))
                if bool(observation.public_state.get("terminal")):
                    terminal_runs += 1
                    if bool(observation.public_state.get("victory")):
                        victorious_runs += 1
                    else:
                        defeated_runs += 1
                    break
                action = policy.choose_action(observation, tuple(environment.legal_actions()))
                prefix.append(action.action_id)
                observation = environment.step(action).next_observation
            else:
                step_limited_runs += 1
            if eligible:
                runs_with_eligible_coordinates += 1
            eligible_coordinates += len(eligible)
            selected = sorted(eligible, key=lambda item: (item[0], item[1]), reverse=True)[
                :maximum_states
            ]
            cases.extend(case for _, _, case in sorted(selected, key=lambda item: item[1]))
            maximum_floor_key = "unknown" if maximum_floor is None else str(maximum_floor)
            maximum_floor_histogram[maximum_floor_key] = (
                maximum_floor_histogram.get(maximum_floor_key, 0) + 1
            )
        finally:
            _close_environment(environment)

    discovery: dict[str, Any] = {
        "schema_version": (
            "bootstrap-curriculum-discovery-v4"
            if policy_artifacts.combat_advancement_config is not None
            else "bootstrap-curriculum-discovery-v3"
        ),
        "requested_runs": run_count,
        "maximum_steps_per_run": maximum_steps,
        "frontier_selection": {
            "decision_types": [decision_type.value for decision_type in decision_types],
            "minimum_source_floor": minimum_floor,
            "minimum_legal_actions": minimum_actions,
            "maximum_states_per_run": maximum_states,
        },
        "eligible_coordinates": eligible_coordinates,
        "captured_coordinates": len(cases),
        "runs_with_eligible_coordinates": runs_with_eligible_coordinates,
        "terminal_runs": terminal_runs,
        "victorious_runs": victorious_runs,
        "defeated_runs": defeated_runs,
        "step_limited_runs": step_limited_runs,
        "source_maximum_floor_histogram": maximum_floor_histogram,
    }
    if run_offset:
        discovery["run_offset"] = run_offset
    body: dict[str, Any] = {
        "schema_version": (
            COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION
            if policy_artifacts.combat_advancement_config is not None
            else TERMINAL_FRONTIER_STATE_SET_SCHEMA_VERSION
        ),
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "capture_policy_id": policy_artifacts.policy_id,
        "partition": partition.value,
        "selection_policy": _string(document.get("selection_policy"), "selection_policy"),
        "discovery": discovery,
        "signal_spec": signal_spec.as_dict(),
        "cases": cases,
        "capture_policy": policy_artifacts.provenance(),
    }
    frozen = {**body, "state_set_id": manifest_identifier(body)}
    state_set = load_bootstrap_state_set_document(frozen)
    _validate_bootstrap_split(state_set, split_manifest)
    return frozen


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


def capture_curriculum_state(
    *,
    backend: SearchBackendSpec,
    run_seed: int,
    decision_type: DecisionType,
    decision_index: int,
    maximum_prefix_steps: int,
    policy_artifacts: BootstrapPolicyArtifacts | None = None,
) -> _CapturedBootstrapState:
    if decision_type in {DecisionType.MENU, DecisionType.TERMINAL, DecisionType.UNKNOWN}:
        raise ValueError(f"Unsupported curriculum decision type: {decision_type.value}")
    if decision_index < 0:
        raise ValueError("Curriculum decision index must be non-negative")
    environment = load_search_environment(backend)
    try:
        observation = environment.reset(run_seed)
        policy = _load_bootstrap_policy(policy_artifacts, environment)
        prefix: list[str] = []
        seen = 0
        for _ in range(maximum_prefix_steps + 1):
            if observation.decision_type is decision_type:
                if seen == decision_index:
                    actions = tuple(environment.legal_actions())
                    if not actions:
                        raise RuntimeError("Captured curriculum state has no legal actions")
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
        f"Run seed {run_seed} did not reach {decision_type.value} decision {decision_index} "
        f"within {maximum_prefix_steps} decisions"
    )


def execute_bootstrap_task(task: BootstrapSimulationTask) -> dict[str, object]:
    environment, source = restore_search_checkpoint(task.backend, task.checkpoint)
    sampled: object | None = None
    try:
        mechanics = PublicMechanicsService()
        source_snapshot = mechanics.snapshot(environment, source)
        source_action = _action_by_id(source_snapshot.legal_actions, task.action_id)
        sampled, accepted_hidden_seed, hidden_resample_attempts = _sample_bootstrap_hidden_world(
            environment,
            source,
            source_snapshot.legal_actions,
            mechanics=mechanics,
            task=task,
        )
        policy = _load_bootstrap_policy(task.continuation_policy, sampled)
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
            "method": _bootstrap_output_method(task),
            "patch_id": environment.patch_id,
            "ruleset_manifest_id": environment.ruleset.manifest_id,
            "source_state_hash": task.checkpoint.state_hash,
            "action_id": task.action_id,
            "simulation_seed": task.simulation_seed,
            "continuation_policy_id": task.continuation_policy_id,
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
        if (
            task.continuation_policy is not None
            and task.continuation_policy.combat_advancement_config is not None
        ):
            usage = getattr(policy, "usage", None)
            if not callable(usage):
                raise RuntimeError("Combat-advancement policy exposes no usage accounting")
            output.update(
                {
                    "hidden_resample_seed": accepted_hidden_seed,
                    "hidden_resample_attempts": hidden_resample_attempts,
                    "combat_advancement_usage": usage().as_dict(),
                }
            )
        output["bootstrap_utility"] = bootstrap_utility(output)
        return output
    finally:
        if sampled is not None:
            _close_environment(sampled)
        _close_environment(environment)


def _sample_bootstrap_hidden_world(
    environment: EnvironmentAdapter,
    source: Observation,
    legal_actions: Sequence[LegalAction],
    *,
    mechanics: PublicMechanicsService,
    task: BootstrapSimulationTask,
) -> tuple[EnvironmentAdapter, int, int]:
    config = (
        None
        if task.continuation_policy is None
        else task.continuation_policy.combat_advancement_config
    )
    maximum_attempts = 1 if config is None else config.maximum_public_resample_attempts
    for attempt_index in range(maximum_attempts):
        seed = (
            task.simulation_seed
            if attempt_index == 0
            else _bootstrap_retry_seed(task.simulation_seed, attempt_index)
        )
        sampled = environment.clone(resample_hidden=True, seed=seed)
        sampled_snapshot = mechanics.snapshot(sampled, source)
        if sampled_snapshot.legal_actions == tuple(legal_actions):
            return sampled, seed, attempt_index + 1
        _close_environment(sampled)
    raise RuntimeError("Hidden-world clone changed public legal actions")


def _bootstrap_retry_seed(base_seed: int, attempt_index: int) -> int:
    payload = f"bootstrap-public-condition-v1|{base_seed}|{attempt_index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def _bootstrap_output_method(task: BootstrapSimulationTask) -> str:
    if (
        task.continuation_policy is not None
        and task.continuation_policy.combat_advancement_config is not None
    ):
        return "paired-public-combat-advancement-rollout-v3"
    if task.continuation_policy is not None:
        return "paired-public-progress-rollout-v2"
    return "paired-public-progress-rollout-v1"


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
    state_set: BootstrapStateSetLike,
    split_manifest: SplitManifest,
    objective: ObjectiveSpec,
    config: BootstrapConfig,
    output_directory: Path,
    task_runner: Callable[[BootstrapSimulationTask], dict[str, object]] | None = None,
    resume: bool = False,
    policy_artifacts: BootstrapPolicyArtifacts | None = None,
) -> BootstrapDatasetResult:
    _validate_bootstrap_split(state_set, split_manifest)
    if isinstance(state_set, CurriculumStateSet):
        _validate_curriculum_discovery_readiness(state_set)
        _validate_execution_policy(state_set, policy_artifacts)
    elif policy_artifacts is not None:
        raise ValueError("Learned policy artifacts require a curriculum state set")
    if objective.objective_id != state_set.objective_id:
        raise ValueError("Bootstrap objective differs from frozen state set")
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists() and not resume:
        raise FileExistsError(output_directory)
    output_directory.mkdir(parents=True, exist_ok=resume)
    report_path = output_directory / "bootstrap-teacher-dataset.json"
    if report_path.exists():
        if not resume:
            raise FileExistsError(report_path)
        _prepare_failed_dataset_resume(
            report_path,
            backend=backend,
            state_set=state_set,
            objective=objective,
            config=config,
            policy_artifacts=policy_artifacts,
        )
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
            if isinstance(case, CurriculumStateCase):
                captured = capture_curriculum_state(
                    backend=backend,
                    run_seed=case.run_seed,
                    decision_type=case.decision_type,
                    decision_index=case.decision_index,
                    maximum_prefix_steps=config.maximum_prefix_steps,
                    policy_artifacts=policy_artifacts,
                )
            else:
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
            tasks = _bootstrap_tasks(
                backend,
                captured,
                config,
                continuation_policy=policy_artifacts,
            )
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
                curriculum=isinstance(state_set, CurriculumStateSet),
            )
            record_body: dict[str, Any] = {
                "schema_version": (
                    "bootstrap-teacher-record-v2"
                    if isinstance(state_set, CurriculumStateSet)
                    else "bootstrap-teacher-record-v1"
                ),
                "state_id": case.state_id,
                "run_seed": case.run_seed,
                "source_state_hash": captured.checkpoint.state_hash,
                "model_input": model_input.as_dict(),
                "target": target,
            }
            if isinstance(case, CurriculumStateCase):
                record_body.update(
                    {
                        "decision_type": case.decision_type.value,
                        "decision_index": case.decision_index,
                        "source_floor": _public_integer(
                            captured.observation, ("floor",), ("run", "floor")
                        ),
                        "source_act": _public_act(captured.observation),
                    }
                )
            else:
                record_body["combat_state_index"] = case.combat_state_index
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
    summary = (
        _curriculum_dataset_summary(case_documents, state_set)
        if isinstance(state_set, CurriculumStateSet)
        else _dataset_summary(case_documents)
    )
    signal_assessment = (
        _assess_curriculum_signal(summary, state_set.signal_spec)
        if isinstance(state_set, CurriculumStateSet)
        else None
    )
    body: dict[str, Any] = {
        "schema_version": _dataset_schema_for(state_set),
        "teacher_id": (
            CURRICULUM_TEACHER_ID
            if isinstance(state_set, CurriculumStateSet)
            else BOOTSTRAP_TEACHER_ID
        ),
        "utility_id": BOOTSTRAP_UTILITY_ID,
        "seed_protocol_id": BOOTSTRAP_SEED_PROTOCOL_ID,
        "objective_id": state_set.objective_id,
        "objective": objective.as_dict(),
        "auxiliary_reward_allowed": False,
        "backend": backend.as_dict(),
        "state_set": state_set.as_dict(),
        "configuration": _dataset_configuration(config, policy_artifacts),
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
        "claim_scope": f"{state_set.partition}_curriculum_only",
    }
    if signal_assessment is not None:
        body["signal_assessment"] = signal_assessment
    report = {**body, "dataset_id": manifest_identifier(body)}
    write_exclusive_json(report_path, report)
    return BootstrapDatasetResult(summary["failed_cases"] == 0, report_path, report)


def combine_curriculum_datasets(
    component_report_paths: Sequence[Path],
    *,
    output_directory: Path,
    split_manifest: SplitManifest,
) -> BootstrapDatasetResult:
    """Materialize a verified, seed-disjoint learned curriculum as one dataset."""
    if len(component_report_paths) < 2:
        raise ValueError("Curriculum composition requires at least two component datasets")
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists():
        raise FileExistsError(output_directory)

    components: list[tuple[Path, dict[str, Any], CurriculumStateSet]] = []
    for raw_path in component_report_paths:
        report_path = raw_path.expanduser().resolve()
        verification = verify_bootstrap_teacher_dataset(
            report_path,
            split_manifest=split_manifest,
        )
        if not verification.valid:
            raise ValueError(
                f"Component curriculum failed verification ({report_path}): "
                + "; ".join(verification.errors)
            )
        report = _load_object(report_path)
        if report.get("schema_version") != LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION:
            raise ValueError("Curriculum composition requires learned-policy v3 datasets")
        state_set = load_bootstrap_state_set_document(report.get("state_set"))
        if not isinstance(state_set, CurriculumStateSet) or state_set.capture_policy is None:
            raise ValueError("Curriculum composition requires learned-policy state sets")
        if state_set.partition != SplitName.TRAIN.value:
            raise ValueError("Curriculum composition is restricted to the train partition")
        components.append((report_path, report, state_set))

    _, first_report, first_state_set = components[0]
    invariant_report_fields = (
        "teacher_id",
        "utility_id",
        "seed_protocol_id",
        "objective_id",
        "objective",
        "auxiliary_reward_allowed",
        "backend",
        "configuration",
        "claim_scope",
    )
    for _, report, state_set in components[1:]:
        if any(report.get(field) != first_report.get(field) for field in invariant_report_fields):
            raise ValueError("Component curricula use incompatible dataset configuration")
        if (
            state_set.split_manifest_id != first_state_set.split_manifest_id
            or state_set.ruleset_manifest_id != first_state_set.ruleset_manifest_id
            or state_set.objective_id != first_state_set.objective_id
            or state_set.capture_policy_id != first_state_set.capture_policy_id
            or state_set.capture_policy != first_state_set.capture_policy
        ):
            raise ValueError("Component curricula use incompatible state-set provenance")

    seen_state_ids: set[str] = set()
    seen_run_seeds: set[int] = set()
    combined_cases: list[CurriculumStateCase] = []
    for _, _, state_set in components:
        state_ids = {case.state_id for case in state_set.cases}
        run_seeds = {case.run_seed for case in state_set.cases}
        if seen_state_ids & state_ids:
            raise ValueError("Component curricula contain overlapping state IDs")
        if seen_run_seeds & run_seeds:
            raise ValueError("Component curricula contain overlapping complete-run seeds")
        seen_state_ids.update(state_ids)
        seen_run_seeds.update(run_seeds)
        combined_cases.extend(state_set.cases)

    signal_specs = [state_set.signal_spec for _, _, state_set in components]
    combined_signal_spec = CurriculumSignalSpec(
        minimum_states=max(spec.minimum_states for spec in signal_specs),
        minimum_source_floors=max(spec.minimum_source_floors for spec in signal_specs),
        minimum_decision_types=max(spec.minimum_decision_types for spec in signal_specs),
        minimum_effective_labeled_states=max(
            spec.minimum_effective_labeled_states for spec in signal_specs
        ),
        minimum_half_split_agreement=max(
            spec.minimum_half_split_agreement for spec in signal_specs
        ),
        minimum_occupied_maximum_floor_bins=max(
            spec.minimum_occupied_maximum_floor_bins for spec in signal_specs
        ),
    )
    combined_occurrences: dict[str, set[int]] = {}
    unreachable: list[Any] = []
    requested_coordinates = 0
    terminal_runs = 0
    step_limited_runs = 0
    maximum_steps: set[int] = set()
    for _, _, state_set in components:
        discovery = state_set.discovery
        for decision_type, indices in _mapping(
            discovery.get("decision_occurrences"), "decision occurrences"
        ).items():
            combined_occurrences.setdefault(decision_type, set()).update(
                _integer(index, "decision occurrence")
                for index in _list(indices, "decision occurrences")
            )
        unreachable.extend(
            _list(discovery.get("unreachable_coordinates"), "unreachable coordinates")
        )
        requested_coordinates += _integer(
            discovery.get("requested_coordinates"), "requested coordinates"
        )
        terminal_runs += _integer(discovery.get("terminal_runs"), "terminal runs")
        step_limited_runs += _integer(discovery.get("step_limited_runs"), "step-limited runs")
        maximum_steps.add(_integer(discovery.get("maximum_steps_per_run"), "maximum steps per run"))
    if len(maximum_steps) != 1:
        raise ValueError("Component curricula use different discovery step limits")
    discovery = {
        "schema_version": "bootstrap-curriculum-discovery-v2",
        "requested_runs": len(seen_run_seeds),
        "maximum_steps_per_run": maximum_steps.pop(),
        "decision_occurrences": {
            key: sorted(values) for key, values in sorted(combined_occurrences.items())
        },
        "requested_coordinates": requested_coordinates,
        "captured_coordinates": len(combined_cases),
        "unreachable_coordinates": unreachable,
        "terminal_runs": terminal_runs,
        "step_limited_runs": step_limited_runs,
        "component_state_set_ids": [state_set.state_set_id for _, _, state_set in components],
    }
    state_body: dict[str, Any] = {
        "schema_version": LEARNED_CURRICULUM_STATE_SET_SCHEMA_VERSION,
        "split_manifest_id": first_state_set.split_manifest_id,
        "ruleset_manifest_id": first_state_set.ruleset_manifest_id,
        "objective_id": first_state_set.objective_id,
        "capture_policy_id": first_state_set.capture_policy_id,
        "partition": first_state_set.partition,
        "selection_policy": "verified-seed-disjoint-curriculum-composition-v1",
        "discovery": discovery,
        "signal_spec": combined_signal_spec.as_dict(),
        "cases": [case.as_dict() for case in combined_cases],
        "capture_policy": first_state_set.capture_policy,
    }
    state_document = {**state_body, "state_set_id": manifest_identifier(state_body)}
    combined_state_set = load_bootstrap_state_set_document(state_document)
    if not isinstance(combined_state_set, CurriculumStateSet):
        raise AssertionError("Composed curriculum did not produce a curriculum state set")
    _validate_bootstrap_split(combined_state_set, split_manifest)

    output_directory.parent.mkdir(parents=True, exist_ok=True)
    staging = output_directory.with_name(
        f".{output_directory.name}.compose-{uuid5(NAMESPACE_URL, str(time.time_ns()))}"
    )
    staging.mkdir(parents=False, exist_ok=False)
    case_documents: list[dict[str, Any]] = []
    try:
        for report_path, report, state_set in components:
            references = _list(report.get("cases"), "dataset cases")
            if len(references) != len(state_set.cases):
                raise ValueError("Component case references differ from state set")
            for case, raw_reference in zip(state_set.cases, references, strict=True):
                reference = _mapping(raw_reference, "dataset case")
                expected_relative = Path("cases") / case.state_id / "case.json"
                if Path(_string(reference.get("path"), "case path")) != expected_relative:
                    raise ValueError("Component case path is not in its canonical location")
                source_case_root = report_path.parent / expected_relative.parent
                destination_case_root = staging / expected_relative.parent
                shutil.copytree(
                    source_case_root,
                    destination_case_root,
                    copy_function=_hardlink_or_copy,
                )
                case_documents.append(_load_object(destination_case_root / "case.json"))

        summary = _curriculum_dataset_summary(case_documents, combined_state_set)
        signal_assessment = _assess_curriculum_signal(summary, combined_signal_spec)
        body: dict[str, Any] = {
            "schema_version": LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION,
            "teacher_id": first_report["teacher_id"],
            "utility_id": first_report["utility_id"],
            "seed_protocol_id": first_report["seed_protocol_id"],
            "objective_id": first_report["objective_id"],
            "objective": first_report["objective"],
            "auxiliary_reward_allowed": False,
            "backend": first_report["backend"],
            "state_set": combined_state_set.as_dict(),
            "configuration": first_report["configuration"],
            "started_at": min(
                _string(report.get("started_at"), "started_at") for _, report, _ in components
            ),
            "completed_at": max(
                _string(report.get("completed_at"), "completed_at") for _, report, _ in components
            ),
            "cases": [
                {
                    "state_id": case["state_id"],
                    "path": str(Path("cases") / case["state_id"] / "case.json"),
                    "sha256": sha256_file(staging / "cases" / case["state_id"] / "case.json"),
                    "case_id": case["case_id"],
                }
                for case in case_documents
            ],
            "summary": summary,
            "claim_scope": "train_curriculum_only",
            "signal_assessment": signal_assessment,
        }
        report = {**body, "dataset_id": manifest_identifier(body)}
        report_path = staging / "bootstrap-teacher-dataset.json"
        write_exclusive_json(report_path, report)
        staging.replace(output_directory)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    final_report_path = output_directory / "bootstrap-teacher-dataset.json"
    return BootstrapDatasetResult(summary["failed_cases"] == 0, final_report_path, report)


def _hardlink_or_copy(source: str, destination: str) -> str:
    try:
        os.link(source, destination)
        return destination
    except OSError:
        return shutil.copy2(source, destination)


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
        dataset_schema = report.get("schema_version")
        if dataset_schema not in {
            BOOTSTRAP_DATASET_SCHEMA_VERSION,
            CURRICULUM_DATASET_SCHEMA_VERSION,
            LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION,
            TERMINAL_FRONTIER_DATASET_SCHEMA_VERSION,
            COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION,
        }:
            errors.append("unsupported bootstrap dataset schema")
        expected_teacher_id = (
            CURRICULUM_TEACHER_ID
            if dataset_schema
            in {
                CURRICULUM_DATASET_SCHEMA_VERSION,
                LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION,
                TERMINAL_FRONTIER_DATASET_SCHEMA_VERSION,
                COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION,
            }
            else BOOTSTRAP_TEACHER_ID
        )
        if report.get("teacher_id") != expected_teacher_id:
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
        state_set = load_bootstrap_state_set_document(report.get("state_set"))
        _validate_bootstrap_split(state_set, split_manifest)
        configuration = _mapping(report.get("configuration"), "dataset configuration")
        continuation = configuration.get("continuation_policy")
        if isinstance(state_set, CurriculumStateSet) and state_set.capture_policy is not None:
            if continuation != state_set.capture_policy:
                errors.append("dataset continuation policy differs from capture policy")
        elif continuation is not None:
            errors.append("baseline dataset unexpectedly declares a learned continuation policy")
        if dataset_schema == COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION:
            from spireshift.agents.combat_advancement import CombatAdvancementConfig

            search_config = CombatAdvancementConfig.from_mapping(
                configuration.get("combat_advancement_config")
            )
            if (
                not isinstance(state_set, CurriculumStateSet)
                or state_set.capture_policy is None
                or state_set.capture_policy.get("combat_advancement_config_id")
                != search_config.config_id
            ):
                errors.append("dataset combat-advancement config differs from state set")
        if report.get("claim_scope") != f"{state_set.partition}_curriculum_only":
            errors.append("bootstrap dataset claim scope differs from state-set partition")
        if isinstance(state_set, CurriculumStateSet) != (
            dataset_schema
            in {
                CURRICULUM_DATASET_SCHEMA_VERSION,
                LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION,
                TERMINAL_FRONTIER_DATASET_SCHEMA_VERSION,
                COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION,
            }
        ):
            errors.append("bootstrap dataset and state-set schema generations differ")
        if isinstance(state_set, CurriculumStateSet):
            expected_schema = _dataset_schema_for(state_set)
            if dataset_schema != expected_schema:
                errors.append("bootstrap dataset policy generation differs from state set")
        raw_cases = _list(report.get("cases"), "dataset cases")
        expected_cases = cast(Sequence[BootstrapStateCase | CurriculumStateCase], state_set.cases)
        if len(raw_cases) != len(expected_cases):
            errors.append("bootstrap dataset case count differs from frozen state set")
        root = report_path.parent.resolve()
        regenerated: list[dict[str, Any]] = []
        for index, expected in enumerate(expected_cases):
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
            if isinstance(expected, CurriculumStateCase):
                if record.get("decision_type") != expected.decision_type.value:
                    errors.append(f"case {expected.state_id}: record decision type mismatch")
                if record.get("decision_index") != expected.decision_index:
                    errors.append(f"case {expected.state_id}: record decision index mismatch")
                if record.get("source_floor") != expected.expected_source_floor:
                    errors.append(f"case {expected.state_id}: record source floor mismatch")
                if record.get("source_act") != expected.expected_source_act:
                    errors.append(f"case {expected.state_id}: record source act mismatch")
            elif record.get("combat_state_index") != expected.combat_state_index:
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
            samples = _integer(configuration.get("samples_per_candidate"), "samples_per_candidate")
            batch_tasks = _list(batch_report.get("tasks"), "batch tasks")
            reconstructed_target = _build_bootstrap_target(
                reconstructed_actions,
                batch_tasks,
                samples,
                curriculum=isinstance(state_set, CurriculumStateSet),
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
                continuation_policy_id=state_set.capture_policy_id,
            )
            if not batch_errors:
                verified_cases += 1
        regenerated_summary = (
            _curriculum_dataset_summary(regenerated, state_set)
            if isinstance(state_set, CurriculumStateSet)
            else _dataset_summary(regenerated)
        )
        if regenerated_summary != report.get("summary"):
            errors.append("bootstrap dataset summary differs from case evidence")
        if isinstance(state_set, CurriculumStateSet):
            expected_assessment = _assess_curriculum_signal(
                regenerated_summary, state_set.signal_spec
            )
            if report.get("signal_assessment") != expected_assessment:
                errors.append("curriculum signal assessment differs from case evidence")
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


def load_curriculum_policy_examples(
    report_path: Path,
    *,
    split_manifest: SplitManifest,
) -> tuple[CurriculumPolicyExample, ...]:
    verification = verify_bootstrap_teacher_dataset(
        report_path,
        split_manifest=split_manifest,
    )
    if not verification.valid:
        raise ValueError(
            "Curriculum dataset failed verification: " + "; ".join(verification.errors)
        )
    report = _load_object(report_path)
    if report.get("schema_version") not in {
        CURRICULUM_DATASET_SCHEMA_VERSION,
        LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION,
        TERMINAL_FRONTIER_DATASET_SCHEMA_VERSION,
        COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION,
    }:
        raise ValueError("Policy examples require a curriculum dataset")
    root = report_path.parent.resolve()
    examples: list[CurriculumPolicyExample] = []
    for raw_reference in _list(report.get("cases"), "dataset cases"):
        reference = _mapping(raw_reference, "dataset case")
        case_path = _safe_child(root, _string(reference.get("path"), "case path"))
        case = _load_object(case_path)
        if case.get("status") != "completed":
            continue
        record = _mapping(case.get("record"), "case record")
        model_input = model_input_from_mapping(record.get("model_input"))
        target = _mapping(record.get("target"), "curriculum target")
        policy_target = tuple(
            _probability(value, "soft policy probability")
            for value in _list(target.get("soft_policy_target"), "soft policy target")
        )
        if len(policy_target) != len(model_input.candidates):
            raise ValueError("Curriculum policy target differs from candidate count")
        if not math.isclose(sum(policy_target), 1.0, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("Curriculum soft policy target does not sum to one")
        raw_matrix = _list(target.get("paired_preference_matrix"), "preference matrix")
        matrix = tuple(
            tuple(
                _probability(value, "paired preference")
                for value in _list(raw_row, "preference row")
            )
            for raw_row in raw_matrix
        )
        if len(matrix) != len(policy_target) or any(
            len(row) != len(policy_target) for row in matrix
        ):
            raise ValueError("Curriculum paired preference matrix is not square")
        examples.append(
            CurriculumPolicyExample(
                state_id=_string(record.get("state_id"), "state ID"),
                model_input=model_input,
                policy_target=policy_target,
                policy_target_weight=_probability(
                    target.get("policy_target_weight"), "policy target weight"
                ),
                paired_preference_matrix=matrix,
                hard_target_eligible=_boolean(
                    target.get("hard_target_eligible"), "hard target eligibility"
                ),
            )
        )
    if not examples:
        raise ValueError("Curriculum dataset contains no completed policy examples")
    return tuple(examples)


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
        "schema_version": _worker_result_schema(task),
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
        result.get("schema_version") != _worker_result_schema(task)
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
    *,
    continuation_policy: BootstrapPolicyArtifacts | None = None,
) -> tuple[BootstrapSimulationTask, ...]:
    tasks: list[BootstrapSimulationTask] = []
    for sample_index in range(config.samples_per_candidate):
        seed = _bootstrap_seed(config.sampling_seed, captured.checkpoint.state_hash, sample_index)
        for action in captured.legal_actions:
            identity_parts = [BOOTSTRAP_TEACHER_ID]
            if continuation_policy is not None:
                identity_parts.append(continuation_policy.policy_id)
            identity_parts.extend((captured.checkpoint.state_hash, action.action_id, str(seed)))
            task_id = str(
                uuid5(
                    NAMESPACE_URL,
                    "|".join(identity_parts),
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
                    continuation_policy,
                )
            )
    return tuple(tasks)


def _build_bootstrap_target(
    actions: Sequence[LegalAction],
    raw_evidence: Sequence[Any],
    samples_per_candidate: int,
    *,
    curriculum: bool = False,
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
        candidate: dict[str, Any] = {
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
                sum(value is True for value in act_known) / len(act_known) if act_known else None
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
        if curriculum:
            candidate["progress_utility_standard_error"] = math.sqrt(
                _variance(utilities) / len(utilities)
            )
        candidates.append(candidate)
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
    target = {
        "teacher_id": CURRICULUM_TEACHER_ID if curriculum else BOOTSTRAP_TEACHER_ID,
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
    if curriculum:
        target.update(_paired_preference_target(candidates, selected))
    return target


def _paired_preference_target(
    candidates: Sequence[dict[str, Any]],
    selected: int,
) -> dict[str, Any]:
    outcome_rows = [
        [_mapping(value, "candidate outcome") for value in candidate["outcomes"]]
        for candidate in candidates
    ]
    sample_count = len(outcome_rows[0])
    if any(len(row) != sample_count for row in outcome_rows):
        raise RuntimeError("Paired preference candidates have different sample counts")
    matrix: list[list[float]] = []
    for left_index, left in enumerate(outcome_rows):
        row: list[float] = []
        for right_index, right in enumerate(outcome_rows):
            if left_index == right_index:
                row.append(0.5)
                continue
            score = 0.0
            for left_outcome, right_outcome in zip(left, right, strict=True):
                left_rank = _outcome_rank(left_outcome)
                right_rank = _outcome_rank(right_outcome)
                score += 1.0 if left_rank > right_rank else 0.5 if left_rank == right_rank else 0.0
            row.append(score / sample_count)
        matrix.append(row)
    if len(candidates) == 1:
        strengths = [1.0]
    else:
        strengths = [
            sum(value for index, value in enumerate(row) if index != candidate_index)
            / (len(candidates) - 1)
            for candidate_index, row in enumerate(matrix)
        ]
    total_strength = sum(strengths)
    soft_target = (
        [value / total_strength for value in strengths]
        if total_strength > 0.0
        else [1.0 / len(strengths) for _ in strengths]
    )
    ordered = sorted(strengths, reverse=True)
    paired_margin = ordered[0] - ordered[1] if len(ordered) > 1 else 0.0
    selected_wins = 0.0
    for sample_index in range(sample_count):
        selected_rank = _outcome_rank(outcome_rows[selected][sample_index])
        best_rank = max(_outcome_rank(row[sample_index]) for row in outcome_rows)
        tied_best = sum(_outcome_rank(row[sample_index]) == best_rank for row in outcome_rows)
        if selected_rank == best_rank:
            selected_wins += 1.0 / tied_best
    winner_confidence = selected_wins / sample_count
    half_split_agreement: bool | None = None
    if sample_count >= 2:
        midpoint = sample_count // 2
        first = _select_candidate_from_outcomes(candidates, 0, midpoint)
        second = _select_candidate_from_outcomes(candidates, midpoint, sample_count)
        half_split_agreement = first == second
    stability_multiplier = (
        1.0 if half_split_agreement is True else 0.5 if half_split_agreement is False else 0.0
    )
    target_weight = (
        max(0.0, min(1.0, 2.0 * winner_confidence - 1.0)) * stability_multiplier
        if len(candidates) > 1
        else 0.0
    )
    return {
        "paired_preference_matrix": matrix,
        "soft_policy_target": soft_target,
        "winner_confidence": winner_confidence,
        "paired_preference_margin": paired_margin,
        "half_split_winner_agreement": half_split_agreement,
        "policy_target_weight": target_weight,
        "hard_target_eligible": (
            len(candidates) > 1
            and strengths.count(max(strengths)) == 1
            and strengths[selected] == max(strengths)
            and half_split_agreement is True
            and winner_confidence >= 0.75
            and paired_margin > 0.0
        ),
        "policy_training_interface": "paired-preference-soft-target-v1",
    }


def _outcome_rank(output: dict[str, object]) -> tuple[int, int, int, int]:
    return (
        int(output.get("terminal") is True and output.get("victory") is True),
        _optional_integer(output.get("maximum_floor")) or 0,
        int(output.get("act_completed") is True),
        _optional_integer(output.get("final_hp")) or 0,
    )


def _select_candidate_from_outcomes(
    candidates: Sequence[dict[str, Any]],
    start: int,
    stop: int,
) -> int:
    return max(
        range(len(candidates)),
        key=lambda index: _aggregate_outcome_rank(
            [
                _mapping(value, "candidate outcome")
                for value in _list(candidates[index]["outcomes"], "candidate outcomes")[start:stop]
            ],
            index,
        ),
    )


def _aggregate_outcome_rank(
    outcomes: Sequence[dict[str, object]],
    candidate_index: int,
) -> tuple[float, float, float, float, int]:
    ranks = [_outcome_rank(outcome) for outcome in outcomes]
    count = len(ranks)
    return (
        sum(rank[0] for rank in ranks) / count,
        sum(rank[1] for rank in ranks) / count,
        sum(rank[2] for rank in ranks) / count,
        sum(rank[3] for rank in ranks) / count,
        -candidate_index,
    )


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
                    "schema_version": _worker_result_schema(task),
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
    continuation_policy_id: str,
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
        if task.continuation_policy_id != continuation_policy_id:
            raise ValueError("bootstrap task continuation policy differs from state set")
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
    combat_advancement = (
        task.continuation_policy is not None
        and task.continuation_policy.combat_advancement_config is not None
    )
    if combat_advancement:
        expected_keys.update(
            {
                "hidden_resample_seed",
                "hidden_resample_attempts",
                "combat_advancement_usage",
            }
        )
    _exact_keys(output, expected_keys, "bootstrap output")
    expected = {
        "method": _bootstrap_output_method(task),
        "patch_id": task.checkpoint.patch_id,
        "ruleset_manifest_id": task.checkpoint.ruleset_manifest_id,
        "source_state_hash": task.checkpoint.state_hash,
        "action_id": task.action_id,
        "simulation_seed": task.simulation_seed,
        "continuation_policy_id": task.continuation_policy_id,
    }
    if any(output.get(key) != value for key, value in expected.items()):
        raise ValueError("bootstrap output identity mismatch")
    if combat_advancement:
        _integer(output.get("hidden_resample_seed"), "hidden resample seed")
        attempts = _integer(output.get("hidden_resample_attempts"), "hidden resample attempts")
        config = cast(BootstrapPolicyArtifacts, task.continuation_policy).combat_advancement_config
        if config is None or not 1 <= attempts <= config.maximum_public_resample_attempts:
            raise ValueError("bootstrap hidden resample attempts exceed the declared limit")
        usage = _mapping(output.get("combat_advancement_usage"), "combat advancement usage")
        _exact_keys(
            usage,
            {
                "policy_only_decisions",
                "search_decisions",
                "search_fallback_decisions",
                "simulated_transitions",
                "hidden_worlds",
                "public_resample_attempts",
                "public_resample_failures",
            },
            "combat advancement usage",
        )
        if any(_integer(value, f"combat advancement {key}") < 0 for key, value in usage.items()):
            raise ValueError("combat advancement usage must be non-negative")
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


def _curriculum_dataset_summary(
    cases: Sequence[dict[str, Any]],
    state_set: CurriculumStateSet,
) -> dict[str, Any]:
    summary = _dataset_summary(cases)
    completed = [case for case in cases if case.get("status") == "completed"]
    records = [
        _mapping(case.get("record"), "case record")
        for case in completed
        if isinstance(case.get("record"), dict)
    ]
    targets = [_mapping(record.get("target"), "record target") for record in records]
    half_known = [
        target.get("half_split_winner_agreement")
        for target in targets
        if isinstance(target.get("half_split_winner_agreement"), bool)
    ]
    decision_counts = {
        decision_type.value: sum(case.decision_type is decision_type for case in state_set.cases)
        for decision_type in sorted(
            {case.decision_type for case in state_set.cases}, key=lambda item: item.value
        )
    }
    floor_counts: dict[str, int] = {}
    for case in state_set.cases:
        key = "unknown" if case.expected_source_floor is None else str(case.expected_source_floor)
        floor_counts[key] = floor_counts.get(key, 0) + 1
    weights = [
        _number(target.get("policy_target_weight"), "policy target weight") for target in targets
    ]
    summary_document = {
        **summary,
        "unique_states": len({case.expected_state_hash for case in state_set.cases}),
        "source_floor_histogram": floor_counts,
        "decision_type_histogram": decision_counts,
        "reachable_coordinates": len(state_set.cases),
        "unreachable_coordinates": (
            0
            if state_set.signal_spec.requires_terminal_signal
            else len(
                _list(
                    state_set.discovery.get("unreachable_coordinates"),
                    "unreachable coordinates",
                )
            )
        ),
        "effective_labeled_states": sum(weights),
        "hard_target_eligible_states": sum(
            target.get("hard_target_eligible") is True for target in targets
        ),
        "half_split_evaluable_states": len(half_known),
        "half_split_winner_agreement_rate": (
            sum(value is True for value in half_known) / len(half_known) if half_known else None
        ),
        "mean_paired_preference_margin": (
            sum(
                _number(target.get("paired_preference_margin"), "paired preference margin")
                for target in targets
            )
            / len(targets)
            if targets
            else 0.0
        ),
        "terminal_outcome_classes": {
            "victory": summary["terminal_victories"],
            "non_victory": summary["simulations"] - summary["terminal_victories"],
        },
    }
    if state_set.signal_spec.requires_terminal_signal:
        outcomes = [
            _as_mapping(outcome)
            for target in targets
            for candidate in map(_as_mapping, _list(target.get("candidates"), "target candidates"))
            for outcome in _list(candidate.get("outcomes"), "candidate outcomes")
        ]
        terminal_defeats = sum(
            outcome.get("terminal") is True and outcome.get("victory") is False
            for outcome in outcomes
        )
        censored = sum(outcome.get("terminal") is not True for outcome in outcomes)
        terminal_variation = 0
        fully_observed = 0
        for target in targets:
            rates: list[float] = []
            all_candidates_observed = True
            for candidate in map(_as_mapping, _list(target.get("candidates"), "target candidates")):
                candidate_outcomes = [
                    _as_mapping(outcome)
                    for outcome in _list(candidate.get("outcomes"), "candidate outcomes")
                ]
                completed_outcomes = [
                    outcome for outcome in candidate_outcomes if outcome.get("terminal") is True
                ]
                if not completed_outcomes:
                    all_candidates_observed = False
                    break
                rates.append(
                    sum(outcome.get("victory") is True for outcome in completed_outcomes)
                    / len(completed_outcomes)
                )
            if all_candidates_observed and rates:
                fully_observed += 1
                terminal_variation += max(rates) > min(rates)
        summary_document.update(
            {
                "terminal_defeats": terminal_defeats,
                "censored_simulations": censored,
                "states_with_complete_candidate_terminal_observation": fully_observed,
                "states_with_candidate_terminal_variation": terminal_variation,
                "terminal_outcome_classes": {
                    "victory": summary["terminal_victories"],
                    "defeat": terminal_defeats,
                    "censored": censored,
                },
            }
        )
    return summary_document


def _assess_curriculum_signal(
    summary: dict[str, Any],
    spec: CurriculumSignalSpec,
) -> dict[str, Any]:
    source_floor_histogram = _mapping(
        summary.get("source_floor_histogram"), "source floor histogram"
    )
    known_source_floors = sum(key != "unknown" for key in source_floor_histogram)
    decision_types = len(_mapping(summary.get("decision_type_histogram"), "decision histogram"))
    half_rate = summary.get("half_split_winner_agreement_rate")
    checks = {
        "completion": summary.get("completion_rate") == 1.0,
        "states": _integer(summary.get("unique_states"), "unique states") >= spec.minimum_states,
        "source_floors": known_source_floors >= spec.minimum_source_floors,
        "decision_types": decision_types >= spec.minimum_decision_types,
        "effective_labeled_states": _number(
            summary.get("effective_labeled_states"), "effective labeled states"
        )
        >= spec.minimum_effective_labeled_states,
        "half_split_agreement": (
            isinstance(half_rate, (int, float))
            and not isinstance(half_rate, bool)
            and float(half_rate) >= spec.minimum_half_split_agreement
        ),
        "maximum_floor_bins": _integer(
            summary.get("occupied_maximum_floor_bins"), "occupied maximum floor bins"
        )
        >= spec.minimum_occupied_maximum_floor_bins,
    }
    terminal_classes = _mapping(summary.get("terminal_outcome_classes"), "terminal classes")
    if spec.requires_terminal_signal:
        terminal_head_checks = {
            "minimum_terminal_victories": (
                _integer(terminal_classes.get("victory"), "victories")
                >= cast(int, spec.minimum_terminal_victories)
            ),
            "minimum_terminal_defeats": (
                _integer(terminal_classes.get("defeat"), "defeats")
                >= cast(int, spec.minimum_terminal_defeats)
            ),
            "minimum_states_with_candidate_terminal_variation": (
                _integer(
                    summary.get("states_with_candidate_terminal_variation"),
                    "states with candidate terminal variation",
                )
                >= cast(int, spec.minimum_states_with_candidate_terminal_variation)
            ),
        }
        assessment_schema = "bootstrap-curriculum-signal-assessment-v2"
    else:
        terminal_head_checks = {
            "victories_present": _integer(terminal_classes.get("victory"), "victories") > 0,
            "non_victories_present": (
                _integer(terminal_classes.get("non_victory"), "non-victories") > 0
            ),
        }
        assessment_schema = "bootstrap-curriculum-signal-assessment-v1"
    return {
        "schema_version": assessment_schema,
        "spec": spec.as_dict(),
        "auxiliary_policy_signal_pass": all(checks.values()),
        "terminal_head_promotion_pass": all(terminal_head_checks.values()),
        "checks": checks,
        "terminal_head_checks": terminal_head_checks,
    }


def _validate_curriculum_discovery_readiness(state_set: CurriculumStateSet) -> None:
    unique_states = len({case.expected_state_hash for case in state_set.cases})
    known_floors = {
        case.expected_source_floor
        for case in state_set.cases
        if case.expected_source_floor is not None
    }
    decision_types = {case.decision_type for case in state_set.cases}
    failures: list[str] = []
    if unique_states < state_set.signal_spec.minimum_states:
        failures.append(
            f"{unique_states} unique states < {state_set.signal_spec.minimum_states} required"
        )
    if len(known_floors) < state_set.signal_spec.minimum_source_floors:
        failures.append(
            f"{len(known_floors)} source floors < "
            f"{state_set.signal_spec.minimum_source_floors} required"
        )
    if len(decision_types) < state_set.signal_spec.minimum_decision_types:
        failures.append(
            f"{len(decision_types)} decision types < "
            f"{state_set.signal_spec.minimum_decision_types} required"
        )
    if failures:
        raise ValueError("Curriculum discovery signal gate failed: " + "; ".join(failures))


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


def _validate_execution_policy(
    state_set: CurriculumStateSet,
    artifacts: BootstrapPolicyArtifacts | None,
) -> None:
    if state_set.capture_policy is None:
        if artifacts is not None:
            raise ValueError("Baseline curriculum state set cannot use learned policy artifacts")
        return
    if artifacts is None:
        raise ValueError("Learned curriculum state set requires checkpoint artifacts")
    if artifacts.provenance() != state_set.capture_policy:
        raise ValueError("Learned policy artifacts differ from frozen state-set provenance")


def _dataset_configuration(
    config: BootstrapConfig,
    artifacts: BootstrapPolicyArtifacts | None,
) -> dict[str, object]:
    configuration = config.as_dict()
    if artifacts is not None:
        configuration["continuation_policy"] = artifacts.provenance()
        if artifacts.combat_advancement_config is not None:
            configuration["combat_advancement_config"] = (
                artifacts.combat_advancement_config.as_dict()
            )
    return configuration


def _dataset_schema_for(state_set: BootstrapStateSetLike) -> str:
    if not isinstance(state_set, CurriculumStateSet):
        return BOOTSTRAP_DATASET_SCHEMA_VERSION
    if (
        state_set.capture_policy is not None
        and state_set.capture_policy.get("kind") == "combat_advancement_checkpoint"
    ):
        return COMBAT_ADVANCEMENT_DATASET_SCHEMA_VERSION
    if state_set.discovery.get("schema_version") == "bootstrap-curriculum-discovery-v3":
        return TERMINAL_FRONTIER_DATASET_SCHEMA_VERSION
    if state_set.capture_policy is not None:
        return LEARNED_CURRICULUM_DATASET_SCHEMA_VERSION
    return CURRICULUM_DATASET_SCHEMA_VERSION


def _worker_result_schema(task: BootstrapSimulationTask) -> str:
    if (
        task.continuation_policy is not None
        and task.continuation_policy.combat_advancement_config is not None
    ):
        return COMBAT_ADVANCEMENT_WORKER_RESULT_SCHEMA_VERSION
    return (
        LEARNED_BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION
        if task.continuation_policy is not None
        else BOOTSTRAP_WORKER_RESULT_SCHEMA_VERSION
    )


def _prepare_failed_dataset_resume(
    report_path: Path,
    *,
    backend: SearchBackendSpec,
    state_set: BootstrapStateSetLike,
    objective: ObjectiveSpec,
    config: BootstrapConfig,
    policy_artifacts: BootstrapPolicyArtifacts | None,
) -> None:
    report = _load_object(report_path)
    report_body = {key: value for key, value in report.items() if key != "dataset_id"}
    if report.get("dataset_id") != manifest_identifier(report_body):
        raise ValueError("Cannot resume a bootstrap dataset with an invalid identity")
    expected_schema = _dataset_schema_for(state_set)
    if report.get("schema_version") != expected_schema:
        raise ValueError("Cannot resume a bootstrap dataset with a different schema")
    previous_state_set = load_bootstrap_state_set_document(report.get("state_set"))
    if previous_state_set.as_dict() != state_set.as_dict():
        raise ValueError("Cannot resume a bootstrap dataset with a different state set")
    if report.get("backend") != backend.as_dict():
        raise ValueError("Cannot resume a bootstrap dataset with a different backend")
    if report.get("objective") != objective.as_dict():
        raise ValueError("Cannot resume a bootstrap dataset with a different objective")
    if report.get("configuration") != _dataset_configuration(config, policy_artifacts):
        raise ValueError("Cannot resume a bootstrap dataset with different configuration")
    summary = _mapping(report.get("summary"), "dataset summary")
    if _integer(summary.get("failed_cases"), "failed cases") <= 0:
        raise ValueError("Cannot resume a completed bootstrap dataset")
    index = 1
    while (candidate := report_path.with_name(f"failed-dataset-{index:04d}.json")).exists():
        index += 1
    report_path.replace(candidate)


def _validate_bootstrap_split(
    state_set: BootstrapStateSetLike,
    split_manifest: SplitManifest,
) -> None:
    if state_set.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Bootstrap state set references a different split manifest")
    if state_set.ruleset_manifest_id != split_manifest.ruleset_manifest_id:
        raise ValueError("Bootstrap state-set ruleset differs from split manifest")
    if state_set.objective_id != split_manifest.objective_id:
        raise ValueError("Bootstrap state-set objective differs from split manifest")
    expected_partition = SplitName(state_set.partition)
    for case in state_set.cases:
        if split_manifest.split_for_seed(case.run_seed) is not expected_partition:
            raise ValueError(
                f"Bootstrap seed {case.run_seed} is outside the {state_set.partition} partition"
            )


def _load_curriculum_state_set_document(
    document: dict[str, Any],
) -> CurriculumStateSet:
    schema_version = document.get("schema_version")
    learned = schema_version in {
        LEARNED_CURRICULUM_STATE_SET_SCHEMA_VERSION,
        TERMINAL_FRONTIER_STATE_SET_SCHEMA_VERSION,
        COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION,
    }
    frontier = schema_version in {
        TERMINAL_FRONTIER_STATE_SET_SCHEMA_VERSION,
        COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION,
    }
    expected_keys = {
        "schema_version",
        "state_set_id",
        "split_manifest_id",
        "ruleset_manifest_id",
        "objective_id",
        "capture_policy_id",
        "partition",
        "selection_policy",
        "discovery",
        "signal_spec",
        "cases",
    }
    if learned:
        expected_keys.add("capture_policy")
    _exact_keys(
        document,
        expected_keys,
        "curriculum state set",
    )
    state_set_id = _string(document.get("state_set_id"), "state_set_id")
    body = {key: item for key, item in document.items() if key != "state_set_id"}
    if state_set_id != manifest_identifier(body):
        raise ValueError("Curriculum state-set identity mismatch")
    discovery = dict(_mapping(document.get("discovery"), "discovery"))
    captured = _integer(discovery.get("captured_coordinates"), "captured coordinates")
    if frontier:
        expected_discovery_schema = (
            "bootstrap-curriculum-discovery-v4"
            if schema_version == COMBAT_ADVANCEMENT_STATE_SET_SCHEMA_VERSION
            else "bootstrap-curriculum-discovery-v3"
        )
        if discovery.get("schema_version") != expected_discovery_schema:
            raise ValueError(
                "Terminal-frontier state set has the wrong discovery evidence generation"
            )
        eligible = _integer(discovery.get("eligible_coordinates"), "eligible coordinates")
        if captured > eligible:
            raise ValueError("Frontier discovery captured more states than were eligible")
        requested_runs = _integer(discovery.get("requested_runs"), "requested runs")
        terminal_runs = _integer(discovery.get("terminal_runs"), "terminal runs")
        step_limited_runs = _integer(discovery.get("step_limited_runs"), "step-limited runs")
        if requested_runs != terminal_runs + step_limited_runs:
            raise ValueError("Frontier discovery does not account for every requested run")
        victorious_runs = _integer(discovery.get("victorious_runs"), "victorious runs")
        defeated_runs = _integer(discovery.get("defeated_runs"), "defeated runs")
        if terminal_runs != victorious_runs + defeated_runs:
            raise ValueError("Frontier discovery does not account for every terminal run")
    else:
        requested = _integer(discovery.get("requested_coordinates"), "requested coordinates")
        unreachable = _list(discovery.get("unreachable_coordinates"), "unreachable coordinates")
        if requested != captured + len(unreachable):
            raise ValueError("Curriculum discovery does not account for every requested coordinate")
    state_set = CurriculumStateSet(
        state_set_id=state_set_id,
        split_manifest_id=_string(document.get("split_manifest_id"), "split_manifest_id"),
        ruleset_manifest_id=_string(document.get("ruleset_manifest_id"), "ruleset_manifest_id"),
        objective_id=_string(document.get("objective_id"), "objective_id"),
        capture_policy_id=_string(document.get("capture_policy_id"), "capture_policy_id"),
        partition=_string(document.get("partition"), "partition"),
        selection_policy=_string(document.get("selection_policy"), "selection_policy"),
        discovery=discovery,
        signal_spec=_curriculum_signal_spec(document.get("signal_spec")),
        cases=tuple(
            _curriculum_state_case(value)
            for value in _list(document.get("cases"), "curriculum cases")
        ),
        capture_policy=(
            {
                key: _string(item, f"capture_policy.{key}")
                for key, item in _mapping(document.get("capture_policy"), "capture_policy").items()
            }
            if learned
            else None
        ),
    )
    if len(state_set.cases) != captured:
        raise ValueError("Curriculum captured-coordinate count differs from cases")
    if frontier:
        selection = _mapping(discovery.get("frontier_selection"), "frontier selection")
        minimum_floor = _integer(selection.get("minimum_source_floor"), "minimum source floor")
        minimum_actions = _integer(selection.get("minimum_legal_actions"), "minimum legal actions")
        allowed_types = {
            DecisionType(_string(value, "frontier decision type"))
            for value in _list(selection.get("decision_types"), "frontier decision types")
        }
        if not state_set.signal_spec.requires_terminal_signal:
            raise ValueError("Terminal-frontier state set omits terminal signal thresholds")
        if any(
            case.expected_source_floor is None
            or case.expected_source_floor < minimum_floor
            or case.expected_legal_actions < minimum_actions
            or case.decision_type not in allowed_types
            for case in state_set.cases
        ):
            raise ValueError("Terminal-frontier case violates its frozen selection policy")
    return state_set


def _validate_policy_provenance(
    provenance: dict[str, str],
    *,
    policy_id: str,
    split_manifest_id: str,
    ruleset_manifest_id: str,
) -> None:
    combat_advancement = provenance.get("kind") == "combat_advancement_checkpoint"
    expected_keys = {
        "kind",
        "policy_id",
        "model_id",
        "training_report_id",
        "split_manifest_id",
        "ruleset_manifest_id",
    }
    if combat_advancement:
        expected_keys.add("combat_advancement_config_id")
    _exact_keys(
        provenance,
        expected_keys,
        "bootstrap policy provenance",
    )
    expected = {
        "kind": (
            "combat_advancement_checkpoint" if combat_advancement else "production_checkpoint"
        ),
        "policy_id": policy_id,
        "split_manifest_id": split_manifest_id,
        "ruleset_manifest_id": ruleset_manifest_id,
    }
    if any(provenance.get(key) != value for key, value in expected.items()):
        raise ValueError("Bootstrap policy provenance does not match the state set")
    model_id = provenance.get("model_id")
    expected_policy_id = f"production-checkpoint-policy-v1:{model_id}"
    if combat_advancement:
        config_id = _string(
            provenance.get("combat_advancement_config_id"),
            "combat_advancement_config_id",
        )
        expected_policy_id = f"combat-advancement-policy-v1:{model_id}:{config_id}"
    if policy_id != expected_policy_id:
        raise ValueError("Bootstrap policy ID does not match its model ID")
    _string(provenance.get("training_report_id"), "training_report_id")


def _load_bootstrap_policy(
    artifacts: BootstrapPolicyArtifacts | None,
    environment: object,
) -> Policy:
    if artifacts is None:
        return ProgressBootstrapPolicy()
    ruleset = getattr(environment, "ruleset", None)
    if ruleset is None:
        raise ValueError("Bootstrap environment exposes no ruleset identity")
    if artifacts.combat_advancement_config is None:
        return artifacts.load_policy(ruleset)
    return artifacts.load_policy(ruleset, environment=cast(EnvironmentAdapter, environment))


def _curriculum_state_case(value: object) -> CurriculumStateCase:
    document = _mapping(value, "curriculum state case")
    _exact_keys(
        document,
        {
            "state_id",
            "run_seed",
            "decision_type",
            "decision_index",
            "expected_state_hash",
            "expected_legal_actions",
            "expected_source_floor",
            "expected_source_act",
        },
        "curriculum state case",
    )
    state_hash = _string(document.get("expected_state_hash"), "expected_state_hash")
    if len(state_hash) != 64 or any(
        character not in "0123456789abcdef" for character in state_hash
    ):
        raise ValueError("Curriculum expected_state_hash must be a lowercase SHA-256 digest")
    source_floor = document.get("expected_source_floor")
    if source_floor is not None:
        source_floor = _integer(source_floor, "expected_source_floor")
    source_act = document.get("expected_source_act")
    if source_act is not None and (
        isinstance(source_act, bool) or not isinstance(source_act, (int, str))
    ):
        raise ValueError("expected_source_act must be an integer, string, or null")
    case = CurriculumStateCase(
        state_id=_string(document.get("state_id"), "state_id"),
        run_seed=_integer(document.get("run_seed"), "run_seed"),
        decision_type=DecisionType(_string(document.get("decision_type"), "decision_type")),
        decision_index=_integer(document.get("decision_index"), "decision_index"),
        expected_state_hash=state_hash,
        expected_legal_actions=_integer(
            document.get("expected_legal_actions"), "expected_legal_actions"
        ),
        expected_source_floor=source_floor,
        expected_source_act=source_act,
    )
    if (
        case.run_seed < 0
        or case.decision_index < 0
        or case.expected_legal_actions <= 0
        or case.decision_type in {DecisionType.MENU, DecisionType.TERMINAL, DecisionType.UNKNOWN}
    ):
        raise ValueError("Curriculum case fields are outside their allowed range")
    return case


def _curriculum_signal_spec(value: object) -> CurriculumSignalSpec:
    document = _mapping(value, "curriculum signal spec")
    base_keys = {
        "minimum_states",
        "minimum_source_floors",
        "minimum_decision_types",
        "minimum_effective_labeled_states",
        "minimum_half_split_agreement",
        "minimum_occupied_maximum_floor_bins",
    }
    terminal_keys = {
        "minimum_terminal_victories",
        "minimum_terminal_defeats",
        "minimum_states_with_candidate_terminal_variation",
    }
    keys = frozenset(document)
    if keys not in {frozenset(base_keys), frozenset(base_keys | terminal_keys)}:
        raise ValueError(
            "Curriculum signal spec must contain either the legacy thresholds or all "
            "terminal-signal thresholds"
        )
    return CurriculumSignalSpec(
        minimum_states=_integer(document.get("minimum_states"), "minimum_states"),
        minimum_source_floors=_integer(
            document.get("minimum_source_floors"), "minimum_source_floors"
        ),
        minimum_decision_types=_integer(
            document.get("minimum_decision_types"), "minimum_decision_types"
        ),
        minimum_effective_labeled_states=_number(
            document.get("minimum_effective_labeled_states"),
            "minimum_effective_labeled_states",
        ),
        minimum_half_split_agreement=_number(
            document.get("minimum_half_split_agreement"), "minimum_half_split_agreement"
        ),
        minimum_occupied_maximum_floor_bins=_integer(
            document.get("minimum_occupied_maximum_floor_bins"),
            "minimum_occupied_maximum_floor_bins",
        ),
        minimum_terminal_victories=(
            _integer(document.get("minimum_terminal_victories"), "minimum_terminal_victories")
            if "minimum_terminal_victories" in document
            else None
        ),
        minimum_terminal_defeats=(
            _integer(document.get("minimum_terminal_defeats"), "minimum_terminal_defeats")
            if "minimum_terminal_defeats" in document
            else None
        ),
        minimum_states_with_candidate_terminal_variation=(
            _integer(
                document.get("minimum_states_with_candidate_terminal_variation"),
                "minimum_states_with_candidate_terminal_variation",
            )
            if "minimum_states_with_candidate_terminal_variation" in document
            else None
        ),
    )


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


def _probability(value: object, label: str) -> float:
    probability = _number(value, label)
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{label} must be between zero and one")
    return probability


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
