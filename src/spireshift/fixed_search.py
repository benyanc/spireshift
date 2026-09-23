from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import NAMESPACE_URL, uuid5

from spireshift.agents.baseline import SearchRolloutPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.search_workers import (
    PublicStateCheckpoint,
    SearchBackendSpec,
    SearchSimulationTask,
    SearchTaskRunner,
    SearchWorkerStatus,
    capture_checkpoint,
    load_search_environment,
    run_search_worker_batch,
    verify_search_worker_batch,
)

FIXED_SEARCH_REPORT_SCHEMA_VERSION = "fixed-search-report-v2"
FIXED_SEARCH_VERIFICATION_SCHEMA_VERSION = "fixed-search-verification-v1"
FIXED_SEARCH_PLANNER_ID = "isolated-root-uct-terminal-victory-v1"
FIXED_SEARCH_OBJECTIVE_ID = "terminal-victory-v1"
REQUIRED_TIER_NAMES = ("shallow", "medium", "expensive")


@dataclass(frozen=True, slots=True)
class FixedSearchTier:
    name: str
    simulations: int

    def __post_init__(self) -> None:
        if self.name not in REQUIRED_TIER_NAMES:
            raise ValueError(f"Unsupported fixed-search tier: {self.name}")
        if isinstance(self.simulations, bool) or self.simulations <= 0:
            raise ValueError("Tier simulations must be positive")

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "simulations": self.simulations}


@dataclass(frozen=True, slots=True)
class FixedSearchConfig:
    tiers: tuple[FixedSearchTier, ...] = (
        FixedSearchTier("shallow", 16),
        FixedSearchTier("medium", 64),
        FixedSearchTier("expensive", 256),
    )
    exploration_constant: float = math.sqrt(2.0)
    sampling_seed: int = 0
    maximum_rollout_steps: int = 4096
    workers: int = 4
    worker_timeout_seconds: float = 120.0

    def __post_init__(self) -> None:
        names = tuple(tier.name for tier in self.tiers)
        if names != REQUIRED_TIER_NAMES:
            raise ValueError(f"Fixed-search tiers must be ordered as {REQUIRED_TIER_NAMES}")
        simulations = tuple(tier.simulations for tier in self.tiers)
        if simulations != tuple(sorted(set(simulations))):
            raise ValueError("Fixed-search simulation budgets must be strictly increasing")
        if not math.isfinite(self.exploration_constant) or self.exploration_constant < 0.0:
            raise ValueError("exploration_constant must be finite and non-negative")
        if isinstance(self.sampling_seed, bool) or self.sampling_seed < 0:
            raise ValueError("sampling_seed must be non-negative")
        if self.maximum_rollout_steps <= 0:
            raise ValueError("maximum_rollout_steps must be positive")
        if self.workers <= 0:
            raise ValueError("workers must be positive")
        if not math.isfinite(self.worker_timeout_seconds) or self.worker_timeout_seconds <= 0.0:
            raise ValueError("worker_timeout_seconds must be finite and positive")

    def as_dict(self) -> dict[str, object]:
        return {
            "tiers": [tier.as_dict() for tier in self.tiers],
            "exploration_constant": self.exploration_constant,
            "sampling_seed": self.sampling_seed,
            "maximum_rollout_steps": self.maximum_rollout_steps,
            "workers": self.workers,
            "worker_timeout_seconds": self.worker_timeout_seconds,
        }


@dataclass(frozen=True, slots=True)
class CapturedCombatState:
    checkpoint: PublicStateCheckpoint
    observation: Observation
    legal_actions: tuple[LegalAction, ...]
    capture_method: str
    combat_state_index: int | None


@dataclass(frozen=True, slots=True)
class FixedSearchSuiteResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FixedSearchVerification:
    valid: bool
    report_id: str | None
    tiers: int
    simulations: int
    verified_worker_batches: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": FIXED_SEARCH_VERIFICATION_SCHEMA_VERSION,
            "valid": self.valid,
            "report_id": self.report_id,
            "tiers": self.tiers,
            "simulations": self.simulations,
            "verified_worker_batches": self.verified_worker_batches,
            "errors": list(self.errors),
        }


class CombatSearchPlanner(Protocol):
    planner_id: str

    def plan_tier(
        self,
        *,
        backend: SearchBackendSpec,
        captured: CapturedCombatState,
        tier: FixedSearchTier,
        config: FixedSearchConfig,
        output_directory: Path,
        task_runner: SearchTaskRunner | None = None,
    ) -> dict[str, Any]: ...


