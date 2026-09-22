from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any, cast

from spireshift.core.protocols import EnvironmentAdapter
from spireshift.mechanics import PublicMechanicsService, outcome_signature

MECHANICS_FIXTURE_SCHEMA_VERSION = "mechanics-fixture-v1"
MECHANICS_AUDIT_SCHEMA_VERSION = "mechanics-audit-v1"


def audit_mechanics_fixture(
    fixture: object,
    environment_factory: Callable[[], EnvironmentAdapter],
) -> dict[str, object]:
    specification = _mapping(fixture, "mechanics fixture")
    if specification.get("schema_version") != MECHANICS_FIXTURE_SCHEMA_VERSION:
        raise ValueError("Unsupported mechanics fixture schema")
    fixture_id = _string(specification.get("fixture_id"), "fixture_id")
    expected_patch = _string(specification.get("patch_id"), "patch_id")
    expected_manifest = _string(specification.get("ruleset_manifest_id"), "ruleset_manifest_id")
    tolerance = _probability(specification.get("probability_tolerance"), "probability_tolerance")
    service = PublicMechanicsService()
    cases: list[dict[str, object]] = []
    divergence_count = 0
    exact_queries = 0
    approximate_queries = 0
    unavailable_queries = 0
    maximum_total_variation = 0.0
    for raw_case in _list(specification.get("cases"), "cases"):
        case = _mapping(raw_case, "mechanics case")
        environment = environment_factory()
        if environment.patch_id != expected_patch:
            raise ValueError("Fixture patch differs from environment patch")
        if environment.ruleset.manifest_id != expected_manifest:
            raise ValueError("Fixture ruleset differs from environment ruleset")
        observation = environment.reset(_integer(case.get("seed"), "case seed"))
        for prefix_action_id in _string_list(case.get("action_prefix"), "action_prefix"):
            prefix_snapshot = service.snapshot(environment, observation)
            prefix_action = _action_by_id(prefix_snapshot.legal_actions, prefix_action_id)
            observation = environment.step(prefix_action).next_observation
        snapshot = service.snapshot(environment, observation)
        divergences: list[dict[str, object]] = []
        expected_state_hash = _string(case.get("state_hash"), "case state_hash")
        if observation.state_hash != expected_state_hash:
            divergences.append(
                _divergence("state_hash", expected_state_hash, observation.state_hash)
            )
        expected_actions = _list(case.get("legal_actions"), "case legal_actions")
        actual_actions = [action.as_dict() for action in snapshot.legal_actions]
        if expected_actions != actual_actions:
            divergences.append(_divergence("legal_actions", expected_actions, actual_actions))
        outcome_results: list[dict[str, object]] = []
        expected_outcomes = _mapping(case.get("outcomes"), "case outcomes")
        for action_id, raw_distribution in expected_outcomes.items():
            if not isinstance(action_id, str):
                raise ValueError("Outcome action IDs must be strings")
            expected_distribution = {
                _string(item.get("signature"), "outcome signature"): _probability(
                    item.get("probability"), "outcome probability"
                )
                for item in (
                    _mapping(raw_item, "expected outcome")
                    for raw_item in _list(raw_distribution, "expected outcome distribution")
                )
            }
            action = _action_by_id(snapshot.legal_actions, action_id)
            resample_seeds = tuple(
                _integer(seed, "resample seed")
                for seed in _list(case.get("resample_seeds", []), "resample_seeds")
            )
            estimate = service.outcomes(
                environment,
                snapshot,
                action,
                resample_seeds=resample_seeds,
            )
            exact_queries += int(estimate.exact)
            approximate_queries += int(estimate.method.value == "public_resampling")
            unavailable_queries += int(estimate.method.value == "unavailable")
            actual_distribution = {
                outcome_signature(outcome.transition): outcome.probability
                for outcome in estimate.outcomes
            }
            total_variation = _total_variation(expected_distribution, actual_distribution)
            maximum_error = max(
                (
                    abs(expected_distribution.get(key, 0.0) - actual_distribution.get(key, 0.0))
                    for key in expected_distribution.keys() | actual_distribution.keys()
                ),
                default=0.0,
            )
            maximum_total_variation = max(maximum_total_variation, total_variation)
            status = "pass" if maximum_error <= tolerance else "diverged"
            if status == "diverged":
                divergences.append(
                    _divergence(
                        f"outcomes.{action_id}",
                        expected_distribution,
                        actual_distribution,
                    )
                )
            outcome_results.append(
                {
                    "action_id": action_id,
                    "method": estimate.method.value,
                    "sample_count": estimate.sample_count,
                    "approximation_reason": estimate.approximation_reason,
                    "total_variation": total_variation,
                    "maximum_probability_error": maximum_error,
                    "status": status,
                }
            )
        divergence_count += len(divergences)
        cases.append(
            {
                "case_id": _string(case.get("case_id"), "case_id"),
                "seed": _integer(case.get("seed"), "case seed"),
                "state_hash": observation.state_hash,
                "legal_action_status": (
                    "pass" if expected_actions == actual_actions else "diverged"
                ),
                "outcomes": outcome_results,
                "divergences": divergences,
            }
        )
    return {
        "schema_version": MECHANICS_AUDIT_SCHEMA_VERSION,
        "fixture_id": fixture_id,
        "patch_id": expected_patch,
        "ruleset_manifest_id": expected_manifest,
        "mechanics_service_id": service.service_id,
        "verdict": "pass" if divergence_count == 0 else "diverged",
        "probability_tolerance": tolerance,
        "summary": {
            "cases": len(cases),
            "exact_queries": exact_queries,
            "approximate_queries": approximate_queries,
            "unavailable_queries": unavailable_queries,
            "divergences": divergence_count,
            "maximum_total_variation": maximum_total_variation,
        },
        "cases": cases,
    }


def _action_by_id(actions: object, action_id: str) -> Any:
    for action in cast(Any, actions):
        if action.action_id == action_id:
            return action
    raise ValueError(f"Fixture action is not legal: {action_id}")


def _total_variation(expected: dict[str, float], actual: dict[str, float]) -> float:
    return 0.5 * sum(
        abs(expected.get(key, 0.0) - actual.get(key, 0.0))
        for key in expected.keys() | actual.keys()
    )


def _divergence(path: str, expected: object, actual: object) -> dict[str, object]:
    return {"path": path, "expected": expected, "actual": actual}


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _string_list(value: object, label: str) -> tuple[str, ...]:
    return tuple(_string(item, label) for item in _list(value, label))


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _probability(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ValueError(f"{label} must be between zero and one")
    return result
