from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import LegalAction, Observation, Transition
from spireshift.representations import CompositionalModelInput, build_model_input


class OutcomeMethod(StrEnum):
    EXACT_ENUMERATION = "exact_enumeration"
    PUBLIC_RESAMPLING = "public_resampling"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class WeightedTransition:
    probability: float
    transition: Transition

    def __post_init__(self) -> None:
        if not math.isfinite(self.probability) or self.probability <= 0.0:
            raise ValueError("Outcome probability must be finite and positive")


@runtime_checkable
class ExactPublicOutcomeProvider(Protocol):
    """Optional engine capability derived only from player-observable information."""

    def public_outcomes(self, action: LegalAction) -> Sequence[WeightedTransition]: ...


@dataclass(frozen=True, slots=True)
class MechanicsSnapshot:
    observation: Observation
    legal_actions: tuple[LegalAction, ...]
    action_mask: tuple[bool, ...]
    model_input: CompositionalModelInput


@dataclass(frozen=True, slots=True)
class OutcomeEstimate:
    patch_id: str
    source_state_hash: str
    action: LegalAction
    method: OutcomeMethod
    outcomes: tuple[WeightedTransition, ...]
    sample_count: int
    approximation_reason: str | None

    @property
    def exact(self) -> bool:
        return self.method is OutcomeMethod.EXACT_ENUMERATION

    @property
    def deterministic_transition(self) -> Transition | None:
        if not self.exact or len(self.outcomes) != 1:
            return None
        outcome = self.outcomes[0]
        return outcome.transition if math.isclose(outcome.probability, 1.0) else None


class PublicMechanicsService:
    """One public-information rules interface for policies, search, and advisors."""

    service_id = "public-mechanics-v1"

    def snapshot(
        self,
        environment: EnvironmentAdapter,
        observation: Observation,
    ) -> MechanicsSnapshot:
        _validate_identity(environment, observation)
        legal_actions = tuple(environment.legal_actions())
        _validate_legal_actions(observation, legal_actions)
        model_input = build_model_input(environment.ruleset, observation, legal_actions)
        action_mask = tuple(True for _ in legal_actions)
        if model_input.action_mask != action_mask:
            raise RuntimeError("Mechanics and model action masks differ")
        return MechanicsSnapshot(observation, legal_actions, action_mask, model_input)

    def outcomes(
        self,
        environment: EnvironmentAdapter,
        snapshot: MechanicsSnapshot,
        action: LegalAction,
        *,
        resample_seeds: Sequence[int] = (),
    ) -> OutcomeEstimate:
        current = self.snapshot(environment, snapshot.observation)
        if current.legal_actions != snapshot.legal_actions:
            raise RuntimeError("Mechanics snapshot is stale")
        selected = _require_legal(action, current.legal_actions)
        if isinstance(environment, ExactPublicOutcomeProvider):
            outcomes = tuple(environment.public_outcomes(selected))
            _validate_outcomes(snapshot.observation, selected, outcomes)
            return OutcomeEstimate(
                patch_id=environment.patch_id,
                source_state_hash=snapshot.observation.state_hash,
                action=selected,
                method=OutcomeMethod.EXACT_ENUMERATION,
                outcomes=_sort_outcomes(outcomes),
                sample_count=0,
                approximation_reason=None,
            )
        seeds = tuple(resample_seeds)
        if not seeds:
            return OutcomeEstimate(
                patch_id=environment.patch_id,
                source_state_hash=snapshot.observation.state_hash,
                action=selected,
                method=OutcomeMethod.UNAVAILABLE,
                outcomes=(),
                sample_count=0,
                approximation_reason=(
                    "engine exposes no exact public outcome enumeration and no resample seeds "
                    "were supplied"
                ),
            )
        if len(seeds) != len(set(seeds)):
            raise ValueError("Public resample seeds must be unique")
        sampled: list[Transition] = []
        for seed in seeds:
            clone = environment.clone(resample_hidden=True, seed=seed)
            clone_snapshot = self.snapshot(clone, snapshot.observation)
            if clone_snapshot.legal_actions != snapshot.legal_actions:
                raise RuntimeError("Hidden-state resampling changed the public legal actions")
            sampled.append(clone.step(_require_legal(selected, clone_snapshot.legal_actions)))
        outcomes = _empirical_distribution(sampled)
        _validate_outcomes(snapshot.observation, selected, outcomes)
        return OutcomeEstimate(
            patch_id=environment.patch_id,
            source_state_hash=snapshot.observation.state_hash,
            action=selected,
            method=OutcomeMethod.PUBLIC_RESAMPLING,
            outcomes=outcomes,
            sample_count=len(seeds),
            approximation_reason=(
                "empirical distribution from public-state hidden-world resampling"
            ),
        )


def outcome_signature(transition: Transition) -> str:
    return "|".join(
        (
            transition.next_observation.state_hash,
            format(transition.reward, ".1f"),
            str(transition.terminal).lower(),
            str(transition.victory).lower(),
        )
    )


def _validate_identity(environment: EnvironmentAdapter, observation: Observation) -> None:
    if environment.patch_id != environment.ruleset.patch_id:
        raise RuntimeError("Environment patch does not match its ruleset identity")
    if observation.patch_id != environment.patch_id:
        raise RuntimeError("Observation patch does not match its environment")


def _validate_legal_actions(
    observation: Observation,
    actions: Sequence[LegalAction],
) -> None:
    action_ids = [action.action_id for action in actions]
    if len(action_ids) != len(set(action_ids)):
        raise RuntimeError("Legal action IDs must be unique")
    terminal = bool(observation.public_state.get("terminal"))
    if terminal and actions:
        raise RuntimeError("Terminal observations must not advertise legal actions")
    if not terminal and not actions:
        raise RuntimeError("Non-terminal observations must advertise a legal action")


def _require_legal(action: LegalAction, actions: Sequence[LegalAction]) -> LegalAction:
    by_id = {candidate.action_id: candidate for candidate in actions}
    selected = by_id.get(action.action_id)
    if selected is None or selected != action:
        raise ValueError(f"Action is not legal in the mechanics snapshot: {action.action_id}")
    return selected


def _validate_outcomes(
    observation: Observation,
    action: LegalAction,
    outcomes: Sequence[WeightedTransition],
) -> None:
    if not outcomes:
        raise RuntimeError("An available outcome distribution must not be empty")
    total = sum(outcome.probability for outcome in outcomes)
    if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        raise RuntimeError(f"Outcome probabilities sum to {total!r}, not one")
    signatures: set[str] = set()
    for outcome in outcomes:
        transition = outcome.transition
        if transition.observation != observation:
            raise RuntimeError("Outcome transition starts from a different public observation")
        if transition.action != action:
            raise RuntimeError("Outcome transition uses a different action")
        signature = outcome_signature(transition)
        if signature in signatures:
            raise RuntimeError("Outcome distribution contains duplicate public outcomes")
        signatures.add(signature)


def _empirical_distribution(transitions: Sequence[Transition]) -> tuple[WeightedTransition, ...]:
    if not transitions:
        raise ValueError("At least one sampled transition is required")
    counts = Counter(outcome_signature(transition) for transition in transitions)
    representative = {outcome_signature(transition): transition for transition in transitions}
    return tuple(
        WeightedTransition(count / len(transitions), representative[signature])
        for signature, count in sorted(counts.items())
    )


def _sort_outcomes(outcomes: Sequence[WeightedTransition]) -> tuple[WeightedTransition, ...]:
    return tuple(sorted(outcomes, key=lambda outcome: outcome_signature(outcome.transition)))
