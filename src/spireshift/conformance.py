from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, cast

from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import LegalAction, Observation, Transition

CONFORMANCE_SUITE_VERSION = "environment-conformance-v1"
CONFORMANCE_REPORT_VERSION = "conformance-report-v1"
CONFORMANCE_TRACE_VERSION = "conformance-trace-v1"
DIFFERENTIAL_REPORT_VERSION = "differential-report-v1"

_FORBIDDEN_PUBLIC_KEYS = {
    "draw_order",
    "draw_pile_order",
    "encounter_sequence",
    "future",
    "future_reward",
    "hidden",
    "next_reward",
    "random_seed",
    "rng",
    "run_seed",
    "seed",
}


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class CheckResult:
    check_id: str
    status: CheckStatus
    detail: str
    metrics: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["status"] = self.status.value
        return value


@dataclass(frozen=True, slots=True)
class ConformanceReport:
    suite_version: str
    ruleset: dict[str, object]
    seeds: tuple[int, ...]
    checks: tuple[CheckResult, ...]

    @property
    def verdict(self) -> str:
        if any(check.status is CheckStatus.FAIL for check in self.checks):
            return "fail"
        if any(check.status is CheckStatus.INCONCLUSIVE for check in self.checks):
            return "conditional_pass"
        return "pass"

    def as_dict(self) -> dict[str, object]:
        counts = {
            status.value: sum(check.status is status for check in self.checks)
            for status in CheckStatus
        }
        return {
            "schema_version": CONFORMANCE_REPORT_VERSION,
            "suite_version": self.suite_version,
            "verdict": self.verdict,
            "ruleset": self.ruleset,
            "seeds": list(self.seeds),
            "summary": counts,
            "checks": [check.as_dict() for check in self.checks],
        }


def run_environment_conformance(
    factory: Callable[[], EnvironmentAdapter],
    *,
    seeds: Sequence[int] = (1, 7),
    max_steps: int = 4096,
) -> ConformanceReport:
    normalized_seeds = tuple(seeds)
    if not normalized_seeds:
        raise ValueError("At least one conformance seed is required")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    environment = factory()
    ruleset = environment.ruleset.as_dict()
    checks = tuple(
        _run_check(check_id, operation)
        for check_id, operation in (
            ("identity", lambda: _check_identity(factory, normalized_seeds[0])),
            ("reset", lambda: _check_reset(factory, normalized_seeds[0])),
            ("legal_actions", lambda: _check_legal_actions(factory, normalized_seeds[0])),
            ("stepping", lambda: _check_stepping(factory, normalized_seeds[0])),
            ("illegal_action", lambda: _check_illegal_action(factory, normalized_seeds[0])),
            ("faithful_clone", lambda: _check_faithful_clone(factory, normalized_seeds[0])),
            (
                "hidden_resampling",
                lambda: _check_hidden_resampling(factory, normalized_seeds[0], max_steps),
            ),
            ("replay", lambda: _check_replay(factory, normalized_seeds[0], max_steps)),
            (
                "public_state_isolation",
                lambda: _check_public_state(factory, normalized_seeds, max_steps),
            ),
            (
                "terminal_reward",
                lambda: _check_terminal_reward(factory, normalized_seeds, max_steps),
            ),
        )
    )
    return ConformanceReport(
        suite_version=CONFORMANCE_SUITE_VERSION,
        ruleset=ruleset,
        seeds=normalized_seeds,
        checks=checks,
    )


