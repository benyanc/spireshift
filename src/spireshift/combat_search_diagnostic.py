from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spireshift.agents.combat_advancement import (
    CombatAdvancementConfig,
    CombatAdvancementPolicy,
    CombatAdvancementUsage,
    combat_advancement_policy_id,
)
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

COMBAT_SEARCH_DIAGNOSTIC_SPEC_SCHEMA_VERSION = "combat-search-diagnostic-spec-v1"
COMBAT_SEARCH_DIAGNOSTIC_CASE_SCHEMA_VERSION = "combat-search-diagnostic-case-v1"
COMBAT_SEARCH_DIAGNOSTIC_REPORT_SCHEMA_VERSION = "combat-search-diagnostic-report-v1"
BASE_VARIANT_NAME = "base"
BASE_POLICY_KIND = "production_checkpoint"
SEARCH_POLICY_KIND = "combat_advancement"
CLAIM_SCOPE = "paired_train_only_combat_search_diagnostic"
_VARIANT_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IDENTIFIER_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class CombatSearchDiagnosticVariant:
    name: str
    config: CombatAdvancementConfig

    def __post_init__(self) -> None:
        if self.name == BASE_VARIANT_NAME or _VARIANT_PATTERN.fullmatch(self.name) is None:
            raise ValueError("Combat-search diagnostic variant name differs")
        if self.config.schema_version != "combat-advancement-config-v2":
            raise ValueError("Combat-search diagnostics require v2 selection configuration")

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "combat_advancement_config": self.config.as_dict()}


@dataclass(frozen=True, slots=True)
class CombatSearchDiagnosticSpec:
    split_manifest_id: str
    ruleset_manifest_id: str
    model_id: str
    training_report_id: str
    run_offset: int
    run_count: int
    workers: int
    maximum_decisions_per_run: int
    cycle_repetition_threshold: int
    variants: tuple[CombatSearchDiagnosticVariant, ...]
    objective_id: str = "terminal-victory-v1"
    partition: str = SplitName.TRAIN.value
    schema_version: str = COMBAT_SEARCH_DIAGNOSTIC_SPEC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COMBAT_SEARCH_DIAGNOSTIC_SPEC_SCHEMA_VERSION:
            raise ValueError("Combat-search diagnostic specification schema differs")
        if self.partition != SplitName.TRAIN.value:
            raise ValueError("Combat-search diagnostics may use only train seeds")
        if self.objective_id != "terminal-victory-v1":
            raise ValueError("Combat-search diagnostics must preserve terminal victory")
        for name, value in (
            ("split_manifest_id", self.split_manifest_id),
            ("ruleset_manifest_id", self.ruleset_manifest_id),
            ("model_id", self.model_id),
            ("training_report_id", self.training_report_id),
        ):
            if _IDENTIFIER_PATTERN.fullmatch(value) is None:
                raise ValueError(f"{name} must be a content identifier")
        for count_name, count_value, minimum in (
            ("run_offset", self.run_offset, 0),
            ("run_count", self.run_count, 1),
            ("workers", self.workers, 1),
            ("maximum_decisions_per_run", self.maximum_decisions_per_run, 1),
            ("cycle_repetition_threshold", self.cycle_repetition_threshold, 2),
        ):
            if isinstance(count_value, bool) or count_value < minimum:
                raise ValueError(f"{count_name} must be at least {minimum}")
        if not self.variants:
            raise ValueError("Combat-search diagnostic specification has no search variants")
        names = [variant.name for variant in self.variants]
        ids = [variant.config.config_id for variant in self.variants]
        if len(names) != len(set(names)) or len(ids) != len(set(ids)):
            raise ValueError("Combat-search diagnostic variants must be unique")
        if sum(variant.config.selection_mode == "shadow" for variant in self.variants) != 1:
            raise ValueError("Combat-search diagnostics require exactly one shadow variant")

    def body(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "model_id": self.model_id,
            "training_report_id": self.training_report_id,
            "partition": self.partition,
            "run_offset": self.run_offset,
            "run_count": self.run_count,
            "workers": self.workers,
            "maximum_decisions_per_run": self.maximum_decisions_per_run,
            "cycle_repetition_threshold": self.cycle_repetition_threshold,
            "variants": [variant.as_dict() for variant in self.variants],
        }

    @property
    def spec_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "spec_id": self.spec_id}

    @classmethod
    def from_mapping(cls, value: object) -> CombatSearchDiagnosticSpec:
        document = _mapping(value, "combat-search diagnostic specification")
        expected = {
            "schema_version",
            "spec_id",
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "model_id",
            "training_report_id",
            "partition",
            "run_offset",
            "run_count",
            "workers",
            "maximum_decisions_per_run",
            "cycle_repetition_threshold",
            "variants",
        }
        _exact_keys(document, expected, "combat-search diagnostic specification")
        variants = tuple(
            CombatSearchDiagnosticVariant(
                name=_string(_mapping(item, "diagnostic variant").get("name"), "variant name"),
                config=CombatAdvancementConfig.from_mapping(
                    _mapping(item, "diagnostic variant").get("combat_advancement_config")
                ),
            )
            for item in _list(document.get("variants"), "diagnostic variants")
        )
        spec = cls(
            schema_version=_string(document.get("schema_version"), "schema_version"),
            split_manifest_id=_string(document.get("split_manifest_id"), "split_manifest_id"),
            ruleset_manifest_id=_string(document.get("ruleset_manifest_id"), "ruleset_manifest_id"),
            objective_id=_string(document.get("objective_id"), "objective_id"),
            model_id=_string(document.get("model_id"), "model_id"),
            training_report_id=_string(document.get("training_report_id"), "training_report_id"),
            partition=_string(document.get("partition"), "partition"),
            run_offset=_integer(document.get("run_offset"), "run_offset"),
            run_count=_integer(document.get("run_count"), "run_count"),
            workers=_integer(document.get("workers"), "workers"),
            maximum_decisions_per_run=_integer(
                document.get("maximum_decisions_per_run"), "maximum_decisions_per_run"
            ),
            cycle_repetition_threshold=_integer(
                document.get("cycle_repetition_threshold"), "cycle_repetition_threshold"
            ),
            variants=variants,
        )
        if document.get("spec_id") != spec.spec_id:
            raise ValueError("Combat-search diagnostic specification identity mismatch")
        return spec