@dataclass(slots=True)
class _CandidateAccumulator:
    index: int
    action: LegalAction
    attempted: int = 0
    completed: int = 0
    terminal: int = 0
    truncated: int = 0
    failures: int = 0
    victories: int = 0
    transitions: int = 0
    sampled_worlds: int = 0
    cpu_seconds: float = 0.0
    worker_wall_seconds: float = 0.0

    @property
    def conservative_value(self) -> float:
        return self.victories / self.attempted if self.attempted else 0.0


class IsolatedRootUctPlanner:
    planner_id = FIXED_SEARCH_PLANNER_ID

    def plan_tier(
        self,
        *,
        backend: SearchBackendSpec,
        captured: CapturedCombatState,
        tier: FixedSearchTier,
        config: FixedSearchConfig,
        output_directory: Path,
        task_runner: SearchTaskRunner | None = None,
    ) -> dict[str, Any]:
        actions = captured.legal_actions
        if tier.simulations < len(actions):
            raise ValueError(
                f"{tier.name} budget {tier.simulations} cannot visit all {len(actions)} candidates"
            )
        accumulators = [
            _CandidateAccumulator(index=index, action=action)
            for index, action in enumerate(actions)
        ]
        simulations: list[dict[str, Any]] = []
        wave_reports: list[dict[str, object]] = []
        started = time.perf_counter()
        ordinal = 0
        wave_index = 0
        while ordinal < tier.simulations:
            wave_size = min(config.workers, tier.simulations - ordinal)
            tasks: list[SearchSimulationTask] = []
            task_context: dict[str, tuple[int, int]] = {}
            for _ in range(wave_size):
                candidate_index = _select_candidate(accumulators, config.exploration_constant)
                candidate = accumulators[candidate_index]
                simulation_seed = _simulation_seed(
                    config.sampling_seed,
                    captured.checkpoint.state_hash,
                    ordinal,
                )
                task_id = str(
                    uuid5(
                        NAMESPACE_URL,
                        "|".join(
                            (
                                FIXED_SEARCH_PLANNER_ID,
                                captured.checkpoint.ruleset_manifest_id,
                                captured.checkpoint.state_hash,
                                candidate.action.action_id,
                                str(simulation_seed),
                            )
                        ),
                    )
                )
                task = SearchSimulationTask.create(
                    backend=backend,
                    checkpoint=captured.checkpoint,
                    action_id=candidate.action.action_id,
                    simulation_seed=simulation_seed,
                    maximum_rollout_steps=config.maximum_rollout_steps,
                    task_id=task_id,
                )
                tasks.append(task)
                task_context[task_id] = (ordinal, candidate_index)
                candidate.attempted += 1
                ordinal += 1
            wave_directory = output_directory / f"wave-{wave_index:04d}"
            batch = run_search_worker_batch(
                tasks=tasks,
                workers=config.workers,
                worker_timeout_seconds=config.worker_timeout_seconds,
                output_directory=wave_directory,
                task_runner=task_runner,
                batch_id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"{captured.checkpoint.state_hash}|{tier.name}|wave|{wave_index}",
                    )
                ),
            )
            relative_report = str(batch.report_path.relative_to(output_directory.parent.parent))
            wave_reports.append(
                {
                    "wave_index": wave_index,
                    "report_path": relative_report,
                    "report_sha256": sha256_file(batch.report_path),
                }
            )
            raw_evidence = batch.report.get("tasks")
            if not isinstance(raw_evidence, list):
                raise RuntimeError("Search worker batch omitted task evidence")
            for raw_item in raw_evidence:
                item = _mapping(raw_item, "search worker evidence")
                task_id = _string(item.get("task_id"), "task_id")
                simulation_ordinal, candidate_index = task_context[task_id]
                candidate = accumulators[candidate_index]
                status = _string(item.get("status"), "status")
                cpu_seconds = _optional_number(item.get("cpu_seconds"))
                wall_seconds = _optional_number(item.get("wall_seconds"))
                if cpu_seconds is not None:
                    candidate.cpu_seconds += cpu_seconds
                if wall_seconds is not None:
                    candidate.worker_wall_seconds += wall_seconds
                output_value = item.get("output")
                output = output_value if isinstance(output_value, dict) else None
                if status == SearchWorkerStatus.COMPLETED.value and output is not None:
                    candidate.completed += 1
                    transitions = _integer(output.get("transitions"), "transitions")
                    candidate.transitions += transitions
                    candidate.sampled_worlds += _integer(
                        output.get("sampled_worlds"), "sampled_worlds"
                    )
                    terminal = _boolean(output.get("terminal"), "terminal")
                    truncated = _boolean(output.get("truncated"), "truncated")
                    victory = _boolean(output.get("victory"), "victory")
                    candidate.terminal += int(terminal)
                    candidate.truncated += int(truncated)
                    candidate.victories += int(terminal and victory)
                    candidate.failures += int(not terminal)
                else:
                    candidate.failures += 1
                simulations.append(
                    {
                        "ordinal": simulation_ordinal,
                        "task_id": task_id,
                        "candidate_index": candidate_index,
                        "source_action_id": candidate.action.action_id,
                        "simulation_seed": tasks[
                            next(
                                index for index, task in enumerate(tasks) if task.task_id == task_id
                            )
                        ].simulation_seed,
                        "status": status,
                        "cpu_seconds": cpu_seconds,
                        "wall_seconds": wall_seconds,
                        "output": output,
                    }
                )
            wave_index += 1
        simulations.sort(key=lambda item: cast(int, item["ordinal"]))
        tier_wall_seconds = time.perf_counter() - started
        candidates = [
            _candidate_document(candidate, tier.simulations) for candidate in accumulators
        ]
        selected_index = max(
            range(len(accumulators)),
            key=lambda index: (
                accumulators[index].conservative_value,
                accumulators[index].terminal,
                -index,
            ),
        )
        attempted = sum(candidate.attempted for candidate in accumulators)
        completed = sum(candidate.completed for candidate in accumulators)
        terminal_count = sum(candidate.terminal for candidate in accumulators)
        failures = sum(candidate.failures for candidate in accumulators)
        transitions = sum(candidate.transitions for candidate in accumulators)
        sampled_worlds = sum(candidate.sampled_worlds for candidate in accumulators)
        cpu_seconds = sum(candidate.cpu_seconds for candidate in accumulators)
        worker_latencies = [
            cast(float, simulation["wall_seconds"])
            for simulation in simulations
            if isinstance(simulation.get("wall_seconds"), (int, float))
            and not isinstance(simulation.get("wall_seconds"), bool)
        ]
        return {
            "tier": tier.name,
            "simulation_budget": tier.simulations,
            "selected_candidate_index": selected_index,
            "selected_action_id": actions[selected_index].action_id,
            "candidates": candidates,
            "simulations": simulations,
            "wave_reports": wave_reports,
            "summary": {
                "attempted_simulations": attempted,
                "completed_simulations": completed,
                "terminal_simulations": terminal_count,
                "failed_or_truncated_simulations": failures,
                "worker_crashes": sum(
                    simulation["status"]
                    in {SearchWorkerStatus.CRASHED.value, SearchWorkerStatus.TIMEOUT.value}
                    for simulation in simulations
                ),
                "transitions": transitions,
                "sampled_worlds": sampled_worlds,
                "unique_simulation_seeds": len(
                    {simulation["simulation_seed"] for simulation in simulations}
                ),
                "unique_final_state_hashes": len(
                    {
                        output["final_state_hash"]
                        for simulation in simulations
                        for output in [simulation.get("output")]
                        if isinstance(output, dict)
                        and isinstance(output.get("final_state_hash"), str)
                    }
                ),
                "worker_cpu_seconds": cpu_seconds,
                "wall_seconds": tier_wall_seconds,
                "mean_worker_wall_seconds": _mean_or_none(worker_latencies),
                "p95_worker_wall_seconds": _percentile_or_none(worker_latencies, 0.95),
            },
        }