def capture_conformance_trace(
    environment: EnvironmentAdapter,
    *,
    seed: int,
    fixture_id: str,
    max_steps: int = 4096,
) -> dict[str, object]:
    observation = environment.reset(seed)
    steps: list[dict[str, object]] = []
    for decision_index in range(max_steps):
        if _is_terminal(observation):
            break
        legal_actions = tuple(environment.legal_actions())
        action = _select_action(legal_actions)
        transition = environment.step(action)
        steps.append(
            {
                "decision_index": decision_index,
                "observation": observation.as_dict(),
                "legal_actions": [candidate.as_dict() for candidate in legal_actions],
                "selected_action": action.as_dict(),
                "next_observation": transition.next_observation.as_dict(),
                "reward": transition.reward,
                "terminal": transition.terminal,
                "victory": transition.victory,
            }
        )
        observation = transition.next_observation
    if not _is_terminal(observation):
        raise RuntimeError(f"Trace did not terminate within {max_steps} decisions")
    return {
        "schema_version": CONFORMANCE_TRACE_VERSION,
        "fixture_id": fixture_id,
        "ruleset": environment.ruleset.as_dict(),
        "seed": seed,
        "steps": steps,
        "outcome": {
            "terminal": True,
            "victory": bool(observation.public_state.get("victory")),
            "decisions": len(steps),
            "final_state_hash": observation.state_hash,
        },
    }


def compare_conformance_traces(
    reference: object,
    candidate: object,
    *,
    max_divergences: int = 100,
) -> dict[str, object]:
    if max_divergences <= 0:
        raise ValueError("max_divergences must be positive")
    expected = _trace_mapping(reference, "reference")
    actual = _trace_mapping(candidate, "candidate")
    errors = _comparability_errors(expected, actual)
    if errors:
        return {
            "schema_version": DIFFERENTIAL_REPORT_VERSION,
            "verdict": "incomparable",
            "reference_fixture_id": expected["fixture_id"],
            "candidate_fixture_id": actual["fixture_id"],
            "comparability_errors": errors,
            "compared_decisions": 0,
            "mismatch_count": 0,
            "divergences_truncated": False,
            "divergences": [],
        }

    divergences: list[dict[str, object]] = []
    _collect_differences(
        expected["steps"],
        actual["steps"],
        "steps",
        divergences,
        max_divergences + 1,
    )
    _collect_differences(
        expected["outcome"],
        actual["outcome"],
        "outcome",
        divergences,
        max_divergences + 1,
    )
    divergences_truncated = len(divergences) > max_divergences
    reported_divergences = divergences[:max_divergences]
    expected_steps = _sequence(expected["steps"], "reference.steps")
    actual_steps = _sequence(actual["steps"], "candidate.steps")
    return {
        "schema_version": DIFFERENTIAL_REPORT_VERSION,
        "verdict": "exact_match" if not reported_divergences else "diverged",
        "reference_fixture_id": expected["fixture_id"],
        "candidate_fixture_id": actual["fixture_id"],
        "comparability_errors": [],
        "compared_decisions": min(len(expected_steps), len(actual_steps)),
        "reference_decisions": len(expected_steps),
        "candidate_decisions": len(actual_steps),
        "mismatch_count": len(reported_divergences),
        "divergences_truncated": divergences_truncated,
        "divergences": reported_divergences,
    }


def trace_sha256(trace: object) -> str:
    encoded = json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _run_check(check_id: str, operation: Callable[[], CheckResult]) -> CheckResult:
    try:
        return operation()
    except Exception as error:  # noqa: BLE001 - a failed backend must become report data.
        return CheckResult(
            check_id=check_id,
            status=CheckStatus.FAIL,
            detail=f"{type(error).__name__}: {error}",
            metrics={"exception_type": type(error).__name__},
        )


def _check_identity(factory: Callable[[], EnvironmentAdapter], seed: int) -> CheckResult:
    environment = factory()
    observation = environment.reset(seed)
    if environment.patch_id != environment.ruleset.patch_id:
        raise AssertionError("environment patch_id differs from ruleset patch_id")
    if observation.patch_id != environment.ruleset.patch_id:
        raise AssertionError("observation patch_id differs from ruleset patch_id")
    return _passed("identity", "Environment, ruleset, and observation patch identities agree")


def _check_reset(factory: Callable[[], EnvironmentAdapter], seed: int) -> CheckResult:
    first = factory()
    second = factory()
    first_observation = first.reset(seed)
    second_observation = second.reset(seed)
    _validate_observation(first_observation)
    _validate_observation(second_observation)
    if first_observation.as_dict() != second_observation.as_dict():
        raise AssertionError("same-seed reset produced different observations")
    if _action_dicts(first.legal_actions()) != _action_dicts(second.legal_actions()):
        raise AssertionError("same-seed reset produced different legal actions")
    return _passed("reset", "Same-seed resets produce identical public states and actions")


