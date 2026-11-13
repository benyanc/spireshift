from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.liveness import PublicNoOpActionGuard
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

TERMINAL_DISCOVERY_CONFIG_SCHEMA_VERSION = "terminal-trajectory-discovery-config-v1"
TERMINAL_DISCOVERY_CASE_SCHEMA_VERSION = "terminal-trajectory-discovery-case-v1"
TERMINAL_DISCOVERY_REPORT_SCHEMA_VERSION = "terminal-trajectory-discovery-v1"
TERMINAL_DISCOVERY_VERIFICATION_SCHEMA_VERSION = "terminal-trajectory-discovery-verification-v1"
EXPLORATION_CONTROLLER_ID = "sparse-policy-exploration-v1"
CLAIM_SCOPE = "train_only_terminal_trajectory_discovery"


@dataclass(frozen=True, slots=True)
class ExplorationProfile:
    name: str
    exploration_rate: float
    temperature: float

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", self.name) is None:
            raise ValueError("Exploration profile name must be lowercase kebab case")
        if not math.isfinite(self.exploration_rate) or not 0.0 < self.exploration_rate <= 1.0:
            raise ValueError("Exploration rate must be greater than zero and at most one")
        if not math.isfinite(self.temperature) or self.temperature <= 0.0:
            raise ValueError("Exploration temperature must be positive")

    def body(self) -> dict[str, object]:
        return {
            "name": self.name,
            "exploration_rate": self.exploration_rate,
            "temperature": self.temperature,
        }

    @property
    def profile_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "profile_id": self.profile_id}

    @classmethod
    def from_mapping(cls, value: object) -> ExplorationProfile:
        document = _mapping(value, "exploration profile")
        if set(document) != {"name", "exploration_rate", "temperature", "profile_id"}:
            raise ValueError("Exploration profile fields differ")
        profile = cls(
            name=_string(document.get("name"), "profile name"),
            exploration_rate=_number(document.get("exploration_rate"), "exploration rate"),
            temperature=_number(document.get("temperature"), "temperature"),
        )
        if document.get("profile_id") != profile.profile_id:
            raise ValueError("Exploration profile identity mismatch")
        return profile


