from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid5

from spireshift.agents.baseline import SearchRolloutPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import LegalAction
from spireshift.fixed_search import (
    FIXED_SEARCH_OBJECTIVE_ID,
    FixedSearchConfig,
    load_fixed_search_report,
    run_fixed_search_suite,
    verify_fixed_search_report,
)
from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.search_workers import (
    PublicStateCheckpoint,
    SearchBackendSpec,
    SearchSimulationTask,
    SearchTaskRunner,
    SearchWorkerBatchResult,
    SearchWorkerStatus,
    load_search_task,
    run_search_worker_batch,
    verify_search_worker_batch,
)
from spireshift.splits import SplitManifest, SplitName

SEARCH_BENCHMARK_STATE_SET_SCHEMA_VERSION = "search-benchmark-state-set-v1"
SEARCH_BENCHMARK_REPORT_SCHEMA_VERSION = "search-compute-quality-report-v1"
SEARCH_BENCHMARK_VERIFICATION_SCHEMA_VERSION = "search-compute-quality-verification-v1"
INDEPENDENT_EVALUATION_PROTOCOL_ID = "sha256-paired-independent-candidate-evaluation-v1"


@dataclass(frozen=True, slots=True)
class SearchBenchmarkCase:
    state_id: str
    run_seed: int
    combat_state_index: int
    expected_state_hash: str
    expected_legal_actions: int

    def __post_init__(self) -> None:
        if not self.state_id:
            raise ValueError("Benchmark state_id must be non-empty")
        if isinstance(self.run_seed, bool) or self.run_seed < 0:
            raise ValueError("Benchmark run_seed must be non-negative")
        if isinstance(self.combat_state_index, bool) or self.combat_state_index < 0:
            raise ValueError("Benchmark combat_state_index must be non-negative")
        if len(self.expected_state_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.expected_state_hash
        ):
            raise ValueError("Benchmark expected_state_hash must be a lowercase SHA-256 digest")
        if isinstance(self.expected_legal_actions, bool) or self.expected_legal_actions <= 0:
            raise ValueError("Benchmark expected_legal_actions must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "state_id": self.state_id,
            "run_seed": self.run_seed,
            "combat_state_index": self.combat_state_index,
            "expected_state_hash": self.expected_state_hash,
            "expected_legal_actions": self.expected_legal_actions,
        }


@dataclass(frozen=True, slots=True)
class SearchBenchmarkStateSet:
    state_set_id: str
    split_manifest_id: str
    ruleset_manifest_id: str
    objective_id: str
    capture_policy_id: str
    partition: str
    selection_policy: str
    cases: tuple[SearchBenchmarkCase, ...]

    def __post_init__(self) -> None:
        if (
            not self.split_manifest_id
            or not self.ruleset_manifest_id
            or not self.objective_id
            or not self.capture_policy_id
        ):
            raise ValueError("Benchmark state-set identities must be non-empty")
        if self.partition != "validation":
            raise ValueError("The first compute-quality benchmark must use validation states")
        if not self.selection_policy:
            raise ValueError("Benchmark selection_policy must be non-empty")
        if not self.cases:
            raise ValueError("Benchmark state set must contain at least one case")
        ids = [case.state_id for case in self.cases]
        coordinates = [(case.run_seed, case.combat_state_index) for case in self.cases]
        if len(ids) != len(set(ids)) or len(coordinates) != len(set(coordinates)):
            raise ValueError("Benchmark cases must have unique IDs and coordinates")

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": SEARCH_BENCHMARK_STATE_SET_SCHEMA_VERSION,
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
class SearchBenchmarkConfig:
    search: FixedSearchConfig
    maximum_prefix_steps: int = 4096
    evaluation_samples_per_candidate: int = 64
    evaluation_sampling_seed: int = 1
    evaluation_workers: int = 8
    evaluation_worker_timeout_seconds: float = 120.0
    calibration_bins: int = 10

    def __post_init__(self) -> None:
        if self.maximum_prefix_steps <= 0:
            raise ValueError("maximum_prefix_steps must be positive")
        if self.evaluation_samples_per_candidate <= 0:
            raise ValueError("evaluation_samples_per_candidate must be positive")
        if isinstance(self.evaluation_sampling_seed, bool) or self.evaluation_sampling_seed < 0:
            raise ValueError("evaluation_sampling_seed must be non-negative")
        if self.evaluation_workers <= 0:
            raise ValueError("evaluation_workers must be positive")
        if (
            not math.isfinite(self.evaluation_worker_timeout_seconds)
            or self.evaluation_worker_timeout_seconds <= 0.0
        ):
            raise ValueError("evaluation_worker_timeout_seconds must be finite and positive")
        if self.calibration_bins <= 0:
            raise ValueError("calibration_bins must be positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "search": self.search.as_dict(),
            "maximum_prefix_steps": self.maximum_prefix_steps,
            "evaluation_samples_per_candidate": self.evaluation_samples_per_candidate,
            "evaluation_sampling_seed": self.evaluation_sampling_seed,
            "evaluation_workers": self.evaluation_workers,
            "evaluation_worker_timeout_seconds": self.evaluation_worker_timeout_seconds,
            "calibration_bins": self.calibration_bins,
        }