def _check_legal_actions(factory: Callable[[], EnvironmentAdapter], seed: int) -> CheckResult:
    environment = factory()
    observation = environment.reset(seed)
    actions = tuple(environment.legal_actions())
    if not _is_terminal(observation) and not actions:
        raise AssertionError("non-terminal state has no legal actions")
    action_ids = [action.action_id for action in actions]
    if len(action_ids) != len(set(action_ids)):
        raise AssertionError("legal action IDs are not unique")
    json.dumps(_action_dicts(actions))
    if _action_dicts(actions) != _action_dicts(environment.legal_actions()):
        raise AssertionError("reading legal actions is not idempotent")
    return _passed(
        "legal_actions",
        "Legal actions are non-empty when required, unique, serializable, and idempotent",
        action_count=len(actions),
    )


def _check_stepping(factory: Callable[[], EnvironmentAdapter], seed: int) -> CheckResult:
    environment = factory()
    observation = environment.reset(seed)
    legal_actions = tuple(environment.legal_actions())
    action = _select_action(legal_actions)
    transition = environment.step(action)
    if transition.observation != observation:
        raise AssertionError("transition does not link from the current observation")
    if transition.action != action:
        raise AssertionError("transition does not record the selected legal action")
    _validate_observation(transition.next_observation)
    return _passed("stepping", "A legal step preserves transition linkage and state validity")


def _check_illegal_action(factory: Callable[[], EnvironmentAdapter], seed: int) -> CheckResult:
    environment = factory()
    observation = environment.reset(seed)
    baseline = environment.clone(resample_hidden=False)
    legal_before = _action_dicts(environment.legal_actions())
    invalid = LegalAction("__spireshift_invalid__", "invalid", {})
    try:
        environment.step(invalid)
    except (ValueError, RuntimeError):
        pass
    else:
        raise AssertionError("environment accepted an action outside the legal set")
    if legal_before != _action_dicts(environment.legal_actions()):
        raise AssertionError("rejected action mutated the environment")
    if observation.state_hash != _state_hash(observation.public_state):
        raise AssertionError("state changed while rejecting an illegal action")
    action = _select_action(environment.legal_actions())
    if environment.step(action).as_dict() != baseline.step(action).as_dict():
        raise AssertionError("rejected action changed a later transition")
    return _passed("illegal_action", "Illegal actions are rejected without state mutation")


def _check_faithful_clone(factory: Callable[[], EnvironmentAdapter], seed: int) -> CheckResult:
    environment = factory()
    environment.reset(seed)
    cloned = environment.clone(resample_hidden=False)
    original_actions = tuple(environment.legal_actions())
    cloned_actions = tuple(cloned.legal_actions())
    if _action_dicts(original_actions) != _action_dicts(cloned_actions):
        raise AssertionError("faithful clone changed legal actions")
    action = _select_action(original_actions)
    clone_transition = cloned.step(action)
    original_transition = environment.step(action)
    if clone_transition.as_dict() != original_transition.as_dict():
        raise AssertionError("faithful clone diverged after the same action")
    return _passed("faithful_clone", "Faithful clones are independent and step identically")


def _check_hidden_resampling(
    factory: Callable[[], EnvironmentAdapter], seed: int, max_steps: int
) -> CheckResult:
    resample_seeds = (17, 99, 991)
    for resample_seed in resample_seeds:
        environment = factory()
        environment.reset(seed)
        cloned = environment.clone(resample_hidden=True, seed=resample_seed)
        for step in range(max_steps):
            original_actions = tuple(environment.legal_actions())
            cloned_actions = tuple(cloned.legal_actions())
            if _action_dicts(original_actions) != _action_dicts(cloned_actions):
                return _passed(
                    "hidden_resampling",
                    "A resampled clone produced a different plausible successor",
                    divergence_step=step,
                    resample_seed=resample_seed,
                )
            if not original_actions:
                break
            action = _select_action(original_actions)
            original_transition = environment.step(action)
            clone_transition = cloned.step(action)
            if (
                original_transition.next_observation.as_dict()
                != clone_transition.next_observation.as_dict()
            ):
                return _passed(
                    "hidden_resampling",
                    "A resampled clone produced a different plausible successor",
                    divergence_step=step,
                    resample_seed=resample_seed,
                )
            if original_transition.terminal or clone_transition.terminal:
                break
    return CheckResult(
        check_id="hidden_resampling",
        status=CheckStatus.INCONCLUSIVE,
        detail="No hidden-outcome divergence was observed within the configured trajectory",
        metrics={"max_steps": max_steps, "resample_seeds": list(resample_seeds)},
    )