def capture_combat_state(
    *,
    backend: SearchBackendSpec,
    run_seed: int,
    combat_state_index: int = 0,
    maximum_prefix_steps: int = 4096,
    action_prefix: Sequence[str] | None = None,
) -> CapturedCombatState:
    if isinstance(combat_state_index, bool) or combat_state_index < 0:
        raise ValueError("combat_state_index must be non-negative")
    if maximum_prefix_steps <= 0:
        raise ValueError("maximum_prefix_steps must be positive")
    environment = load_search_environment(backend)
    observation = environment.reset(run_seed)
    prefix: list[str] = []
    try:
        if action_prefix is not None:
            for action_id in action_prefix:
                action = _action_by_id(environment.legal_actions(), action_id)
                observation = environment.step(action).next_observation
                prefix.append(action_id)
            _require_combat(observation)
            actions = tuple(environment.legal_actions())
            if not actions:
                raise RuntimeError("Captured combat state has no legal actions")
            return CapturedCombatState(
                capture_checkpoint(
                    run_seed=run_seed,
                    action_prefix=prefix,
                    environment=environment,
                    observation=observation,
                ),
                observation,
                actions,
                "explicit_action_prefix",
                None,
            )
        seen_combat_states = 0
        policy = SearchRolloutPolicy()
        for _ in range(maximum_prefix_steps + 1):
            if observation.decision_type in {DecisionType.COMBAT, DecisionType.COMBAT_SELECTION}:
                if seen_combat_states == combat_state_index:
                    actions = tuple(environment.legal_actions())
                    if not actions:
                        raise RuntimeError("Captured combat state has no legal actions")
                    return CapturedCombatState(
                        capture_checkpoint(
                            run_seed=run_seed,
                            action_prefix=prefix,
                            environment=environment,
                            observation=observation,
                        ),
                        observation,
                        actions,
                        "baseline_policy_combat_index",
                        combat_state_index,
                    )
                seen_combat_states += 1
            if bool(observation.public_state.get("terminal")):
                break
            actions = tuple(environment.legal_actions())
            action = policy.choose_action(observation, actions)
            transition = environment.step(action)
            prefix.append(action.action_id)
            observation = transition.next_observation
        raise RuntimeError(f"Run ended before combat state index {combat_state_index} was captured")
    finally:
        _close_environment(environment)


