from __future__ import annotations

import copy
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Self

import pytest

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.core.manifest import RulesetIdentity
from spireshift.core.types import LegalAction, Observation, Transition
from spireshift.mechanics import OutcomeMethod, PublicMechanicsService, outcome_signature
from spireshift.mechanics_audit import audit_mechanics_fixture

FIXTURE_PATH = Path("tests/fixtures/mechanics/mock-v1.json")


class _SamplingOnlyEnvironment:
    """Hide the mock exact-outcome extension to exercise the generic engine path."""

    def __init__(self, environment: MockSpireEnvironment | None = None) -> None:
        self._environment = environment or MockSpireEnvironment()
        self.patch_id: str = self._environment.patch_id
        self.ruleset: RulesetIdentity = self._environment.ruleset

    def reset(self, seed: int) -> Observation:
        return self._environment.reset(seed)

    def legal_actions(self) -> Sequence[LegalAction]:
        return self._environment.legal_actions()

    def step(self, action: LegalAction) -> Transition:
        return self._environment.step(action)

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> Self:
        return type(self)(self._environment.clone(resample_hidden=resample_hidden, seed=seed))


def test_snapshot_is_shared_model_and_legality_input() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)

    snapshot = PublicMechanicsService().snapshot(environment, observation)

    assert snapshot.legal_actions == tuple(environment.legal_actions())
    assert snapshot.action_mask == snapshot.model_input.action_mask == (True, True)
    assert tuple(candidate.source_action_id for candidate in snapshot.model_input.candidates) == (
        "safe_path",
        "elite_path",
    )


def test_exact_rules_enumerate_deterministic_and_stochastic_outcomes_without_mutation() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(7)
    service = PublicMechanicsService()
    snapshot = service.snapshot(environment, observation)
    by_id = {action.action_id: action for action in snapshot.legal_actions}

    safe = service.outcomes(environment, snapshot, by_id["safe_path"])
    elite = service.outcomes(environment, snapshot, by_id["elite_path"])

    assert safe.method is OutcomeMethod.EXACT_ENUMERATION
    assert safe.deterministic_transition is not None
    assert safe.deterministic_transition.next_observation.public_state["floor"] == 1
    assert elite.method is OutcomeMethod.EXACT_ENUMERATION
    assert elite.deterministic_transition is None
    assert sorted(outcome.probability for outcome in elite.outcomes) == [0.25, 0.75]
    assert environment.legal_actions() == snapshot.legal_actions
    assert service.snapshot(environment, observation) == snapshot


def test_generic_backend_marks_public_resampling_as_approximate() -> None:
    environment = _SamplingOnlyEnvironment()
    observation = environment.reset(7)
    service = PublicMechanicsService()
    snapshot = service.snapshot(environment, observation)
    elite = next(action for action in snapshot.legal_actions if action.action_id == "elite_path")

    estimate = service.outcomes(
        environment,
        snapshot,
        elite,
        resample_seeds=tuple(range(256)),
    )

    assert estimate.method is OutcomeMethod.PUBLIC_RESAMPLING
    assert not estimate.exact
    assert estimate.sample_count == 256
    assert estimate.approximation_reason is not None
    probabilities = {
        outcome.transition.next_observation.public_state["terminal"]: outcome.probability
        for outcome in estimate.outcomes
    }
    assert probabilities[True] == pytest.approx(0.25, abs=0.06)
    assert probabilities[False] == pytest.approx(0.75, abs=0.06)


def test_missing_engine_capability_is_explicit_instead_of_silently_inferred() -> None:
    environment = _SamplingOnlyEnvironment()
    observation = environment.reset(7)
    service = PublicMechanicsService()
    snapshot = service.snapshot(environment, observation)

    estimate = service.outcomes(environment, snapshot, snapshot.legal_actions[0])

    assert estimate.method is OutcomeMethod.UNAVAILABLE
    assert estimate.outcomes == ()
    assert estimate.sample_count == 0
    assert estimate.approximation_reason is not None


def test_outcome_signature_contains_only_public_transition_evidence() -> None:
    environment = MockSpireEnvironment()
    observation = environment.reset(3)
    snapshot = PublicMechanicsService().snapshot(environment, observation)
    estimate = PublicMechanicsService().outcomes(
        environment,
        snapshot,
        snapshot.legal_actions[0],
    )

    signature = outcome_signature(estimate.outcomes[0].transition)

    assert signature == (
        f"{estimate.outcomes[0].transition.next_observation.state_hash}|0.0|false|false"
    )


def test_authoritative_fixture_reports_zero_divergence_by_mechanic_and_patch() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    report = audit_mechanics_fixture(fixture, MockSpireEnvironment)

    assert report["patch_id"] == "mock-v1"
    assert report["verdict"] == "pass"
    assert report["summary"] == {
        "cases": 2,
        "exact_queries": 3,
        "approximate_queries": 0,
        "unavailable_queries": 0,
        "divergences": 0,
        "maximum_total_variation": 0.0,
    }


def test_authoritative_fixture_audit_localizes_probability_divergence() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(fixture)
    changed["cases"][0]["outcomes"]["elite_path"][0]["probability"] = 0.5

    report = audit_mechanics_fixture(changed, MockSpireEnvironment)

    assert report["verdict"] == "diverged"
    cases = report["cases"]
    assert isinstance(cases, list)
    first_case = cases[0]
    assert isinstance(first_case, dict)
    divergences = first_case["divergences"]
    assert isinstance(divergences, list)
    assert divergences[0]["path"] == "outcomes.elite_path"