def _check_replay(
    factory: Callable[[], EnvironmentAdapter], seed: int, max_steps: int
) -> CheckResult:
    source = factory()
    transitions = _rollout(source, seed, max_steps)
    replay = factory()
    observation = replay.reset(seed)
    for index, expected in enumerate(transitions):
        if observation.as_dict() != expected.observation.as_dict():
            raise AssertionError(f"replay observation diverged at decision {index}")
        legal = {action.action_id: action for action in replay.legal_actions()}
        if expected.action.action_id not in legal:
            raise AssertionError(f"recorded action is not legal at decision {index}")
        actual = replay.step(legal[expected.action.action_id])
        if actual.as_dict() != expected.as_dict():
            raise AssertionError(f"replay transition diverged at decision {index}")
        observation = actual.next_observation
    return _passed(
        "replay",
        "Recorded actions reproduce every public transition exactly",
        decisions=len(transitions),
    )


def _check_public_state(
    factory: Callable[[], EnvironmentAdapter], seeds: tuple[int, ...], max_steps: int
) -> CheckResult:
    inspected = 0
    for seed in seeds:
        environment = factory()
        observation = environment.reset(seed)
        for _ in range(max_steps + 1):
            _validate_observation(observation)
            forbidden = sorted(_forbidden_paths(observation.public_state))
            if forbidden:
                raise AssertionError(f"public state exposes forbidden fields: {forbidden}")
            inspected += 1
            if _is_terminal(observation):
                break
            transition = environment.step(_select_action(environment.legal_actions()))
            observation = transition.next_observation
        else:
            raise AssertionError(f"seed {seed} did not terminate within {max_steps} decisions")
    return _passed(
        "public_state_isolation",
        "Public observations are serializable, self-hashed, and contain no forbidden field names",
        observations=inspected,
    )


def _check_terminal_reward(
    factory: Callable[[], EnvironmentAdapter], seeds: tuple[int, ...], max_steps: int
) -> CheckResult:
    victories = 0
    losses = 0
    decisions = 0
    for seed in seeds:
        transitions = _rollout(factory(), seed, max_steps)
        if not transitions or not transitions[-1].terminal:
            raise AssertionError(f"seed {seed} did not reach a terminal transition")
        for transition in transitions:
            if transition.reward == 1.0 and not (transition.terminal and transition.victory):
                raise AssertionError("positive reward appeared outside terminal victory")
            if transition.reward not in (0.0, 1.0):
                raise AssertionError("environment emitted a shaped reward")
        if transitions[-1].victory:
            victories += 1
        else:
            losses += 1
        decisions += len(transitions)
    return _passed(
        "terminal_reward",
        "Rewards are binary and positive only on terminal victory",
        seeds=len(seeds),
        decisions=decisions,
        victories=victories,
        losses=losses,
    )


def _rollout(environment: EnvironmentAdapter, seed: int, max_steps: int) -> list[Transition]:
    observation = environment.reset(seed)
    transitions: list[Transition] = []
    for _ in range(max_steps):
        if _is_terminal(observation):
            break
        action = _select_action(environment.legal_actions())
        transition = environment.step(action)
        transitions.append(transition)
        observation = transition.next_observation
        if transition.terminal:
            break
    if not transitions or not transitions[-1].terminal:
        raise AssertionError(f"rollout did not terminate within {max_steps} decisions")
    return transitions


def _select_action(actions: Sequence[LegalAction]) -> LegalAction:
    if not actions:
        raise AssertionError("non-terminal environment returned no legal actions")
    return actions[-1]


