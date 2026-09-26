from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from spireshift.agents.learned import ProductionPolicyDecision
from spireshift.core.manifest import manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation

COMBAT_ADVANCEMENT_CONFIG_SCHEMA_VERSION = "combat-advancement-config-v1"
COMBAT_ADVANCEMENT_POLICY_VERSION = "combat-advancement-policy-v1"
TERMINAL_VICTORY_OBJECTIVE_ID = "terminal-victory-v1"
PUBLIC_RESAMPLE_EXHAUSTION_POLICY_ONLY_FALLBACK = "policy_only_fallback"


class CandidatePredictor(Protocol):
    policy_id: str
    model_id: str

    def predict(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> ProductionPolicyDecision: ...

    def choose_action(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> LegalAction: ...


@dataclass(frozen=True, slots=True)
class CombatAdvancementConfig:
    candidate_worlds: int
    maximum_rollout_steps: int
    maximum_simulated_transitions_per_decision: int
    maximum_public_resample_attempts: int
    public_resample_exhaustion: str
    progress_weight: float
    tactical_survival_weight: float
    sampling_salt: str
    objective_id: str = TERMINAL_VICTORY_OBJECTIVE_ID
    schema_version: str = COMBAT_ADVANCEMENT_CONFIG_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COMBAT_ADVANCEMENT_CONFIG_SCHEMA_VERSION:
            raise ValueError("Combat-advancement configuration schema differs")
        if self.objective_id != TERMINAL_VICTORY_OBJECTIVE_ID:
            raise ValueError("Combat advancement must preserve the terminal-victory objective")
        if self.public_resample_exhaustion != PUBLIC_RESAMPLE_EXHAUSTION_POLICY_ONLY_FALLBACK:
            raise ValueError(
                "Combat advancement must fall back to the public-state policy when hidden-world "
                "resampling is exhausted"
            )
        for name, value in (
            ("candidate_worlds", self.candidate_worlds),
            ("maximum_rollout_steps", self.maximum_rollout_steps),
            (
                "maximum_simulated_transitions_per_decision",
                self.maximum_simulated_transitions_per_decision,
            ),
            ("maximum_public_resample_attempts", self.maximum_public_resample_attempts),
        ):
            if isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be positive")
        for weight_name, weight_value in (
            ("progress_weight", float(self.progress_weight)),
            ("tactical_survival_weight", float(self.tactical_survival_weight)),
        ):
            if not math.isfinite(weight_value) or weight_value < 0.0:
                raise ValueError(f"{weight_name} must be finite and non-negative")
        if not math.isclose(
            self.progress_weight + self.tactical_survival_weight,
            1.0,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("Combat-advancement leaf weights must sum to one")
        if not self.sampling_salt:
            raise ValueError("sampling_salt must be non-empty")

    def body(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "objective_id": self.objective_id,
            "candidate_worlds": self.candidate_worlds,
            "maximum_rollout_steps": self.maximum_rollout_steps,
            "maximum_simulated_transitions_per_decision": (
                self.maximum_simulated_transitions_per_decision
            ),
            "maximum_public_resample_attempts": self.maximum_public_resample_attempts,
            "public_resample_exhaustion": self.public_resample_exhaustion,
            "progress_weight": self.progress_weight,
            "tactical_survival_weight": self.tactical_survival_weight,
            "sampling_salt": self.sampling_salt,
        }

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "config_id": self.config_id}

    @classmethod
    def from_mapping(cls, value: object) -> CombatAdvancementConfig:
        if not isinstance(value, dict):
            raise ValueError("Combat-advancement configuration must be an object")
        expected = {
            "schema_version",
            "config_id",
            "objective_id",
            "candidate_worlds",
            "maximum_rollout_steps",
            "maximum_simulated_transitions_per_decision",
            "maximum_public_resample_attempts",
            "public_resample_exhaustion",
            "progress_weight",
            "tactical_survival_weight",
            "sampling_salt",
        }
        if set(value) != expected:
            raise ValueError("Combat-advancement configuration fields differ")
        config = cls(
            schema_version=_string(value.get("schema_version"), "schema_version"),
            objective_id=_string(value.get("objective_id"), "objective_id"),
            candidate_worlds=_integer(value.get("candidate_worlds"), "candidate_worlds"),
            maximum_rollout_steps=_integer(
                value.get("maximum_rollout_steps"), "maximum_rollout_steps"
            ),
            maximum_simulated_transitions_per_decision=_integer(
                value.get("maximum_simulated_transitions_per_decision"),
                "maximum_simulated_transitions_per_decision",
            ),
            maximum_public_resample_attempts=_integer(
                value.get("maximum_public_resample_attempts"),
                "maximum_public_resample_attempts",
            ),
            public_resample_exhaustion=_string(
                value.get("public_resample_exhaustion"), "public_resample_exhaustion"
            ),
            progress_weight=_number(value.get("progress_weight"), "progress_weight"),
            tactical_survival_weight=_number(
                value.get("tactical_survival_weight"), "tactical_survival_weight"
            ),
            sampling_salt=_string(value.get("sampling_salt"), "sampling_salt"),
        )
        if value.get("config_id") != config.config_id:
            raise ValueError("Combat-advancement configuration identity mismatch")
        return config


def load_combat_advancement_config(path: Path) -> CombatAdvancementConfig:
    document = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    return CombatAdvancementConfig.from_mapping(document)


@dataclass(frozen=True, slots=True)
class CombatCandidateEstimate:
    candidate_index: int
    action_id: str
    mean_search_value: float
    sampled_search_values: tuple[float, ...]
    terminal_victories: int
    terminal_defeats: int
    bootstrapped_leaves: int


@dataclass(frozen=True, slots=True)
class CombatAdvancementDecision:
    source_state_hash: str
    selected_candidate_index: int
    selected_action: LegalAction
    effective_rollout_steps: int
    simulated_transitions: int
    hidden_worlds: int
    public_resample_attempts: int
    accepted_world_seeds: tuple[int, ...]
    candidates: tuple[CombatCandidateEstimate, ...]


@dataclass(frozen=True, slots=True)
class CombatAdvancementUsage:
    policy_only_decisions: int
    search_decisions: int
    search_fallback_decisions: int
    simulated_transitions: int
    hidden_worlds: int
    public_resample_attempts: int
    public_resample_failures: int

    def as_dict(self) -> dict[str, int]:
        return {
            "policy_only_decisions": self.policy_only_decisions,
            "search_decisions": self.search_decisions,
            "search_fallback_decisions": self.search_fallback_decisions,
            "simulated_transitions": self.simulated_transitions,
            "hidden_worlds": self.hidden_worlds,
            "public_resample_attempts": self.public_resample_attempts,
            "public_resample_failures": self.public_resample_failures,
        }


class _PublicWorldSamplingExhausted(RuntimeError):
    def __init__(self, attempts: int) -> None:
        super().__init__("Could not sample a hidden world consistent with the public legal actions")
        self.attempts = attempts


class CombatAdvancementPolicy:
    """Use equal-budget combat lookahead with learned public-state leaf values.

    The floor and tactical-risk heads are an auxiliary leaf heuristic. Exact terminal wins and
    losses encountered inside the horizon retain their binary terminal-victory values. Full-run
    evaluation must still report terminal victory as its primary outcome.
    """

    def __init__(
        self,
        *,
        environment: EnvironmentAdapter,
        base_policy: CandidatePredictor,
        config: CombatAdvancementConfig,
    ) -> None:
        if (
            environment.ruleset.manifest_id
            != getattr(base_policy, "ruleset", environment.ruleset).manifest_id
        ):
            raise ValueError("Combat-advancement policy and environment rulesets differ")
        self.environment = environment
        self.base_policy = base_policy
        self.config = config
        self.model_id = base_policy.model_id
        self.policy_id = (
            f"{COMBAT_ADVANCEMENT_POLICY_VERSION}:{self.model_id}:{self.config.config_id}"
        )
        self.last_decision: CombatAdvancementDecision | None = None
        self._policy_only_decisions = 0
        self._search_decisions = 0
        self._search_fallback_decisions = 0
        self._simulated_transitions = 0
        self._hidden_worlds = 0
        self._public_resample_attempts = 0
        self._public_resample_failures = 0

    def choose_action(
        self,
        observation: Observation,
        legal_actions: Sequence[LegalAction],
    ) -> LegalAction:
        actions = tuple(legal_actions)
        if not actions:
            raise ValueError("Policy cannot act without legal actions")
        if tuple(self.environment.legal_actions()) != actions:
            raise ValueError("Combat-advancement legal actions are stale or out of order")
        if observation.decision_type is not DecisionType.COMBAT or len(actions) == 1:
            self._policy_only_decisions += 1
            self.last_decision = None
            return self.base_policy.choose_action(observation, actions)
        try:
            decision = self._search(observation, actions)
        except _PublicWorldSamplingExhausted as error:
            self._policy_only_decisions += 1
            self._search_fallback_decisions += 1
            self._public_resample_attempts += error.attempts
            self._public_resample_failures += 1
            self.last_decision = None
            return self.base_policy.choose_action(observation, actions)
        self.last_decision = decision
        self._search_decisions += 1
        self._simulated_transitions += decision.simulated_transitions
        self._hidden_worlds += decision.hidden_worlds
        self._public_resample_attempts += decision.public_resample_attempts
        return decision.selected_action

    def usage(self) -> CombatAdvancementUsage:
        return CombatAdvancementUsage(
            policy_only_decisions=self._policy_only_decisions,
            search_decisions=self._search_decisions,
            search_fallback_decisions=self._search_fallback_decisions,
            simulated_transitions=self._simulated_transitions,
            hidden_worlds=self._hidden_worlds,
            public_resample_attempts=self._public_resample_attempts,
            public_resample_failures=self._public_resample_failures,
        )

    def _search(
        self,
        observation: Observation,
        actions: tuple[LegalAction, ...],
    ) -> CombatAdvancementDecision:
        denominator = len(actions) * self.config.candidate_worlds
        effective_steps = min(
            self.config.maximum_rollout_steps,
            self.config.maximum_simulated_transitions_per_decision // denominator,
        )
        if effective_steps <= 0:
            raise RuntimeError(
                "Combat-advancement budget cannot sample every action in every paired world"
            )
        values: list[list[float]] = [[] for _ in actions]
        victories = [0 for _ in actions]
        defeats = [0 for _ in actions]
        bootstraps = [0 for _ in actions]
        simulated_transitions = 0
        public_resample_attempts = 0
        accepted_world_seeds: list[int] = []
        worlds: list[EnvironmentAdapter] = []
        try:
            for world_index in range(self.config.candidate_worlds):
                try:
                    world, accepted_seed, attempts = self._compatible_world(
                        observation,
                        actions,
                        world_index,
                    )
                except _PublicWorldSamplingExhausted as error:
                    raise _PublicWorldSamplingExhausted(
                        public_resample_attempts + error.attempts
                    ) from error
                worlds.append(world)
                public_resample_attempts += attempts
                accepted_world_seeds.append(accepted_seed)

            base = self.base_policy.predict(observation, actions)
            source_floor = _public_integer(observation, ("floor",), ("run", "floor"))
            for world in worlds:
                for candidate_index, action in enumerate(actions):
                    branch = world.clone(resample_hidden=False)
                    try:
                        value, transitions, outcome = self._evaluate_branch(
                            branch,
                            observation,
                            action,
                            source_floor=source_floor,
                            maximum_steps=effective_steps,
                        )
                    finally:
                        _close_environment(branch)
                    values[candidate_index].append(value)
                    simulated_transitions += transitions
                    if outcome == "victory":
                        victories[candidate_index] += 1
                    elif outcome == "defeat":
                        defeats[candidate_index] += 1
                    else:
                        bootstraps[candidate_index] += 1
        finally:
            for world in worlds:
                _close_environment(world)
        if simulated_transitions > self.config.maximum_simulated_transitions_per_decision:
            raise AssertionError("Combat-advancement search exceeded its transition budget")
        estimates = tuple(
            CombatCandidateEstimate(
                candidate_index=index,
                action_id=action.action_id,
                mean_search_value=sum(values[index]) / len(values[index]),
                sampled_search_values=tuple(values[index]),
                terminal_victories=victories[index],
                terminal_defeats=defeats[index],
                bootstrapped_leaves=bootstraps[index],
            )
            for index, action in enumerate(actions)
        )
        selected_index = max(
            range(len(actions)),
            key=lambda index: (
                estimates[index].mean_search_value,
                base.policy[index],
                -index,
            ),
        )
        return CombatAdvancementDecision(
            source_state_hash=observation.state_hash,
            selected_candidate_index=selected_index,
            selected_action=actions[selected_index],
            effective_rollout_steps=effective_steps,
            simulated_transitions=simulated_transitions,
            hidden_worlds=self.config.candidate_worlds,
            public_resample_attempts=public_resample_attempts,
            accepted_world_seeds=tuple(accepted_world_seeds),
            candidates=estimates,
        )

    def _compatible_world(
        self,
        observation: Observation,
        actions: tuple[LegalAction, ...],
        world_index: int,
    ) -> tuple[EnvironmentAdapter, int, int]:
        for attempt_index in range(self.config.maximum_public_resample_attempts):
            seed = _sample_seed(
                self.config.sampling_salt,
                observation.state_hash,
                world_index,
                attempt_index,
            )
            world = self.environment.clone(resample_hidden=True, seed=seed)
            if tuple(world.legal_actions()) == actions:
                return world, seed, attempt_index + 1
            _close_environment(world)
        raise _PublicWorldSamplingExhausted(self.config.maximum_public_resample_attempts)

    def _evaluate_branch(
        self,
        environment: EnvironmentAdapter,
        source: Observation,
        action: LegalAction,
        *,
        source_floor: int | None,
        maximum_steps: int,
    ) -> tuple[float, int, str]:
        transition = environment.step(action)
        if transition.observation != source:
            raise RuntimeError("Hidden-world clone changed the source public observation")
        transitions = 1
        observation = transition.next_observation
        while (
            not transition.terminal
            and transitions < maximum_steps
            and observation.decision_type in {DecisionType.COMBAT, DecisionType.COMBAT_SELECTION}
        ):
            legal_actions = tuple(environment.legal_actions())
            continuation = self.base_policy.choose_action(observation, legal_actions)
            transition = environment.step(continuation)
            transitions += 1
            observation = transition.next_observation
        if transition.terminal:
            return (
                (1.0 if transition.victory else 0.0),
                transitions,
                ("victory" if transition.victory else "defeat"),
            )
        legal_actions = tuple(environment.legal_actions())
        if not legal_actions:
            raise RuntimeError("Nonterminal combat-advancement leaf has no legal actions")
        prediction = self.base_policy.predict(observation, legal_actions)
        return self._auxiliary_leaf_value(prediction, source_floor), transitions, "bootstrap"

    def _auxiliary_leaf_value(
        self,
        prediction: ProductionPolicyDecision,
        source_floor: int | None,
    ) -> float:
        thresholds = tuple(
            threshold
            for threshold in sorted(prediction.maximum_floor_reach)
            if source_floor is None or threshold > source_floor
        )
        candidate_values: list[float] = []
        for candidate_index in range(len(prediction.source_action_ids)):
            components: list[tuple[float, float]] = []
            if thresholds and self.config.progress_weight > 0.0:
                progress = sum(
                    prediction.maximum_floor_reach[threshold][candidate_index]
                    for threshold in thresholds
                ) / len(thresholds)
                components.append((self.config.progress_weight, progress))
            if self.config.tactical_survival_weight > 0.0:
                components.append(
                    (
                        self.config.tactical_survival_weight,
                        1.0 - prediction.tactical_death_risk[candidate_index],
                    )
                )
            total_weight = sum(weight for weight, _ in components)
            if total_weight <= 0.0:
                raise RuntimeError("Combat-advancement leaf has no usable auxiliary head")
            candidate_values.append(
                sum(weight * value for weight, value in components) / total_weight
            )
        return max(candidate_values)


def _sample_seed(salt: str, state_hash: str, world_index: int, attempt_index: int) -> int:
    payload = f"{salt}|{state_hash}|{world_index}|{attempt_index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def _public_integer(observation: Observation, *paths: tuple[str, ...]) -> int | None:
    for path in paths:
        current: Any = observation.public_state
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, int) and not isinstance(current, bool):
                return current
    return None


def _close_environment(environment: object) -> None:
    close = getattr(environment, "close", None)
    if callable(close):
        close()


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value