def run_fixed_search_suite(
    *,
    backend: SearchBackendSpec,
    run_seed: int,
    output_directory: Path,
    config: FixedSearchConfig | None = None,
    combat_state_index: int = 0,
    maximum_prefix_steps: int = 4096,
    action_prefix: Sequence[str] | None = None,
    planner: CombatSearchPlanner | None = None,
    task_runner: SearchTaskRunner | None = None,
    now: Callable[[], str] | None = None,
) -> FixedSearchSuiteResult:
    selected_config = config or FixedSearchConfig()
    output_directory.mkdir(parents=True, exist_ok=False)
    output_directory = output_directory.resolve()
    captured = capture_combat_state(
        backend=backend,
        run_seed=run_seed,
        combat_state_index=combat_state_index,
        maximum_prefix_steps=maximum_prefix_steps,
        action_prefix=action_prefix,
    )
    if selected_config.tiers[0].simulations < len(captured.legal_actions):
        raise ValueError(
            "Shallow search budget must visit every legal candidate at least once: "
            f"budget={selected_config.tiers[0].simulations}, "
            f"candidates={len(captured.legal_actions)}"
        )
    selected_planner = planner or IsolatedRootUctPlanner()
    started_at = (now or _utc_now)()
    tiers: list[dict[str, Any]] = []
    for tier in selected_config.tiers:
        tiers.append(
            selected_planner.plan_tier(
                backend=backend,
                captured=captured,
                tier=tier,
                config=selected_config,
                output_directory=output_directory / "tiers" / tier.name,
                task_runner=task_runner,
            )
        )
    completed_at = (now or _utc_now)()
    total_simulations = sum(
        _integer(_mapping(tier["summary"], "tier summary")["attempted_simulations"], "attempted")
        for tier in tiers
    )
    total_transitions = sum(
        _integer(_mapping(tier["summary"], "tier summary")["transitions"], "transitions")
        for tier in tiers
    )
    total_failures = sum(
        _integer(
            _mapping(tier["summary"], "tier summary")["failed_or_truncated_simulations"],
            "failures",
        )
        for tier in tiers
    )
    report_body: dict[str, Any] = {
        "schema_version": FIXED_SEARCH_REPORT_SCHEMA_VERSION,
        "planner_id": selected_planner.planner_id,
        "objective_id": FIXED_SEARCH_OBJECTIVE_ID,
        "started_at": started_at,
        "completed_at": completed_at,
        "backend": backend.as_dict(),
        "backend_attribution": _backend_attribution(backend),
        "ruleset_manifest_id": captured.checkpoint.ruleset_manifest_id,
        "patch_id": captured.checkpoint.patch_id,
        "configuration": selected_config.as_dict(),
        "capture": {
            "method": captured.capture_method,
            "combat_state_index": captured.combat_state_index,
            "policy_id": (
                SearchRolloutPolicy().policy_id
                if captured.capture_method == "baseline_policy_combat_index"
                else None
            ),
        },
        "checkpoint": captured.checkpoint.as_dict(),
        "decision_type": captured.observation.decision_type.value,
        "legal_actions": [action.as_dict() for action in captured.legal_actions],
        "tiers": tiers,
        "summary": {
            "tiers": len(tiers),
            "candidate_count": len(captured.legal_actions),
            "attempted_simulations": total_simulations,
            "failed_or_truncated_simulations": total_failures,
            "transitions": total_transitions,
            "all_tiers_complete": total_failures == 0,
            "selected_action_ids": {
                _string(tier["tier"], "tier"): _string(
                    tier["selected_action_id"], "selected_action_id"
                )
                for tier in tiers
            },
        },
    }
    report = {**report_body, "report_id": manifest_identifier(report_body)}
    report_path = output_directory / "fixed-search-report.json"
    write_exclusive_json(report_path, report)
    return FixedSearchSuiteResult(total_failures == 0, report_path, report)


