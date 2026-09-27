from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spireshift.agents.combat_advancement import (
    COMBAT_CLEAR_DECISION_TYPES,
    CombatAdvancementConfig,
    CombatAdvancementDecision,
    CombatAdvancementPolicy,
    CombatBranchOutcome,
    combat_advancement_policy_id,
)
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import Observation
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

INTERVENTION_SPEC_SCHEMA_VERSION = "combat-search-intervention-spec-v1"
COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION = "combat-search-intervention-spec-v2"
INTERVENTION_CASE_SCHEMA_VERSION = "combat-search-intervention-case-v1"
COMBAT_RESOLUTION_INTERVENTION_CASE_SCHEMA_VERSION = "combat-search-intervention-case-v2"
INTERVENTION_REPORT_SCHEMA_VERSION = "combat-search-intervention-report-v1"
COMBAT_RESOLUTION_INTERVENTION_REPORT_SCHEMA_VERSION = "combat-search-intervention-report-v2"
CLAIM_SCOPE = "paired_train_only_single_search_intervention_diagnostic"
_IDENTIFIER_PATTERN = r"^sha256:[a-f0-9]{64}$"


@dataclass(frozen=True, slots=True)
class MarginStratum:
    name: str
    minimum: float
    maximum: float | None
    maximum_interventions_per_seed: int

    def __post_init__(self) -> None:
        allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
        if not self.name or any(character not in allowed for character in self.name):
            raise ValueError("Intervention stratum name differs")
        if not math.isfinite(self.minimum) or self.minimum < 0.0:
            raise ValueError("Intervention stratum minimum must be finite and non-negative")
        if self.maximum is not None and (
            not math.isfinite(self.maximum) or self.maximum <= self.minimum
        ):
            raise ValueError("Intervention stratum maximum must exceed its minimum")
        if (
            isinstance(self.maximum_interventions_per_seed, bool)
            or self.maximum_interventions_per_seed <= 0
        ):
            raise ValueError("Intervention stratum cap must be positive")

    def contains(self, margin: float) -> bool:
        return margin >= self.minimum and (self.maximum is None or margin < self.maximum)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "maximum_interventions_per_seed": self.maximum_interventions_per_seed,
        }

    @classmethod
    def from_mapping(cls, value: object) -> MarginStratum:
        document = _mapping(value, "margin stratum")
        _exact_keys(
            document,
            {"name", "minimum", "maximum", "maximum_interventions_per_seed"},
            "margin stratum",
        )
        maximum_value = document.get("maximum")
        return cls(
            name=_string(document.get("name"), "stratum name"),
            minimum=_number(document.get("minimum"), "stratum minimum"),
            maximum=(None if maximum_value is None else _number(maximum_value, "stratum maximum")),
            maximum_interventions_per_seed=_integer(
                document.get("maximum_interventions_per_seed"), "stratum cap"
            ),
        )


@dataclass(frozen=True, slots=True)
class CombatResolutionPromotionGate:
    minimum_qualifying_interventions: int
    minimum_unique_seeds: int
    minimum_beneficial_interventions: int
    maximum_harmful_interventions: int

    def __post_init__(self) -> None:
        for name, value, minimum in (
            ("minimum_qualifying_interventions", self.minimum_qualifying_interventions, 1),
            ("minimum_unique_seeds", self.minimum_unique_seeds, 1),
            ("minimum_beneficial_interventions", self.minimum_beneficial_interventions, 1),
            ("maximum_harmful_interventions", self.maximum_harmful_interventions, 0),
        ):
            if isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")

    def as_dict(self) -> dict[str, int]:
        return {
            "minimum_qualifying_interventions": self.minimum_qualifying_interventions,
            "minimum_unique_seeds": self.minimum_unique_seeds,
            "minimum_beneficial_interventions": self.minimum_beneficial_interventions,
            "maximum_harmful_interventions": self.maximum_harmful_interventions,
        }

    @classmethod
    def from_mapping(cls, value: object) -> CombatResolutionPromotionGate:
        document = _mapping(value, "combat-resolution promotion gate")
        expected = {
            "minimum_qualifying_interventions",
            "minimum_unique_seeds",
            "minimum_beneficial_interventions",
            "maximum_harmful_interventions",
        }
        _exact_keys(document, expected, "combat-resolution promotion gate")
        return cls(
            minimum_qualifying_interventions=_integer(
                document.get("minimum_qualifying_interventions"),
                "minimum qualifying interventions",
            ),
            minimum_unique_seeds=_integer(
                document.get("minimum_unique_seeds"), "minimum unique seeds"
            ),
            minimum_beneficial_interventions=_integer(
                document.get("minimum_beneficial_interventions"),
                "minimum beneficial interventions",
            ),
            maximum_harmful_interventions=_integer(
                document.get("maximum_harmful_interventions"),
                "maximum harmful interventions",
            ),
        )