@dataclass(frozen=True, slots=True)
class TerminalDiscoveryConfig:
    split_manifest_id: str
    ruleset_manifest_id: str
    model_id: str
    training_report_id: str
    run_offset: int
    run_count: int
    attempts_per_profile: int
    workers: int
    maximum_decisions_per_run: int
    cycle_repetition_threshold: int
    liveness_tail_length: int
    no_op_fallback_threshold: int
    sampling_salt: str
    profiles: tuple[ExplorationProfile, ...]
    objective_id: str = "terminal-victory-v1"
    partition: str = SplitName.TRAIN.value

    def __post_init__(self) -> None:
        if self.partition != SplitName.TRAIN.value:
            raise ValueError("Terminal discovery may use only train runs")
        if self.objective_id != "terminal-victory-v1":
            raise ValueError("Terminal discovery must preserve terminal victory")
        for name, value, minimum in (
            ("run_offset", self.run_offset, 0),
            ("run_count", self.run_count, 1),
            ("attempts_per_profile", self.attempts_per_profile, 1),
            ("workers", self.workers, 1),
            ("maximum_decisions_per_run", self.maximum_decisions_per_run, 1),
            ("cycle_repetition_threshold", self.cycle_repetition_threshold, 2),
            ("liveness_tail_length", self.liveness_tail_length, 1),
            ("no_op_fallback_threshold", self.no_op_fallback_threshold, 1),
        ):
            if isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")
        if not self.sampling_salt:
            raise ValueError("Terminal discovery sampling salt must be non-empty")
        if not self.profiles:
            raise ValueError("Terminal discovery needs at least one exploration profile")
        names = [profile.name for profile in self.profiles]
        if len(names) != len(set(names)):
            raise ValueError("Terminal discovery profile names must be unique")

    def body(self) -> dict[str, object]:
        return {
            "schema_version": TERMINAL_DISCOVERY_CONFIG_SCHEMA_VERSION,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "model_id": self.model_id,
            "training_report_id": self.training_report_id,
            "partition": self.partition,
            "run_offset": self.run_offset,
            "run_count": self.run_count,
            "attempts_per_profile": self.attempts_per_profile,
            "workers": self.workers,
            "maximum_decisions_per_run": self.maximum_decisions_per_run,
            "cycle_repetition_threshold": self.cycle_repetition_threshold,
            "liveness_tail_length": self.liveness_tail_length,
            "no_op_fallback_threshold": self.no_op_fallback_threshold,
            "exploration_controller_id": EXPLORATION_CONTROLLER_ID,
            "sampling_salt": self.sampling_salt,
            "profiles": [profile.as_dict() for profile in self.profiles],
        }

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "config_id": self.config_id}

    @classmethod
    def from_mapping(cls, value: object) -> TerminalDiscoveryConfig:
        document = _mapping(value, "terminal discovery config")
        expected = {
            "schema_version",
            "config_id",
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "model_id",
            "training_report_id",
            "partition",
            "run_offset",
            "run_count",
            "attempts_per_profile",
            "workers",
            "maximum_decisions_per_run",
            "cycle_repetition_threshold",
            "liveness_tail_length",
            "no_op_fallback_threshold",
            "exploration_controller_id",
            "sampling_salt",
            "profiles",
        }
        if set(document) != expected:
            raise ValueError("Terminal discovery config fields differ")
        if document.get("schema_version") != TERMINAL_DISCOVERY_CONFIG_SCHEMA_VERSION:
            raise ValueError("Terminal discovery config schema differs")
        if document.get("exploration_controller_id") != EXPLORATION_CONTROLLER_ID:
            raise ValueError("Terminal discovery exploration controller differs")
        raw_profiles = document.get("profiles")
        if not isinstance(raw_profiles, list):
            raise ValueError("Terminal discovery profiles must be an array")
        config = cls(
            split_manifest_id=_string(document.get("split_manifest_id"), "split manifest ID"),
            ruleset_manifest_id=_string(document.get("ruleset_manifest_id"), "ruleset ID"),
            objective_id=_string(document.get("objective_id"), "objective ID"),
            model_id=_string(document.get("model_id"), "model ID"),
            training_report_id=_string(document.get("training_report_id"), "training report ID"),
            partition=_string(document.get("partition"), "partition"),
            run_offset=_integer(document.get("run_offset"), "run offset"),
            run_count=_integer(document.get("run_count"), "run count"),
            attempts_per_profile=_integer(
                document.get("attempts_per_profile"), "attempts per profile"
            ),
            workers=_integer(document.get("workers"), "workers"),
            maximum_decisions_per_run=_integer(
                document.get("maximum_decisions_per_run"), "maximum decisions"
            ),
            cycle_repetition_threshold=_integer(
                document.get("cycle_repetition_threshold"), "cycle threshold"
            ),
            liveness_tail_length=_integer(
                document.get("liveness_tail_length"), "liveness tail length"
            ),
            no_op_fallback_threshold=_integer(
                document.get("no_op_fallback_threshold"), "fallback threshold"
            ),
            sampling_salt=_string(document.get("sampling_salt"), "sampling salt"),
            profiles=tuple(ExplorationProfile.from_mapping(profile) for profile in raw_profiles),
        )
        if document.get("config_id") != config.config_id:
            raise ValueError("Terminal discovery config identity mismatch")
        return config


@dataclass(frozen=True, slots=True)
class TerminalDiscoveryResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


def load_terminal_discovery_config(path: Path) -> TerminalDiscoveryConfig:
    return TerminalDiscoveryConfig.from_mapping(_load_object(path, "terminal discovery config"))


