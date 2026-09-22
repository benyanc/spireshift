from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import TerminalVictoryPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.objective import ObjectiveSpec
from spireshift.core.protocols import EnvironmentAdapter, Policy
from spireshift.core.types import LegalAction, Observation
from spireshift.mechanics import PublicMechanicsService
from spireshift.representations import ENCODER_ID
from spireshift.splits import (
    SplitManifest,
    SplitName,
    audit_dataset_index_document,
    freeze_dataset_index,
)

TEACHER_DATASET_SCHEMA_VERSION = "teacher-dataset-v1"
TEACHER_RECORD_SCHEMA_VERSION = "teacher-record-v1"
TEACHER_VERIFICATION_SCHEMA_VERSION = "teacher-dataset-verification-v1"
TEACHER_ID = "monte-carlo-ucb-terminal-victory-v1"
SEED_PROTOCOL_ID = "sha256-domain-parity-v1"


@dataclass(frozen=True, slots=True)
class TeacherConfig:
    search_simulations: int = 256
    evaluation_samples_per_candidate: int = 256
    exploration_constant: float = math.sqrt(2.0)
    sampling_seed: int = 0
    maximum_rollout_steps: int = 4096

    def __post_init__(self) -> None:
        if self.search_simulations <= 0:
            raise ValueError("search_simulations must be positive")
        if self.evaluation_samples_per_candidate <= 0:
            raise ValueError("evaluation_samples_per_candidate must be positive")
        if not math.isfinite(self.exploration_constant) or self.exploration_constant < 0:
            raise ValueError("exploration_constant must be finite and non-negative")
        if self.sampling_seed < 0:
            raise ValueError("sampling_seed must be non-negative")
        if self.maximum_rollout_steps <= 0:
            raise ValueError("maximum_rollout_steps must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "search_simulations": self.search_simulations,
            "evaluation_samples_per_candidate": self.evaluation_samples_per_candidate,
            "exploration_constant": self.exploration_constant,
            "sampling_seed": self.sampling_seed,
            "maximum_rollout_steps": self.maximum_rollout_steps,
        }


@dataclass(frozen=True, slots=True)
class SimulationOutcome:
    sample_index: int
    simulation_seed: int
    terminal_victory: bool
    terminal_reward: float
    decisions: int

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_index": self.sample_index,
            "simulation_seed": self.simulation_seed,
            "terminal_victory": self.terminal_victory,
            "terminal_reward": self.terminal_reward,
            "decisions": self.decisions,
        }


@dataclass(frozen=True, slots=True)
class OutcomeEstimate:
    samples: tuple[SimulationOutcome, ...]
    value: float
    variance: float

    @classmethod
    def from_samples(cls, samples: Sequence[SimulationOutcome]) -> OutcomeEstimate:
        canonical = tuple(samples)
        if not canonical:
            raise ValueError("An outcome estimate requires at least one sample")
        values = [sample.terminal_reward for sample in canonical]
        value = sum(values) / len(values)
        variance = sum((outcome - value) ** 2 for outcome in values) / len(values)
        return cls(canonical, value, variance)

    def as_dict(self) -> dict[str, object]:
        return {
            "sample_count": len(self.samples),
            "terminal_value": self.value,
            "outcome_variance": self.variance,
            "outcomes": [sample.as_dict() for sample in self.samples],
        }


@dataclass(frozen=True, slots=True)
class TeacherCandidate:
    candidate_index: int
    source_action_id: str
    action_kind: str
    search: OutcomeEstimate
    visit_probability: float
    independent_evaluation: OutcomeEstimate

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_index": self.candidate_index,
            "source_action_id": self.source_action_id,
            "action_kind": self.action_kind,
            "search": {
                **self.search.as_dict(),
                "visits": len(self.search.samples),
                "visit_probability": self.visit_probability,
            },
            "independent_evaluation": self.independent_evaluation.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class TeacherTarget:
    candidates: tuple[TeacherCandidate, ...]
    selected_candidate_index: int
    search_seed_domain: str
    evaluation_seed_domain: str

    @property
    def selected_action_id(self) -> str:
        return self.candidates[self.selected_candidate_index].source_action_id

    def as_dict(self) -> dict[str, object]:
        return {
            "teacher_id": TEACHER_ID,
            "seed_protocol_id": SEED_PROTOCOL_ID,
            "search_seed_domain": self.search_seed_domain,
            "evaluation_seed_domain": self.evaluation_seed_domain,
            "search_simulations": sum(
                len(candidate.search.samples) for candidate in self.candidates
            ),
            "evaluation_samples_per_candidate": len(
                self.candidates[0].independent_evaluation.samples
            ),
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "selected_candidate_index": self.selected_candidate_index,
            "selected_action_id": self.selected_action_id,
        }