@dataclass(frozen=True, slots=True)
class CombatSearchInterventionSpec:
    split_manifest_id: str
    ruleset_manifest_id: str
    model_id: str
    training_report_id: str
    run_offset: int
    run_count: int
    workers: int
    maximum_decisions_per_run: int
    cycle_repetition_threshold: int
    shadow_config: CombatAdvancementConfig
    margin_strata: tuple[MarginStratum, ...]
    selection_salt: str
    selection_rule: str = "all_recommendations"
    promotion_gate: CombatResolutionPromotionGate | None = None
    objective_id: str = "terminal-victory-v1"
    partition: str = SplitName.TRAIN.value
    schema_version: str = INTERVENTION_SPEC_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version not in {
            INTERVENTION_SPEC_SCHEMA_VERSION,
            COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION,
        }:
            raise ValueError("Combat-search intervention specification schema differs")
        if self.partition != SplitName.TRAIN.value:
            raise ValueError("Combat-search interventions may use only train seeds")
        if self.objective_id != "terminal-victory-v1":
            raise ValueError("Combat-search interventions must preserve terminal victory")
        for identity_name, identity_value in (
            ("split_manifest_id", self.split_manifest_id),
            ("ruleset_manifest_id", self.ruleset_manifest_id),
            ("model_id", self.model_id),
            ("training_report_id", self.training_report_id),
        ):
            if not _is_identifier(identity_value):
                raise ValueError(f"{identity_name} must be a content identifier")
        for count_name, count_value, minimum in (
            ("run_offset", self.run_offset, 0),
            ("run_count", self.run_count, 1),
            ("workers", self.workers, 1),
            ("maximum_decisions_per_run", self.maximum_decisions_per_run, 1),
            ("cycle_repetition_threshold", self.cycle_repetition_threshold, 2),
        ):
            if isinstance(count_value, bool) or count_value < minimum:
                raise ValueError(f"{count_name} must be at least {minimum}")
        if not self.selection_salt:
            raise ValueError("Intervention selection salt must be non-empty")
        if self.shadow_config.selection_mode != "shadow":
            raise ValueError("Intervention search configuration must use shadow mode")
        if self.schema_version == INTERVENTION_SPEC_SCHEMA_VERSION:
            if (
                self.shadow_config.schema_version != "combat-advancement-config-v2"
                or self.shadow_config.minimum_search_advantage != 0.0
                or self.selection_rule != "all_recommendations"
                or self.promotion_gate is not None
            ):
                raise ValueError("Version-1 interventions require zero-margin selection")
        elif (
            self.shadow_config.schema_version != "combat-advancement-config-v4"
            or self.shadow_config.override_rule != "combat_clear_rescue"
            or self.selection_rule != "configured_override_eligible"
            or self.promotion_gate is None
        ):
            raise ValueError("Version-2 interventions require combat-clear eligible selection")
        if not self.margin_strata:
            raise ValueError("Combat-search intervention specification has no margin strata")
        names = [stratum.name for stratum in self.margin_strata]
        if len(names) != len(set(names)):
            raise ValueError("Intervention stratum names must be unique")
        if self.margin_strata[0].minimum != 0.0:
            raise ValueError("Intervention strata must begin at zero")
        for left, right in zip(self.margin_strata, self.margin_strata[1:], strict=False):
            if left.maximum != right.minimum:
                raise ValueError("Intervention strata must be contiguous")
        if self.margin_strata[-1].maximum is not None:
            raise ValueError("Final intervention stratum must be unbounded")

    def body(self) -> dict[str, object]:
        body: dict[str, object] = {
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
            "shadow_combat_advancement_config": self.shadow_config.as_dict(),
            "margin_strata": [stratum.as_dict() for stratum in self.margin_strata],
            "selection_salt": self.selection_salt,
        }
        if self.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
            assert self.promotion_gate is not None
            body.update(
                {
                    "selection_rule": self.selection_rule,
                    "promotion_gate": self.promotion_gate.as_dict(),
                }
            )
        return body

    @property
    def spec_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "spec_id": self.spec_id}

    @classmethod
    def from_mapping(cls, value: object) -> CombatSearchInterventionSpec:
        document = _mapping(value, "combat-search intervention specification")
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
            "shadow_combat_advancement_config",
            "margin_strata",
            "selection_salt",
        }
        schema_version = _string(document.get("schema_version"), "schema_version")
        if schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
            expected.update({"selection_rule", "promotion_gate"})
        _exact_keys(document, expected, "combat-search intervention specification")
        spec = cls(
            schema_version=schema_version,
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
            shadow_config=CombatAdvancementConfig.from_mapping(
                document.get("shadow_combat_advancement_config")
            ),
            margin_strata=tuple(
                MarginStratum.from_mapping(item)
                for item in _list(document.get("margin_strata"), "margin strata")
            ),
            selection_salt=_string(document.get("selection_salt"), "selection_salt"),
            selection_rule=(
                _string(document.get("selection_rule"), "selection_rule")
                if schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION
                else "all_recommendations"
            ),
            promotion_gate=(
                CombatResolutionPromotionGate.from_mapping(document.get("promotion_gate"))
                if schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION
                else None
            ),
        )
        if document.get("spec_id") != spec.spec_id:
            raise ValueError("Combat-search intervention specification identity mismatch")
        return spec


@dataclass(slots=True)
class _PendingIntervention:
    priority: str
    stratum: MarginStratum
    decision_index: int
    source_observation: Observation
    source_maximum_floor: int
    decision: CombatAdvancementDecision
    environment: EnvironmentAdapter


@dataclass(frozen=True, slots=True)
class CombatSearchInterventionResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


def load_combat_search_intervention_spec(path: Path) -> CombatSearchInterventionSpec:
    return CombatSearchInterventionSpec.from_mapping(
        _load_object(path, "combat-search intervention specification")
    )


