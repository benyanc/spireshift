from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from spireshift.core.manifest import RulesetIdentity
from spireshift.core.protocols import EnvironmentAdapter, Policy
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.models import model_from_checkpoint
from spireshift.representations import CompositionalModelInput, ScalarFeature, build_model_input

TERMINAL_VICTORY_OBJECTIVE_ID = "terminal-victory-v1"
TACTICAL_VALUE_METHOD = "terminal-victory-leaf-mixture-v1"
COMPUTE_UNIT_DEFINITION = "one simulated transition or one run-value inference"


class RunValuePrediction(Protocol):
    @property
    def run_value(self) -> float: ...


class RunValueModel(Protocol):
    def predict(self, representation: CompositionalModelInput) -> RunValuePrediction: ...


class RunValueEstimator(Protocol):
    @property
    def estimator_id(self) -> str: ...

    @property
    def objective_id(self) -> str: ...

    def estimate(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> RunValueEstimate: ...


@dataclass(frozen=True, slots=True)
class RunValueEstimate:
    terminal_victory_probability: float
    estimator_id: str
    representation_hash: str
    source_state_hash: str
    represented_state_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _probability(self.terminal_victory_probability, "terminal victory probability")
        if not self.estimator_id:
            raise ValueError("estimator_id must be non-empty")
        if not self.representation_hash:
            raise ValueError("representation_hash must be non-empty")
        if not self.source_state_hash:
            raise ValueError("source_state_hash must be non-empty")
        if not self.represented_state_paths:
            raise ValueError("represented_state_paths must be non-empty")


@dataclass(frozen=True, slots=True)
class ModelRunValueEstimator:
    ruleset: RulesetIdentity
    model: RunValueModel
    estimator_id: str
    objective_id: str = TERMINAL_VICTORY_OBJECTIVE_ID

    def estimate(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> RunValueEstimate:
        if observation.decision_type is DecisionType.TERMINAL:
            raise ValueError("Terminal observations must use their exact terminal return")
        if not legal_actions:
            raise ValueError("A nonterminal run-value estimate requires legal actions")
        representation = build_model_input(self.ruleset, observation, legal_actions)
        probability = float(self.model.predict(representation).run_value)
        _probability(probability, "model run value")
        return RunValueEstimate(
            terminal_victory_probability=probability,
            estimator_id=self.estimator_id,
            representation_hash=representation.representation_hash,
            source_state_hash=representation.source_state_hash,
            represented_state_paths=_represented_state_paths(representation),
        )


def model_run_value_estimator_from_checkpoint(
    *,
    checkpoint: object,
    ruleset: RulesetIdentity,
    calibration: object | None = None,
) -> ModelRunValueEstimator:
    if not isinstance(checkpoint, dict):
        raise ValueError("Model checkpoint must be an object")
    if checkpoint.get("ruleset_manifest_id") != ruleset.manifest_id:
        raise ValueError("Run-value checkpoint and tactical ruleset differ")
    if checkpoint.get("objective_id") != TERMINAL_VICTORY_OBJECTIVE_ID:
        raise ValueError("Tactical leaves require a terminal-victory checkpoint")
    model: RunValueModel = model_from_checkpoint(checkpoint)
    raw_model_id = checkpoint.get("model_id")
    if not isinstance(raw_model_id, str) or not raw_model_id:
        raise ValueError("Run-value checkpoint model_id must be non-empty")
    estimator_id = raw_model_id
    if calibration is not None:
        from spireshift.calibration import (
            calibrated_model_from_artifacts,
            validate_calibration_artifact,
        )

        calibration_document = validate_calibration_artifact(calibration, checkpoint=checkpoint)
        model = calibrated_model_from_artifacts(checkpoint, calibration_document)
        raw_calibration_id = calibration_document.get("calibration_id")
        if not isinstance(raw_calibration_id, str) or not raw_calibration_id:
            raise ValueError("Run-value calibration_id must be non-empty")
        estimator_id = raw_calibration_id
    return ModelRunValueEstimator(
        ruleset=ruleset,
        model=model,
        estimator_id=estimator_id,
    )


@dataclass(frozen=True, slots=True)
class TacticalValueConfig:
    candidate_worlds: int = 2
    rollout_samples: int = 8
    rollout_horizon: int = 1
    exact_terminal_weight: float = 1.0
    truncated_rollout_weight: float = 0.5
    bootstrap_weight: float = 0.5
    maximum_compute_units: int = 128

    def __post_init__(self) -> None:
        if self.candidate_worlds <= 0:
            raise ValueError("candidate_worlds must be positive")
        if self.rollout_samples < 0:
            raise ValueError("rollout_samples must be non-negative")
        if self.rollout_horizon <= 0:
            raise ValueError("rollout_horizon must be positive")
        for name, value in (
            ("exact_terminal_weight", self.exact_terminal_weight),
            ("truncated_rollout_weight", self.truncated_rollout_weight),
            ("bootstrap_weight", self.bootstrap_weight),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.exact_terminal_weight <= 0.0:
            raise ValueError("exact_terminal_weight must be positive")
        if self.rollout_samples == 0 and self.bootstrap_weight == 0.0:
            raise ValueError("A nonterminal leaf requires rollout samples or bootstrap weight")
        if self.truncated_rollout_weight > 0.0 and self.rollout_samples <= 0:
            raise ValueError("Positive rollout weight requires rollout samples")
        if self.maximum_compute_units <= 0:
            raise ValueError("maximum_compute_units must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "candidate_worlds": self.candidate_worlds,
            "rollout_samples": self.rollout_samples,
            "rollout_horizon": self.rollout_horizon,
            "exact_terminal_weight": self.exact_terminal_weight,
            "truncated_rollout_weight": self.truncated_rollout_weight,
            "bootstrap_weight": self.bootstrap_weight,
            "maximum_compute_units": self.maximum_compute_units,
        }

    @classmethod
    def from_mapping(cls, value: object) -> TacticalValueConfig:
        if not isinstance(value, dict):
            raise ValueError("tactical value config must be an object")
        expected = set(cls().as_dict())
        actual = set(value)
        if actual != expected:
            raise ValueError(
                "tactical value config fields differ: "
                f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
            )
        return cls(
            candidate_worlds=_integer(value.get("candidate_worlds"), "candidate_worlds"),
            rollout_samples=_integer(value.get("rollout_samples"), "rollout_samples"),
            rollout_horizon=_integer(value.get("rollout_horizon"), "rollout_horizon"),
            exact_terminal_weight=_number(
                value.get("exact_terminal_weight"), "exact_terminal_weight"
            ),
            truncated_rollout_weight=_number(
                value.get("truncated_rollout_weight"), "truncated_rollout_weight"
            ),
            bootstrap_weight=_number(value.get("bootstrap_weight"), "bootstrap_weight"),
            maximum_compute_units=_integer(
                value.get("maximum_compute_units"), "maximum_compute_units"
            ),
        )


@dataclass(frozen=True, slots=True)
class ComputeUsage:
    simulated_transitions: int
    run_value_inferences: int
    sampled_worlds: int

    @property
    def compute_units(self) -> int:
        return self.simulated_transitions + self.run_value_inferences

    def as_dict(self) -> dict[str, int]:
        return {
            "simulated_transitions": self.simulated_transitions,
            "run_value_inferences": self.run_value_inferences,
            "sampled_worlds": self.sampled_worlds,
            "compute_units": self.compute_units,
        }


@dataclass(frozen=True, slots=True)
class LeafValueBreakdown:
    estimated_terminal_victory_probability: float
    exact_terminal_return: float | None
    rollout_terminal_value: float | None
    truncated_rollout_value: float | None
    bootstrapped_run_value: float | None
    rollout_terminal_samples: int
    rollout_bootstrap_samples: int
    representation_hashes: tuple[str, ...]
    represented_state_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _probability(
            self.estimated_terminal_victory_probability,
            "estimated terminal victory probability",
        )


@dataclass(frozen=True, slots=True)
class CandidateValue:
    candidate_index: int
    source_action_id: str
    action_kind: str
    estimated_terminal_victory_probability: float
    sampled_leaf_values: tuple[float, ...]
    rollout_terminal_samples: int
    rollout_bootstrap_samples: int
    successor_state_hashes: tuple[str, ...]
    representation_hashes: tuple[str, ...]
    represented_state_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _probability(
            self.estimated_terminal_victory_probability,
            "candidate terminal victory probability",
        )


@dataclass(frozen=True, slots=True)
class TacticalValueRanking:
    method: str
    objective_id: str
    root_state_hash: str
    selected_candidate_index: int
    candidates: tuple[CandidateValue, ...]
    configuration: TacticalValueConfig
    usage: ComputeUsage
    compute_unit_definition: str = COMPUTE_UNIT_DEFINITION

    @property
    def selected_action_id(self) -> str:
        return self.candidates[self.selected_candidate_index].source_action_id


@dataclass(slots=True)
class _UsageTracker:
    limit: int
    simulated_transitions: int = 0
    run_value_inferences: int = 0
    sampled_worlds: int = 0

    @property
    def used(self) -> int:
        return self.simulated_transitions + self.run_value_inferences

    def consume_transition(self) -> None:
        self._check(1)
        self.simulated_transitions += 1

    def consume_inference(self) -> None:
        self._check(1)
        self.run_value_inferences += 1

    def sample_world(self) -> None:
        self.sampled_worlds += 1

    def snapshot(self) -> ComputeUsage:
        return ComputeUsage(
            self.simulated_transitions,
            self.run_value_inferences,
            self.sampled_worlds,
        )

    def _check(self, additional: int) -> None:
        if self.used + additional > self.limit:
            raise RuntimeError("Tactical leaf evaluation exceeded its declared compute budget")


def rank_tactical_actions(
    *,
    environment: EnvironmentAdapter,
    observation: Observation,
    legal_actions: Sequence[LegalAction],
    continuation_policy: Policy,
    run_value_estimator: RunValueEstimator,
    config: TacticalValueConfig,
    seed: int,
) -> TacticalValueRanking:
    if observation.decision_type not in {DecisionType.COMBAT, DecisionType.COMBAT_SELECTION}:
        raise ValueError("Tactical action ranking requires a combat decision")
    if run_value_estimator.objective_id != TERMINAL_VICTORY_OBJECTIVE_ID:
        raise ValueError("Tactical leaves require a terminal-victory run-value estimator")
    actions = tuple(legal_actions)
    if not actions:
        raise ValueError("Tactical action ranking requires legal actions")
    if tuple(environment.legal_actions()) != actions:
        raise ValueError("Tactical legal actions are stale or out of order")
    if environment.patch_id != observation.patch_id:
        raise ValueError("Tactical environment and observation patches differ")
    required_upper_bound = _compute_upper_bound(len(actions), config)
    if required_upper_bound > config.maximum_compute_units:
        raise ValueError(
            "Declared compute budget cannot complete equal candidate sampling: "
            f"requires at most {required_upper_bound}, has {config.maximum_compute_units}"
        )

    tracker = _UsageTracker(config.maximum_compute_units)
    candidate_values: list[CandidateValue] = []
    for candidate_index, action in enumerate(actions):
        leaf_values: list[float] = []
        terminal_samples = 0
        bootstrap_samples = 0
        successor_hashes: set[str] = set()
        representation_hashes: set[str] = set()
        represented_paths: set[str] = set()
        for world_index in range(config.candidate_worlds):
            world_seed = _sample_seed(
                seed,
                observation.state_hash,
                candidate_index,
                world_index,
                "candidate",
            )
            sampled = environment.clone(resample_hidden=True, seed=world_seed)
            tracker.sample_world()
            tracker.consume_transition()
            transition = sampled.step(action)
            successor_hashes.add(transition.next_observation.state_hash)
            breakdown = evaluate_tactical_leaf(
                environment=sampled,
                observation=transition.next_observation,
                continuation_policy=continuation_policy,
                run_value_estimator=run_value_estimator,
                config=config,
                seed=_sample_seed(
                    seed,
                    observation.state_hash,
                    candidate_index,
                    world_index,
                    "leaf",
                ),
                tracker=tracker,
            )
            leaf_values.append(breakdown.estimated_terminal_victory_probability)
            terminal_samples += breakdown.rollout_terminal_samples
            bootstrap_samples += breakdown.rollout_bootstrap_samples
            representation_hashes.update(breakdown.representation_hashes)
            represented_paths.update(breakdown.represented_state_paths)
        candidate_values.append(
            CandidateValue(
                candidate_index=candidate_index,
                source_action_id=action.action_id,
                action_kind=action.kind,
                estimated_terminal_victory_probability=_mean(leaf_values),
                sampled_leaf_values=tuple(leaf_values),
                rollout_terminal_samples=terminal_samples,
                rollout_bootstrap_samples=bootstrap_samples,
                successor_state_hashes=tuple(sorted(successor_hashes)),
                representation_hashes=tuple(sorted(representation_hashes)),
                represented_state_paths=tuple(sorted(represented_paths)),
            )
        )
    selected_index = max(
        range(len(candidate_values)),
        key=lambda index: candidate_values[index].estimated_terminal_victory_probability,
    )
    return TacticalValueRanking(
        method=TACTICAL_VALUE_METHOD,
        objective_id=TERMINAL_VICTORY_OBJECTIVE_ID,
        root_state_hash=observation.state_hash,
        selected_candidate_index=selected_index,
        candidates=tuple(candidate_values),
        configuration=config,
        usage=tracker.snapshot(),
    )


def evaluate_tactical_leaf(
    *,
    environment: EnvironmentAdapter,
    observation: Observation,
    continuation_policy: Policy,
    run_value_estimator: RunValueEstimator,
    config: TacticalValueConfig,
    seed: int,
    tracker: _UsageTracker | None = None,
) -> LeafValueBreakdown:
    own_tracker = tracker or _UsageTracker(config.maximum_compute_units)
    terminal = _boolean(observation.public_state.get("terminal"), "terminal")
    if terminal:
        victory = _boolean(observation.public_state.get("victory"), "victory")
        exact = 1.0 if victory else 0.0
        return LeafValueBreakdown(exact, exact, None, None, None, 0, 0, (), ())
    if run_value_estimator.objective_id != TERMINAL_VICTORY_OBJECTIVE_ID:
        raise ValueError("Tactical leaves require a terminal-victory run-value estimator")
    current_actions = tuple(environment.legal_actions())
    if not current_actions:
        raise ValueError("Nonterminal tactical leaf has no legal continuation")

    bootstrap: RunValueEstimate | None = None
    representations: set[str] = set()
    paths: set[str] = set()
    weighted_components: list[tuple[float, float]] = []
    if config.bootstrap_weight > 0.0:
        own_tracker.consume_inference()
        bootstrap = run_value_estimator.estimate(observation, current_actions)
        representations.add(bootstrap.representation_hash)
        paths.update(bootstrap.represented_state_paths)
        weighted_components.append(
            (config.bootstrap_weight, bootstrap.terminal_victory_probability)
        )

    rollout_terminal_values: list[float] = []
    truncated_values: list[float] = []
    terminal_samples = 0
    rollout_bootstraps = 0
    if config.rollout_samples > 0:
        for sample_index in range(config.rollout_samples):
            rollout_seed = _sample_seed(
                seed,
                observation.state_hash,
                sample_index,
                0,
                "rollout",
            )
            rollout = environment.clone(resample_hidden=True, seed=rollout_seed)
            own_tracker.sample_world()
            rollout_observation = observation
            terminal_value: float | None = None
            for _ in range(config.rollout_horizon):
                rollout_actions = tuple(rollout.legal_actions())
                if not rollout_actions:
                    raise ValueError("Nonterminal rollout has no legal action")
                action = continuation_policy.choose_action(rollout_observation, rollout_actions)
                own_tracker.consume_transition()
                transition = rollout.step(action)
                rollout_observation = transition.next_observation
                if transition.terminal:
                    terminal_value = transition.reward
                    terminal_samples += 1
                    rollout_terminal_values.append(terminal_value)
                    break
            if terminal_value is None:
                if config.truncated_rollout_weight <= 0.0:
                    continue
                endpoint_actions = tuple(rollout.legal_actions())
                if not endpoint_actions:
                    raise ValueError("Truncated nonterminal rollout has no legal action")
                own_tracker.consume_inference()
                endpoint = run_value_estimator.estimate(rollout_observation, endpoint_actions)
                terminal_value = endpoint.terminal_victory_probability
                representations.add(endpoint.representation_hash)
                paths.update(endpoint.represented_state_paths)
                rollout_bootstraps += 1
                truncated_values.append(terminal_value)
        if rollout_terminal_values:
            weighted_components.append(
                (config.exact_terminal_weight, _mean(rollout_terminal_values))
            )
        if truncated_values:
            weighted_components.append((config.truncated_rollout_weight, _mean(truncated_values)))
    total_weight = sum(weight for weight, _ in weighted_components)
    if total_weight <= 0.0:
        raise ValueError("Nonterminal tactical leaf produced no value component")
    estimate = sum(weight * value for weight, value in weighted_components) / total_weight
    return LeafValueBreakdown(
        estimated_terminal_victory_probability=estimate,
        exact_terminal_return=None,
        rollout_terminal_value=(
            _mean(rollout_terminal_values) if rollout_terminal_values else None
        ),
        truncated_rollout_value=_mean(truncated_values) if truncated_values else None,
        bootstrapped_run_value=(
            None if bootstrap is None else bootstrap.terminal_victory_probability
        ),
        rollout_terminal_samples=terminal_samples,
        rollout_bootstrap_samples=rollout_bootstraps,
        representation_hashes=tuple(sorted(representations)),
        represented_state_paths=tuple(sorted(paths)),
    )


def _compute_upper_bound(candidate_count: int, config: TacticalValueConfig) -> int:
    per_world = 1
    if config.bootstrap_weight > 0.0:
        per_world += 1
    if config.rollout_samples > 0:
        per_world += config.rollout_samples * config.rollout_horizon
        if config.truncated_rollout_weight > 0.0:
            per_world += config.rollout_samples
    return candidate_count * config.candidate_worlds * per_world


def _represented_state_paths(representation: CompositionalModelInput) -> tuple[str, ...]:
    paths = {_feature_path(feature) for feature in representation.global_features}
    paths.update(_feature_path(feature) for feature in representation.persistent_resources)
    for entity in representation.entities:
        for feature in entity.features:
            paths.add(_feature_path(feature))
    return tuple(sorted(paths))


def _feature_path(feature: ScalarFeature) -> str:
    path = ".".join(feature.path)
    if feature.indices:
        path += "".join(f"[{index}]" for index in feature.indices)
    return path


def _sample_seed(
    seed: int,
    state_hash: str,
    first_index: int,
    second_index: int,
    domain: str,
) -> int:
    payload = f"{seed}\0{state_hash}\0{first_index}\0{second_index}\0{domain}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _mean(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("Cannot take the mean of an empty sequence")
    return sum(values) / len(values)


def _probability(value: float, label: str) -> float:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be a finite probability")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result