def run_terminal_trajectory_discovery(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    training_report_id: str,
    config: TerminalDiscoveryConfig,
    output_directory: Path,
    resume: bool = False,
    now: Callable[[], str] | None = None,
) -> TerminalDiscoveryResult:
    _validate_inputs(
        ruleset=ruleset,
        policy=policy,
        split_manifest=split_manifest,
        training_report_id=training_report_id,
        config=config,
    )
    seeds = split_manifest.seeds(SplitName.TRAIN)[
        config.run_offset : config.run_offset + config.run_count
    ]
    if len(seeds) != config.run_count:
        raise ValueError("Terminal discovery seed window exceeds the train partition")
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists() and not resume:
        raise FileExistsError(f"Terminal discovery output already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "terminal-trajectory-discovery.json"
    if report_path.exists():
        raise FileExistsError(f"Terminal discovery report already exists: {report_path}")

    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, ExplorationProfile, int, Path]] = []
    for seed in seeds:
        for profile in config.profiles:
            for attempt in range(config.attempts_per_profile):
                path = _case_path(output_directory, seed, profile.name, attempt)
                if path.exists():
                    cases.append(
                        _load_case(
                            path,
                            seed=seed,
                            profile=profile,
                            attempt=attempt,
                            config=config,
                            policy=policy,
                        )
                    )
                else:
                    pending.append((seed, profile, attempt, path))

    maximum_workers = min(config.workers, max(1, len(pending)))
    with ThreadPoolExecutor(max_workers=maximum_workers) as executor:
        futures: dict[Future[dict[str, Any]], tuple[int, ExplorationProfile, int, Path]] = {}
        for seed, profile, attempt, path in pending:
            future = executor.submit(
                _run_case,
                environment_factory=environment_factory,
                ruleset=ruleset,
                policy=policy,
                config=config,
                seed=seed,
                profile=profile,
                attempt=attempt,
            )
            futures[future] = (seed, profile, attempt, path)
        for future in as_completed(futures):
            path = futures[future][-1]
            case = future.result()
            write_model_artifact(case, path, label="terminal discovery case")
            cases.append(case)

    ordered = sorted(
        cases,
        key=lambda case: (
            int(case["seed"]),
            str(case["profile_name"]),
            int(case["attempt"]),
        ),
    )
    expected_cases = config.run_count * len(config.profiles) * config.attempts_per_profile
    if len(ordered) != expected_cases:
        raise RuntimeError("Terminal discovery did not produce every configured case")
    summary = _summary(ordered, profiles=config.profiles)
    case_references = [_case_reference(output_directory, case) for case in ordered]
    winning_references = [
        reference
        for reference, case in zip(case_references, ordered, strict=True)
        if case["status"] == "completed" and case["victory"] is True
    ]
    victories = int(summary["overall"]["victories"])
    terminal_runs = int(summary["overall"]["terminal_runs"])
    body: dict[str, Any] = {
        "schema_version": TERMINAL_DISCOVERY_REPORT_SCHEMA_VERSION,
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "config_id": config.config_id,
        "model_id": policy.model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "configuration": config.as_dict(),
        "cases": case_references,
        "winning_cases": winning_references,
        "summary": summary,
        "readiness": {
            "terminal_positive_trajectories_found": victories > 0,
            "terminal_value_head_unblocked": 0 < victories < terminal_runs,
            "recommended_next_step": (
                "replay_and_label_winning_trajectories"
                if victories > 0
                else "escalate_to_run_level_search"
            ),
        },
        "claim_scope": CLAIM_SCOPE,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    write_model_artifact(report, report_path, label="terminal trajectory discovery")
    return TerminalDiscoveryResult(
        successful=int(summary["overall"]["failed_runs"]) == 0,
        report_path=report_path,
        report=report,
    )


def verify_terminal_trajectory_discovery(
    report_path: Path,
    *,
    config: TerminalDiscoveryConfig,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    errors: list[str] = []
    report_id: str | None = None
    verified_cases = 0
    try:
        report = _load_object(report_path, "terminal trajectory discovery")
        report_id = report.get("report_id") if isinstance(report.get("report_id"), str) else None
        body = {key: value for key, value in report.items() if key != "report_id"}
        if report_id != manifest_identifier(body):
            raise ValueError("Terminal discovery report identity mismatch")
        expected = {
            "schema_version": TERMINAL_DISCOVERY_REPORT_SCHEMA_VERSION,
            "config_id": config.config_id,
            "model_id": config.model_id,
            "training_report_id": config.training_report_id,
            "split_manifest_id": split_manifest.manifest_id,
            "partition": SplitName.TRAIN.value,
            "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
            "objective_id": split_manifest.objective_id,
            "configuration": config.as_dict(),
            "claim_scope": CLAIM_SCOPE,
        }
        if any(report.get(key) != value for key, value in expected.items()):
            raise ValueError("Terminal discovery report provenance differs")
        seeds = split_manifest.seeds(SplitName.TRAIN)[
            config.run_offset : config.run_offset + config.run_count
        ]
        if len(seeds) != config.run_count:
            raise ValueError("Terminal discovery seed window exceeds the train partition")
        references = report.get("cases")
        if not isinstance(references, list):
            raise ValueError("Terminal discovery case references are missing")
        root = report_path.expanduser().resolve().parent
        cases: list[dict[str, Any]] = []
        coordinates: set[tuple[int, str, int]] = set()
        profiles = {profile.name: profile for profile in config.profiles}
        for raw_reference in references:
            reference = _mapping(raw_reference, "terminal discovery case reference")
            seed = _integer(reference.get("seed"), "case seed")
            profile_name = _string(reference.get("profile_name"), "profile name")
            attempt = _integer(reference.get("attempt"), "attempt")
            profile = profiles.get(profile_name)
            if profile is None:
                raise ValueError("Terminal discovery case uses an unknown profile")
            coordinate = (seed, profile_name, attempt)
            if coordinate in coordinates:
                raise ValueError("Terminal discovery repeats a case coordinate")
            coordinates.add(coordinate)
            relative_path = Path(_string(reference.get("path"), "case path"))
            case_path = (root / relative_path).resolve()
            if root not in case_path.parents:
                raise ValueError("Terminal discovery case escapes its report root")
            case = _load_case_document(
                case_path,
                seed=seed,
                profile=profile,
                attempt=attempt,
                config=config,
            )
            if reference.get("case_id") != case["case_id"]:
                raise ValueError("Terminal discovery case reference identity mismatch")
            cases.append(case)
            verified_cases += 1
        expected_coordinates = {
            (seed, profile.name, attempt)
            for seed in seeds
            for profile in config.profiles
            for attempt in range(config.attempts_per_profile)
        }
        if coordinates != expected_coordinates:
            raise ValueError("Terminal discovery case coverage differs")
        ordered = sorted(
            cases,
            key=lambda case: (
                int(case["seed"]),
                str(case["profile_name"]),
                int(case["attempt"]),
            ),
        )
        expected_summary = _summary(ordered, profiles=config.profiles)
        if report.get("summary") != expected_summary:
            raise ValueError("Terminal discovery summary differs from its cases")
        expected_winners = [
            _case_reference(root, case)
            for case in ordered
            if case["status"] == "completed" and case["victory"] is True
        ]
        if report.get("winning_cases") != expected_winners:
            raise ValueError("Terminal discovery winning-case references differ")
        victories = int(expected_summary["overall"]["victories"])
        terminal_runs = int(expected_summary["overall"]["terminal_runs"])
        expected_readiness = {
            "terminal_positive_trajectories_found": victories > 0,
            "terminal_value_head_unblocked": 0 < victories < terminal_runs,
            "recommended_next_step": (
                "replay_and_label_winning_trajectories"
                if victories > 0
                else "escalate_to_run_level_search"
            ),
        }
        if report.get("readiness") != expected_readiness:
            raise ValueError("Terminal discovery readiness differs from its cases")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    body = {
        "schema_version": TERMINAL_DISCOVERY_VERIFICATION_SCHEMA_VERSION,
        "valid": not errors,
        "report_id": report_id,
        "config_id": config.config_id,
        "verified_cases": verified_cases,
        "errors": errors,
    }
    return {**body, "verification_id": manifest_identifier(body)}


def _run_case(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    config: TerminalDiscoveryConfig,
    seed: int,
    profile: ExplorationProfile,
    attempt: int,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Terminal discovery environment ruleset changed")
        observation = environment.reset(seed)
        guard = PublicNoOpActionGuard(
            repetition_threshold=config.no_op_fallback_threshold,
            event_limit=config.liveness_tail_length,
        )
        records: list[dict[str, Any]] = []
        action_ids: list[str] = []
        transition_occurrences: dict[tuple[str, str, str], list[int]] = {}
        unchanged_counts: dict[tuple[str, str, str], int] = {}
        trace_tail: list[dict[str, Any]] = []
        maximum_state_action_repetitions = 0
        state_action_counts: dict[tuple[str, str], int] = {}
        maximum_public_transition_repetitions = 0
        detected_transition: tuple[str, str, str] | None = None
        detected_occurrences: list[int] = []
        detected_decision_type: str | None = None
        maximum_floor = _public_integer(observation.public_state.get("floor")) or 0
        maximum_act: int | str | None = observation.public_state.get("act")
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        termination_reason = "terminal" if terminal else "decision_limit"
        exploration_opportunities = 0
        exploration_invocations = 0
        non_argmax_actions = 0

        for decision_index in range(config.maximum_decisions_per_run):
            if terminal:
                break
            legal_actions = tuple(environment.legal_actions())
            if not legal_actions:
                raise RuntimeError("Nonterminal terminal-discovery state has no legal actions")
            eligible_actions = guard.eligible_actions(observation, legal_actions)
            decision = policy.predict(observation, eligible_actions)
            argmax_index = decision.selected_candidate_index
            selected_index = argmax_index
            exploration_invoked = False
            if len(eligible_actions) > 1:
                exploration_opportunities += 1
                gate = _deterministic_fraction(
                    config.sampling_salt,
                    policy.model_id,
                    seed,
                    profile.profile_id,
                    attempt,
                    decision_index,
                    observation.state_hash,
                    "gate",
                )
                if gate < profile.exploration_rate:
                    exploration_invoked = True
                    exploration_invocations += 1
                    selected_index = _sample_alternative_index(
                        policy=decision.policy,
                        argmax_index=argmax_index,
                        temperature=profile.temperature,
                        sample=_deterministic_fraction(
                            config.sampling_salt,
                            policy.model_id,
                            seed,
                            profile.profile_id,
                            attempt,
                            decision_index,
                            observation.state_hash,
                            "alternative",
                        ),
                    )
            action = eligible_actions[selected_index]
            if selected_index != argmax_index:
                non_argmax_actions += 1
            if action not in legal_actions:
                raise RuntimeError("Terminal discovery selected an illegal action")
            source = observation
            transition = environment.step(action)
            observation = transition.next_observation
            guard.observe_transition(
                observation=source,
                action=action,
                next_observation=observation,
                decision_index=decision_index,
            )
            action_ids.append(action.action_id)
            key = (source.state_hash, action.action_id, observation.state_hash)
            occurrences = transition_occurrences.setdefault(key, [])
            occurrences.append(decision_index)
            state_action = (source.state_hash, action.action_id)
            state_action_counts[state_action] = state_action_counts.get(state_action, 0) + 1
            maximum_state_action_repetitions = max(
                maximum_state_action_repetitions, state_action_counts[state_action]
            )
            if source.state_hash == observation.state_hash:
                unchanged_counts[key] = unchanged_counts.get(key, 0) + 1
            maximum_public_transition_repetitions = max(
                maximum_public_transition_repetitions, len(occurrences)
            )
            trace_entry = {
                "decision_index": decision_index,
                "state_hash": source.state_hash,
                "decision_type": source.decision_type.value,
                "action_id": action.action_id,
                "next_state_hash": observation.state_hash,
                "public_state_changed": source.state_hash != observation.state_hash,
            }
            trace_tail.append(trace_entry)
            if len(trace_tail) > config.liveness_tail_length:
                del trace_tail[0]
            records.append(
                {
                    "decision_index": decision_index,
                    "decision_type": source.decision_type.value,
                    "source_state_hash": source.state_hash,
                    "source_floor": _public_integer(source.public_state.get("floor")),
                    "source_act": source.public_state.get("act"),
                    "legal_action_count": len(legal_actions),
                    "eligible_action_count": len(eligible_actions),
                    "candidate_action_ids": list(decision.source_action_ids),
                    "policy": [_artifact_float(value) for value in decision.policy],
                    "argmax_candidate_index": argmax_index,
                    "argmax_action_id": eligible_actions[argmax_index].action_id,
                    "selected_candidate_index": selected_index,
                    "selected_action_id": action.action_id,
                    "exploration_invoked": exploration_invoked,
                    "non_argmax_action": selected_index != argmax_index,
                    "next_state_hash": observation.state_hash,
                    "terminal_after_action": transition.terminal,
                    "victory_after_action": transition.victory,
                }
            )
            next_floor = _public_integer(observation.public_state.get("floor")) or 0
            maximum_floor = max(maximum_floor, next_floor)
            maximum_act = _maximum_act(maximum_act, observation.public_state.get("act"))
            terminal = transition.terminal
            victory = transition.victory if terminal else False
            if terminal:
                termination_reason = "terminal"
                break
            if len(occurrences) >= config.cycle_repetition_threshold:
                detected_transition = key
                detected_occurrences = list(occurrences)
                detected_decision_type = source.decision_type.value
                termination_reason = "policy_cycle"
                break

        body: dict[str, Any] = {
            "schema_version": TERMINAL_DISCOVERY_CASE_SCHEMA_VERSION,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "profile_name": profile.name,
            "profile_id": profile.profile_id,
            "attempt": attempt,
            "model_id": policy.model_id,
            "policy_id": policy.policy_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "completed",
            "error": None,
            "decisions": records,
            "terminal": terminal,
            "victory": victory if terminal else False,
            "truncated": not terminal,
            "termination_reason": termination_reason,
            "maximum_floor": maximum_floor,
            "maximum_act": maximum_act,
            "final_state_hash": observation.state_hash,
            "action_trace_sha256": "sha256:"
            + hashlib.sha256("\n".join(action_ids).encode()).hexdigest(),
            "exploration": {
                "controller_id": EXPLORATION_CONTROLLER_ID,
                "opportunities": exploration_opportunities,
                "invocations": exploration_invocations,
                "non_argmax_actions": non_argmax_actions,
            },
            "liveness": _liveness_diagnostic(
                detected_transition=detected_transition,
                detected_occurrences=detected_occurrences,
                detected_decision_type=detected_decision_type,
                unchanged_counts=unchanged_counts,
                maximum_state_action_repetitions=maximum_state_action_repetitions,
                maximum_public_transition_repetitions=maximum_public_transition_repetitions,
                config=config,
                trace_tail=trace_tail,
            ),
            "fallback": guard.as_dict(),
        }
    except Exception as error:
        body = {
            "schema_version": TERMINAL_DISCOVERY_CASE_SCHEMA_VERSION,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "profile_name": profile.name,
            "profile_id": profile.profile_id,
            "attempt": attempt,
            "model_id": policy.model_id,
            "policy_id": policy.policy_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "decisions": [],
            "terminal": None,
            "victory": None,
            "truncated": None,
            "termination_reason": None,
            "maximum_floor": None,
            "maximum_act": None,
            "final_state_hash": None,
            "action_trace_sha256": None,
            "exploration": None,
            "liveness": None,
            "fallback": None,
        }
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                close()
    return {**body, "case_id": manifest_identifier(body)}


def _summary(
    cases: Sequence[dict[str, Any]], *, profiles: Sequence[ExplorationProfile]
) -> dict[str, Any]:
    return {
        "overall": _case_summary(cases),
        "profiles": {
            profile.name: _case_summary(
                [case for case in cases if case["profile_name"] == profile.name]
            )
            for profile in profiles
        },
    }


def _case_summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    terminal = [case for case in completed if case["terminal"] is True]
    victories = sum(case["victory"] is True for case in terminal)
    decisions = sum(len(case["decisions"]) for case in completed)
    opportunities = sum(int(case["exploration"]["opportunities"]) for case in completed)
    invocations = sum(int(case["exploration"]["invocations"]) for case in completed)
    non_argmax = sum(int(case["exploration"]["non_argmax_actions"]) for case in completed)
    return {
        "benchmark_denominator": len(cases),
        "completed_runs": len(completed),
        "failed_runs": len(cases) - len(completed),
        "terminal_runs": len(terminal),
        "truncated_runs": len(completed) - len(terminal),
        "policy_cycle_runs": sum(
            case["termination_reason"] == "policy_cycle" for case in completed
        ),
        "decision_limit_runs": sum(
            case["termination_reason"] == "decision_limit" for case in completed
        ),
        "victories": victories,
        "victory_rate": _artifact_float(victories / max(1, len(cases))),
        "mean_maximum_floor": _artifact_float(
            sum(int(case["maximum_floor"]) for case in completed) / max(1, len(completed))
        ),
        "maximum_floor": max((int(case["maximum_floor"]) for case in completed), default=0),
        "decisions": decisions,
        "exploration_opportunities": opportunities,
        "exploration_invocations": invocations,
        "non_argmax_actions": non_argmax,
        "realized_exploration_rate": _artifact_float(invocations / max(1, opportunities)),
        "unique_action_traces": len({str(case["action_trace_sha256"]) for case in completed}),
        "seeds_with_victory": len(
            {int(case["seed"]) for case in terminal if case["victory"] is True}
        ),
        "fallback_runs": sum(int(case["fallback"]["invocations"]) > 0 for case in completed),
        "fallback_invocations": sum(int(case["fallback"]["invocations"]) for case in completed),
        "nondegenerate_terminal_outcomes": 0 < victories < len(terminal),
    }


def _sample_alternative_index(
    *, policy: Sequence[float], argmax_index: int, temperature: float, sample: float
) -> int:
    weights = [
        0.0 if index == argmax_index else max(0.0, float(value)) ** (1.0 / temperature)
        for index, value in enumerate(policy)
    ]
    total = sum(weights)
    if total <= 0.0:
        weights = [0.0 if index == argmax_index else 1.0 for index in range(len(policy))]
        total = sum(weights)
    target = sample * total
    cumulative = 0.0
    selected = next(index for index in range(len(policy)) if index != argmax_index)
    for index, weight in enumerate(weights):
        cumulative += weight
        if weight > 0.0:
            selected = index
        if target < cumulative:
            return index
    return selected


def _deterministic_fraction(*parts: object) -> float:
    payload = "\n".join(str(part) for part in parts).encode()
    integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
    return integer / 2**64


def _liveness_diagnostic(
    *,
    detected_transition: tuple[str, str, str] | None,
    detected_occurrences: Sequence[int],
    detected_decision_type: str | None,
    unchanged_counts: dict[tuple[str, str, str], int],
    maximum_state_action_repetitions: int,
    maximum_public_transition_repetitions: int,
    config: TerminalDiscoveryConfig,
    trace_tail: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    cycle_detected = detected_transition is not None
    source_hash, action_id, next_hash = (
        detected_transition if detected_transition is not None else (None, None, None)
    )
    return {
        "schema_version": "policy-liveness-diagnostic-v1",
        "cycle_detected": cycle_detected,
        "classification": (
            "unchanged_public_state_action"
            if cycle_detected and source_hash == next_hash
            else "repeated_public_transition"
            if cycle_detected
            else None
        ),
        "repetition_threshold": config.cycle_repetition_threshold,
        "tail_limit": config.liveness_tail_length,
        "maximum_state_action_repetitions": maximum_state_action_repetitions,
        "maximum_public_transition_repetitions": maximum_public_transition_repetitions,
        "repeated_state_hash": source_hash,
        "repeated_action_id": action_id,
        "repeated_next_state_hash": next_hash,
        "decision_type": detected_decision_type,
        "first_occurrence_decision": detected_occurrences[0] if cycle_detected else None,
        "first_repeat_decision": detected_occurrences[1] if cycle_detected else None,
        "detection_decision": detected_occurrences[-1] if cycle_detected else None,
        "repeated_transition_occurrences": len(detected_occurrences) if cycle_detected else None,
        "unchanged_transition_occurrences": (
            unchanged_counts.get(detected_transition, 0)
            if detected_transition is not None
            else None
        ),
        "tail": list(trace_tail),
    }


def _validate_inputs(
    *,
    ruleset: RulesetIdentity,
    policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    training_report_id: str,
    config: TerminalDiscoveryConfig,
) -> None:
    expected = {
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "model_id": policy.model_id,
        "training_report_id": training_report_id,
        "objective_id": split_manifest.objective_id,
        "partition": SplitName.TRAIN.value,
    }
    if any(getattr(config, key) != value for key, value in expected.items()):
        raise ValueError("Terminal discovery config provenance differs")
    if split_manifest.ruleset_manifest_id != ruleset.manifest_id:
        raise ValueError("Terminal discovery split and environment rulesets differ")
    if split_manifest.objective_id != "terminal-victory-v1":
        raise ValueError("Terminal discovery split does not use terminal victory")
    if policy.ruleset != ruleset or policy.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Terminal discovery policy provenance differs")


def _load_case(
    path: Path,
    *,
    seed: int,
    profile: ExplorationProfile,
    attempt: int,
    config: TerminalDiscoveryConfig,
    policy: ProductionCheckpointPolicy,
) -> dict[str, Any]:
    case = _load_case_document(
        path,
        seed=seed,
        profile=profile,
        attempt=attempt,
        config=config,
    )
    if case.get("policy_id") != policy.policy_id:
        raise ValueError("Terminal discovery resumed policy differs")
    return case


def _load_case_document(
    path: Path,
    *,
    seed: int,
    profile: ExplorationProfile,
    attempt: int,
    config: TerminalDiscoveryConfig,
) -> dict[str, Any]:
    case = _load_object(path, "terminal discovery case")
    case_id = case.get("case_id")
    body = {key: value for key, value in case.items() if key != "case_id"}
    if case_id != manifest_identifier(body):
        raise ValueError("Terminal discovery case identity mismatch")
    expected = {
        "schema_version": TERMINAL_DISCOVERY_CASE_SCHEMA_VERSION,
        "config_id": config.config_id,
        "seed": seed,
        "partition": SplitName.TRAIN.value,
        "profile_name": profile.name,
        "profile_id": profile.profile_id,
        "attempt": attempt,
        "model_id": config.model_id,
        "policy_id": f"production-checkpoint-policy-v1:{config.model_id}",
        "ruleset_manifest_id": config.ruleset_manifest_id,
    }
    if any(case.get(key) != value for key, value in expected.items()):
        raise ValueError("Terminal discovery resumed case configuration differs")
    _validate_case(case, config=config)
    return case


def _validate_case(case: dict[str, Any], *, config: TerminalDiscoveryConfig) -> None:
    if case.get("status") not in ("completed", "failed"):
        raise ValueError("Terminal discovery case status differs")
    if case["status"] == "failed":
        if not isinstance(case.get("error"), str):
            raise ValueError("Failed terminal discovery case has no error")
        return
    records = case.get("decisions")
    if not isinstance(records, list) or len(records) > config.maximum_decisions_per_run:
        raise ValueError("Terminal discovery decisions are invalid")
    if any(
        not isinstance(record, dict) or record.get("decision_index") != index
        for index, record in enumerate(records)
    ):
        raise ValueError("Terminal discovery decision trace is invalid")
    if case.get("termination_reason") not in ("terminal", "policy_cycle", "decision_limit"):
        raise ValueError("Terminal discovery termination reason differs")
    exploration = case.get("exploration")
    if (
        not isinstance(exploration, dict)
        or exploration.get("controller_id") != EXPLORATION_CONTROLLER_ID
    ):
        raise ValueError("Terminal discovery exploration evidence differs")
    opportunities = _integer(exploration.get("opportunities"), "exploration opportunities")
    invocations = _integer(exploration.get("invocations"), "exploration invocations")
    non_argmax = _integer(exploration.get("non_argmax_actions"), "non-argmax actions")
    if not 0 <= non_argmax <= invocations <= opportunities <= len(records):
        raise ValueError("Terminal discovery exploration counts are inconsistent")
    if case.get("terminal") is True and case.get("termination_reason") != "terminal":
        raise ValueError("Terminal discovery terminal case reason differs")
    if case.get("victory") is True and case.get("terminal") is not True:
        raise ValueError("Terminal discovery victory is not terminal")


def _case_reference(output_directory: Path, case: dict[str, Any]) -> dict[str, Any]:
    path = _case_path(
        output_directory,
        int(case["seed"]),
        str(case["profile_name"]),
        int(case["attempt"]),
    )
    return {
        "seed": case["seed"],
        "profile_name": case["profile_name"],
        "attempt": case["attempt"],
        "path": str(path.relative_to(output_directory)),
        "case_id": case["case_id"],
    }


def _case_path(output_directory: Path, seed: int, profile_name: str, attempt: int) -> Path:
    return output_directory / "cases" / f"seed-{seed:06d}-{profile_name}-attempt-{attempt:03d}.json"


def _maximum_act(current: int | str | None, candidate: object) -> int | str | None:
    def rank(value: object) -> tuple[int, str]:
        if isinstance(value, bool) or value is None:
            return (-1, "")
        if isinstance(value, int):
            return (value, str(value))
        if isinstance(value, str):
            return (0, value)
        return (-1, "")

    return candidate if rank(candidate) > rank(current) else current  # type: ignore[return-value]


def _public_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _artifact_float(value: float) -> float:
    return float(f"{value:.12g}")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    return _mapping(value, label)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    return value


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