@dataclass(frozen=True, slots=True)
class TeacherDatasetVerification:
    valid: bool
    dataset_id: str
    runs: int
    records: int
    search_simulations: int
    evaluation_simulations: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": TEACHER_VERIFICATION_SCHEMA_VERSION,
            "valid": self.valid,
            "dataset_id": self.dataset_id,
            "runs": self.runs,
            "records": self.records,
            "search_simulations": self.search_simulations,
            "evaluation_simulations": self.evaluation_simulations,
            "errors": list(self.errors),
        }


def build_teacher_target(
    *,
    environment: EnvironmentAdapter,
    observation: Observation,
    legal_actions: Sequence[LegalAction],
    continuation_policy: Policy,
    config: TeacherConfig,
    run_seed: int,
    decision_index: int,
) -> TeacherTarget:
    actions = tuple(legal_actions)
    if not actions:
        raise ValueError("Teacher target requires at least one legal action")
    if config.search_simulations < len(actions):
        raise ValueError("search_simulations must visit every legal candidate at least once")
    if environment.patch_id != observation.patch_id:
        raise ValueError("Teacher environment and observation patches differ")
    current_actions = tuple(environment.legal_actions())
    if current_actions != actions:
        raise ValueError("Teacher legal actions are stale or out of order")

    namespace = _seed_namespace(
        config.sampling_seed,
        run_seed,
        decision_index,
        observation.state_hash,
    )
    search_domain = f"{namespace}:search-even"
    evaluation_domain = f"{namespace}:evaluation-odd"
    search_samples: list[list[SimulationOutcome]] = [[] for _ in actions]
    search_ordinal = 0

    for candidate_index, action in enumerate(actions):
        search_samples[candidate_index].append(
            _simulate_candidate(
                environment,
                action,
                sample_index=search_ordinal,
                simulation_seed=_sample_seed(namespace, search_ordinal, evaluation=False),
                continuation_policy=continuation_policy,
                maximum_rollout_steps=config.maximum_rollout_steps,
            )
        )
        search_ordinal += 1

    while search_ordinal < config.search_simulations:
        candidate_index = _ucb_candidate(search_samples, config.exploration_constant)
        search_samples[candidate_index].append(
            _simulate_candidate(
                environment,
                actions[candidate_index],
                sample_index=search_ordinal,
                simulation_seed=_sample_seed(namespace, search_ordinal, evaluation=False),
                continuation_policy=continuation_policy,
                maximum_rollout_steps=config.maximum_rollout_steps,
            )
        )
        search_ordinal += 1

    evaluation_samples: list[list[SimulationOutcome]] = [[] for _ in actions]
    for candidate_index, action in enumerate(actions):
        for sample_index in range(config.evaluation_samples_per_candidate):
            ordinal = candidate_index * config.evaluation_samples_per_candidate + sample_index
            evaluation_samples[candidate_index].append(
                _simulate_candidate(
                    environment,
                    action,
                    sample_index=sample_index,
                    simulation_seed=_sample_seed(namespace, ordinal, evaluation=True),
                    continuation_policy=continuation_policy,
                    maximum_rollout_steps=config.maximum_rollout_steps,
                )
            )

    candidates = tuple(
        TeacherCandidate(
            candidate_index=index,
            source_action_id=action.action_id,
            action_kind=action.kind,
            search=(search := OutcomeEstimate.from_samples(search_samples[index])),
            visit_probability=len(search.samples) / config.search_simulations,
            independent_evaluation=OutcomeEstimate.from_samples(evaluation_samples[index]),
        )
        for index, action in enumerate(actions)
    )
    selected = max(
        range(len(candidates)),
        key=lambda index: (
            len(candidates[index].search.samples),
            candidates[index].search.value,
            -index,
        ),
    )
    return TeacherTarget(candidates, selected, search_domain, evaluation_domain)