@dataclass(frozen=True, slots=True)
class SearchBenchmarkResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SearchBenchmarkVerification:
    valid: bool
    report_id: str | None
    cases: int
    verified_cases: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": SEARCH_BENCHMARK_VERIFICATION_SCHEMA_VERSION,
            "valid": self.valid,
            "report_id": self.report_id,
            "cases": self.cases,
            "verified_cases": self.verified_cases,
            "errors": list(self.errors),
        }


def freeze_search_benchmark_state_set(
    specification: object,
    *,
    split_manifest: SplitManifest | None = None,
) -> dict[str, Any]:
    document = _mapping(specification, "benchmark state-set specification")
    body: dict[str, Any] = {
        "schema_version": SEARCH_BENCHMARK_STATE_SET_SCHEMA_VERSION,
        "split_manifest_id": _string(document.get("split_manifest_id"), "split_manifest_id"),
        "ruleset_manifest_id": _string(document.get("ruleset_manifest_id"), "ruleset_manifest_id"),
        "objective_id": _string(document.get("objective_id"), "objective_id"),
        "capture_policy_id": _string(document.get("capture_policy_id"), "capture_policy_id"),
        "partition": _string(document.get("partition"), "partition"),
        "selection_policy": _string(document.get("selection_policy"), "selection_policy"),
        "cases": [
            SearchBenchmarkCase(
                state_id=_string(case.get("state_id"), "state_id"),
                run_seed=_integer(case.get("run_seed"), "run_seed"),
                combat_state_index=_integer(case.get("combat_state_index"), "combat_state_index"),
                expected_state_hash=_string(case.get("expected_state_hash"), "expected_state_hash"),
                expected_legal_actions=_integer(
                    case.get("expected_legal_actions"), "expected_legal_actions"
                ),
            ).as_dict()
            for value in _list(document.get("cases"), "cases")
            for case in [_mapping(value, "case")]
        ],
    }
    frozen = {**body, "state_set_id": manifest_identifier(body)}
    state_set = load_search_benchmark_state_set_document(frozen)
    if split_manifest is not None:
        _validate_state_set_split(state_set, split_manifest)
    return frozen


def load_search_benchmark_state_set(path: Path) -> SearchBenchmarkStateSet:
    return load_search_benchmark_state_set_document(_load_object(path))


def write_search_benchmark_state_set(document: object, path: Path) -> None:
    state_set = load_search_benchmark_state_set_document(document)
    write_exclusive_json(path, state_set.as_dict())


def load_search_benchmark_state_set_document(document: object) -> SearchBenchmarkStateSet:
    value = _mapping(document, "benchmark state set")
    if value.get("schema_version") != SEARCH_BENCHMARK_STATE_SET_SCHEMA_VERSION:
        raise ValueError("Unsupported search benchmark state-set schema")
    state_set_id = _string(value.get("state_set_id"), "state_set_id")
    body = {key: item for key, item in value.items() if key != "state_set_id"}
    if state_set_id != manifest_identifier(body):
        raise ValueError("Benchmark state-set identity mismatch")
    cases = tuple(
        SearchBenchmarkCase(
            state_id=_string(case.get("state_id"), "state_id"),
            run_seed=_integer(case.get("run_seed"), "run_seed"),
            combat_state_index=_integer(case.get("combat_state_index"), "combat_state_index"),
            expected_state_hash=_string(case.get("expected_state_hash"), "expected_state_hash"),
            expected_legal_actions=_integer(
                case.get("expected_legal_actions"), "expected_legal_actions"
            ),
        )
        for raw_case in _list(value.get("cases"), "cases")
        for case in [_mapping(raw_case, "case")]
    )
    return SearchBenchmarkStateSet(
        state_set_id=state_set_id,
        split_manifest_id=_string(value.get("split_manifest_id"), "split_manifest_id"),
        ruleset_manifest_id=_string(value.get("ruleset_manifest_id"), "ruleset_manifest_id"),
        objective_id=_string(value.get("objective_id"), "objective_id"),
        capture_policy_id=_string(value.get("capture_policy_id"), "capture_policy_id"),
        partition=_string(value.get("partition"), "partition"),
        selection_policy=_string(value.get("selection_policy"), "selection_policy"),
        cases=cases,
    )


def _validate_state_set_split(
    state_set: SearchBenchmarkStateSet,
    split_manifest: SplitManifest,
) -> None:
    if state_set.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Benchmark state set names a different split manifest")
    if state_set.ruleset_manifest_id != split_manifest.ruleset_manifest_id:
        raise ValueError("Benchmark state set ruleset differs from split manifest")
    if state_set.objective_id != split_manifest.objective_id:
        raise ValueError("Benchmark state set objective differs from split manifest")
    if state_set.capture_policy_id != SearchRolloutPolicy.policy_id:
        raise ValueError("Benchmark state set uses an unsupported capture policy")
    for case in state_set.cases:
        if split_manifest.split_for_seed(case.run_seed) is not SplitName.VALIDATION:
            raise ValueError(f"Benchmark case {case.state_id} is not in the validation split")