def run_combat_search_interventions(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    base_policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    spec: CombatSearchInterventionSpec,
    output_directory: Path,
    resume: bool = False,
    now: Callable[[], str] | None = None,
) -> CombatSearchInterventionResult:
    _validate_inputs(ruleset, base_policy, split_manifest, spec)
    seeds = split_manifest.seeds(SplitName.TRAIN)[
        spec.run_offset : spec.run_offset + spec.run_count
    ]
    if len(seeds) != spec.run_count:
        raise ValueError("Combat-search intervention seed window exceeds the train partition")
    if output_directory.exists() and not resume:
        raise FileExistsError(
            f"Combat-search intervention output already exists: {output_directory}"
        )
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "combat-search-intervention-report.json"
    if report_path.exists():
        raise FileExistsError(f"Combat-search intervention report already exists: {report_path}")

    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, Path]] = []
    for seed in seeds:
        path = _case_path(output_directory, seed)
        if path.exists():
            cases.append(_load_case(path, seed=seed, spec=spec))
        else:
            pending.append((seed, path))
    with ThreadPoolExecutor(max_workers=min(spec.workers, max(1, len(pending)))) as executor:
        futures: dict[Future[dict[str, Any]], tuple[int, Path]] = {}
        for seed, path in pending:
            future = executor.submit(
                _evaluate_seed,
                environment_factory=environment_factory,
                ruleset=ruleset,
                base_policy=base_policy,
                spec=spec,
                seed=seed,
            )
            futures[future] = (seed, path)
        for future in as_completed(futures):
            _, path = futures[future]
            case = future.result()
            write_model_artifact(case, path, label="combat-search intervention case")
            cases.append(case)

    ordered = sorted(cases, key=lambda case: int(case["seed"]))
    if len(ordered) != spec.run_count:
        raise RuntimeError("Combat-search intervention did not produce every seed case")
    summary = _summary(ordered, spec)
    body: dict[str, Any] = {
        "schema_version": _report_schema_version(spec),
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "intervention_spec_id": spec.spec_id,
        "model_id": base_policy.model_id,
        "training_report_id": spec.training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "configuration": _report_configuration(spec, seeds, base_policy.model_id),
        "cases": [
            {
                "seed": case["seed"],
                "path": str(
                    _case_path(output_directory, int(case["seed"])).relative_to(output_directory)
                ),
                "case_id": case["case_id"],
            }
            for case in ordered
        ],
        "summary": summary,
        "claim_scope": CLAIM_SCOPE,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    write_model_artifact(report, report_path, label="combat-search intervention report")
    return CombatSearchInterventionResult(
        successful=all(case["status"] == "completed" for case in ordered),
        report_path=report_path,
        report=report,
    )


def load_combat_search_interventions(
    path: Path,
    *,
    spec: CombatSearchInterventionSpec,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    report = _load_object(path, "combat-search intervention report")
    report_id = report.get("report_id")
    body = {key: value for key, value in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Combat-search intervention report identity mismatch")
    expected = {
        "schema_version": _report_schema_version(spec),
        "intervention_spec_id": spec.spec_id,
        "model_id": spec.model_id,
        "training_report_id": spec.training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": "terminal-victory-v1",
        "claim_scope": CLAIM_SCOPE,
    }
    if any(report.get(key) != value for key, value in expected.items()):
        raise ValueError("Combat-search intervention report provenance differs")
    seeds = split_manifest.seeds(SplitName.TRAIN)[
        spec.run_offset : spec.run_offset + spec.run_count
    ]
    expected_configuration = _report_configuration(spec, seeds, spec.model_id)
    if report.get("configuration") != expected_configuration:
        raise ValueError("Combat-search intervention configuration differs")
    references = _list(report.get("cases"), "intervention case references")
    root = path.parent.resolve()
    cases: list[dict[str, Any]] = []
    seen: set[int] = set()
    for reference_value in references:
        reference = _mapping(reference_value, "intervention case reference")
        _exact_keys(reference, {"seed", "path", "case_id"}, "intervention case reference")
        seed = _integer(reference.get("seed"), "case seed")
        if seed in seen:
            raise ValueError("Combat-search intervention repeats a seed case")
        seen.add(seed)
        relative = Path(_string(reference.get("path"), "case path"))
        case_path = (root / relative).resolve()
        if root not in case_path.parents:
            raise ValueError("Combat-search intervention case escapes its root")
        case = _load_case(case_path, seed=seed, spec=spec)
        if reference.get("case_id") != case["case_id"]:
            raise ValueError("Combat-search intervention case reference identity mismatch")
        cases.append(case)
    if seen != set(seeds):
        raise ValueError("Combat-search intervention seed coverage differs")
    if report.get("summary") != _summary(cases, spec):
        raise ValueError("Combat-search intervention summary differs from its cases")
    return report


def _evaluate_seed(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    base_policy: ProductionCheckpointPolicy,
    spec: CombatSearchInterventionSpec,
    seed: int,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    retained: dict[str, list[_PendingIntervention]] = {
        stratum.name: [] for stratum in spec.margin_strata
    }
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Combat-search intervention environment ruleset changed")
        shadow = CombatAdvancementPolicy(
            environment=environment,
            base_policy=base_policy,
            config=spec.shadow_config,
        )
        observation = environment.reset(seed)
        maximum_floor = _public_floor(observation)
        decisions = 0
        actions: list[str] = []
        wall_seconds = 0.0
        cpu_seconds = 0.0
        transition_counts: dict[tuple[str, str, str], int] = {}
        cycle_detected = False
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        available = {stratum.name: 0 for stratum in spec.margin_strata}
        search_simulations = 0
        recommended_overrides = 0
        eligible_recommendations = 0
        while not terminal and decisions < spec.maximum_decisions_per_run:
            legal_actions = tuple(environment.legal_actions())
            if not legal_actions:
                raise RuntimeError("Nonterminal intervention source state has no legal actions")
            wall_started = time.perf_counter()
            cpu_started = time.thread_time()
            action = shadow.choose_action(observation, legal_actions)
            cpu_seconds += time.thread_time() - cpu_started
            wall_seconds += time.perf_counter() - wall_started
            search = shadow.last_decision
            if search is not None:
                search_simulations += search.hidden_worlds * len(search.candidates)
            if search is not None and search.search_override_recommended:
                recommended_overrides += 1
                selection_eligible = spec.selection_rule == "all_recommendations" or (
                    search.override_rule_eligible
                    and search.search_advantage >= spec.shadow_config.minimum_search_advantage
                )
                if selection_eligible:
                    eligible_recommendations += 1
                    stratum = _stratum_for_margin(search.search_advantage, spec.margin_strata)
                    available[stratum.name] += 1
                    _consider_intervention(
                        retained=retained[stratum.name],
                        stratum=stratum,
                        selection_salt=spec.selection_salt,
                        seed=seed,
                        decision_index=decisions,
                        source_observation=observation,
                        source_maximum_floor=maximum_floor,
                        decision=search,
                        environment=environment,
                    )
            source_hash = observation.state_hash
            actions.append(action.action_id)
            transition = environment.step(action)
            observation = transition.next_observation
            decisions += 1
            maximum_floor = max(maximum_floor, _public_floor(observation))
            terminal = transition.terminal
            victory = transition.victory
            coordinate = (source_hash, action.action_id, observation.state_hash)
            transition_counts[coordinate] = transition_counts.get(coordinate, 0) + 1
            if not terminal and transition_counts[coordinate] >= spec.cycle_repetition_threshold:
                cycle_detected = True
                break
        termination_reason = (
            "terminal" if terminal else "policy_cycle" if cycle_detected else "decision_limit"
        )
        base_run = {
            "decisions": decisions,
            "terminal": terminal,
            "victory": victory if terminal else False,
            "truncated": not terminal,
            "termination_reason": termination_reason,
            "maximum_floor": maximum_floor,
            "final_state_hash": observation.state_hash,
            "action_trace_sha256": _action_trace_id(actions),
            "total_decision_seconds": _artifact_float(wall_seconds),
            "total_decision_cpu_seconds": _artifact_float(cpu_seconds),
        }
        selected = sorted(
            (item for values in retained.values() for item in values),
            key=lambda item: (item.decision_index, item.stratum.name, item.priority),
        )
        interventions: list[dict[str, Any]] = []
        for pending in selected:
            interventions.append(
                _evaluate_intervention(
                    pending=pending,
                    base_run=base_run,
                    base_policy=base_policy,
                    maximum_total_decisions=spec.maximum_decisions_per_run,
                    cycle_repetition_threshold=spec.cycle_repetition_threshold,
                )
            )
        usage = shadow.usage()
        body: dict[str, Any] = {
            "schema_version": _case_schema_version(spec),
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "model_id": base_policy.model_id,
            "base_policy_id": base_policy.policy_id,
            "shadow_policy_id": shadow.policy_id,
            "shadow_combat_advancement_config_id": spec.shadow_config.config_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "completed",
            "error": None,
            "base_run": base_run,
            "source_search": {
                "usage": usage.as_dict(),
                "simulations": search_simulations,
                "recommended_overrides": recommended_overrides,
                "available_recommendations_by_stratum": available,
                "selected_interventions_by_stratum": {
                    stratum.name: len(retained[stratum.name]) for stratum in spec.margin_strata
                },
                **(
                    {"eligible_recommendations": eligible_recommendations}
                    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION
                    else {}
                ),
            },
            "interventions": interventions,
        }
    except Exception as error:
        body = {
            "schema_version": _case_schema_version(spec),
            "seed": seed,
            "partition": SplitName.TRAIN.value,
            "model_id": base_policy.model_id,
            "base_policy_id": base_policy.policy_id,
            "shadow_policy_id": combat_advancement_policy_id(
                base_policy.model_id, spec.shadow_config
            ),
            "shadow_combat_advancement_config_id": spec.shadow_config.config_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "base_run": None,
            "source_search": None,
            "interventions": [],
        }
    finally:
        for items in retained.values():
            for pending in items:
                _close_environment(pending.environment)
        if environment is not None:
            _close_environment(environment)
    return {**body, "case_id": manifest_identifier(body)}


def _consider_intervention(
    *,
    retained: list[_PendingIntervention],
    stratum: MarginStratum,
    selection_salt: str,
    seed: int,
    decision_index: int,
    source_observation: Observation,
    source_maximum_floor: int,
    decision: CombatAdvancementDecision,
    environment: EnvironmentAdapter,
) -> None:
    priority = (
        "sha256:"
        + hashlib.sha256(
            (
                f"{selection_salt}|{seed}|{decision_index}|{source_observation.state_hash}|"
                f"{decision.search_action.action_id}"
            ).encode()
        ).hexdigest()
    )
    if len(retained) >= stratum.maximum_interventions_per_seed:
        worst = max(retained, key=lambda item: item.priority)
        if priority >= worst.priority:
            return
        retained.remove(worst)
        _close_environment(worst.environment)
    retained.append(
        _PendingIntervention(
            priority=priority,
            stratum=stratum,
            decision_index=decision_index,
            source_observation=source_observation,
            source_maximum_floor=source_maximum_floor,
            decision=decision,
            environment=environment.clone(resample_hidden=False),
        )
    )


def _evaluate_intervention(
    *,
    pending: _PendingIntervention,
    base_run: dict[str, Any],
    base_policy: ProductionCheckpointPolicy,
    maximum_total_decisions: int,
    cycle_repetition_threshold: int,
) -> dict[str, Any]:
    decision = pending.decision
    try:
        environment = pending.environment
        legal_actions = tuple(environment.legal_actions())
        legal_ids = tuple(action.action_id for action in legal_actions)
        candidate_ids = tuple(candidate.action_id for candidate in decision.candidates)
        if legal_ids != candidate_ids:
            raise RuntimeError("Exact intervention clone legal actions changed")
        search_action = legal_actions[decision.search_candidate_index]
        if search_action.action_id != decision.search_action.action_id:
            raise RuntimeError("Exact intervention search action changed")
        actions = [search_action.action_id]
        transition = environment.step(search_action)
        if transition.observation != pending.source_observation:
            raise RuntimeError("Exact intervention clone changed the source observation")
        observation = transition.next_observation
        branch_decisions = 1
        maximum_floor = max(pending.source_maximum_floor, _public_floor(observation))
        terminal = transition.terminal
        victory = transition.victory
        transition_counts: dict[tuple[str, str, str], int] = {
            (
                pending.source_observation.state_hash,
                search_action.action_id,
                observation.state_hash,
            ): 1
        }
        cycle_detected = False
        wall_seconds = 0.0
        cpu_seconds = 0.0
        while not terminal and pending.decision_index + branch_decisions < maximum_total_decisions:
            legal_actions = tuple(environment.legal_actions())
            if not legal_actions:
                raise RuntimeError("Nonterminal counterfactual state has no legal actions")
            wall_started = time.perf_counter()
            cpu_started = time.thread_time()
            action = base_policy.choose_action(observation, legal_actions)
            cpu_seconds += time.thread_time() - cpu_started
            wall_seconds += time.perf_counter() - wall_started
            source_hash = observation.state_hash
            actions.append(action.action_id)
            transition = environment.step(action)
            observation = transition.next_observation
            branch_decisions += 1
            maximum_floor = max(maximum_floor, _public_floor(observation))
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
        outcome = {
            "decisions_after_source": branch_decisions,
            "terminal": terminal,
            "victory": victory if terminal else False,
            "truncated": not terminal,
            "termination_reason": termination_reason,
            "maximum_floor": maximum_floor,
            "final_state_hash": observation.state_hash,
            "action_trace_sha256": _action_trace_id(actions),
            "total_decision_seconds": _artifact_float(wall_seconds),
            "total_decision_cpu_seconds": _artifact_float(cpu_seconds),
        }
        label, floor_difference, victory_difference = _paired_label(base_run, outcome)
        status = "completed"
        error = None
    except Exception as caught:
        outcome = None
        label = "inconclusive"
        floor_difference = None
        victory_difference = None
        status = "failed"
        error = f"{type(caught).__name__}: {caught}"
    candidates: list[dict[str, Any]] = []
    for candidate in decision.candidates:
        candidate_record: dict[str, Any] = {
            "candidate_index": candidate.candidate_index,
            "action_id": candidate.action_id,
            "base_policy_probability": _artifact_float(
                decision.base_policy_probabilities[candidate.candidate_index]
            ),
            "mean_search_value": _artifact_float(candidate.mean_search_value),
            "sampled_search_values": [
                _artifact_float(value) for value in candidate.sampled_search_values
            ],
            "terminal_victories": candidate.terminal_victories,
            "terminal_defeats": candidate.terminal_defeats,
            "bootstrapped_leaves": candidate.bootstrapped_leaves,
        }
        if decision.override_rule == "combat_clear_rescue":
            candidate_record.update(
                {
                    "combat_clears": candidate.combat_clears,
                    "branch_outcomes": [
                        _branch_outcome_dict(outcome) for outcome in candidate.branch_outcomes
                    ],
                }
            )
        candidates.append(candidate_record)
    result = {
        "status": status,
        "error": error,
        "stratum": pending.stratum.name,
        "selection_priority": pending.priority,
        "decision_index": pending.decision_index,
        "source_state_hash": pending.source_observation.state_hash,
        "source_floor": _public_floor(pending.source_observation),
        "source_maximum_floor": pending.source_maximum_floor,
        "base_action_id": decision.base_action.action_id,
        "search_action_id": decision.search_action.action_id,
        "search_advantage": _artifact_float(decision.search_advantage),
        "effective_rollout_steps": decision.effective_rollout_steps,
        "simulated_transitions": decision.simulated_transitions,
        "hidden_worlds": decision.hidden_worlds,
        "public_resample_attempts": decision.public_resample_attempts,
        "accepted_world_seeds": list(decision.accepted_world_seeds),
        "candidates": candidates,
        "counterfactual_run": outcome,
        "paired_label": label,
        "victory_difference": victory_difference,
        "maximum_floor_difference": floor_difference,
    }
    if decision.override_rule == "combat_clear_rescue":
        result.update(
            {
                "source_observation": decision.source_observation,
                "override_rule": decision.override_rule,
                "override_rule_eligible": decision.override_rule_eligible,
                "selection_reason": decision.selection_reason,
            }
        )
    return result


def _load_case(path: Path, *, seed: int, spec: CombatSearchInterventionSpec) -> dict[str, Any]:
    case = _load_object(path, "combat-search intervention case")
    case_id = case.get("case_id")
    body = {key: value for key, value in case.items() if key != "case_id"}
    if case_id != manifest_identifier(body):
        raise ValueError("Combat-search intervention case identity mismatch")
    expected = {
        "schema_version": _case_schema_version(spec),
        "seed": seed,
        "partition": SplitName.TRAIN.value,
        "model_id": spec.model_id,
        "base_policy_id": f"production-checkpoint-policy-v1:{spec.model_id}",
        "shadow_policy_id": combat_advancement_policy_id(spec.model_id, spec.shadow_config),
        "shadow_combat_advancement_config_id": spec.shadow_config.config_id,
        "ruleset_manifest_id": spec.ruleset_manifest_id,
    }
    if any(case.get(key) != value for key, value in expected.items()):
        raise ValueError("Combat-search intervention case provenance differs")
    _exact_keys(
        case,
        {
            "schema_version",
            "case_id",
            "seed",
            "partition",
            "model_id",
            "base_policy_id",
            "shadow_policy_id",
            "shadow_combat_advancement_config_id",
            "ruleset_manifest_id",
            "status",
            "error",
            "base_run",
            "source_search",
            "interventions",
        },
        "combat-search intervention case",
    )
    status = case.get("status")
    if status not in {"completed", "failed"}:
        raise ValueError("Combat-search intervention case status differs")
    if status == "failed":
        if not isinstance(case.get("error"), str) or case.get("base_run") is not None:
            raise ValueError("Failed intervention case fields differ")
        if case.get("source_search") is not None or case.get("interventions") != []:
            raise ValueError("Failed intervention case contains results")
        return case
    if case.get("error") is not None:
        raise ValueError("Completed intervention case has an error")
    base_run = _mapping(case.get("base_run"), "base run")
    _validate_run_outcome(base_run, base=True)
    source_search = _mapping(case.get("source_search"), "source search")
    source_search_fields = {
        "usage",
        "simulations",
        "recommended_overrides",
        "available_recommendations_by_stratum",
        "selected_interventions_by_stratum",
    }
    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
        source_search_fields.add("eligible_recommendations")
    _exact_keys(source_search, source_search_fields, "source search")
    usage = _mapping(source_search.get("usage"), "combat-search usage")
    _validate_usage(usage)
    simulations = _integer(source_search.get("simulations"), "search simulations")
    recommendations = _integer(source_search.get("recommended_overrides"), "recommended overrides")
    if simulations < 0 or recommendations < 0:
        raise ValueError("Combat-search intervention search totals are negative")
    available = _count_mapping(
        source_search.get("available_recommendations_by_stratum"), spec.margin_strata
    )
    selected = _count_mapping(
        source_search.get("selected_interventions_by_stratum"), spec.margin_strata
    )
    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
        eligible = _integer(
            source_search.get("eligible_recommendations"), "eligible recommendations"
        )
        if eligible < 0 or eligible > recommendations or sum(available.values()) != eligible:
            raise ValueError("Combat-search intervention eligibility total differs")
    elif sum(available.values()) != recommendations:
        raise ValueError("Combat-search intervention recommendation total differs")
    for stratum in spec.margin_strata:
        if selected[stratum.name] > min(
            available[stratum.name], stratum.maximum_interventions_per_seed
        ):
            raise ValueError("Combat-search intervention stratum cap differs")
    interventions = _list(case.get("interventions"), "interventions")
    if sum(selected.values()) != len(interventions):
        raise ValueError("Combat-search intervention selected count differs")
    seen: set[tuple[int, str]] = set()
    actual_selected = {stratum.name: 0 for stratum in spec.margin_strata}
    for value in interventions:
        intervention = _mapping(value, "intervention")
        _validate_intervention(intervention, seed=seed, spec=spec, base_run=base_run)
        coordinate = (
            _integer(intervention.get("decision_index"), "decision index"),
            _string(intervention.get("source_state_hash"), "source state hash"),
        )
        if coordinate in seen:
            raise ValueError("Combat-search intervention repeats a source decision")
        seen.add(coordinate)
        actual_selected[_string(intervention.get("stratum"), "stratum")] += 1
    if actual_selected != selected:
        raise ValueError("Combat-search intervention stratum totals differ")
    return case


def _validate_intervention(
    intervention: dict[str, Any],
    *,
    seed: int,
    spec: CombatSearchInterventionSpec,
    base_run: dict[str, Any],
) -> None:
    expected = {
        "status",
        "error",
        "stratum",
        "selection_priority",
        "decision_index",
        "source_state_hash",
        "source_floor",
        "source_maximum_floor",
        "base_action_id",
        "search_action_id",
        "search_advantage",
        "effective_rollout_steps",
        "simulated_transitions",
        "hidden_worlds",
        "public_resample_attempts",
        "accepted_world_seeds",
        "candidates",
        "counterfactual_run",
        "paired_label",
        "victory_difference",
        "maximum_floor_difference",
    }
    resolution_diagnostic = (
        spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION
    )
    if resolution_diagnostic:
        expected.update(
            {
                "source_observation",
                "override_rule",
                "override_rule_eligible",
                "selection_reason",
            }
        )
    _exact_keys(intervention, expected, "intervention")
    decision_index = _integer(intervention.get("decision_index"), "decision index")
    if decision_index < 0 or decision_index >= int(base_run["decisions"]):
        raise ValueError("Combat-search intervention decision index differs")
    state_hash = _string(intervention.get("source_state_hash"), "source state hash")
    if resolution_diagnostic:
        source_public_state = _validate_observation_evidence(
            intervention.get("source_observation"),
            expected_state_hash=state_hash,
            expected_decision_types={"combat", "combat_selection"},
        )
    search_action_id = _string(intervention.get("search_action_id"), "search action id")
    _string(intervention.get("base_action_id"), "base action id")
    margin = _number(intervention.get("search_advantage"), "search advantage")
    if margin < 0.0:
        raise ValueError("Combat-search intervention margin is negative")
    stratum = _stratum_for_margin(margin, spec.margin_strata)
    if intervention.get("stratum") != stratum.name:
        raise ValueError("Combat-search intervention margin stratum differs")
    expected_priority = (
        "sha256:"
        + hashlib.sha256(
            (
                f"{spec.selection_salt}|{seed}|{decision_index}|{state_hash}|{search_action_id}"
            ).encode()
        ).hexdigest()
    )
    if intervention.get("selection_priority") != expected_priority:
        raise ValueError("Combat-search intervention selection priority differs")
    effective_steps = _integer(
        intervention.get("effective_rollout_steps"), "effective rollout steps"
    )
    simulated_transitions = _integer(
        intervention.get("simulated_transitions"), "simulated transitions"
    )
    hidden_worlds = _integer(intervention.get("hidden_worlds"), "hidden worlds")
    public_attempts = _integer(
        intervention.get("public_resample_attempts"), "public resample attempts"
    )
    accepted_seeds = _list(intervention.get("accepted_world_seeds"), "accepted world seeds")
    if (
        effective_steps <= 0
        or effective_steps > spec.shadow_config.maximum_rollout_steps
        or simulated_transitions < 0
        or simulated_transitions > spec.shadow_config.maximum_simulated_transitions_per_decision
        or hidden_worlds != spec.shadow_config.candidate_worlds
        or public_attempts < hidden_worlds
        or len(accepted_seeds) != hidden_worlds
        or any(_integer(seed, "accepted world seed") < 0 for seed in accepted_seeds)
    ):
        raise ValueError("Combat-search intervention search budget evidence differs")
    candidates = _list(intervention.get("candidates"), "intervention candidates")
    if len(candidates) < 2:
        raise ValueError("Combat-search intervention candidate evidence is incomplete")
    action_ids: list[str] = []
    audited_transitions = 0
    for index, candidate_value in enumerate(candidates):
        candidate = _mapping(candidate_value, "intervention candidate")
        candidate_fields = {
            "candidate_index",
            "action_id",
            "base_policy_probability",
            "mean_search_value",
            "sampled_search_values",
            "terminal_victories",
            "terminal_defeats",
            "bootstrapped_leaves",
        }
        if resolution_diagnostic:
            candidate_fields.update({"combat_clears", "branch_outcomes"})
        _exact_keys(candidate, candidate_fields, "intervention candidate")
        if _integer(candidate.get("candidate_index"), "candidate index") != index:
            raise ValueError("Combat-search intervention candidate order differs")
        action_ids.append(_string(candidate.get("action_id"), "candidate action id"))
        probability = _number(candidate.get("base_policy_probability"), "policy probability")
        if not 0.0 <= probability <= 1.0:
            raise ValueError("Combat-search intervention policy probability differs")
        samples = _list(candidate.get("sampled_search_values"), "sampled search values")
        sample_values = [_number(value, "sampled search value") for value in samples]
        if len(sample_values) != spec.shadow_config.candidate_worlds:
            raise ValueError("Combat-search intervention sample count differs")
        mean = _number(candidate.get("mean_search_value"), "mean search value")
        if not math.isclose(mean, sum(sample_values) / len(sample_values), abs_tol=1e-9):
            raise ValueError("Combat-search intervention candidate mean differs")
        outcome_fields = ["terminal_victories", "terminal_defeats"]
        if resolution_diagnostic:
            outcome_fields.append("combat_clears")
        outcome_fields.append("bootstrapped_leaves")
        outcome_counts = tuple(_integer(candidate.get(field), field) for field in outcome_fields)
        outcomes = sum(outcome_counts)
        if outcomes != spec.shadow_config.candidate_worlds:
            raise ValueError("Combat-search intervention candidate outcome counts differ")
        if resolution_diagnostic:
            audited_transitions += _validate_branch_outcomes(
                candidate.get("branch_outcomes"),
                counts=outcome_counts,
                hidden_worlds=spec.shadow_config.candidate_worlds,
                maximum_steps=effective_steps,
                source_public_state=source_public_state,
            )
    if search_action_id not in action_ids or intervention.get("base_action_id") not in action_ids:
        raise ValueError("Combat-search intervention action evidence differs")
    if resolution_diagnostic:
        if intervention.get("override_rule") != "combat_clear_rescue":
            raise ValueError("Combat-search intervention override rule differs")
        if intervention.get("override_rule_eligible") is not True:
            raise ValueError("Combat-search intervention retained an ineligible rescue")
        _string(intervention.get("selection_reason"), "selection reason")
        if margin < spec.shadow_config.minimum_search_advantage:
            raise ValueError("Combat-search intervention retained a below-margin rescue")
        base_candidate = candidates[action_ids.index(str(intervention["base_action_id"]))]
        search_candidate = candidates[action_ids.index(search_action_id)]
        base_defeats = _integer(base_candidate.get("terminal_defeats"), "base defeats")
        search_resolutions = _integer(
            search_candidate.get("terminal_victories"), "search victories"
        ) + _integer(search_candidate.get("combat_clears"), "search combat clears")
        if (
            base_defeats != spec.shadow_config.candidate_worlds
            or search_resolutions != spec.shadow_config.candidate_worlds
        ):
            raise ValueError("Combat-search intervention rescue eligibility differs")
        if audited_transitions != simulated_transitions:
            raise ValueError("Combat-search intervention branch transitions differ")
    status = intervention.get("status")
    if status not in {"completed", "failed"}:
        raise ValueError("Combat-search intervention status differs")
    counterfactual = intervention.get("counterfactual_run")
    if status == "failed":
        if not isinstance(intervention.get("error"), str) or counterfactual is not None:
            raise ValueError("Failed intervention result fields differ")
        if intervention.get("paired_label") != "inconclusive":
            raise ValueError("Failed intervention result label differs")
        return
    if intervention.get("error") is not None:
        raise ValueError("Completed intervention result has an error")
    outcome = _mapping(counterfactual, "counterfactual run")
    _validate_run_outcome(outcome, base=False)
    label, floor_difference, victory_difference = _paired_label(base_run, outcome)
    if intervention.get("paired_label") != label:
        raise ValueError("Combat-search intervention paired label differs")
    if intervention.get("maximum_floor_difference") != floor_difference:
        raise ValueError("Combat-search intervention floor difference differs")
    if intervention.get("victory_difference") != victory_difference:
        raise ValueError("Combat-search intervention victory difference differs")


def _summary(cases: Sequence[dict[str, Any]], spec: CombatSearchInterventionSpec) -> dict[str, Any]:
    completed_cases = [case for case in cases if case["status"] == "completed"]
    base_runs = [case["base_run"] for case in completed_cases]
    interventions = [
        intervention for case in completed_cases for intervention in case["interventions"]
    ]
    completed_interventions = [
        intervention for intervention in interventions if intervention["status"] == "completed"
    ]
    overall = _intervention_summary(completed_interventions)
    by_stratum = []
    for stratum in spec.margin_strata:
        values = [
            intervention
            for intervention in completed_interventions
            if intervention["stratum"] == stratum.name
        ]
        available = sum(
            int(case["source_search"]["available_recommendations_by_stratum"][stratum.name])
            for case in completed_cases
        )
        selected = sum(
            int(case["source_search"]["selected_interventions_by_stratum"][stratum.name])
            for case in completed_cases
        )
        by_stratum.append(
            {
                "name": stratum.name,
                "minimum": stratum.minimum,
                "maximum": stratum.maximum,
                "available_recommendations": available,
                "selected_interventions": selected,
                **_intervention_summary(values),
            }
        )
    beneficial = int(overall["beneficial_interventions"])
    harmful = int(overall["harmful_interventions"])
    represented_beneficial = sum(int(item["beneficial_interventions"]) > 0 for item in by_stratum)
    represented_harmful = sum(int(item["harmful_interventions"]) > 0 for item in by_stratum)
    search_summary = {
        "search_decisions": sum(
            int(case["source_search"]["usage"]["search_decisions"]) for case in completed_cases
        ),
        "simulations": sum(int(case["source_search"]["simulations"]) for case in completed_cases),
        "recommended_overrides": sum(
            int(case["source_search"]["recommended_overrides"]) for case in completed_cases
        ),
        "simulated_transitions": sum(
            int(case["source_search"]["usage"]["simulated_transitions"]) for case in completed_cases
        ),
        "public_resample_failures": sum(
            int(case["source_search"]["usage"]["public_resample_failures"])
            for case in completed_cases
        ),
    }
    labeling_complete = (
        len(completed_cases) == spec.run_count
        and all(run["terminal"] is True for run in base_runs)
        and len(completed_interventions) == len(interventions)
    )
    recommendation: dict[str, Any] = {
        "labeling_complete": labeling_complete,
        "class_diversity_sufficient_for_gate_fitting": (
            beneficial >= 8
            and harmful >= 8
            and represented_beneficial >= 2
            and represented_harmful >= 2
        ),
        "validation_allowed": False,
    }
    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
        assert spec.promotion_gate is not None
        eligible_recommendations = sum(
            int(case["source_search"]["eligible_recommendations"]) for case in completed_cases
        )
        search_summary["eligible_recommendations"] = eligible_recommendations
        unique_seeds = sum(bool(case["interventions"]) for case in completed_cases)
        conclusive = int(overall["conclusive_interventions"])
        recommendation.update(
            {
                "qualifying_interventions": len(interventions),
                "unique_qualifying_seeds": unique_seeds,
                "combat_resolution_signal_sufficient_for_full_run_preflight": (
                    labeling_complete
                    and conclusive == len(interventions)
                    and len(interventions) >= spec.promotion_gate.minimum_qualifying_interventions
                    and unique_seeds >= spec.promotion_gate.minimum_unique_seeds
                    and beneficial >= spec.promotion_gate.minimum_beneficial_interventions
                    and harmful <= spec.promotion_gate.maximum_harmful_interventions
                ),
            }
        )
    return {
        "base_runs": {
            "benchmark_denominator": len(cases),
            "completed_runs": len(completed_cases),
            "failed_runs": len(cases) - len(completed_cases),
            "terminal_runs": sum(run["terminal"] is True for run in base_runs),
            "truncated_runs": sum(run["truncated"] is True for run in base_runs),
            "victories": sum(run["victory"] is True for run in base_runs),
            "mean_maximum_floor": _artifact_float(
                sum(int(run["maximum_floor"]) for run in base_runs) / max(1, len(base_runs))
            ),
            "decisions": sum(int(run["decisions"]) for run in base_runs),
            "total_decision_cpu_seconds": _artifact_float(
                sum(float(run["total_decision_cpu_seconds"]) for run in base_runs)
            ),
        },
        "search": search_summary,
        "interventions": {
            "selected_interventions": len(interventions),
            "completed_interventions": len(completed_interventions),
            "failed_interventions": len(interventions) - len(completed_interventions),
            "overall": overall,
            "by_stratum": by_stratum,
        },
        "recommendation": recommendation,
    }


def _intervention_summary(interventions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    conclusive = [item for item in interventions if item["paired_label"] != "inconclusive"]
    return {
        "evaluated_interventions": len(interventions),
        "conclusive_interventions": len(conclusive),
        "beneficial_interventions": sum(
            item["paired_label"] == "beneficial" for item in conclusive
        ),
        "tied_interventions": sum(item["paired_label"] == "tied" for item in conclusive),
        "harmful_interventions": sum(item["paired_label"] == "harmful" for item in conclusive),
        "counterfactual_victories": sum(
            item["counterfactual_run"]["victory"] is True for item in conclusive
        ),
        "mean_maximum_floor_difference": (
            None
            if not conclusive
            else _artifact_float(
                sum(float(item["maximum_floor_difference"]) for item in conclusive)
                / len(conclusive)
            )
        ),
        "mean_search_advantage": (
            None
            if not interventions
            else _artifact_float(
                sum(float(item["search_advantage"]) for item in interventions) / len(interventions)
            )
        ),
        "counterfactual_decisions": sum(
            int(item["counterfactual_run"]["decisions_after_source"])
            for item in interventions
            if item["counterfactual_run"] is not None
        ),
        "counterfactual_decision_cpu_seconds": _artifact_float(
            sum(
                float(item["counterfactual_run"]["total_decision_cpu_seconds"])
                for item in interventions
                if item["counterfactual_run"] is not None
            )
        ),
    }


def _paired_label(
    base_run: dict[str, Any], counterfactual: dict[str, Any]
) -> tuple[str, int | None, int | None]:
    if base_run["terminal"] is not True or counterfactual["terminal"] is not True:
        return "inconclusive", None, None
    victory_difference = int(counterfactual["victory"]) - int(base_run["victory"])
    floor_difference = int(counterfactual["maximum_floor"]) - int(base_run["maximum_floor"])
    if victory_difference > 0:
        return "beneficial", floor_difference, victory_difference
    if victory_difference < 0:
        return "harmful", floor_difference, victory_difference
    if floor_difference > 0:
        return "beneficial", floor_difference, victory_difference
    if floor_difference < 0:
        return "harmful", floor_difference, victory_difference
    return "tied", floor_difference, victory_difference


def _validate_run_outcome(outcome: dict[str, Any], *, base: bool) -> None:
    decision_key = "decisions" if base else "decisions_after_source"
    expected = {
        decision_key,
        "terminal",
        "victory",
        "truncated",
        "termination_reason",
        "maximum_floor",
        "final_state_hash",
        "action_trace_sha256",
        "total_decision_seconds",
        "total_decision_cpu_seconds",
    }
    _exact_keys(outcome, expected, "run outcome")
    if _integer(outcome.get(decision_key), decision_key) < 0:
        raise ValueError("Combat-search intervention decision count is negative")
    terminal = outcome.get("terminal")
    truncated = outcome.get("truncated")
    victory = outcome.get("victory")
    if not all(isinstance(value, bool) for value in (terminal, truncated, victory)):
        raise ValueError("Combat-search intervention outcome flags differ")
    if truncated is terminal or (victory and not terminal):
        raise ValueError("Combat-search intervention terminal flags differ")
    if outcome.get("termination_reason") not in {
        "terminal",
        "policy_cycle",
        "decision_limit",
    }:
        raise ValueError("Combat-search intervention termination reason differs")
    if (outcome.get("termination_reason") == "terminal") is not terminal:
        raise ValueError("Combat-search intervention termination status differs")
    if _integer(outcome.get("maximum_floor"), "maximum floor") < 0:
        raise ValueError("Combat-search intervention maximum floor is negative")
    _string(outcome.get("final_state_hash"), "final state hash")
    if not _is_identifier(_string(outcome.get("action_trace_sha256"), "action trace")):
        raise ValueError("Combat-search intervention action trace identity differs")
    for field in ("total_decision_seconds", "total_decision_cpu_seconds"):
        if _number(outcome.get(field), field) < 0.0:
            raise ValueError("Combat-search intervention timing is negative")


def _validate_inputs(
    ruleset: RulesetIdentity,
    base_policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    spec: CombatSearchInterventionSpec,
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
        raise ValueError("Combat-search intervention identities differ")
    if getattr(base_policy, "split_manifest_id", None) != split_manifest.manifest_id:
        raise ValueError("Combat-search intervention policy split differs")
    if getattr(base_policy, "ruleset", None) != ruleset:
        raise ValueError("Combat-search intervention policy ruleset differs")


def _case_schema_version(spec: CombatSearchInterventionSpec) -> str:
    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
        return COMBAT_RESOLUTION_INTERVENTION_CASE_SCHEMA_VERSION
    return INTERVENTION_CASE_SCHEMA_VERSION


def _report_schema_version(spec: CombatSearchInterventionSpec) -> str:
    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
        return COMBAT_RESOLUTION_INTERVENTION_REPORT_SCHEMA_VERSION
    return INTERVENTION_REPORT_SCHEMA_VERSION


def _report_configuration(
    spec: CombatSearchInterventionSpec,
    seeds: Sequence[int],
    model_id: str,
) -> dict[str, object]:
    configuration: dict[str, object] = {
        "seeds": list(seeds),
        "workers": spec.workers,
        "maximum_decisions_per_run": spec.maximum_decisions_per_run,
        "cycle_repetition_threshold": spec.cycle_repetition_threshold,
        "shadow_combat_advancement_config_id": spec.shadow_config.config_id,
        "shadow_policy_id": combat_advancement_policy_id(model_id, spec.shadow_config),
        "margin_strata": [stratum.as_dict() for stratum in spec.margin_strata],
        "selection_salt": spec.selection_salt,
    }
    if spec.schema_version == COMBAT_RESOLUTION_INTERVENTION_SPEC_SCHEMA_VERSION:
        assert spec.promotion_gate is not None
        configuration.update(
            {
                "selection_rule": spec.selection_rule,
                "promotion_gate": spec.promotion_gate.as_dict(),
            }
        )
    return configuration


def _branch_outcome_dict(outcome: CombatBranchOutcome) -> dict[str, object]:
    return {
        "outcome": outcome.outcome,
        "transitions": outcome.transitions,
        "resolved_state_hash": outcome.resolved_state_hash,
        "resolved_decision_type": outcome.resolved_decision_type,
        "resolved_observation": outcome.resolved_observation,
        "source_floor": outcome.source_floor,
        "resolved_floor": outcome.resolved_floor,
        "source_hp": outcome.source_hp,
        "resolved_hp": outcome.resolved_hp,
    }


def _validate_branch_outcomes(
    value: object,
    *,
    counts: tuple[int, ...],
    hidden_worlds: int,
    maximum_steps: int,
    source_public_state: dict[str, Any],
) -> int:
    outcomes = _list(value, "branch outcomes")
    if len(outcomes) != hidden_worlds or len(counts) != 4:
        raise ValueError("Combat-search intervention branch outcome count differs")
    observed = {name: 0 for name in ("run_victory", "run_defeat", "combat_clear", "censored")}
    total_transitions = 0
    for outcome_value in outcomes:
        outcome = _mapping(outcome_value, "branch outcome")
        _exact_keys(
            outcome,
            {
                "outcome",
                "transitions",
                "resolved_state_hash",
                "resolved_decision_type",
                "resolved_observation",
                "source_floor",
                "resolved_floor",
                "source_hp",
                "resolved_hp",
            },
            "branch outcome",
        )
        outcome_name = _string(outcome.get("outcome"), "branch outcome")
        if outcome_name not in observed:
            raise ValueError("Combat-search intervention branch outcome differs")
        observed[outcome_name] += 1
        transitions = _integer(outcome.get("transitions"), "branch transitions")
        if transitions <= 0 or transitions > maximum_steps:
            raise ValueError("Combat-search intervention branch transitions differ")
        total_transitions += transitions
        resolved_state_hash = _string(outcome.get("resolved_state_hash"), "resolved state hash")
        decision_type = _string(outcome.get("resolved_decision_type"), "resolved decision type")
        resolved_public_state = _validate_observation_evidence(
            outcome.get("resolved_observation"),
            expected_state_hash=resolved_state_hash,
            expected_decision_types={decision_type},
        )
        if outcome_name == "combat_clear" and decision_type not in {
            item.value for item in COMBAT_CLEAR_DECISION_TYPES
        }:
            raise ValueError("Combat-search intervention combat-clear boundary differs")
        if outcome_name == "censored" and decision_type not in {"combat", "combat_selection"}:
            raise ValueError("Combat-search intervention censored boundary differs")
        if outcome_name in {"run_victory", "run_defeat"} and decision_type != "terminal":
            raise ValueError("Combat-search intervention terminal boundary differs")
        for field in ("source_floor", "resolved_floor", "source_hp", "resolved_hp"):
            field_value = outcome.get(field)
            if field_value is not None and _integer(field_value, field) < 0:
                raise ValueError("Combat-search intervention public resource differs")
        if outcome.get("source_floor") != _public_state_integer(
            source_public_state, ("floor",), ("run", "floor")
        ) or outcome.get("resolved_floor") != _public_state_integer(
            resolved_public_state, ("floor",), ("run", "floor")
        ):
            raise ValueError("Combat-search intervention public floor evidence differs")
        if outcome.get("source_hp") != _public_state_integer(
            source_public_state,
            ("player_hp",),
            ("player", "hp"),
            ("player", "current_hp"),
            ("hp",),
        ) or outcome.get("resolved_hp") != _public_state_integer(
            resolved_public_state,
            ("player_hp",),
            ("player", "hp"),
            ("player", "current_hp"),
            ("hp",),
        ):
            raise ValueError("Combat-search intervention public HP evidence differs")
    expected = dict(
        zip(
            ("run_victory", "run_defeat", "combat_clear", "censored"),
            counts,
            strict=True,
        )
    )
    if observed != expected:
        raise ValueError("Combat-search intervention branch outcome aggregate differs")
    return total_transitions


def _validate_observation_evidence(
    value: object,
    *,
    expected_state_hash: str,
    expected_decision_types: set[str],
) -> dict[str, Any]:
    observation = _mapping(value, "public observation evidence")
    _exact_keys(
        observation,
        {"schema_version", "patch_id", "decision_type", "public_state", "state_hash"},
        "public observation evidence",
    )
    _string(observation.get("schema_version"), "observation schema version")
    _string(observation.get("patch_id"), "observation patch id")
    decision_type = _string(observation.get("decision_type"), "observation decision type")
    if decision_type not in expected_decision_types:
        raise ValueError("Combat-search intervention observation boundary differs")
    public_state = _mapping(observation.get("public_state"), "public state evidence")
    state_hash = _string(observation.get("state_hash"), "observation state hash")
    expected_hash = hashlib.sha256(
        json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if state_hash != expected_state_hash or state_hash != expected_hash:
        raise ValueError("Combat-search intervention public state hash differs")
    return public_state


def _public_state_integer(public_state: dict[str, Any], *paths: tuple[str, ...]) -> int | None:
    for path in paths:
        current: Any = public_state
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, int) and not isinstance(current, bool):
                return current
    return None


def _count_mapping(value: object, strata: Sequence[MarginStratum]) -> dict[str, int]:
    document = _mapping(value, "stratum counts")
    if set(document) != {stratum.name for stratum in strata}:
        raise ValueError("Combat-search intervention stratum count fields differ")
    counts = {name: _integer(count, f"{name} count") for name, count in document.items()}
    if any(count < 0 for count in counts.values()):
        raise ValueError("Combat-search intervention stratum count is negative")
    return counts


def _validate_usage(usage: dict[str, Any]) -> None:
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
    if any(_integer(usage.get(field), field) < 0 for field in expected):
        raise ValueError("Combat-search intervention usage count is negative")
    if int(usage["search_fallback_decisions"]) != int(usage["public_resample_failures"]):
        raise ValueError("Combat-search intervention fallback usage differs")


def _stratum_for_margin(margin: float, strata: Sequence[MarginStratum]) -> MarginStratum:
    for stratum in strata:
        if stratum.contains(margin):
            return stratum
    raise ValueError("Search advantage does not belong to a configured stratum")


def _public_floor(observation: Observation) -> int:
    direct = observation.public_state.get("floor")
    if isinstance(direct, int) and not isinstance(direct, bool):
        return direct
    run = observation.public_state.get("run")
    if isinstance(run, dict):
        nested = run.get("floor")
        if isinstance(nested, int) and not isinstance(nested, bool):
            return nested
    return 0


def _case_path(root: Path, seed: int) -> Path:
    return root / "cases" / f"seed-{seed:06d}.json"


def _action_trace_id(action_ids: Sequence[str]) -> str:
    return "sha256:" + hashlib.sha256("\n".join(action_ids).encode()).hexdigest()


def _artifact_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Artifact number must be finite")
    return float(f"{value:.12g}")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    return _mapping(value, label)


def _mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{name} fields differ")


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


def _is_identifier(value: str) -> bool:
    import re

    return re.fullmatch(_IDENTIFIER_PATTERN, value) is not None


def _close_environment(environment: object) -> None:
    close = getattr(environment, "close", None)
    if callable(close):
        close()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