def generate_mock_teacher_dataset(
    *,
    seeds: Sequence[int],
    partition: SplitName,
    split_manifest: SplitManifest,
    objective: ObjectiveSpec,
    config: TeacherConfig,
    environment_factory: Callable[[], MockSpireEnvironment] = MockSpireEnvironment,
) -> dict[str, Any]:
    canonical_seeds = tuple(seeds)
    if not canonical_seeds:
        raise ValueError("At least one teacher trajectory seed is required")
    if len(canonical_seeds) != len(set(canonical_seeds)):
        raise ValueError("Teacher trajectory seeds must be unique")
    if split_manifest.ruleset_manifest_id != MockSpireEnvironment.ruleset.manifest_id:
        raise ValueError("Split manifest and mock teacher rulesets differ")
    if split_manifest.objective_id != objective.objective_id:
        raise ValueError("Split manifest and teacher objective differ")
    for seed in canonical_seeds:
        if split_manifest.split_for_seed(seed) is not partition:
            raise ValueError(f"Seed {seed} is not in the frozen {partition.value} partition")

    runs: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    total_candidates = 0
    victories = 0
    mechanics = PublicMechanicsService()
    for run_seed in canonical_seeds:
        environment = environment_factory()
        observation = environment.reset(run_seed)
        run_id = f"mock-{partition.value}-seed-{run_seed}"
        drafts: list[dict[str, Any]] = []
        decision_index = 0
        victory = False
        while not bool(observation.public_state["terminal"]):
            mechanics_snapshot = mechanics.snapshot(environment, observation)
            legal_actions = mechanics_snapshot.legal_actions
            model_input = mechanics_snapshot.model_input
            target = build_teacher_target(
                environment=environment,
                observation=observation,
                legal_actions=legal_actions,
                continuation_policy=TerminalVictoryPolicy(),
                config=config,
                run_seed=run_seed,
                decision_index=decision_index,
            )
            selected_action = legal_actions[target.selected_candidate_index]
            transition = environment.step(selected_action)
            encounter_id = f"{run_id}-{decision_index}-{observation.decision_type.value}"
            drafts.append(
                {
                    "schema_version": TEACHER_RECORD_SCHEMA_VERSION,
                    "run_id": run_id,
                    "encounter_id": encounter_id,
                    "decision_index": decision_index,
                    "model_input": model_input.as_dict(),
                    "teacher_target": target.as_dict(),
                    "observed_transition": {
                        "selected_action_id": selected_action.action_id,
                        "next_state_hash": transition.next_observation.state_hash,
                        "terminal": transition.terminal,
                        "victory": transition.victory,
                        "reward": transition.reward,
                    },
                }
            )
            total_candidates += len(legal_actions)
            observation = transition.next_observation
            victory = transition.victory
            decision_index += 1
            if decision_index > config.maximum_rollout_steps:
                raise RuntimeError("Teacher trajectory exceeded maximum_rollout_steps")

        victories += int(victory)
        record_ids: list[str] = []
        encounter_ids: list[str] = []
        for draft in drafts:
            record_body = {**draft, "run_terminal_victory": victory}
            record = {**record_body, "record_id": manifest_identifier(record_body)}
            records.append(record)
            record_ids.append(cast(str, record["record_id"]))
            encounter_ids.append(cast(str, record["encounter_id"]))
        runs.append(
            {
                "run_id": run_id,
                "seed": run_seed,
                "split": partition.value,
                "terminal": True,
                "victory": victory,
                "record_ids": record_ids,
                "encounter_ids": encounter_ids,
            }
        )

    body: dict[str, Any] = {
        "schema_version": TEACHER_DATASET_SCHEMA_VERSION,
        "backend": "mock",
        "ruleset": MockSpireEnvironment.ruleset.as_dict(),
        "objective": objective.as_dict(),
        "split_manifest_id": split_manifest.manifest_id,
        "partition": partition.value,
        "representation_encoder_id": ENCODER_ID,
        "teacher_id": TEACHER_ID,
        "seed_protocol_id": SEED_PROTOCOL_ID,
        "configuration": config.as_dict(),
        "runs": runs,
        "records": records,
        "summary": {
            "runs": len(runs),
            "records": len(records),
            "candidates": total_candidates,
            "victories": victories,
            "defeats": len(runs) - victories,
            "search_simulations": len(records) * config.search_simulations,
            "evaluation_simulations": total_candidates * config.evaluation_samples_per_candidate,
        },
    }
    document = {**body, "dataset_id": manifest_identifier(body)}
    verification = verify_teacher_dataset(document, split_manifest)
    if not verification.valid:
        raise RuntimeError(
            "Generated teacher dataset failed verification: " + "; ".join(verification.errors)
        )
    return document