def run_search_compute_quality_benchmark(
    *,
    backend: SearchBackendSpec,
    state_set: SearchBenchmarkStateSet,
    config: SearchBenchmarkConfig,
    output_directory: Path,
    task_runner: SearchTaskRunner | None = None,
    now: Callable[[], str] | None = None,
) -> SearchBenchmarkResult:
    if state_set.objective_id != FIXED_SEARCH_OBJECTIVE_ID:
        raise ValueError("Search benchmark state set must use terminal-victory-v1")
    if state_set.capture_policy_id != SearchRolloutPolicy.policy_id:
        raise ValueError("Search benchmark state set uses an unsupported capture policy")
    output_directory.mkdir(parents=True, exist_ok=False)
    output_directory = output_directory.resolve()
    clock = now or _utc_now
    started_at = clock()
    cases: list[dict[str, Any]] = []
    for case in state_set.cases:
        case_directory = output_directory / "cases" / case.state_id
        try:
            fixed_result = run_fixed_search_suite(
                backend=backend,
                run_seed=case.run_seed,
                combat_state_index=case.combat_state_index,
                maximum_prefix_steps=config.maximum_prefix_steps,
                output_directory=case_directory / "search",
                config=config.search,
                task_runner=task_runner,
                now=clock,
            )
            fixed_report = fixed_result.report
            if fixed_report.get("ruleset_manifest_id") != state_set.ruleset_manifest_id:
                raise ValueError("Captured state ruleset differs from the frozen benchmark set")
            capture = _mapping(fixed_report.get("capture"), "fixed search capture")
            checkpoint = _mapping(fixed_report.get("checkpoint"), "fixed search checkpoint")
            legal_actions = _list(fixed_report.get("legal_actions"), "fixed search legal actions")
            if capture.get("policy_id") != state_set.capture_policy_id:
                raise ValueError("Captured state policy differs from the frozen benchmark set")
            if checkpoint.get("state_hash") != case.expected_state_hash:
                raise ValueError("Captured public state differs from the frozen benchmark case")
            if len(legal_actions) != case.expected_legal_actions:
                raise ValueError(
                    "Captured legal-action count differs from the frozen benchmark case"
                )
            evaluation = _run_independent_candidate_evaluation(
                backend=backend,
                fixed_report=fixed_report,
                samples_per_candidate=config.evaluation_samples_per_candidate,
                sampling_seed=config.evaluation_sampling_seed,
                workers=config.evaluation_workers,
                worker_timeout_seconds=config.evaluation_worker_timeout_seconds,
                maximum_rollout_steps=config.search.maximum_rollout_steps,
                output_directory=case_directory / "evaluation",
                task_runner=task_runner,
            )
            case_document = _analyze_case(
                case=case,
                fixed_report=fixed_report,
                fixed_report_path=fixed_result.report_path,
                evaluation_report=evaluation.report,
                evaluation_report_path=evaluation.report_path,
                benchmark_root=output_directory,
            )
            cases.append(case_document)
        except Exception as error:  # noqa: BLE001 - failed cases remain in the denominator.
            cases.append(
                {
                    "state_id": case.state_id,
                    "run_seed": case.run_seed,
                    "combat_state_index": case.combat_state_index,
                    "status": "failed",
                    "failure": {"type": type(error).__name__, "message": str(error)},
                    "source_state_hash": None,
                    "search_report": None,
                    "evaluation_report": None,
                    "independent_candidates": [],
                    "tiers": [],
                }
            )
    summary = _aggregate_cases(cases, config.calibration_bins)
    report_body: dict[str, Any] = {
        "schema_version": SEARCH_BENCHMARK_REPORT_SCHEMA_VERSION,
        "objective_id": FIXED_SEARCH_OBJECTIVE_ID,
        "independent_evaluation_protocol_id": INDEPENDENT_EVALUATION_PROTOCOL_ID,
        "started_at": started_at,
        "completed_at": clock(),
        "backend": backend.as_dict(),
        "state_set": state_set.as_dict(),
        "configuration": config.as_dict(),
        "cases": cases,
        "summary": summary,
        "claim_scope": "validation_compute_quality",
    }
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    report_path = output_directory / "search-compute-quality-report.json"
    write_exclusive_json(report_path, report)
    return SearchBenchmarkResult(summary["failed_cases"] == 0, report_path, report)