def verify_fixed_search_report(report_path: Path) -> FixedSearchVerification:
    errors: list[str] = []
    report_id: str | None = None
    verified_worker_batches = 0
    simulations_count = 0
    try:
        report = _load_object(report_path)
        raw_id = report.get("report_id")
        report_id = raw_id if isinstance(raw_id, str) else None
        body = {key: value for key, value in report.items() if key != "report_id"}
        if report_id != manifest_identifier(body):
            errors.append("fixed-search report identity mismatch")
        if report.get("schema_version") != FIXED_SEARCH_REPORT_SCHEMA_VERSION:
            errors.append("unsupported fixed-search report schema")
        if report.get("planner_id") != FIXED_SEARCH_PLANNER_ID:
            errors.append("unsupported fixed-search planner")
        if report.get("objective_id") != FIXED_SEARCH_OBJECTIVE_ID:
            errors.append("fixed search does not optimize terminal victory")
        configuration = _mapping(report.get("configuration"), "configuration")
        configured_tiers = _list(configuration.get("tiers"), "configuration.tiers")
        names = tuple(
            _string(_mapping(tier, "configured tier").get("name"), "configured tier name")
            for tier in configured_tiers
        )
        if names != REQUIRED_TIER_NAMES:
            errors.append("fixed-search tiers are missing or out of order")
        legal_actions = _list(report.get("legal_actions"), "legal_actions")
        action_documents = tuple(_mapping(action, "legal action") for action in legal_actions)
        legal_action_ids = tuple(
            _string(action.get("action_id"), "legal action ID") for action in action_documents
        )
        raw_tiers = _list(report.get("tiers"), "tiers")
        if len(raw_tiers) != len(configured_tiers):
            errors.append("configured and reported tier counts differ")
        prefixes: dict[int, tuple[str, int]] = {}
        root_directory = report_path.parent.resolve()
        total_failures = 0
        total_transitions = 0
        for tier_offset, raw_tier in enumerate(raw_tiers):
            tier = _mapping(raw_tier, f"tiers[{tier_offset}]")
            tier_name = _string(tier.get("tier"), "tier")
            configured_tier = _mapping(configured_tiers[tier_offset], "configured tier")
            simulations = _list(tier.get("simulations"), "tier simulations")
            simulations_count += len(simulations)
            budget = _integer(tier.get("simulation_budget"), "simulation_budget")
            if tier_name != configured_tier.get("name"):
                errors.append(f"tier {tier_name}: name differs from configuration")
            if budget != configured_tier.get("simulations"):
                errors.append(f"tier {tier_name}: budget differs from configuration")
            if len(simulations) != budget:
                errors.append(f"tier {tier_name}: simulation count differs from budget")
            ordinals = [
                _integer(item.get("ordinal"), "ordinal") for item in map(_as_mapping, simulations)
            ]
            if ordinals != list(range(budget)):
                errors.append(f"tier {tier_name}: simulation ordinals are not contiguous")
            for raw_simulation in simulations:
                simulation = _mapping(raw_simulation, "simulation")
                ordinal = _integer(simulation.get("ordinal"), "ordinal")
                action_id = _string(simulation.get("source_action_id"), "source_action_id")
                seed = _integer(simulation.get("simulation_seed"), "simulation_seed")
                if action_id not in legal_action_ids:
                    errors.append(f"tier {tier_name}: simulation uses an unknown action")
                output = simulation.get("output")
                if isinstance(output, dict) and (
                    output.get("source_state_hash")
                    != _mapping(report.get("checkpoint"), "checkpoint").get("state_hash")
                    or output.get("action_id") != action_id
                    or output.get("simulation_seed") != seed
                ):
                    errors.append(f"tier {tier_name}: simulation output identity mismatch")
                expected_prefix = prefixes.get(ordinal)
                current_prefix = (action_id, seed)
                if expected_prefix is None:
                    prefixes[ordinal] = current_prefix
                elif expected_prefix != current_prefix:
                    errors.append(
                        f"tier {tier_name}: paired simulation prefix differs at {ordinal}"
                    )
            worker_evidence: dict[str, dict[str, Any]] = {}
            for raw_wave in _list(tier.get("wave_reports"), "wave_reports"):
                wave = _mapping(raw_wave, "wave report")
                relative = _string(wave.get("report_path"), "wave report path")
                worker_report = _safe_child(root_directory, relative)
                expected_digest = _string(wave.get("report_sha256"), "wave report digest")
                if sha256_file(worker_report) != expected_digest:
                    errors.append(f"worker report digest mismatch: {relative}")
                    continue
                verification = verify_search_worker_batch(worker_report)
                if not verification.valid:
                    errors.extend(
                        f"worker report {relative}: {error}" for error in verification.errors
                    )
                else:
                    verified_worker_batches += 1
                worker_document = _load_object(worker_report)
                for raw_worker_task in _list(worker_document.get("tasks"), "worker tasks"):
                    worker_task = _mapping(raw_worker_task, "worker task")
                    worker_task_id = _string(worker_task.get("task_id"), "worker task ID")
                    if worker_task_id in worker_evidence:
                        errors.append(f"tier {tier_name}: duplicate worker task ID")
                    worker_evidence[worker_task_id] = worker_task
            simulation_by_task = {
                _string(simulation.get("task_id"), "simulation task ID"): simulation
                for simulation in map(_as_mapping, simulations)
            }
            if set(worker_evidence) != set(simulation_by_task):
                errors.append(f"tier {tier_name}: worker and simulation task IDs differ")
            for task_id, simulation in simulation_by_task.items():
                worker = worker_evidence.get(task_id)
                if worker is None:
                    continue
                for field in ("status", "cpu_seconds", "wall_seconds", "output"):
                    if simulation.get(field) != worker.get(field):
                        errors.append(f"tier {tier_name}: task {task_id} {field} mismatch")
            tier_failures, tier_transitions = _verify_tier_aggregates(
                tier,
                action_documents,
                simulations,
                errors,
            )
            total_failures += tier_failures
            total_transitions += tier_transitions
            selected_index = _integer(
                tier.get("selected_candidate_index"), "selected_candidate_index"
            )
            candidates = _list(tier.get("candidates"), "candidates")
            if not 0 <= selected_index < len(candidates):
                errors.append(f"tier {tier_name}: selected candidate is out of range")
            elif tier.get("selected_action_id") != _mapping(
                candidates[selected_index], "selected candidate"
            ).get("source_action_id"):
                errors.append(f"tier {tier_name}: selected action is misaligned")
        summary = _mapping(report.get("summary"), "summary")
        if summary.get("tiers") != len(raw_tiers):
            errors.append("summary tier count mismatch")
        if summary.get("attempted_simulations") != simulations_count:
            errors.append("summary simulation count mismatch")
        if summary.get("failed_or_truncated_simulations") != total_failures:
            errors.append("summary failed simulation count mismatch")
        if summary.get("transitions") != total_transitions:
            errors.append("summary transition count mismatch")
        if summary.get("all_tiers_complete") is not (total_failures == 0):
            errors.append("summary completion flag mismatch")
    except (IndexError, KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return FixedSearchVerification(
        not errors,
        report_id,
        len(raw_tiers) if "raw_tiers" in locals() else 0,
        simulations_count,
        verified_worker_batches,
        tuple(errors),
    )


def load_fixed_search_report(path: Path) -> dict[str, Any]:
    report = _load_object(path)
    if report.get("schema_version") != FIXED_SEARCH_REPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported fixed-search report schema")
    return report


def _verify_tier_aggregates(
    tier: dict[str, Any],
    legal_actions: Sequence[dict[str, Any]],
    simulations: Sequence[object],
    errors: list[str],
) -> tuple[int, int]:
    tier_name = _string(tier.get("tier"), "tier")
    budget = _integer(tier.get("simulation_budget"), "simulation_budget")
    counters = [
        {
            "attempted": 0,
            "completed": 0,
            "terminal": 0,
            "truncated": 0,
            "failures": 0,
            "victories": 0,
            "transitions": 0,
            "sampled_worlds": 0,
            "cpu_seconds": 0.0,
            "wall_seconds": 0.0,
        }
        for _ in legal_actions
    ]
    final_hashes: set[str] = set()
    worker_latencies: list[float] = []
    worker_crashes = 0
    for raw_simulation in simulations:
        simulation = _mapping(raw_simulation, "simulation")
        candidate_index = _integer(simulation.get("candidate_index"), "candidate_index")
        if not 0 <= candidate_index < len(counters):
            errors.append(f"tier {tier_name}: simulation candidate is out of range")
            continue
        counter = counters[candidate_index]
        counter["attempted"] += 1
        action_id = _string(simulation.get("source_action_id"), "source_action_id")
        if action_id != legal_actions[candidate_index].get("action_id"):
            errors.append(f"tier {tier_name}: candidate action alignment mismatch")
        status = _string(simulation.get("status"), "status")
        worker_crashes += int(
            status in {SearchWorkerStatus.CRASHED.value, SearchWorkerStatus.TIMEOUT.value}
        )
        cpu_seconds = _optional_number(simulation.get("cpu_seconds"))
        wall_seconds = _optional_number(simulation.get("wall_seconds"))
        if cpu_seconds is not None:
            counter["cpu_seconds"] += cpu_seconds
        if wall_seconds is not None:
            counter["wall_seconds"] += wall_seconds
            worker_latencies.append(wall_seconds)
        output_value = simulation.get("output")
        output = output_value if isinstance(output_value, dict) else None
        if status == SearchWorkerStatus.COMPLETED.value and output is not None:
            counter["completed"] += 1
            transitions = _integer(output.get("transitions"), "transitions")
            sampled_worlds = _integer(output.get("sampled_worlds"), "sampled_worlds")
            terminal = _boolean(output.get("terminal"), "terminal")
            truncated = _boolean(output.get("truncated"), "truncated")
            victory = _boolean(output.get("victory"), "victory")
            counter["transitions"] += transitions
            counter["sampled_worlds"] += sampled_worlds
            counter["terminal"] += int(terminal)
            counter["truncated"] += int(truncated)
            counter["victories"] += int(terminal and victory)
            counter["failures"] += int(not terminal)
            final_hash = output.get("final_state_hash")
            if isinstance(final_hash, str):
                final_hashes.add(final_hash)
        else:
            counter["failures"] += 1
    candidates = _list(tier.get("candidates"), "candidates")
    if len(candidates) != len(legal_actions):
        errors.append(f"tier {tier_name}: candidate count differs from legal actions")
    for index, counter in enumerate(counters):
        if index >= len(candidates):
            break
        candidate = _mapping(candidates[index], "candidate")
        expected_integers = {
            "candidate_index": index,
            "attempted_simulations": counter["attempted"],
            "completed_simulations": counter["completed"],
            "terminal_simulations": counter["terminal"],
            "truncated_simulations": counter["truncated"],
            "failed_simulations": counter["failures"],
            "victories": counter["victories"],
            "transitions": counter["transitions"],
            "sampled_worlds": counter["sampled_worlds"],
        }
        for field, expected in expected_integers.items():
            if candidate.get(field) != expected:
                errors.append(f"tier {tier_name}: candidate {index} {field} mismatch")
        if candidate.get("source_action_id") != legal_actions[index].get("action_id"):
            errors.append(f"tier {tier_name}: candidate {index} source action mismatch")
        if candidate.get("action_kind") != legal_actions[index].get("kind"):
            errors.append(f"tier {tier_name}: candidate {index} action kind mismatch")
        attempted = cast(int, counter["attempted"])
        terminal_count = cast(int, counter["terminal"])
        victories = cast(int, counter["victories"])
        terminal_value = victories / attempted if attempted else 0.0
        expected_floats: dict[str, float | None] = {
            "terminal_value": terminal_value,
            "completed_terminal_value": (victories / terminal_count if terminal_count else None),
            "outcome_variance": terminal_value * (1.0 - terminal_value),
            "visit_probability": attempted / budget,
            "worker_cpu_seconds": counter["cpu_seconds"],
            "worker_wall_seconds": counter["wall_seconds"],
        }
        for field, expected_candidate in expected_floats.items():
            actual = candidate.get(field)
            if expected_candidate is None:
                if actual is not None:
                    errors.append(f"tier {tier_name}: candidate {index} {field} mismatch")
            elif not _numbers_close(actual, expected_candidate):
                errors.append(f"tier {tier_name}: candidate {index} {field} mismatch")
    summary = _mapping(tier.get("summary"), "tier summary")

    def total(key: str) -> int | float:
        return sum(cast(int | float, counter[key]) for counter in counters)

    expected_summary: dict[str, int | float | None] = {
        "attempted_simulations": int(total("attempted")),
        "completed_simulations": int(total("completed")),
        "terminal_simulations": int(total("terminal")),
        "failed_or_truncated_simulations": int(total("failures")),
        "worker_crashes": worker_crashes,
        "transitions": int(total("transitions")),
        "sampled_worlds": int(total("sampled_worlds")),
        "unique_simulation_seeds": len(
            {
                _integer(_mapping(value, "simulation").get("simulation_seed"), "seed")
                for value in simulations
            }
        ),
        "unique_final_state_hashes": len(final_hashes),
        "worker_cpu_seconds": float(total("cpu_seconds")),
        "mean_worker_wall_seconds": _mean_or_none(worker_latencies),
        "p95_worker_wall_seconds": _percentile_or_none(worker_latencies, 0.95),
    }
    for field, expected_summary_value in expected_summary.items():
        actual = summary.get(field)
        if isinstance(expected_summary_value, float):
            if not _numbers_close(actual, expected_summary_value):
                errors.append(f"tier {tier_name}: summary {field} mismatch")
        elif actual != expected_summary_value:
            errors.append(f"tier {tier_name}: summary {field} mismatch")
    expected_selected = max(
        range(len(counters)),
        key=lambda index: (
            cast(int, counters[index]["victories"])
            / max(1, cast(int, counters[index]["attempted"])),
            cast(int, counters[index]["terminal"]),
            -index,
        ),
    )
    if tier.get("selected_candidate_index") != expected_selected:
        errors.append(f"tier {tier_name}: selected candidate differs from terminal value")
    return int(total("failures")), int(total("transitions"))


def _select_candidate(
    accumulators: Sequence[_CandidateAccumulator], exploration_constant: float
) -> int:
    unvisited = [candidate.index for candidate in accumulators if candidate.attempted == 0]
    if unvisited:
        return unvisited[0]
    total = sum(candidate.attempted for candidate in accumulators)
    return max(
        range(len(accumulators)),
        key=lambda index: (
            accumulators[index].conservative_value
            + exploration_constant
            * math.sqrt(math.log(max(1, total)) / accumulators[index].attempted),
            -index,
        ),
    )


def _candidate_document(
    candidate: _CandidateAccumulator, total_simulations: int
) -> dict[str, object]:
    completed_value = candidate.victories / candidate.terminal if candidate.terminal else None
    conservative_value = candidate.conservative_value
    return {
        "candidate_index": candidate.index,
        "source_action_id": candidate.action.action_id,
        "action_kind": candidate.action.kind,
        "attempted_simulations": candidate.attempted,
        "completed_simulations": candidate.completed,
        "terminal_simulations": candidate.terminal,
        "truncated_simulations": candidate.truncated,
        "failed_simulations": candidate.failures,
        "victories": candidate.victories,
        "terminal_value": conservative_value,
        "completed_terminal_value": completed_value,
        "outcome_variance": conservative_value * (1.0 - conservative_value),
        "visit_probability": candidate.attempted / total_simulations,
        "transitions": candidate.transitions,
        "sampled_worlds": candidate.sampled_worlds,
        "worker_cpu_seconds": candidate.cpu_seconds,
        "worker_wall_seconds": candidate.worker_wall_seconds,
    }


def _simulation_seed(sampling_seed: int, state_hash: str, ordinal: int) -> int:
    payload = f"{sampling_seed}|{state_hash}|fixed-search|{ordinal}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") & ((1 << 63) - 1)