def teacher_dataset_index(
    document: object,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    dataset = _mapping(document, "teacher dataset")
    runs = _list(dataset.get("runs"), "teacher dataset runs")
    records = _list(dataset.get("records"), "teacher dataset records")
    specification = {
        "schema_version": "dataset-index-v1",
        "dataset_id": _string(dataset.get("dataset_id"), "dataset_id"),
        "split_manifest_id": _string(dataset.get("split_manifest_id"), "split_manifest_id"),
        "ruleset_manifest_id": _mapping(dataset.get("ruleset"), "ruleset").get("manifest_id"),
        "runs": [
            {
                "run_id": run["run_id"],
                "seed": run["seed"],
                "split": run["split"],
                "terminal": run["terminal"],
                "record_ids": run["record_ids"],
                "encounter_ids": run["encounter_ids"],
            }
            for raw_run in runs
            for run in [_mapping(raw_run, "teacher run")]
        ],
        "records": [
            {
                "record_id": record["record_id"],
                "run_id": record["run_id"],
                "encounter_id": record["encounter_id"],
                "decision_index": record["decision_index"],
            }
            for raw_record in records
            for record in [_mapping(raw_record, "teacher record")]
        ],
    }
    return freeze_dataset_index(specification, split_manifest)


def verify_teacher_dataset(
    document: object,
    split_manifest: SplitManifest,
) -> TeacherDatasetVerification:
    errors: list[str] = []
    dataset_id = ""
    search_simulations = 0
    evaluation_simulations = 0
    candidate_count = 0
    try:
        dataset = _mapping(document, "teacher dataset")
        dataset_id = _string(dataset.get("dataset_id"), "dataset_id")
        body = {key: value for key, value in dataset.items() if key != "dataset_id"}
        if dataset_id != manifest_identifier(body):
            errors.append("dataset identity mismatch")
        if dataset.get("schema_version") != TEACHER_DATASET_SCHEMA_VERSION:
            errors.append("unsupported teacher dataset schema")
        if dataset.get("teacher_id") != TEACHER_ID:
            errors.append("unsupported teacher ID")
        if dataset.get("seed_protocol_id") != SEED_PROTOCOL_ID:
            errors.append("unsupported sample-seed protocol")
        if dataset.get("backend") != "mock":
            errors.append("unsupported teacher backend")
        if dataset.get("representation_encoder_id") != ENCODER_ID:
            errors.append("unsupported representation encoder")
        if dataset.get("split_manifest_id") != split_manifest.manifest_id:
            errors.append("teacher dataset references a different split manifest")
        ruleset = _mapping(dataset.get("ruleset"), "ruleset")
        if ruleset.get("manifest_id") != split_manifest.ruleset_manifest_id:
            errors.append("teacher dataset ruleset differs from the split manifest")
        if ruleset != MockSpireEnvironment.ruleset.as_dict():
            errors.append("teacher dataset does not match the mock ruleset")
        objective = _mapping(dataset.get("objective"), "objective")
        if objective.get("id") != split_manifest.objective_id:
            errors.append("teacher dataset objective differs from the split manifest")
        partition = SplitName(_string(dataset.get("partition"), "partition"))
        configuration = _mapping(dataset.get("configuration"), "configuration")
        configured_search = _integer(
            configuration.get("search_simulations"), "configuration.search_simulations"
        )
        configured_evaluation = _integer(
            configuration.get("evaluation_samples_per_candidate"),
            "configuration.evaluation_samples_per_candidate",
        )
        teacher_config = TeacherConfig(
            search_simulations=configured_search,
            evaluation_samples_per_candidate=configured_evaluation,
            exploration_constant=_number(
                configuration.get("exploration_constant"),
                "configuration.exploration_constant",
            ),
            sampling_seed=_integer(
                configuration.get("sampling_seed"), "configuration.sampling_seed"
            ),
            maximum_rollout_steps=_integer(
                configuration.get("maximum_rollout_steps"),
                "configuration.maximum_rollout_steps",
            ),
        )
        runs = _list(dataset.get("runs"), "runs")
        records = _list(dataset.get("records"), "records")
    except (KeyError, TypeError, ValueError) as error:
        return TeacherDatasetVerification(False, dataset_id, 0, 0, 0, 0, (str(error),))

    run_by_id: dict[str, dict[str, Any]] = {}
    for offset, raw_run in enumerate(runs):
        try:
            run = _mapping(raw_run, f"runs[{offset}]")
            run_id = _string(run.get("run_id"), f"runs[{offset}].run_id")
            seed = _integer(run.get("seed"), f"runs[{offset}].seed")
            if run_id in run_by_id:
                errors.append(f"duplicate run ID: {run_id}")
            run_by_id[run_id] = run
            if split_manifest.split_for_seed(seed) is not partition:
                errors.append(f"run {run_id} seed is outside the declared partition")
            if run.get("split") != partition.value or run.get("terminal") is not True:
                errors.append(f"run {run_id} has invalid split or terminal status")
        except (TypeError, ValueError) as error:
            errors.append(str(error))

    record_by_run: dict[str, list[dict[str, Any]]] = {run_id: [] for run_id in run_by_id}
    for offset, raw_record in enumerate(records):
        label = f"records[{offset}]"
        try:
            record = _mapping(raw_record, label)
            record_id = _string(record.get("record_id"), f"{label}.record_id")
            _integer(record.get("decision_index"), f"{label}.decision_index")
            record_body = {key: value for key, value in record.items() if key != "record_id"}
            if record_id != manifest_identifier(record_body):
                errors.append(f"{record_id}: record identity mismatch")
            run_id = _string(record.get("run_id"), f"{label}.run_id")
            if run_id not in record_by_run:
                errors.append(f"{record_id}: unknown run {run_id}")
                continue
            record_by_run[run_id].append(record)
            target = _mapping(record.get("teacher_target"), f"{record_id}.teacher_target")
            candidates = _list(target.get("candidates"), f"{record_id}.candidates")
            model_input = _mapping(record.get("model_input"), f"{record_id}.model_input")
            model_body = {
                key: value for key, value in model_input.items() if key != "representation_hash"
            }
            if model_input.get("representation_hash") != manifest_identifier(model_body):
                errors.append(f"{record_id}: model representation identity mismatch")
            model_candidates = _list(model_input.get("candidates"), f"{record_id}.model candidates")
            if len(candidates) != len(model_candidates) or not candidates:
                errors.append(f"{record_id}: candidate count mismatch")
                continue
            candidate_count += len(candidates)
            search_seeds: set[int] = set()
            evaluation_seeds: set[int] = set()
            candidate_keys: list[tuple[int, float, int]] = []
            total_visits = _integer(target.get("search_simulations"), "search_simulations")
            if total_visits != configured_search:
                errors.append(f"{record_id}: search budget differs from dataset configuration")
            expected_evaluation_count = _integer(
                target.get("evaluation_samples_per_candidate"),
                "evaluation_samples_per_candidate",
            )
            if expected_evaluation_count != configured_evaluation:
                errors.append(f"{record_id}: evaluation budget differs from dataset configuration")
            search_simulations += total_visits
            observed_visits = 0
            for candidate_index, raw_candidate in enumerate(candidates):
                candidate = _mapping(raw_candidate, f"{record_id}.candidate[{candidate_index}]")
                model_candidate = _mapping(
                    model_candidates[candidate_index],
                    f"{record_id}.model_candidate[{candidate_index}]",
                )
                if candidate.get("candidate_index") != candidate_index:
                    errors.append(f"{record_id}: candidate indexes are not contiguous")
                if candidate.get("source_action_id") != model_candidate.get("source_action_id"):
                    errors.append(f"{record_id}: candidate action alignment mismatch")
                if candidate.get("action_kind") != model_candidate.get("action_kind"):
                    errors.append(f"{record_id}: candidate kind alignment mismatch")
                search = _mapping(candidate.get("search"), "search estimate")
                evaluation = _mapping(
                    candidate.get("independent_evaluation"), "independent evaluation"
                )
                search_outcomes = _verify_estimate(search, "search", errors)
                evaluation_outcomes = _verify_estimate(evaluation, "independent evaluation", errors)
                search_seeds.update(sample["simulation_seed"] for sample in search_outcomes)
                evaluation_seeds.update(sample["simulation_seed"] for sample in evaluation_outcomes)
                evaluation_simulations += len(evaluation_outcomes)
                visits = _integer(search.get("visits"), "search.visits")
                observed_visits += visits
                if visits != len(search_outcomes):
                    errors.append(f"{record_id}: search visits and outcomes differ")
                if len(evaluation_outcomes) != expected_evaluation_count:
                    errors.append(f"{record_id}: independent evaluation count mismatch")
                expected_probability = visits / total_visits
                if search.get("visit_probability") != expected_probability:
                    errors.append(f"{record_id}: visit probability mismatch")
                candidate_keys.append(
                    (visits, cast(float, search.get("terminal_value")), -candidate_index)
                )
            if observed_visits != total_visits or len(search_seeds) != total_visits:
                errors.append(f"{record_id}: search samples are not unique and complete")
            if len(evaluation_seeds) != expected_evaluation_count * len(candidates):
                errors.append(f"{record_id}: evaluation samples are not unique and complete")
            if search_seeds & evaluation_seeds:
                errors.append(f"{record_id}: search and evaluation samples overlap")
            if any(seed % 2 for seed in search_seeds) or any(
                seed % 2 == 0 for seed in evaluation_seeds
            ):
                errors.append(f"{record_id}: sample seed domains violate parity isolation")
            selected = _integer(target.get("selected_candidate_index"), "selected index")
            expected_selected = max(range(len(candidate_keys)), key=candidate_keys.__getitem__)
            if selected != expected_selected:
                errors.append(f"{record_id}: teacher selection does not match search visits")
            if target.get("selected_action_id") != candidates[selected].get("source_action_id"):
                errors.append(f"{record_id}: selected action is not candidate aligned")
            transition = _mapping(record.get("observed_transition"), "observed transition")
            if transition.get("selected_action_id") != target.get("selected_action_id"):
                errors.append(f"{record_id}: observed action differs from teacher selection")
            run = run_by_id[run_id]
            if record.get("run_terminal_victory") != run.get("victory"):
                errors.append(f"{record_id}: run outcome label mismatch")
        except (IndexError, KeyError, TypeError, ValueError) as error:
            errors.append(f"{label}: {error}")

    for run_id, run in run_by_id.items():
        run_records = sorted(
            record_by_run[run_id], key=lambda record: cast(int, record.get("decision_index"))
        )
        indices = [record.get("decision_index") for record in run_records]
        if indices != list(range(len(run_records))):
            errors.append(f"run {run_id}: decision indexes are not contiguous")
        expected_record_ids = [record.get("record_id") for record in run_records]
        expected_encounter_ids = [record.get("encounter_id") for record in run_records]
        if run.get("record_ids") != expected_record_ids:
            errors.append(f"run {run_id}: record ID list mismatch")
        if run.get("encounter_ids") != expected_encounter_ids:
            errors.append(f"run {run_id}: encounter ID list mismatch")
        final_transition = run_records[-1].get("observed_transition") if run_records else None
        if not isinstance(final_transition, dict) or final_transition.get("terminal") is not True:
            errors.append(f"run {run_id}: final record is not terminal")
        try:
            run_seed = _integer(run.get("seed"), f"run {run_id}.seed")
            replay_environment = MockSpireEnvironment()
            replay_observation = replay_environment.reset(run_seed)
            replay_victory = False
            for decision_index, record in enumerate(run_records):
                model_input = _mapping(record.get("model_input"), "model input")
                if model_input.get("source_state_hash") != replay_observation.state_hash:
                    errors.append(f"run {run_id}: source state hash failed trajectory replay")
                legal_actions = tuple(replay_environment.legal_actions())
                expected_target = build_teacher_target(
                    environment=replay_environment,
                    observation=replay_observation,
                    legal_actions=legal_actions,
                    continuation_policy=TerminalVictoryPolicy(),
                    config=teacher_config,
                    run_seed=run_seed,
                    decision_index=decision_index,
                )
                if record.get("teacher_target") != expected_target.as_dict():
                    errors.append(f"run {run_id}: teacher target failed exact regeneration")
                selected_by_id = {action.action_id: action for action in legal_actions}
                selected_action = selected_by_id.get(expected_target.selected_action_id)
                if selected_action is None:
                    errors.append(f"run {run_id}: regenerated teacher action is not legal")
                    break
                replay_transition = replay_environment.step(selected_action)
                observed = _mapping(record.get("observed_transition"), "observed transition")
                expected_transition = {
                    "selected_action_id": selected_action.action_id,
                    "next_state_hash": replay_transition.next_observation.state_hash,
                    "terminal": replay_transition.terminal,
                    "victory": replay_transition.victory,
                    "reward": replay_transition.reward,
                }
                if observed != expected_transition:
                    errors.append(f"run {run_id}: observed transition failed trajectory replay")
                replay_observation = replay_transition.next_observation
                replay_victory = replay_transition.victory
            if not bool(replay_observation.public_state["terminal"]):
                errors.append(f"run {run_id}: replay did not reach a terminal state")
            if run.get("victory") is not replay_victory:
                errors.append(f"run {run_id}: terminal victory failed trajectory replay")
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            errors.append(f"run {run_id}: replay failed: {error}")

    try:
        index = teacher_dataset_index(dataset, split_manifest)
        index_audit = audit_dataset_index_document(index, split_manifest)
        errors.extend(f"dataset index: {error}" for error in index_audit.errors)
    except (KeyError, TypeError, ValueError) as error:
        errors.append(f"dataset index: {error}")

    summary = dataset.get("summary")
    if isinstance(summary, dict):
        expected_summary = {
            "runs": len(runs),
            "records": len(records),
            "candidates": candidate_count,
            "victories": sum(run.get("victory") is True for run in run_by_id.values()),
            "defeats": sum(run.get("victory") is not True for run in run_by_id.values()),
            "search_simulations": search_simulations,
            "evaluation_simulations": evaluation_simulations,
        }
        if summary != expected_summary:
            errors.append("dataset summary mismatch")
    else:
        errors.append("dataset summary must be an object")
    return TeacherDatasetVerification(
        not errors,
        dataset_id,
        len(runs),
        len(records),
        search_simulations,
        evaluation_simulations,
        tuple(errors),
    )


def load_teacher_dataset(path: Path) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load teacher dataset {path}: {error}") from error
    return _mapping(value, "teacher dataset")


def write_teacher_dataset(document: dict[str, Any], path: Path) -> None:
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace immutable teacher dataset: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8", newline="\n")


def _simulate_candidate(
    environment: EnvironmentAdapter,
    action: LegalAction,
    *,
    sample_index: int,
    simulation_seed: int,
    continuation_policy: Policy,
    maximum_rollout_steps: int,
) -> SimulationOutcome:
    simulation = environment.clone(resample_hidden=True, seed=simulation_seed)
    candidates = {candidate.action_id: candidate for candidate in simulation.legal_actions()}
    simulation_action = candidates.get(action.action_id)
    if simulation_action is None or simulation_action != action:
        raise RuntimeError("Cloned teacher state changed the legal candidate set")
    transition = simulation.step(simulation_action)
    decisions = 1
    while not transition.terminal:
        if decisions >= maximum_rollout_steps:
            raise RuntimeError("Teacher simulation exceeded maximum_rollout_steps")
        legal_actions = simulation.legal_actions()
        next_action = continuation_policy.choose_action(transition.next_observation, legal_actions)
        transition = simulation.step(next_action)
        decisions += 1
    return SimulationOutcome(
        sample_index=sample_index,
        simulation_seed=simulation_seed,
        terminal_victory=transition.victory,
        terminal_reward=transition.reward,
        decisions=decisions,
    )


def _ucb_candidate(samples: Sequence[Sequence[SimulationOutcome]], exploration: float) -> int:
    total = sum(len(candidate) for candidate in samples)
    return max(
        range(len(samples)),
        key=lambda index: (
            _mean_reward(samples[index])
            + exploration * math.sqrt(math.log(total) / len(samples[index])),
            -index,
        ),
    )


def _mean_reward(samples: Sequence[SimulationOutcome]) -> float:
    return sum(sample.terminal_reward for sample in samples) / len(samples)


def _seed_namespace(
    sampling_seed: int,
    run_seed: int,
    decision_index: int,
    state_hash: str,
) -> str:
    encoded = f"{sampling_seed}|{run_seed}|{decision_index}|{state_hash}".encode()
    return hashlib.sha256(encoded).hexdigest()


def _sample_seed(namespace: str, ordinal: int, *, evaluation: bool) -> int:
    if ordinal < 0 or ordinal >= 1_000_000:
        raise ValueError("Teacher sampling supports fewer than one million samples per domain")
    digest = hashlib.sha256(f"{namespace}|{ordinal}".encode()).digest()
    base = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return base * 2 + int(evaluation)


def _verify_estimate(
    estimate: dict[str, Any],
    label: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    outcomes = [
        _mapping(value, f"{label}.outcomes[{index}]")
        for index, value in enumerate(_list(estimate.get("outcomes"), f"{label}.outcomes"))
    ]
    if not outcomes:
        errors.append(f"{label}: outcomes must not be empty")
    if estimate.get("sample_count") != len(outcomes):
        errors.append(f"{label}: sample count mismatch")
    sample_indexes: set[int] = set()
    simulation_seeds: set[int] = set()
    for offset, sample in enumerate(outcomes):
        try:
            sample_index = _integer(sample.get("sample_index"), f"{label}.sample_index")
            simulation_seed = _integer(sample.get("simulation_seed"), f"{label}.simulation_seed")
            decisions = _integer(sample.get("decisions"), f"{label}.decisions")
            if sample_index < 0 or simulation_seed < 0 or decisions <= 0:
                raise ValueError(f"{label}.outcomes[{offset}] has a negative field")
            if sample_index in sample_indexes or simulation_seed in simulation_seeds:
                errors.append(f"{label}: duplicate sample index or simulation seed")
            sample_indexes.add(sample_index)
            simulation_seeds.add(simulation_seed)
        except ValueError as error:
            errors.append(str(error))
    rewards = [sample.get("terminal_reward") for sample in outcomes]
    if any(reward not in {0.0, 1.0} for reward in rewards):
        errors.append(f"{label}: non-binary terminal reward")
        return outcomes
    numeric_rewards = cast(list[float], rewards)
    value = sum(numeric_rewards) / len(numeric_rewards) if numeric_rewards else 0.0
    variance = (
        sum((reward - value) ** 2 for reward in numeric_rewards) / len(numeric_rewards)
        if numeric_rewards
        else 0.0
    )
    if estimate.get("terminal_value") != value:
        errors.append(f"{label}: terminal value mismatch")
    if estimate.get("outcome_variance") != variance:
        errors.append(f"{label}: outcome variance mismatch")
    for sample in outcomes:
        if not isinstance(sample.get("terminal_victory"), bool):
            errors.append(f"{label}: terminal_victory must be boolean")
            continue
        if sample.get("terminal_victory") is not bool(sample.get("terminal_reward")):
            errors.append(f"{label}: victory and reward mismatch")
    return outcomes


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


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


def _number(value: object, label: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result