def verify_search_compute_quality_report(report_path: Path) -> SearchBenchmarkVerification:
    errors: list[str] = []
    report_id: str | None = None
    verified_cases = 0
    raw_cases: list[Any] = []
    try:
        report = _load_object(report_path)
        raw_report_id = report.get("report_id")
        report_id = raw_report_id if isinstance(raw_report_id, str) else None
        body = {key: value for key, value in report.items() if key != "report_id"}
        if report_id != manifest_identifier(body):
            errors.append("search benchmark report identity mismatch")
        if report.get("schema_version") != SEARCH_BENCHMARK_REPORT_SCHEMA_VERSION:
            errors.append("unsupported search benchmark report schema")
        if report.get("objective_id") != FIXED_SEARCH_OBJECTIVE_ID:
            errors.append("search benchmark objective mismatch")
        if report.get("independent_evaluation_protocol_id") != (INDEPENDENT_EVALUATION_PROTOCOL_ID):
            errors.append("independent evaluation protocol mismatch")
        state_set = load_search_benchmark_state_set_document(report.get("state_set"))
        if state_set.capture_policy_id != SearchRolloutPolicy.policy_id:
            errors.append("benchmark capture policy is unsupported")
        configuration = _mapping(report.get("configuration"), "configuration")
        bins = _integer(configuration.get("calibration_bins"), "calibration_bins")
        raw_cases = _list(report.get("cases"), "cases")
        if len(raw_cases) != len(state_set.cases):
            errors.append("benchmark case count differs from frozen state set")
        root = report_path.parent.resolve()
        regenerated_cases: list[dict[str, Any]] = []
        for index, expected_case in enumerate(state_set.cases):
            if index >= len(raw_cases):
                break
            case = _mapping(raw_cases[index], f"cases[{index}]")
            if (
                case.get("state_id") != expected_case.state_id
                or case.get("run_seed") != expected_case.run_seed
                or case.get("combat_state_index") != expected_case.combat_state_index
            ):
                errors.append(f"case {expected_case.state_id}: frozen case identity mismatch")
                regenerated_cases.append(case)
                continue
            search_value = case.get("search_report")
            evaluation_value = case.get("evaluation_report")
            if search_value is None and evaluation_value is None and case.get("status") == "failed":
                regenerated_cases.append(case)
                continue
            search_reference = _mapping(search_value, "search_report")
            evaluation_reference = _mapping(evaluation_value, "evaluation_report")
            case_error_count = len(errors)
            fixed_path = _verify_linked_report(
                root,
                search_reference,
                "fixed-search report",
                errors,
            )
            evaluation_path = _verify_linked_report(
                root,
                evaluation_reference,
                "evaluation report",
                errors,
            )
            fixed_verification = verify_fixed_search_report(fixed_path)
            if not fixed_verification.valid:
                errors.extend(
                    f"case {expected_case.state_id} fixed search: {error}"
                    for error in fixed_verification.errors
                )
            evaluation_verification = verify_search_worker_batch(evaluation_path)
            if not evaluation_verification.valid:
                errors.extend(
                    f"case {expected_case.state_id} evaluation: {error}"
                    for error in evaluation_verification.errors
                )
            fixed_report = load_fixed_search_report(fixed_path)
            evaluation_report = _load_object(evaluation_path)
            if fixed_report.get("backend") != report.get("backend"):
                errors.append(f"case {expected_case.state_id}: backend differs from benchmark")
            if fixed_report.get("ruleset_manifest_id") != state_set.ruleset_manifest_id:
                errors.append(f"case {expected_case.state_id}: ruleset differs from state set")
            _verify_case_protocol(
                expected_case,
                fixed_report,
                evaluation_report,
                evaluation_path,
                configuration,
                errors,
            )
            regenerated = _analyze_case(
                case=expected_case,
                fixed_report=fixed_report,
                fixed_report_path=fixed_path,
                evaluation_report=evaluation_report,
                evaluation_report_path=evaluation_path,
                benchmark_root=root,
            )
            if regenerated != case:
                errors.append(f"case {expected_case.state_id}: analysis differs from evidence")
            elif len(errors) == case_error_count:
                verified_cases += 1
            regenerated_cases.append(regenerated)
        if report.get("summary") != _aggregate_cases(regenerated_cases, bins):
            errors.append("benchmark summary differs from case evidence")
    except (IndexError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return SearchBenchmarkVerification(
        not errors,
        report_id,
        len(raw_cases),
        verified_cases,
        tuple(errors),
    )


def _run_independent_candidate_evaluation(
    *,
    backend: SearchBackendSpec,
    fixed_report: dict[str, Any],
    samples_per_candidate: int,
    sampling_seed: int,
    workers: int,
    worker_timeout_seconds: float,
    maximum_rollout_steps: int,
    output_directory: Path,
    task_runner: SearchTaskRunner | None = None,
) -> SearchWorkerBatchResult:
    checkpoint = PublicStateCheckpoint.from_mapping(fixed_report.get("checkpoint"))
    actions = tuple(
        LegalAction(
            action_id=_string(action.get("action_id"), "action_id"),
            kind=_string(action.get("kind"), "kind"),
            payload=_mapping(action.get("payload"), "payload"),
        )
        for raw_action in _list(fixed_report.get("legal_actions"), "legal_actions")
        for action in [_mapping(raw_action, "legal action")]
    )
    search_seeds = {
        _integer(simulation.get("simulation_seed"), "search simulation seed")
        for raw_tier in _list(fixed_report.get("tiers"), "tiers")
        for tier in [_mapping(raw_tier, "tier")]
        for raw_simulation in _list(tier.get("simulations"), "simulations")
        for simulation in [_mapping(raw_simulation, "simulation")]
    }
    tasks: list[SearchSimulationTask] = []
    paired_seeds: list[int] = []
    used_seeds = set(search_seeds)
    for sample_index in range(samples_per_candidate):
        seed = _independent_evaluation_seed(
            sampling_seed,
            checkpoint.state_hash,
            sample_index,
            used_seeds,
        )
        paired_seeds.append(seed)
        used_seeds.add(seed)
    for action in actions:
        for seed in paired_seeds:
            task_id = str(
                uuid5(
                    NAMESPACE_URL,
                    "|".join(
                        (
                            INDEPENDENT_EVALUATION_PROTOCOL_ID,
                            checkpoint.ruleset_manifest_id,
                            checkpoint.state_hash,
                            action.action_id,
                            str(seed),
                        )
                    ),
                )
            )
            tasks.append(
                SearchSimulationTask.create(
                    backend=backend,
                    checkpoint=checkpoint,
                    action_id=action.action_id,
                    simulation_seed=seed,
                    maximum_rollout_steps=maximum_rollout_steps,
                    task_id=task_id,
                )
            )
    return run_search_worker_batch(
        tasks=tasks,
        workers=workers,
        worker_timeout_seconds=worker_timeout_seconds,
        output_directory=output_directory,
        task_runner=task_runner,
        batch_id=str(
            uuid5(
                NAMESPACE_URL,
                f"{INDEPENDENT_EVALUATION_PROTOCOL_ID}|{checkpoint.state_hash}|{sampling_seed}",
            )
        ),
    )


def _analyze_case(
    *,
    case: SearchBenchmarkCase,
    fixed_report: dict[str, Any],
    fixed_report_path: Path,
    evaluation_report: dict[str, Any],
    evaluation_report_path: Path,
    benchmark_root: Path,
) -> dict[str, Any]:
    action_documents = tuple(
        _mapping(action, "legal action")
        for action in _list(fixed_report.get("legal_actions"), "legal_actions")
    )
    independent = _independent_candidate_summaries(
        action_documents,
        evaluation_report,
        evaluation_report_path,
    )
    best_value = max(
        _number(candidate["terminal_value"], "terminal_value") for candidate in independent
    )
    best_indices = {
        _integer(candidate["candidate_index"], "candidate_index")
        for candidate in independent
        if _number(candidate["terminal_value"], "terminal_value") == best_value
    }
    tiers: list[dict[str, Any]] = []
    for raw_tier in _list(fixed_report.get("tiers"), "tiers"):
        tier = _mapping(raw_tier, "tier")
        selected_index = _integer(tier.get("selected_candidate_index"), "selected_candidate_index")
        search_candidates = _list(tier.get("candidates"), "search candidates")
        search_candidate = _mapping(search_candidates[selected_index], "search candidate")
        evaluation_candidate = independent[selected_index]
        predicted_death = 1.0 - _number(
            search_candidate.get("terminal_value"), "search terminal value"
        )
        observed_death = 1.0 - _number(
            evaluation_candidate["terminal_value"], "evaluation terminal value"
        )
        attempts = _integer(evaluation_candidate["attempted_simulations"], "evaluation attempts")
        deaths = attempts - _integer(evaluation_candidate["victories"], "victories")
        brier = (
            (attempts - deaths) * predicted_death**2 + deaths * (predicted_death - 1.0) ** 2
        ) / attempts
        tier_summary = _mapping(tier.get("summary"), "tier summary")
        tiers.append(
            {
                "tier": _string(tier.get("tier"), "tier"),
                "simulation_budget": _integer(tier.get("simulation_budget"), "simulation_budget"),
                "selected_candidate_index": selected_index,
                "selected_action_id": _string(tier.get("selected_action_id"), "selected_action_id"),
                "predicted_terminal_value": 1.0 - predicted_death,
                "independent_terminal_value": 1.0 - observed_death,
                "best_independent_terminal_value": best_value,
                "terminal_value_regret": best_value - (1.0 - observed_death),
                "independent_best_action": selected_index in best_indices,
                "predicted_death_risk": predicted_death,
                "observed_death_risk": observed_death,
                "death_risk_brier": brier,
                "independent_attempts": attempts,
                "independent_deaths": deaths,
                "act_completion_rate": evaluation_candidate["act_completion_rate"],
                "mean_post_action_hp": evaluation_candidate["mean_post_action_hp"],
                "mean_final_hp": evaluation_candidate["mean_final_hp"],
                "compute": {
                    "attempted_simulations": tier_summary["attempted_simulations"],
                    "transitions": tier_summary["transitions"],
                    "worker_cpu_seconds": tier_summary["worker_cpu_seconds"],
                    "wall_seconds": tier_summary["wall_seconds"],
                    "p95_worker_wall_seconds": tier_summary["p95_worker_wall_seconds"],
                },
            }
        )
    checkpoint = _mapping(fixed_report.get("checkpoint"), "checkpoint")
    fixed_summary = _mapping(fixed_report.get("summary"), "fixed search summary")
    evaluation_summary = _mapping(evaluation_report.get("summary"), "evaluation summary")
    complete = (
        fixed_summary.get("all_tiers_complete") is True
        and evaluation_summary.get("failed_tasks") == 0
    )
    return {
        "state_id": case.state_id,
        "run_seed": case.run_seed,
        "combat_state_index": case.combat_state_index,
        "status": "completed" if complete else "failed",
        "failure": (
            None
            if complete
            else {
                "type": "incomplete_simulations",
                "message": "Search or independent evaluation retained failed simulations",
            }
        ),
        "source_state_hash": checkpoint.get("state_hash"),
        "search_report": _report_reference(
            fixed_report_path,
            benchmark_root,
            fixed_report.get("report_id"),
        ),
        "evaluation_report": _report_reference(
            evaluation_report_path,
            benchmark_root,
            None,
        ),
        "independent_candidates": independent,
        "tiers": tiers,
    }


def _independent_candidate_summaries(
    legal_actions: Sequence[dict[str, Any]],
    evaluation_report: dict[str, Any],
    evaluation_report_path: Path,
) -> list[dict[str, Any]]:
    by_action: dict[str, list[tuple[dict[str, Any], SearchSimulationTask]]] = {
        _string(action.get("action_id"), "action_id"): [] for action in legal_actions
    }
    root = evaluation_report_path.parent
    for raw_evidence in _list(evaluation_report.get("tasks"), "evaluation tasks"):
        evidence = _mapping(raw_evidence, "evaluation task")
        request_path = _safe_child(
            root,
            _string(evidence.get("request_path"), "evaluation request path"),
        )
        task = load_search_task(request_path)
        by_action.setdefault(task.action_id, []).append((evidence, task))
    summaries: list[dict[str, Any]] = []
    for candidate_index, action in enumerate(legal_actions):
        action_id = _string(action.get("action_id"), "action_id")
        evidence_items = by_action.get(action_id, [])
        if not evidence_items:
            raise ValueError(f"Independent evaluation omitted action {action_id}")
        victories = 0
        completed = 0
        terminal = 0
        failures = 0
        transitions = 0
        cpu_seconds = 0.0
        worker_wall_seconds = 0.0
        act_completed = 0
        act_known = 0
        post_action_hps: list[int] = []
        final_hps: list[int] = []
        seeds: set[int] = set()
        for evidence, task in evidence_items:
            seeds.add(task.simulation_seed)
            cpu = _optional_number(evidence.get("cpu_seconds"))
            wall = _optional_number(evidence.get("wall_seconds"))
            cpu_seconds += 0.0 if cpu is None else cpu
            worker_wall_seconds += 0.0 if wall is None else wall
            output_value = evidence.get("output")
            output = output_value if isinstance(output_value, dict) else None
            if evidence.get("status") == SearchWorkerStatus.COMPLETED.value and output is not None:
                completed += 1
                terminal_value = _boolean(output.get("terminal"), "terminal")
                victory = _boolean(output.get("victory"), "victory")
                terminal += int(terminal_value)
                victories += int(terminal_value and victory)
                failures += int(not terminal_value)
                transitions += _integer(output.get("transitions"), "transitions")
                diagnostics = _mapping(output.get("diagnostics"), "diagnostics")
                completed_act = diagnostics.get("act_completed")
                if isinstance(completed_act, bool):
                    act_known += 1
                    act_completed += int(completed_act)
                post_hp = _optional_integer(diagnostics.get("post_action_hp"))
                final_hp = _optional_integer(diagnostics.get("final_hp"))
                if post_hp is not None:
                    post_action_hps.append(post_hp)
                if final_hp is not None:
                    final_hps.append(final_hp)
            else:
                failures += 1
        attempts = len(evidence_items)
        value = victories / attempts
        summaries.append(
            {
                "candidate_index": candidate_index,
                "source_action_id": action_id,
                "action_kind": _string(action.get("kind"), "action kind"),
                "attempted_simulations": attempts,
                "completed_simulations": completed,
                "terminal_simulations": terminal,
                "failed_or_truncated_simulations": failures,
                "victories": victories,
                "terminal_value": value,
                "death_risk": 1.0 - value,
                "outcome_variance": value * (1.0 - value),
                "transitions": transitions,
                "unique_simulation_seeds": len(seeds),
                "worker_cpu_seconds": cpu_seconds,
                "worker_wall_seconds": worker_wall_seconds,
                "act_completion_rate": (act_completed / act_known if act_known else None),
                "act_completion_samples": act_known,
                "mean_post_action_hp": _mean_or_none(post_action_hps),
                "post_action_hp_samples": len(post_action_hps),
                "mean_final_hp": _mean_or_none(final_hps),
                "final_hp_samples": len(final_hps),
            }
        )
    return summaries


def _verify_case_protocol(
    case: SearchBenchmarkCase,
    fixed_report: dict[str, Any],
    evaluation_report: dict[str, Any],
    evaluation_report_path: Path,
    configuration: dict[str, Any],
    errors: list[str],
) -> None:
    label = f"case {case.state_id}"
    expected_search = _mapping(configuration.get("search"), "search configuration")
    if fixed_report.get("configuration") != expected_search:
        errors.append(f"{label}: fixed-search configuration differs from benchmark")
    capture = _mapping(fixed_report.get("capture"), "fixed-search capture")
    if capture.get("combat_state_index") != case.combat_state_index:
        errors.append(f"{label}: captured combat index differs from frozen case")
    if capture.get("policy_id") != SearchRolloutPolicy.policy_id:
        errors.append(f"{label}: capture policy differs from frozen state set")
    checkpoint_document = _mapping(fixed_report.get("checkpoint"), "fixed-search checkpoint")
    checkpoint = PublicStateCheckpoint.from_mapping(checkpoint_document)
    if checkpoint.run_seed != case.run_seed:
        errors.append(f"{label}: checkpoint run seed differs from frozen case")
    maximum_prefix_steps = _integer(
        configuration.get("maximum_prefix_steps"),
        "maximum_prefix_steps",
    )
    if len(checkpoint.action_prefix) > maximum_prefix_steps:
        errors.append(f"{label}: checkpoint prefix exceeds benchmark limit")
    if checkpoint.state_hash != case.expected_state_hash:
        errors.append(f"{label}: checkpoint hash differs from frozen case")

    evaluation_configuration = _mapping(
        evaluation_report.get("configuration"),
        "evaluation configuration",
    )
    if evaluation_configuration.get("workers") != configuration.get("evaluation_workers"):
        errors.append(f"{label}: evaluation worker count differs from benchmark")
    if evaluation_configuration.get("worker_timeout_seconds") != configuration.get(
        "evaluation_worker_timeout_seconds"
    ):
        errors.append(f"{label}: evaluation timeout differs from benchmark")

    legal_actions = tuple(
        _string(action.get("action_id"), "legal action ID")
        for raw_action in _list(fixed_report.get("legal_actions"), "legal actions")
        for action in [_mapping(raw_action, "legal action")]
    )
    if len(legal_actions) != case.expected_legal_actions:
        errors.append(f"{label}: legal-action count differs from frozen case")
    search_seeds = {
        _integer(simulation.get("simulation_seed"), "search simulation seed")
        for raw_tier in _list(fixed_report.get("tiers"), "tiers")
        for tier in [_mapping(raw_tier, "tier")]
        for raw_simulation in _list(tier.get("simulations"), "simulations")
        for simulation in [_mapping(raw_simulation, "simulation")]
    }
    tasks_by_action: dict[str, list[SearchSimulationTask]] = {
        action_id: [] for action_id in legal_actions
    }
    root = evaluation_report_path.parent
    for raw_evidence in _list(evaluation_report.get("tasks"), "evaluation tasks"):
        evidence = _mapping(raw_evidence, "evaluation task")
        request_path = _safe_child(
            root,
            _string(evidence.get("request_path"), "evaluation request path"),
        )
        task = load_search_task(request_path)
        if task.checkpoint != checkpoint:
            errors.append(f"{label}: evaluation task checkpoint differs from search checkpoint")
        if task.maximum_rollout_steps != expected_search.get("maximum_rollout_steps"):
            errors.append(f"{label}: evaluation rollout limit differs from benchmark")
        if task.action_id not in tasks_by_action:
            errors.append(f"{label}: evaluation task has an unknown action")
            continue
        tasks_by_action[task.action_id].append(task)

    samples = _integer(
        configuration.get("evaluation_samples_per_candidate"),
        "evaluation_samples_per_candidate",
    )
    sampling_seed = _integer(
        configuration.get("evaluation_sampling_seed"),
        "evaluation_sampling_seed",
    )
    expected_seeds: list[int] = []
    excluded = set(search_seeds)
    for sample_index in range(samples):
        seed = _independent_evaluation_seed(
            sampling_seed,
            checkpoint.state_hash,
            sample_index,
            excluded,
        )
        expected_seeds.append(seed)
        excluded.add(seed)
    for action_id, tasks in tasks_by_action.items():
        seeds = [task.simulation_seed for task in tasks]
        if len(seeds) != len(expected_seeds) or set(seeds) != set(expected_seeds):
            errors.append(f"{label}: action {action_id} does not use the paired evaluation seeds")
        if search_seeds.intersection(seeds):
            errors.append(f"{label}: search and evaluation seed domains overlap")


def _aggregate_cases(cases: Sequence[dict[str, Any]], calibration_bins: int) -> dict[str, Any]:
    completed = [case for case in cases if case.get("status") == "completed"]
    evidenced = [case for case in cases if case.get("tiers") or case.get("independent_candidates")]
    tiers: dict[str, dict[str, Any]] = {}
    for tier_name in ("shallow", "medium", "expensive"):
        tier_results = [
            tier
            for case in completed
            for tier in _list(case.get("tiers"), "case tiers")
            if isinstance(tier, dict) and tier.get("tier") == tier_name
        ]
        regrets = [_number(tier["terminal_value_regret"], "regret") for tier in tier_results]
        predicted = [
            _number(tier["predicted_death_risk"], "predicted death risk") for tier in tier_results
        ]
        observed = [
            _number(tier["observed_death_risk"], "observed death risk") for tier in tier_results
        ]
        weights = [
            _integer(tier["independent_attempts"], "independent attempts") for tier in tier_results
        ]
        briers = [_number(tier["death_risk_brier"], "death brier") for tier in tier_results]
        compute = [_mapping(tier.get("compute"), "compute") for tier in tier_results]
        act_rates = [
            float(value)
            for tier in tier_results
            for value in [tier.get("act_completion_rate")]
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        hp_values = [
            float(value)
            for tier in tier_results
            for value in [tier.get("mean_post_action_hp")]
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        latencies = [_number(item["wall_seconds"], "wall seconds") for item in compute]
        total_weight = sum(weights)
        tiers[tier_name] = {
            "evaluated_states": len(tier_results),
            "mean_terminal_value_regret": _mean_or_none(regrets),
            "maximum_terminal_value_regret": max(regrets) if regrets else None,
            "independent_best_action_rate": (
                sum(tier.get("independent_best_action") is True for tier in tier_results)
                / len(tier_results)
                if tier_results
                else None
            ),
            "mean_predicted_death_risk": _mean_or_none(predicted),
            "mean_observed_death_risk": _mean_or_none(observed),
            "death_risk_brier": (
                sum(score * weight for score, weight in zip(briers, weights, strict=True))
                / total_weight
                if total_weight
                else None
            ),
            "death_risk_ece": _weighted_ece(
                predicted,
                observed,
                weights,
                calibration_bins,
            ),
            "mean_attempted_simulations": _mean_or_none(
                [_number(item["attempted_simulations"], "attempted") for item in compute]
            ),
            "mean_transitions": _mean_or_none(
                [_number(item["transitions"], "transitions") for item in compute]
            ),
            "mean_worker_cpu_seconds": _mean_or_none(
                [_number(item["worker_cpu_seconds"], "cpu seconds") for item in compute]
            ),
            "mean_wall_seconds": _mean_or_none(latencies),
            "p50_wall_seconds": _percentile_or_none(latencies, 0.50),
            "p95_wall_seconds": _percentile_or_none(latencies, 0.95),
            "p99_wall_seconds": _percentile_or_none(latencies, 0.99),
            "mean_act_completion_rate": _mean_or_none(act_rates),
            "mean_post_action_hp": _mean_or_none(hp_values),
        }
    attempted_search = sum(
        _integer(_mapping(tier.get("compute"), "compute")["attempted_simulations"], "attempted")
        for case in evidenced
        for tier in _list(case.get("tiers"), "case tiers")
        if isinstance(tier, dict)
    )
    evaluation_simulations = sum(
        _integer(candidate["attempted_simulations"], "attempted")
        for case in evidenced
        for candidate in _list(case.get("independent_candidates"), "independent candidates")
        if isinstance(candidate, dict)
    )
    search_transitions = sum(
        _integer(_mapping(tier.get("compute"), "compute")["transitions"], "transitions")
        for case in evidenced
        for tier in _list(case.get("tiers"), "case tiers")
        if isinstance(tier, dict)
    )
    evaluation_transitions = sum(
        _integer(candidate["transitions"], "transitions")
        for case in evidenced
        for candidate in _list(case.get("independent_candidates"), "independent candidates")
        if isinstance(candidate, dict)
    )
    return {
        "benchmark_denominator": len(cases),
        "completed_cases": len(completed),
        "failed_cases": len(cases) - len(completed),
        "completion_rate": len(completed) / len(cases) if cases else 0.0,
        "search_simulations": attempted_search,
        "independent_evaluation_simulations": evaluation_simulations,
        "simulations": attempted_search + evaluation_simulations,
        "search_transitions": search_transitions,
        "independent_evaluation_transitions": evaluation_transitions,
        "transitions": search_transitions + evaluation_transitions,
        "tiers": tiers,
    }


def _weighted_ece(
    predicted: Sequence[float],
    observed: Sequence[float],
    weights: Sequence[int],
    bins: int,
) -> float | None:
    total = sum(weights)
    if total == 0:
        return None
    error = 0.0
    for bin_index in range(bins):
        low = bin_index / bins
        high = (bin_index + 1) / bins
        indexes = [
            index
            for index, probability in enumerate(predicted)
            if low <= probability < high or (bin_index == bins - 1 and probability == 1.0)
        ]
        weight = sum(weights[index] for index in indexes)
        if not weight:
            continue
        predicted_mean = sum(predicted[index] * weights[index] for index in indexes) / weight
        observed_mean = sum(observed[index] * weights[index] for index in indexes) / weight
        error += weight / total * abs(predicted_mean - observed_mean)
    return error


def _independent_evaluation_seed(
    sampling_seed: int,
    state_hash: str,
    sample_index: int,
    excluded: set[int],
) -> int:
    collision = 0
    while True:
        payload = (
            f"{sampling_seed}|{state_hash}|independent-evaluation|{sample_index}|{collision}"
        ).encode()
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)
        if seed not in excluded:
            return seed
        collision += 1


def _report_reference(path: Path, root: Path, content_id: object) -> dict[str, object]:
    return {
        "path": str(path.resolve().relative_to(root.resolve())),
        "sha256": sha256_file(path),
        "content_id": content_id if isinstance(content_id, str) else None,
    }


def _verify_linked_report(
    root: Path,
    reference: dict[str, Any],
    label: str,
    errors: list[str],
) -> Path:
    path = _safe_child(root, _string(reference.get("path"), f"{label} path"))
    expected_digest = _string(reference.get("sha256"), f"{label} digest")
    if sha256_file(path) != expected_digest:
        errors.append(f"{label} digest mismatch")
    return path


def _safe_child(directory: Path, relative: str) -> Path:
    candidate = (directory / relative).resolve()
    if candidate == directory or directory not in candidate.parents:
        raise ValueError("benchmark evidence path escapes its directory")
    if not candidate.is_file():
        raise ValueError("benchmark evidence file is missing")
    return candidate


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


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
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _optional_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
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


def _mean_or_none(values: Sequence[int | float]) -> float | None:
    return sum(values) / len(values) if values else None


def _percentile_or_none(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = math.ceil(quantile * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