def _backend_attribution(backend: SearchBackendSpec) -> dict[str, object]:
    if backend.kind == "evangambit":
        return {
            "project": "evangambit/sts2",
            "license": "MIT",
            "source": "https://github.com/evangambit/sts2",
            "role": "pinned external simulator backend",
        }
    return {
        "project": "SpireShift",
        "license": "project fixture",
        "source": "spireshift://src/spireshift/adapters",
        "role": "test-only simulator backend",
    }


def _require_combat(observation: Observation) -> None:
    if observation.decision_type not in {DecisionType.COMBAT, DecisionType.COMBAT_SELECTION}:
        raise ValueError(
            f"Fixed combat search requires a combat state, got {observation.decision_type.value}"
        )


def _close_environment(environment: EnvironmentAdapter) -> None:
    close = getattr(environment, "close", None)
    if callable(close):
        close()


def _action_by_id(actions: Sequence[LegalAction], action_id: str) -> LegalAction:
    matches = [action for action in actions if action.action_id == action_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one legal action {action_id!r}, found {len(matches)}")
    return matches[0]


def _mean_or_none(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _percentile_or_none(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = math.ceil(quantile * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _safe_child(directory: Path, relative: str) -> Path:
    candidate = (directory / relative).resolve()
    if candidate == directory or directory not in candidate.parents:
        raise ValueError("worker report path escapes the fixed-search directory")
    return candidate


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


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
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be boolean")
    return value


def _optional_number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("optional number must be numeric or null")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError("optional number must be finite and non-negative")
    return result


def _numbers_close(value: object, expected: float) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isclose(float(value), expected, rel_tol=1e-12, abs_tol=1e-12)
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