def _validate_observation(observation: Observation) -> None:
    if observation.schema_version != "observation-v1":
        raise AssertionError(f"unsupported observation schema: {observation.schema_version}")
    json.dumps(observation.public_state, sort_keys=True)
    expected_hash = _state_hash(observation.public_state)
    if observation.state_hash != expected_hash:
        raise AssertionError(
            "observation state hash mismatch: "
            f"expected {expected_hash}, got {observation.state_hash}"
        )


def _state_hash(public_state: object) -> str:
    encoded = json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _is_terminal(observation: Observation) -> bool:
    return bool(observation.public_state.get("terminal"))


def _action_dicts(actions: Sequence[LegalAction]) -> list[dict[str, Any]]:
    return [action.as_dict() for action in actions]


def _forbidden_paths(value: object, path: str = "public_state") -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold().replace("-", "_").replace(" ", "_")
            child_path = f"{path}.{key}"
            tokens = set(normalized.split("_"))
            if (
                normalized in _FORBIDDEN_PUBLIC_KEYS
                or normalized.startswith("privileged_")
                or tokens.intersection({"rng", "seed", "hidden", "future"})
            ):
                found.add(child_path)
            found.update(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(_forbidden_paths(child, f"{path}[{index}]"))
    return found


def _passed(check_id: str, detail: str, **metrics: object) -> CheckResult:
    return CheckResult(check_id, CheckStatus.PASS, detail, metrics)


def _trace_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} trace must be an object")
    mapping = cast(dict[str, object], value)
    if mapping.get("schema_version") != CONFORMANCE_TRACE_VERSION:
        raise ValueError(f"{label} trace has an unsupported schema")
    required = {"schema_version", "fixture_id", "ruleset", "seed", "steps", "outcome"}
    if set(mapping) != required:
        raise ValueError(f"{label} trace fields differ from {sorted(required)}")
    return mapping


def _comparability_errors(reference: dict[str, object], candidate: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if reference["seed"] != candidate["seed"]:
        errors.append("seed_mismatch")
    reference_ruleset = _object_mapping(reference["ruleset"], "reference.ruleset")
    candidate_ruleset = _object_mapping(candidate["ruleset"], "candidate.ruleset")
    if reference_ruleset.get("patch_id") != candidate_ruleset.get("patch_id"):
        errors.append("patch_mismatch")
    reference_interface = _object_mapping(
        reference_ruleset.get("interface"), "reference.ruleset.interface"
    )
    candidate_interface = _object_mapping(
        candidate_ruleset.get("interface"), "candidate.ruleset.interface"
    )
    for field in ("observation_schema", "action_schema", "information_policy_id"):
        if reference_interface.get(field) != candidate_interface.get(field):
            errors.append(f"{field}_mismatch")
    return errors


def _collect_differences(
    expected: object,
    actual: object,
    path: str,
    divergences: list[dict[str, object]],
    limit: int,
) -> None:
    if len(divergences) >= limit:
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected) | set(actual))
        for key in keys:
            if key not in expected:
                divergences.append(
                    {"path": f"{path}.{key}", "expected": None, "actual": actual[key]}
                )
            elif key not in actual:
                divergences.append(
                    {"path": f"{path}.{key}", "expected": expected[key], "actual": None}
                )
            else:
                _collect_differences(
                    expected[key], actual[key], f"{path}.{key}", divergences, limit
                )
            if len(divergences) >= limit:
                return
        return
    if isinstance(expected, list) and isinstance(actual, list):
        for index in range(max(len(expected), len(actual))):
            if index >= len(expected):
                divergences.append(
                    {"path": f"{path}[{index}]", "expected": None, "actual": actual[index]}
                )
            elif index >= len(actual):
                divergences.append(
                    {"path": f"{path}[{index}]", "expected": expected[index], "actual": None}
                )
            else:
                _collect_differences(
                    expected[index], actual[index], f"{path}[{index}]", divergences, limit
                )
            if len(divergences) >= limit:
                return
        return
    if expected != actual:
        divergences.append({"path": path, "expected": expected, "actual": actual})


def _object_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _sequence(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value