@dataclass(frozen=True, slots=True)
class CombatSearchDiagnosticResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


def load_combat_search_diagnostic_spec(path: Path) -> CombatSearchDiagnosticSpec:
    return CombatSearchDiagnosticSpec.from_mapping(_load_object(path, "diagnostic specification"))


def run_combat_search_diagnostic(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    base_policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    spec: CombatSearchDiagnosticSpec,
    output_directory: Path,
    resume: bool = False,
    now: Callable[[], str] | None = None,
) -> CombatSearchDiagnosticResult:
    _validate_inputs(ruleset, base_policy, split_manifest, spec)
    train_seeds = split_manifest.seeds(SplitName.TRAIN)
    seeds = tuple(train_seeds[spec.run_offset : spec.run_offset + spec.run_count])
    if len(seeds) != spec.run_count:
        raise ValueError("Combat-search diagnostic seed window exceeds the train partition")
    if output_directory.exists() and not resume:
        raise FileExistsError(f"Combat-search diagnostic output already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "combat-search-diagnostic-report.json"
    if report_path.exists():
        raise FileExistsError(f"Combat-search diagnostic report already exists: {report_path}")

    variants: tuple[CombatSearchDiagnosticVariant | None, ...] = (None, *spec.variants)
    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, CombatSearchDiagnosticVariant | None, Path]] = []
    for seed in seeds:
        for variant in variants:
            case_path = _case_path(output_directory, seed, _variant_name(variant))
            if case_path.exists():
                cases.append(
                    _load_case(
                        case_path,
                        seed=seed,
                        variant=variant,
                        model_id=base_policy.model_id,
                        ruleset_manifest_id=ruleset.manifest_id,
                    )
                )
            else:
                pending.append((seed, variant, case_path))

    with ThreadPoolExecutor(max_workers=min(spec.workers, max(1, len(pending)))) as executor:
        future_to_task: dict[
            Future[dict[str, Any]], tuple[int, CombatSearchDiagnosticVariant | None, Path]
        ] = {}
        for seed, variant, case_path in pending:
            future = executor.submit(
                _evaluate_case,
                environment_factory=environment_factory,
                ruleset=ruleset,
                seed=seed,
                variant=variant,
                base_policy=base_policy,
                maximum_decisions=spec.maximum_decisions_per_run,
                cycle_repetition_threshold=spec.cycle_repetition_threshold,
            )
            future_to_task[future] = (seed, variant, case_path)
        for future in as_completed(future_to_task):
            _, _, case_path = future_to_task[future]
            case = future.result()
            write_model_artifact(case, case_path, label="combat-search diagnostic case")
            cases.append(case)

    ordered_cases = sorted(cases, key=lambda case: (int(case["seed"]), str(case["variant_name"])))
    expected_count = len(seeds) * len(variants)
    if len(ordered_cases) != expected_count:
        raise RuntimeError("Combat-search diagnostic did not produce every paired case")
    summary = _diagnostic_summary(ordered_cases, spec)
    body: dict[str, Any] = {
        "schema_version": COMBAT_SEARCH_DIAGNOSTIC_REPORT_SCHEMA_VERSION,
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "diagnostic_spec_id": spec.spec_id,
        "model_id": base_policy.model_id,
        "training_report_id": spec.training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "configuration": {
            "seeds": list(seeds),
            "workers": spec.workers,
            "maximum_decisions_per_run": spec.maximum_decisions_per_run,
            "cycle_repetition_threshold": spec.cycle_repetition_threshold,
            "variants": _variant_provenance(spec, base_policy.model_id),
        },
        "cases": [
            {
                "seed": case["seed"],
                "variant_name": case["variant_name"],
                "path": str(
                    _case_path(
                        output_directory, int(case["seed"]), str(case["variant_name"])
                    ).relative_to(output_directory)
                ),
                "case_id": case["case_id"],
            }
            for case in ordered_cases
        ],
        "summary": summary,
        "claim_scope": CLAIM_SCOPE,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    write_model_artifact(report, report_path, label="combat-search diagnostic report")
    return CombatSearchDiagnosticResult(
        successful=all(case["status"] == "completed" for case in ordered_cases),
        report_path=report_path,
        report=report,
    )


def load_combat_search_diagnostic(
    path: Path,
    *,
    spec: CombatSearchDiagnosticSpec,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    report = _load_object(path, "combat-search diagnostic report")
    report_id = report.get("report_id")
    body = {key: item for key, item in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Combat-search diagnostic report identity mismatch")
    expected = {
        "schema_version": COMBAT_SEARCH_DIAGNOSTIC_REPORT_SCHEMA_VERSION,
        "diagnostic_spec_id": spec.spec_id,
        "model_id": spec.model_id,
        "training_report_id": spec.training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": "terminal-victory-v1",
        "claim_scope": CLAIM_SCOPE,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError("Combat-search diagnostic report provenance differs")
    configuration = _mapping(report.get("configuration"), "diagnostic configuration")
    seeds = tuple(
        _integer(seed, "diagnostic seed") for seed in _list(configuration.get("seeds"), "seeds")
    )
    expected_seeds = split_manifest.seeds(SplitName.TRAIN)[
        spec.run_offset : spec.run_offset + spec.run_count
    ]
    if seeds != expected_seeds:
        raise ValueError("Combat-search diagnostic seed window differs")
    expected_configuration = {
        "seeds": list(expected_seeds),
        "workers": spec.workers,
        "maximum_decisions_per_run": spec.maximum_decisions_per_run,
        "cycle_repetition_threshold": spec.cycle_repetition_threshold,
        "variants": _variant_provenance(spec, spec.model_id),
    }
    if configuration != expected_configuration:
        raise ValueError("Combat-search diagnostic configuration differs")

    references = _list(report.get("cases"), "diagnostic case references")
    root = path.parent.resolve()
    variant_by_name = {variant.name: variant for variant in spec.variants}
    cases: list[dict[str, Any]] = []
    coordinates: set[tuple[int, str]] = set()
    for reference_value in references:
        reference = _mapping(reference_value, "diagnostic case reference")
        _exact_keys(reference, {"seed", "variant_name", "path", "case_id"}, "case reference")
        seed = _integer(reference.get("seed"), "case seed")
        name = _string(reference.get("variant_name"), "case variant")
        coordinate = (seed, name)
        if coordinate in coordinates:
            raise ValueError("Combat-search diagnostic repeats a case")
        coordinates.add(coordinate)
        variant = None if name == BASE_VARIANT_NAME else variant_by_name.get(name)
        if name != BASE_VARIANT_NAME and variant is None:
            raise ValueError("Combat-search diagnostic case variant differs")
        relative_path = Path(_string(reference.get("path"), "case path"))
        case_path = (root / relative_path).resolve()
        if root not in case_path.parents:
            raise ValueError("Combat-search diagnostic case escapes its root")
        case = _load_case(
            case_path,
            seed=seed,
            variant=variant,
            model_id=spec.model_id,
            ruleset_manifest_id=spec.ruleset_manifest_id,
        )
        if reference.get("case_id") != case["case_id"]:
            raise ValueError("Combat-search diagnostic case reference identity mismatch")
        cases.append(case)
    expected_coordinates = {
        (seed, name)
        for seed in expected_seeds
        for name in (BASE_VARIANT_NAME, *(variant.name for variant in spec.variants))
    }
    if coordinates != expected_coordinates:
        raise ValueError("Combat-search diagnostic paired case coverage differs")
    expected_summary = _diagnostic_summary(cases, spec)
    if report.get("summary") != expected_summary:
        raise ValueError("Combat-search diagnostic summary differs from its cases")
    return report


def _validate_inputs(
    ruleset: RulesetIdentity,
    base_policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    spec: CombatSearchDiagnosticSpec,
) -> None:
    expected = {
        "model_id": base_policy.model_id,
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "objective_id": split_manifest.objective_id,
    }
    actual = {
        "model_id": spec.model_id,
        "split_manifest_id": spec.split_manifest_id,
        "ruleset_manifest_id": spec.ruleset_manifest_id,
        "objective_id": spec.objective_id,
    }
    if actual != expected:
        raise ValueError("Combat-search diagnostic identities differ")
    if getattr(base_policy, "split_manifest_id", None) != split_manifest.manifest_id:
        raise ValueError("Combat-search diagnostic policy split differs")
    if getattr(base_policy, "ruleset", None) != ruleset:
        raise ValueError("Combat-search diagnostic policy ruleset differs")


def _evaluate_case(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    seed: int,
    variant: CombatSearchDiagnosticVariant | None,
    base_policy: ProductionCheckpointPolicy,
    maximum_decisions: int,
    cycle_repetition_threshold: int,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    name = _variant_name(variant)
    policy_kind = BASE_POLICY_KIND if variant is None else SEARCH_POLICY_KIND
    policy_id = (
        base_policy.policy_id
        if variant is None
        else combat_advancement_policy_id(base_policy.model_id, variant.config)
    )
    config_id = None if variant is None else variant.config.config_id
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Combat-search diagnostic environment ruleset changed")
        policy: ProductionCheckpointPolicy | CombatAdvancementPolicy = base_policy
        if variant is not None:
            policy = CombatAdvancementPolicy(
                environment=environment,
                base_policy=base_policy,
                config=variant.config,
            )
        observation = environment.reset(seed)
        maximum_floor = _public_integer(observation.public_state.get("floor")) or 0
        decisions = 0
        action_ids: list[str] = []
        decision_wall_seconds: list[float] = []
        decision_cpu_seconds: list[float] = []
        search_trace: list[dict[str, Any]] = []
        fallback_indices: list[int] = []
        transition_counts: dict[tuple[str, str, str], int] = {}
        cycle_detected = False
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        while not terminal and decisions < maximum_decisions:
            actions = tuple(environment.legal_actions())
            if not actions:
                raise RuntimeError("Nonterminal diagnostic state has no legal actions")
            failures_before = (
                policy.usage().public_resample_failures
                if isinstance(policy, CombatAdvancementPolicy)
                else 0
            )
            wall_started = time.perf_counter()
            cpu_started = time.thread_time()
            action = policy.choose_action(observation, actions)
            decision_cpu_seconds.append(time.thread_time() - cpu_started)
            decision_wall_seconds.append(time.perf_counter() - wall_started)
            if action not in actions:
                raise RuntimeError("Combat-search diagnostic policy selected an illegal action")
            if isinstance(policy, CombatAdvancementPolicy):
                usage = policy.usage()
                if usage.public_resample_failures > failures_before:
                    fallback_indices.append(decisions)
                search_decision = policy.last_decision
                if search_decision is not None:
                    search_trace.append(
                        {
                            "decision_index": decisions,
                            "source_state_hash": search_decision.source_state_hash,
                            "base_action_id": search_decision.base_action.action_id,
                            "search_action_id": search_decision.search_action.action_id,
                            "selected_action_id": search_decision.selected_action.action_id,
                            "search_advantage": _artifact_float(search_decision.search_advantage),
                            "override_recommended": (search_decision.search_override_recommended),
                            "override_executed": search_decision.search_override_executed,
                            "selection_reason": search_decision.selection_reason,
                            "candidate_count": len(search_decision.candidates),
                            "simulated_transitions": search_decision.simulated_transitions,
                            "hidden_worlds": search_decision.hidden_worlds,
                            "public_resample_attempts": (search_decision.public_resample_attempts),
                        }
                    )
            source_hash = observation.state_hash
            action_ids.append(action.action_id)
            transition = environment.step(action)
            observation = transition.next_observation
            decisions += 1
            maximum_floor = max(
                maximum_floor,
                _public_integer(observation.public_state.get("floor")) or 0,
            )
            terminal = transition.terminal
            victory = transition.victory
            coordinate = (source_hash, action.action_id, observation.state_hash)
            transition_counts[coordinate] = transition_counts.get(coordinate, 0) + 1
            if not terminal and transition_counts[coordinate] >= cycle_repetition_threshold:
                cycle_detected = True
                break
        termination_reason = (
            "terminal" if terminal else "policy_cycle" if cycle_detected else "decision_limit"
        )
        search_diagnostics = None
        if isinstance(policy, CombatAdvancementPolicy):
            usage = policy.usage()
            if usage.search_decisions != len(search_trace):
                raise AssertionError("Combat-search trace and usage counts differ")
            if usage.public_resample_failures != len(fallback_indices):
                raise AssertionError("Combat-search fallback and usage counts differ")
            search_diagnostics = {
                "usage": usage.as_dict(),
                "recommended_overrides": sum(
                    entry["override_recommended"] is True for entry in search_trace
                ),
                "executed_overrides": sum(
                    entry["override_executed"] is True for entry in search_trace
                ),
                "fallback_decision_indices": fallback_indices,
                "decisions": search_trace,
            }
        body: dict[str, Any] = {
            "schema_version": COMBAT_SEARCH_DIAGNOSTIC_CASE_SCHEMA_VERSION,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "variant_name": name,
            "policy_kind": policy_kind,
            "policy_id": policy_id,
            "model_id": base_policy.model_id,
            "combat_advancement_config_id": config_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "completed",
            "error": None,
            "decisions": decisions,
            "terminal": terminal,
            "victory": victory if terminal else False,
            "truncated": not terminal,
            "termination_reason": termination_reason,
            "maximum_floor": maximum_floor,
            "final_state_hash": observation.state_hash,
            "action_trace_sha256": "sha256:"
            + hashlib.sha256("\n".join(action_ids).encode()).hexdigest(),
            "total_decision_seconds": _artifact_float(sum(decision_wall_seconds)),
            "total_decision_cpu_seconds": _artifact_float(sum(decision_cpu_seconds)),
            "search_diagnostics": search_diagnostics,
        }
    except Exception as error:
        body = {
            "schema_version": COMBAT_SEARCH_DIAGNOSTIC_CASE_SCHEMA_VERSION,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "variant_name": name,
            "policy_kind": policy_kind,
            "policy_id": policy_id,
            "model_id": base_policy.model_id,
            "combat_advancement_config_id": config_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "decisions": None,
            "terminal": None,
            "victory": None,
            "truncated": None,
            "termination_reason": None,
            "maximum_floor": None,
            "final_state_hash": None,
            "action_trace_sha256": None,
            "total_decision_seconds": None,
            "total_decision_cpu_seconds": None,
            "search_diagnostics": None,
        }
    finally:
        if environment is not None:
            _close_environment(environment)
    return {**body, "case_id": manifest_identifier(body)}


def _load_case(
    path: Path,
    *,
    seed: int,
    variant: CombatSearchDiagnosticVariant | None,
    model_id: str,
    ruleset_manifest_id: str,
) -> dict[str, Any]:
    case = _load_object(path, "combat-search diagnostic case")
    case_id = case.get("case_id")
    body = {key: item for key, item in case.items() if key != "case_id"}
    if case_id != manifest_identifier(body):
        raise ValueError("Combat-search diagnostic case identity mismatch")
    expected = {
        "schema_version": COMBAT_SEARCH_DIAGNOSTIC_CASE_SCHEMA_VERSION,
        "seed": seed,
        "partition": SplitName.TRAIN.value,
        "variant_name": _variant_name(variant),
        "policy_kind": BASE_POLICY_KIND if variant is None else SEARCH_POLICY_KIND,
        "policy_id": (
            f"production-checkpoint-policy-v1:{model_id}"
            if variant is None
            else combat_advancement_policy_id(model_id, variant.config)
        ),
        "model_id": model_id,
        "combat_advancement_config_id": None if variant is None else variant.config.config_id,
        "ruleset_manifest_id": ruleset_manifest_id,
    }
    if any(case.get(key) != value for key, value in expected.items()):
        raise ValueError("Combat-search diagnostic case provenance differs")
    _validate_case(case, variant=variant)
    return case


def _validate_case(case: dict[str, Any], *, variant: CombatSearchDiagnosticVariant | None) -> None:
    expected_keys = {
        "schema_version",
        "case_id",
        "seed",
        "partition",
        "variant_name",
        "policy_kind",
        "policy_id",
        "model_id",
        "combat_advancement_config_id",
        "ruleset_manifest_id",
        "status",
        "error",
        "decisions",
        "terminal",
        "victory",
        "truncated",
        "termination_reason",
        "maximum_floor",
        "final_state_hash",
        "action_trace_sha256",
        "total_decision_seconds",
        "total_decision_cpu_seconds",
        "search_diagnostics",
    }
    _exact_keys(case, expected_keys, "combat-search diagnostic case")
    result_fields = {
        "decisions",
        "terminal",
        "victory",
        "truncated",
        "termination_reason",
        "maximum_floor",
        "final_state_hash",
        "action_trace_sha256",
        "total_decision_seconds",
        "total_decision_cpu_seconds",
        "search_diagnostics",
    }
    if case.get("status") == "failed":
        if not isinstance(case.get("error"), str) or not case["error"]:
            raise ValueError("Failed combat-search diagnostic case has no error")
        if any(case.get(field) is not None for field in result_fields):
            raise ValueError("Failed combat-search diagnostic case contains results")
        return
    if case.get("status") != "completed" or case.get("error") is not None:
        raise ValueError("Combat-search diagnostic case status differs")
    decisions = _integer(case.get("decisions"), "case decisions")
    maximum_floor = _integer(case.get("maximum_floor"), "case maximum floor")
    if min(decisions, maximum_floor) < 0:
        raise ValueError("Combat-search diagnostic case counts must be non-negative")
    terminal = case.get("terminal")
    victory = case.get("victory")
    truncated = case.get("truncated")
    if not all(isinstance(value, bool) for value in (terminal, victory, truncated)):
        raise ValueError("Combat-search diagnostic outcomes must be boolean")
    if truncated is terminal or (victory is True and terminal is not True):
        raise ValueError("Combat-search diagnostic terminal outcomes are inconsistent")
    reason = case.get("termination_reason")
    if reason not in {"terminal", "policy_cycle", "decision_limit"}:
        raise ValueError("Combat-search diagnostic termination reason differs")
    if terminal is not (reason == "terminal"):
        raise ValueError("Combat-search diagnostic termination reason is inconsistent")
    _string(case.get("final_state_hash"), "final_state_hash")
    _string(case.get("action_trace_sha256"), "action_trace_sha256")
    for field in ("total_decision_seconds", "total_decision_cpu_seconds"):
        _finite_nonnegative(case.get(field), field)
    diagnostics = case.get("search_diagnostics")
    if variant is None:
        if diagnostics is not None:
            raise ValueError("Base diagnostic case contains search evidence")
        return
    diagnostic = _mapping(diagnostics, "search diagnostics")
    _exact_keys(
        diagnostic,
        {
            "usage",
            "recommended_overrides",
            "executed_overrides",
            "fallback_decision_indices",
            "decisions",
        },
        "search diagnostics",
    )
    usage = _usage_from_mapping(diagnostic.get("usage"))
    if usage.policy_only_decisions + usage.search_decisions != decisions:
        raise ValueError("Combat-search diagnostic usage does not cover every decision")
    trace = _list(diagnostic.get("decisions"), "search decision trace")
    if len(trace) != usage.search_decisions:
        raise ValueError("Combat-search diagnostic trace count differs")
    recommended = 0
    executed = 0
    previous_index = -1
    for entry_value in trace:
        entry = _mapping(entry_value, "search decision")
        index = _integer(entry.get("decision_index"), "search decision index")
        if index <= previous_index or index >= decisions:
            raise ValueError("Combat-search diagnostic trace indices differ")
        previous_index = index
        for field in (
            "source_state_hash",
            "base_action_id",
            "search_action_id",
            "selected_action_id",
            "selection_reason",
        ):
            _string(entry.get(field), field)
        _finite_nonnegative(entry.get("search_advantage"), "search advantage")
        recommendation = entry.get("override_recommended")
        execution = entry.get("override_executed")
        if not isinstance(recommendation, bool) or not isinstance(execution, bool):
            raise ValueError("Combat-search diagnostic override flags differ")
        if execution and not recommendation:
            raise ValueError("Combat-search diagnostic executed an unrecommended override")
        recommended += recommendation
        executed += execution
        if _integer(entry.get("candidate_count"), "candidate count") <= 0:
            raise ValueError("Combat-search diagnostic candidate count is not positive")
        for field in ("simulated_transitions", "hidden_worlds", "public_resample_attempts"):
            if _integer(entry.get(field), field) < 0:
                raise ValueError("Combat-search diagnostic search count is negative")
    if recommended != _integer(diagnostic.get("recommended_overrides"), "recommended overrides"):
        raise ValueError("Combat-search diagnostic recommendation count differs")
    if executed != _integer(diagnostic.get("executed_overrides"), "executed overrides"):
        raise ValueError("Combat-search diagnostic execution count differs")
    fallback_indices = [
        _integer(index, "fallback decision index")
        for index in _list(diagnostic.get("fallback_decision_indices"), "fallback indices")
    ]
    if len(fallback_indices) != usage.public_resample_failures or any(
        index < 0 or index >= decisions for index in fallback_indices
    ):
        raise ValueError("Combat-search diagnostic fallback indices differ")


def _diagnostic_summary(
    cases: Sequence[dict[str, Any]], spec: CombatSearchDiagnosticSpec
) -> dict[str, Any]:
    base_cases = [case for case in cases if case["variant_name"] == BASE_VARIANT_NAME]
    base_summary = _run_summary(base_cases)
    variant_summaries: list[dict[str, Any]] = []
    shadow_consistency = True
    for variant in spec.variants:
        variant_cases = [case for case in cases if case["variant_name"] == variant.name]
        paired = _paired_summary(variant_cases, base_cases)
        search = _search_summary(variant_cases)
        run_summary = _run_summary(variant_cases)
        eligible = (
            variant.config.selection_mode == "apply"
            and paired["completed_pairs"] == spec.run_count
            and base_summary["failed_runs"] == 0
            and base_summary["truncated_runs"] == 0
            and run_summary["failed_runs"] == 0
            and run_summary["truncated_runs"] == 0
            and paired["base_only_victories"] == 0
            and paired["mean_maximum_floor_difference"] > 0.0
            and paired["floor_improved_runs"] > paired["floor_worse_runs"]
            and paired["mean_floor_difference_per_search_cpu_hour"] is not None
            and paired["mean_floor_difference_per_search_cpu_hour"] > 0.0
        )
        if variant.config.selection_mode == "shadow":
            shadow_consistency = (
                shadow_consistency and paired["identical_outcome_runs"] == spec.run_count
            )
        variant_summaries.append(
            {
                "name": variant.name,
                "config_id": variant.config.config_id,
                "policy_id": combat_advancement_policy_id(spec.model_id, variant.config),
                "selection_mode": variant.config.selection_mode,
                "minimum_search_advantage": variant.config.minimum_search_advantage,
                "runs": run_summary,
                "search": search,
                "paired_vs_base": paired,
                "eligible_for_validation": eligible,
            }
        )
    eligible_variants = [item for item in variant_summaries if item["eligible_for_validation"]]
    selected = (
        max(
            eligible_variants,
            key=lambda item: (
                item["paired_vs_base"]["mean_maximum_floor_difference"],
                item["paired_vs_base"]["floor_improved_runs"],
                -item["runs"]["total_decision_cpu_seconds"],
            ),
        )
        if shadow_consistency and eligible_variants
        else None
    )
    return {
        "base": base_summary,
        "variants": variant_summaries,
        "recommendation": {
            "shadow_consistency_pass": shadow_consistency,
            "eligible_variant_names": [item["name"] for item in eligible_variants],
            "selected_variant_name": None if selected is None else selected["name"],
            "selected_config_id": None if selected is None else selected["config_id"],
            "validation_allowed": selected is not None,
        },
    }


def _run_summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    terminal = [case for case in completed if case["terminal"] is True]
    victories = sum(case["victory"] is True for case in terminal)
    denominator = len(cases)
    return {
        "benchmark_denominator": denominator,
        "completed_runs": len(completed),
        "failed_runs": denominator - len(completed),
        "terminal_runs": len(terminal),
        "truncated_runs": len(completed) - len(terminal),
        "policy_cycle_runs": sum(
            case["termination_reason"] == "policy_cycle" for case in completed
        ),
        "decision_limit_runs": sum(
            case["termination_reason"] == "decision_limit" for case in completed
        ),
        "victories": victories,
        "victory_rate": _artifact_float(victories / max(1, denominator)),
        "mean_maximum_floor": _artifact_float(
            sum(int(case["maximum_floor"]) for case in completed) / max(1, len(completed))
        ),
        "decisions": sum(int(case["decisions"]) for case in completed),
        "total_decision_seconds": _artifact_float(
            sum(float(case["total_decision_seconds"]) for case in completed)
        ),
        "total_decision_cpu_seconds": _artifact_float(
            sum(float(case["total_decision_cpu_seconds"]) for case in completed)
        ),
    }


def _search_summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    usage = [
        _mapping(_mapping(case["search_diagnostics"], "search diagnostics").get("usage"), "usage")
        for case in completed
    ]
    traces = [
        entry
        for case in completed
        for entry in _list(
            _mapping(case["search_diagnostics"], "search diagnostics").get("decisions"),
            "search decisions",
        )
    ]
    margins = [
        float(_mapping(entry, "search decision")["search_advantage"])
        for entry in traces
        if _mapping(entry, "search decision").get("override_recommended") is True
    ]
    return {
        "policy_only_decisions": sum(int(item["policy_only_decisions"]) for item in usage),
        "search_decisions": sum(int(item["search_decisions"]) for item in usage),
        "search_fallback_decisions": sum(int(item["search_fallback_decisions"]) for item in usage),
        "simulations": sum(
            int(_mapping(entry, "search decision")["candidate_count"])
            * int(_mapping(entry, "search decision")["hidden_worlds"])
            for entry in traces
        ),
        "simulated_transitions": sum(int(item["simulated_transitions"]) for item in usage),
        "hidden_worlds": sum(int(item["hidden_worlds"]) for item in usage),
        "public_resample_attempts": sum(int(item["public_resample_attempts"]) for item in usage),
        "public_resample_failures": sum(int(item["public_resample_failures"]) for item in usage),
        "recommended_overrides": sum(
            int(_mapping(case["search_diagnostics"], "search diagnostics")["recommended_overrides"])
            for case in completed
        ),
        "executed_overrides": sum(
            int(_mapping(case["search_diagnostics"], "search diagnostics")["executed_overrides"])
            for case in completed
        ),
        "mean_recommended_override_margin": (
            None if not margins else _artifact_float(sum(margins) / len(margins))
        ),
        "median_recommended_override_margin": (
            None if not margins else _artifact_float(_percentile(margins, 0.5))
        ),
        "p95_recommended_override_margin": (
            None if not margins else _artifact_float(_percentile(margins, 0.95))
        ),
    }


def _paired_summary(
    variant_cases: Sequence[dict[str, Any]], base_cases: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    variant_by_seed = {int(case["seed"]): case for case in variant_cases}
    base_by_seed = {int(case["seed"]): case for case in base_cases}
    pairs = [
        (variant_by_seed[seed], base_by_seed[seed])
        for seed in sorted(variant_by_seed.keys() & base_by_seed.keys())
        if variant_by_seed[seed]["status"] == "completed"
        and base_by_seed[seed]["status"] == "completed"
    ]
    differences = [
        int(variant["maximum_floor"]) - int(base["maximum_floor"]) for variant, base in pairs
    ]
    mean_difference = _artifact_float(sum(differences) / max(1, len(differences)))
    search_cpu_per_run = sum(
        float(variant["total_decision_cpu_seconds"]) for variant, _ in pairs
    ) / max(1, len(pairs))
    efficiency = (
        None
        if search_cpu_per_run <= 0.0
        else _artifact_float(mean_difference / (search_cpu_per_run / 3600.0))
    )
    return {
        "completed_pairs": len(pairs),
        "variant_only_victories": sum(
            variant["victory"] is True and base["victory"] is not True for variant, base in pairs
        ),
        "base_only_victories": sum(
            base["victory"] is True and variant["victory"] is not True for variant, base in pairs
        ),
        "floor_improved_runs": sum(difference > 0 for difference in differences),
        "floor_tied_runs": sum(difference == 0 for difference in differences),
        "floor_worse_runs": sum(difference < 0 for difference in differences),
        "mean_maximum_floor_difference": mean_difference,
        "mean_floor_difference_per_search_cpu_hour": efficiency,
        "identical_action_trace_runs": sum(
            variant["action_trace_sha256"] == base["action_trace_sha256"] for variant, base in pairs
        ),
        "identical_outcome_runs": sum(
            all(
                variant[field] == base[field]
                for field in (
                    "action_trace_sha256",
                    "terminal",
                    "victory",
                    "truncated",
                    "termination_reason",
                    "maximum_floor",
                    "final_state_hash",
                )
            )
            for variant, base in pairs
        ),
    }


def _variant_provenance(spec: CombatSearchDiagnosticSpec, model_id: str) -> list[dict[str, object]]:
    provenance: list[dict[str, object]] = [
        {
            "name": BASE_VARIANT_NAME,
            "policy_kind": BASE_POLICY_KIND,
            "policy_id": f"production-checkpoint-policy-v1:{model_id}",
            "combat_advancement_config": None,
        }
    ]
    provenance.extend(
        [
            {
                "name": variant.name,
                "policy_kind": SEARCH_POLICY_KIND,
                "policy_id": combat_advancement_policy_id(model_id, variant.config),
                "combat_advancement_config": variant.config.as_dict(),
            }
            for variant in spec.variants
        ]
    )
    return provenance


def _usage_from_mapping(value: object) -> CombatAdvancementUsage:
    usage = _mapping(value, "combat-search usage")
    expected = {
        "policy_only_decisions",
        "search_decisions",
        "search_fallback_decisions",
        "simulated_transitions",
        "hidden_worlds",
        "public_resample_attempts",
        "public_resample_failures",
    }
    _exact_keys(usage, expected, "combat-search usage")
    values = {key: _integer(usage.get(key), key) for key in expected}
    if min(values.values()) < 0:
        raise ValueError("Combat-search diagnostic usage must be non-negative")
    return CombatAdvancementUsage(**values)


def _variant_name(variant: CombatSearchDiagnosticVariant | None) -> str:
    return BASE_VARIANT_NAME if variant is None else variant.name


def _case_path(output_directory: Path, seed: int, variant_name: str) -> Path:
    return output_directory / "cases" / f"seed-{seed:06d}-{variant_name}.json"


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    return dict(_mapping(value, label))


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label.capitalize()} must be an object")
    return dict(value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label.capitalize()} must be an array")
    return list(value)


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{label.capitalize()} fields differ")


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{label} must be finite and non-negative")
    return result


def _public_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _artifact_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Combat-search diagnostic metric must be finite")
    return round(value, 12)


def _close_environment(environment: object) -> None:
    close = getattr(environment, "close", None)
    if callable(close):
        close()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
