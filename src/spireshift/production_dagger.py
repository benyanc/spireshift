from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from spireshift.agents.learned import ProductionPolicyDecision
from spireshift.bootstrap_teacher import (
    BootstrapPolicyArtifacts,
    CurriculumSignalSpec,
    CurriculumStateCase,
    CurriculumStateSet,
    load_bootstrap_state_set_document,
    load_curriculum_policy_examples,
)
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.core.types import DecisionType, LegalAction, Observation
from spireshift.liveness import PublicNoOpActionGuard
from spireshift.models import write_model_artifact
from spireshift.representations import build_model_input
from spireshift.splits import SplitManifest, SplitName

PRODUCTION_DAGGER_CONFIG_SCHEMA_VERSION = "production-dagger-config-v1"
PRODUCTION_DAGGER_CASE_SCHEMA_VERSION = "production-dagger-case-v1"
PRODUCTION_DAGGER_REPORT_SCHEMA_VERSION = "production-dagger-collection-v1"
PRODUCTION_DAGGER_SELECTION_POLICY = "production-selective-dagger-v1"
CLAIM_SCOPE = "train_only_policy_improvement_collection"


class ProductionPolicy(Protocol):
    policy_id: str
    model_id: str
    split_manifest_id: str
    ruleset: RulesetIdentity

    def predict(
        self, observation: Observation, legal_actions: Sequence[LegalAction]
    ) -> ProductionPolicyDecision: ...


@dataclass(frozen=True, slots=True)
class ProductionDaggerConfig:
    split_manifest_id: str
    ruleset_manifest_id: str
    model_id: str
    training_report_id: str
    reference_dataset_id: str
    intervention_spec_id: str
    intervention_report_id: str
    run_offset: int
    run_count: int
    workers: int
    maximum_decisions_per_run: int
    cycle_repetition_threshold: int
    liveness_tail_length: int
    no_op_fallback_threshold: int
    rare_state_max_fraction: float
    high_entropy_threshold: float
    terminal_frontier_states_per_run: int
    maximum_selected_states_per_run: int
    minimum_selected_states: int
    minimum_source_floors: int
    minimum_decision_types: int
    selection_salt: str
    objective_id: str = "terminal-victory-v1"
    partition: str = SplitName.TRAIN.value

    def __post_init__(self) -> None:
        if self.partition != SplitName.TRAIN.value:
            raise ValueError("Production DAgger may collect only train runs")
        if self.objective_id != "terminal-victory-v1":
            raise ValueError("Production DAgger must preserve terminal victory")
        for name, value, minimum in (
            ("run_offset", self.run_offset, 0),
            ("run_count", self.run_count, 1),
            ("workers", self.workers, 1),
            ("maximum_decisions_per_run", self.maximum_decisions_per_run, 1),
            ("cycle_repetition_threshold", self.cycle_repetition_threshold, 2),
            ("liveness_tail_length", self.liveness_tail_length, 1),
            ("no_op_fallback_threshold", self.no_op_fallback_threshold, 1),
            ("terminal_frontier_states_per_run", self.terminal_frontier_states_per_run, 1),
            ("maximum_selected_states_per_run", self.maximum_selected_states_per_run, 1),
            ("minimum_selected_states", self.minimum_selected_states, 1),
            ("minimum_source_floors", self.minimum_source_floors, 1),
            ("minimum_decision_types", self.minimum_decision_types, 1),
        ):
            if isinstance(value, bool) or value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")
        if self.terminal_frontier_states_per_run > self.maximum_selected_states_per_run:
            raise ValueError("Terminal-frontier reservation exceeds the per-run selection cap")
        for name, threshold in (
            ("rare_state_max_fraction", self.rare_state_max_fraction),
            ("high_entropy_threshold", self.high_entropy_threshold),
        ):
            if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
                raise ValueError(f"{name} must be between zero and one")
        if not self.selection_salt:
            raise ValueError("Production DAgger selection salt must be non-empty")

    def body(self) -> dict[str, object]:
        return {
            "schema_version": PRODUCTION_DAGGER_CONFIG_SCHEMA_VERSION,
            "split_manifest_id": self.split_manifest_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            "objective_id": self.objective_id,
            "model_id": self.model_id,
            "training_report_id": self.training_report_id,
            "reference_dataset_id": self.reference_dataset_id,
            "intervention_spec_id": self.intervention_spec_id,
            "intervention_report_id": self.intervention_report_id,
            "partition": self.partition,
            "run_offset": self.run_offset,
            "run_count": self.run_count,
            "workers": self.workers,
            "maximum_decisions_per_run": self.maximum_decisions_per_run,
            "cycle_repetition_threshold": self.cycle_repetition_threshold,
            "liveness_tail_length": self.liveness_tail_length,
            "no_op_fallback_threshold": self.no_op_fallback_threshold,
            "rare_state_max_fraction": self.rare_state_max_fraction,
            "high_entropy_threshold": self.high_entropy_threshold,
            "terminal_frontier_states_per_run": self.terminal_frontier_states_per_run,
            "maximum_selected_states_per_run": self.maximum_selected_states_per_run,
            "minimum_selected_states": self.minimum_selected_states,
            "minimum_source_floors": self.minimum_source_floors,
            "minimum_decision_types": self.minimum_decision_types,
            "selection_salt": self.selection_salt,
        }

    @property
    def config_id(self) -> str:
        return manifest_identifier(self.body())

    def as_dict(self) -> dict[str, object]:
        return {**self.body(), "config_id": self.config_id}

    @classmethod
    def from_mapping(cls, value: object) -> ProductionDaggerConfig:
        document = _mapping(value, "production DAgger config")
        expected = {
            "schema_version",
            "config_id",
            "split_manifest_id",
            "ruleset_manifest_id",
            "objective_id",
            "model_id",
            "training_report_id",
            "reference_dataset_id",
            "intervention_spec_id",
            "intervention_report_id",
            "partition",
            "run_offset",
            "run_count",
            "workers",
            "maximum_decisions_per_run",
            "cycle_repetition_threshold",
            "liveness_tail_length",
            "no_op_fallback_threshold",
            "rare_state_max_fraction",
            "high_entropy_threshold",
            "terminal_frontier_states_per_run",
            "maximum_selected_states_per_run",
            "minimum_selected_states",
            "minimum_source_floors",
            "minimum_decision_types",
            "selection_salt",
        }
        if set(document) != expected:
            raise ValueError("Production DAgger config fields differ")
        if document.get("schema_version") != PRODUCTION_DAGGER_CONFIG_SCHEMA_VERSION:
            raise ValueError("Production DAgger config schema differs")
        config = cls(
            split_manifest_id=_string(document.get("split_manifest_id"), "split manifest ID"),
            ruleset_manifest_id=_string(document.get("ruleset_manifest_id"), "ruleset ID"),
            objective_id=_string(document.get("objective_id"), "objective ID"),
            model_id=_string(document.get("model_id"), "model ID"),
            training_report_id=_string(document.get("training_report_id"), "training report ID"),
            reference_dataset_id=_string(
                document.get("reference_dataset_id"), "reference dataset ID"
            ),
            intervention_spec_id=_string(
                document.get("intervention_spec_id"), "intervention spec ID"
            ),
            intervention_report_id=_string(
                document.get("intervention_report_id"), "intervention report ID"
            ),
            partition=_string(document.get("partition"), "partition"),
            run_offset=_integer(document.get("run_offset"), "run offset"),
            run_count=_integer(document.get("run_count"), "run count"),
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
            rare_state_max_fraction=_number(
                document.get("rare_state_max_fraction"), "rare-state fraction"
            ),
            high_entropy_threshold=_number(
                document.get("high_entropy_threshold"), "entropy threshold"
            ),
            terminal_frontier_states_per_run=_integer(
                document.get("terminal_frontier_states_per_run"), "frontier state count"
            ),
            maximum_selected_states_per_run=_integer(
                document.get("maximum_selected_states_per_run"), "selection cap"
            ),
            minimum_selected_states=_integer(
                document.get("minimum_selected_states"), "minimum selected states"
            ),
            minimum_source_floors=_integer(
                document.get("minimum_source_floors"), "minimum source floors"
            ),
            minimum_decision_types=_integer(
                document.get("minimum_decision_types"), "minimum decision types"
            ),
            selection_salt=_string(document.get("selection_salt"), "selection salt"),
        )
        if document.get("config_id") != config.config_id:
            raise ValueError("Production DAgger config identity mismatch")
        return config


@dataclass(frozen=True, slots=True)
class ProductionDaggerReference:
    dataset_id: str
    capture_policy_id: str
    run_seeds: frozenset[int]
    feature_counts: Counter[str]
    examples: int

    @classmethod
    def from_dataset(
        cls, report_path: Path, *, split_manifest: SplitManifest
    ) -> ProductionDaggerReference:
        examples = load_curriculum_policy_examples(
            report_path,
            split_manifest=split_manifest,
        )
        report = _load_object(report_path, "reference curriculum")
        dataset_id = _string(report.get("dataset_id"), "reference dataset ID")
        state_set = load_bootstrap_state_set_document(report.get("state_set"))
        if not isinstance(state_set, CurriculumStateSet):
            raise ValueError("Production DAgger reference must be a curriculum dataset")
        if state_set.partition != SplitName.TRAIN.value:
            raise ValueError("Production DAgger reference must use train runs")
        return cls(
            dataset_id=dataset_id,
            capture_policy_id=state_set.capture_policy_id,
            run_seeds=frozenset(case.run_seed for case in state_set.cases),
            feature_counts=Counter(
                example.model_input.model_feature_digest() for example in examples
            ),
            examples=len(examples),
        )


@dataclass(frozen=True, slots=True)
class ProductionDaggerResult:
    successful: bool
    report_path: Path
    state_set_path: Path | None
    causal_preferences_path: Path
    report: dict[str, Any]


def load_production_dagger_config(path: Path) -> ProductionDaggerConfig:
    return ProductionDaggerConfig.from_mapping(_load_object(path, "production DAgger config"))


def run_production_dagger_collection(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionPolicy,
    policy_artifacts: BootstrapPolicyArtifacts,
    split_manifest: SplitManifest,
    reference: ProductionDaggerReference,
    causal_preferences: dict[str, Any],
    config: ProductionDaggerConfig,
    output_directory: Path,
    resume: bool = False,
    now: Callable[[], str] | None = None,
) -> ProductionDaggerResult:
    _validate_collection_inputs(
        ruleset=ruleset,
        policy=policy,
        policy_artifacts=policy_artifacts,
        split_manifest=split_manifest,
        reference=reference,
        causal_preferences=causal_preferences,
        config=config,
    )
    seeds = split_manifest.seeds(SplitName.TRAIN)[
        config.run_offset : config.run_offset + config.run_count
    ]
    if len(seeds) != config.run_count:
        raise ValueError("Production DAgger seed window exceeds the train partition")
    if reference.run_seeds & set(seeds):
        raise ValueError("Production DAgger runs overlap the reference curriculum")
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists() and not resume:
        raise FileExistsError(f"Production DAgger output already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "production-dagger-collection.json"
    state_set_path = output_directory / "state-set.json"
    causal_path = output_directory / "causal-preferences.json"
    if report_path.exists() or state_set_path.exists():
        raise FileExistsError("Production DAgger aggregate output already exists")
    _write_idempotent(causal_preferences, causal_path, label="causal preference set")

    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, Path]] = []
    for seed in seeds:
        path = _case_path(output_directory, seed)
        if path.exists():
            cases.append(_load_case(path, seed=seed, config=config, policy=policy))
        else:
            pending.append((seed, path))
    with ThreadPoolExecutor(max_workers=min(config.workers, max(1, len(pending)))) as executor:
        futures: dict[Future[dict[str, Any]], tuple[int, Path]] = {}
        for seed, path in pending:
            future = executor.submit(
                _collect_run,
                environment_factory=environment_factory,
                ruleset=ruleset,
                policy=policy,
                reference=reference,
                config=config,
                seed=seed,
            )
            futures[future] = (seed, path)
        for future in as_completed(futures):
            _, path = futures[future]
            case = future.result()
            write_model_artifact(case, path, label="production DAgger case")
            cases.append(case)

    ordered = sorted(cases, key=lambda case: int(case["seed"]))
    if len(ordered) != config.run_count:
        raise RuntimeError("Production DAgger did not produce every run")
    summary = _collection_summary(ordered)
    selected_records = [
        record
        for case in ordered
        if case["status"] == "completed"
        for record in case["decisions"]
        if record["selected_for_relabeling"] is True
    ]
    state_set: dict[str, Any] | None = None
    if (
        summary["failed_runs"] == 0
        and summary["policy_cycle_runs"] == 0
        and summary["decision_limit_runs"] == 0
        and len(selected_records) >= config.minimum_selected_states
        and len(
            {
                record["source_floor"]
                for record in selected_records
                if record["source_floor"] is not None
            }
        )
        >= config.minimum_source_floors
        and len({record["decision_type"] for record in selected_records})
        >= config.minimum_decision_types
    ):
        state_set = _build_state_set(
            cases=ordered,
            selected_records=selected_records,
            policy_artifacts=policy_artifacts,
            split_manifest=split_manifest,
            config=config,
        )
        write_model_artifact(state_set, state_set_path, label="production DAgger state set")
    body: dict[str, Any] = {
        "schema_version": PRODUCTION_DAGGER_REPORT_SCHEMA_VERSION,
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "config_id": config.config_id,
        "model_id": policy.model_id,
        "training_report_id": config.training_report_id,
        "reference_dataset_id": reference.dataset_id,
        "causal_preference_set_id": causal_preferences["preference_set_id"],
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TRAIN.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "configuration": config.as_dict(),
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
        "causal_preferences": {
            "path": str(causal_path.relative_to(output_directory)),
            "preference_set_id": causal_preferences["preference_set_id"],
        },
        "state_set": (
            None
            if state_set is None
            else {
                "path": str(state_set_path.relative_to(output_directory)),
                "state_set_id": state_set["state_set_id"],
            }
        ),
        "summary": summary,
        "readiness": {
            "passed": state_set is not None,
            "minimum_selected_states": config.minimum_selected_states,
            "minimum_source_floors": config.minimum_source_floors,
            "minimum_decision_types": config.minimum_decision_types,
            "terminal_value_head_unblocked": (
                0 < int(summary["victories"]) < int(summary["terminal_runs"])
            ),
            "blocking_data_limitation": _terminal_data_limitation(summary),
        },
        "claim_scope": CLAIM_SCOPE,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    write_model_artifact(report, report_path, label="production DAgger collection")
    return ProductionDaggerResult(
        successful=state_set is not None,
        report_path=report_path,
        state_set_path=state_set_path if state_set is not None else None,
        causal_preferences_path=causal_path,
        report=report,
    )


def verify_production_dagger_collection(
    report_path: Path,
    *,
    config: ProductionDaggerConfig,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    errors: list[str] = []
    report_id: str | None = None
    verified_cases = 0
    try:
        report = _load_object(report_path, "production DAgger collection")
        report_id = report.get("report_id") if isinstance(report.get("report_id"), str) else None
        body = {key: value for key, value in report.items() if key != "report_id"}
        if report_id != manifest_identifier(body):
            errors.append("collection report identity mismatch")
        expected = {
            "schema_version": PRODUCTION_DAGGER_REPORT_SCHEMA_VERSION,
            "config_id": config.config_id,
            "model_id": config.model_id,
            "training_report_id": config.training_report_id,
            "reference_dataset_id": config.reference_dataset_id,
            "split_manifest_id": split_manifest.manifest_id,
            "partition": SplitName.TRAIN.value,
            "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
            "objective_id": split_manifest.objective_id,
            "claim_scope": CLAIM_SCOPE,
        }
        if any(report.get(key) != value for key, value in expected.items()):
            errors.append("collection report provenance differs")
        if report.get("configuration") != config.as_dict():
            errors.append("collection configuration differs")
        root = report_path.expanduser().resolve().parent
        cases: list[dict[str, Any]] = []
        for raw_reference in _list(report.get("cases"), "collection case references"):
            reference = _mapping(raw_reference, "collection case reference")
            seed = _integer(reference.get("seed"), "collection seed")
            path = (root / _string(reference.get("path"), "collection case path")).resolve()
            if root not in path.parents:
                raise ValueError("Collection case escapes its report root")
            case = _load_case_document(path, seed=seed, config=config)
            if reference.get("case_id") != case.get("case_id"):
                errors.append(f"seed {seed}: referenced case identity mismatch")
            cases.append(case)
            verified_cases += 1
        expected_seeds = split_manifest.seeds(SplitName.TRAIN)[
            config.run_offset : config.run_offset + config.run_count
        ]
        if tuple(sorted(int(case["seed"]) for case in cases)) != tuple(sorted(expected_seeds)):
            errors.append("collection seed coverage differs")
        if report.get("summary") != _collection_summary(cases):
            errors.append("collection summary differs from case evidence")
        causal_reference = _mapping(report.get("causal_preferences"), "causal reference")
        causal_path = (root / _string(causal_reference.get("path"), "causal path")).resolve()
        causal = _load_content_addressed(causal_path, "preference_set_id")
        if (
            causal_reference.get("preference_set_id") != causal.get("preference_set_id")
            or report.get("causal_preference_set_id") != causal.get("preference_set_id")
            or causal.get("intervention_spec_id") != config.intervention_spec_id
            or causal.get("intervention_report_id") != config.intervention_report_id
        ):
            errors.append("causal preference provenance differs")
        state_reference = report.get("state_set")
        if state_reference is not None:
            state_mapping = _mapping(state_reference, "state-set reference")
            state_path = (root / _string(state_mapping.get("path"), "state-set path")).resolve()
            state_set = load_bootstrap_state_set_document(
                _load_object(state_path, "production DAgger state set")
            )
            if state_mapping.get("state_set_id") != state_set.state_set_id:
                errors.append("state-set reference identity mismatch")
            if not isinstance(state_set, CurriculumStateSet):
                errors.append("production DAgger did not produce a curriculum state set")
            else:
                selected = sum(
                    record["selected_for_relabeling"] is True
                    for case in cases
                    if case["status"] == "completed"
                    for record in case["decisions"]
                )
                if len(state_set.cases) != selected:
                    errors.append("state-set coverage differs from selected decisions")
    except (OSError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        errors.append(str(error))
    return {
        "schema_version": "production-dagger-verification-v1",
        "valid": not errors,
        "report_id": report_id,
        "verified_cases": verified_cases,
        "errors": errors,
    }


def _validate_collection_inputs(
    *,
    ruleset: RulesetIdentity,
    policy: ProductionPolicy,
    policy_artifacts: BootstrapPolicyArtifacts,
    split_manifest: SplitManifest,
    reference: ProductionDaggerReference,
    causal_preferences: dict[str, Any],
    config: ProductionDaggerConfig,
) -> None:
    expected = {
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": ruleset.manifest_id,
        "objective_id": split_manifest.objective_id,
        "model_id": policy.model_id,
        "training_report_id": policy_artifacts.training_report_id,
        "reference_dataset_id": reference.dataset_id,
        "intervention_spec_id": causal_preferences.get("intervention_spec_id"),
        "intervention_report_id": causal_preferences.get("intervention_report_id"),
    }
    if any(getattr(config, key) != value for key, value in expected.items()):
        raise ValueError("Production DAgger config provenance differs from supplied artifacts")
    if split_manifest.ruleset_manifest_id != ruleset.manifest_id:
        raise ValueError("Production DAgger split and environment rulesets differ")
    if policy.ruleset != ruleset or policy.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Production DAgger policy provenance differs")
    policy_artifacts.validate_for(
        split_manifest_id=split_manifest.manifest_id,
        ruleset_manifest_id=ruleset.manifest_id,
    )
    if policy_artifacts.policy_id != policy.policy_id:
        raise ValueError("Production DAgger policy artifact identity differs")
    if reference.capture_policy_id != policy.policy_id:
        raise ValueError("Production DAgger must continue the reference capture policy")
    if causal_preferences.get("partition") != SplitName.TRAIN.value:
        raise ValueError("Production DAgger causal preferences are not train-owned")


def _collect_run(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    policy: ProductionPolicy,
    reference: ProductionDaggerReference,
    config: ProductionDaggerConfig,
    seed: int,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Production DAgger environment ruleset changed")
        observation = environment.reset(seed)
        guard = PublicNoOpActionGuard(
            repetition_threshold=config.no_op_fallback_threshold,
            event_limit=config.liveness_tail_length,
        )
        occurrences: Counter[DecisionType] = Counter()
        transition_counts: Counter[tuple[str, str, str]] = Counter()
        action_ids: list[str] = []
        records: list[dict[str, Any]] = []
        maximum_floor = _public_floor(observation) or 0
        maximum_act = _public_act(observation)
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        termination_reason = "terminal" if terminal else "decision_limit"
        for decision_index in range(config.maximum_decisions_per_run):
            if terminal:
                break
            legal_actions = tuple(environment.legal_actions())
            if not legal_actions:
                raise RuntimeError("Nonterminal DAgger state has no legal actions")
            actions = guard.eligible_actions(observation, legal_actions)
            fallback_active = len(actions) != len(legal_actions)
            representation = build_model_input(ruleset, observation, actions)
            decision = policy.predict(observation, actions)
            if decision.representation_hash != representation.representation_hash:
                raise RuntimeError("DAgger policy and collector representations differ")
            if (
                decision.selected_action not in actions
                or decision.selected_action not in legal_actions
            ):
                raise RuntimeError("DAgger policy selected an illegal action")
            entropy = _normalized_entropy(decision.policy)
            digest = representation.model_feature_digest()
            reference_frequency = reference.feature_counts[digest]
            reference_fraction = reference_frequency / reference.examples
            reasons: list[str] = []
            selectable = len(legal_actions) > 1 and not fallback_active
            if selectable and reference_fraction <= config.rare_state_max_fraction:
                reasons.append("rare_reference_state")
            if selectable and entropy >= config.high_entropy_threshold:
                reasons.append("high_policy_entropy")
            occurrence = occurrences[observation.decision_type]
            occurrences[observation.decision_type] += 1
            source_observation = observation
            source_floor = _public_floor(observation)
            source_act = _public_act(observation)
            action = decision.selected_action
            transition = environment.step(action)
            observation = transition.next_observation
            guard.observe_transition(
                observation=source_observation,
                action=action,
                next_observation=observation,
                decision_index=decision_index,
            )
            key = (source_observation.state_hash, action.action_id, observation.state_hash)
            transition_counts[key] += 1
            action_ids.append(action.action_id)
            records.append(
                {
                    "decision_index": decision_index,
                    "decision_type": source_observation.decision_type.value,
                    "decision_occurrence": occurrence,
                    "source_state_hash": source_observation.state_hash,
                    "source_floor": source_floor,
                    "source_act": source_act,
                    "representation_hash": representation.representation_hash,
                    "model_feature_digest": digest,
                    "legal_action_count": len(legal_actions),
                    "eligible_action_count": len(actions),
                    "candidate_action_ids": list(decision.source_action_ids),
                    "selected_candidate_index": decision.selected_candidate_index,
                    "selected_action_id": action.action_id,
                    "policy": [_artifact_float(value) for value in decision.policy],
                    "policy_confidence": _artifact_float(max(decision.policy)),
                    "normalized_policy_entropy": _artifact_float(entropy),
                    "reference_frequency": reference_frequency,
                    "reference_fraction": _artifact_float(reference_fraction),
                    "fallback_active": fallback_active,
                    "selection_reasons": reasons,
                    "selection_priority": _selection_priority(
                        config.selection_salt,
                        seed,
                        decision_index,
                        source_observation.state_hash,
                    ),
                    "selected_for_relabeling": False,
                    "next_state_hash": observation.state_hash,
                    "public_state_changed": source_observation.state_hash != observation.state_hash,
                    "terminal_after_action": transition.terminal,
                    "victory_after_action": transition.victory,
                }
            )
            maximum_floor = max(maximum_floor, _public_floor(observation) or 0)
            next_act = _public_act(observation)
            if _act_rank(next_act) > _act_rank(maximum_act):
                maximum_act = next_act
            terminal = transition.terminal
            victory = transition.victory if terminal else False
            if terminal:
                termination_reason = "terminal"
                break
            if transition_counts[key] >= config.cycle_repetition_threshold:
                termination_reason = "policy_cycle"
                break
        _select_records(records, config=config)
        body: dict[str, Any] = {
            "schema_version": PRODUCTION_DAGGER_CASE_SCHEMA_VERSION,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
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
            "fallback": guard.as_dict(),
        }
    except Exception as error:  # noqa: BLE001 - failures remain in the denominator.
        body = {
            "schema_version": PRODUCTION_DAGGER_CASE_SCHEMA_VERSION,
            "config_id": config.config_id,
            "seed": seed,
            "partition": SplitName.TRAIN.value,
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
            "fallback": None,
        }
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                close()
    return {**body, "case_id": manifest_identifier(body)}


def _select_records(records: list[dict[str, Any]], *, config: ProductionDaggerConfig) -> None:
    selectable = [
        record
        for record in records
        if int(record["legal_action_count"]) > 1 and record["fallback_active"] is False
    ]
    frontier = sorted(
        selectable,
        key=lambda record: int(record["decision_index"]),
        reverse=True,
    )[: config.terminal_frontier_states_per_run]
    for record in frontier:
        reasons = list(record["selection_reasons"])
        if "terminal_frontier" not in reasons:
            reasons.append("terminal_frontier")
        record["selection_reasons"] = reasons
    candidates = [record for record in selectable if record["selection_reasons"]]
    candidates.sort(
        key=lambda record: (
            "terminal_frontier" not in record["selection_reasons"],
            -float(record["normalized_policy_entropy"]),
            int(record["reference_frequency"]),
            -(_public_number(record.get("source_floor")) or -1.0),
            -int(record["decision_index"]),
            str(record["selection_priority"]),
        )
    )
    for record in candidates[: config.maximum_selected_states_per_run]:
        record["selected_for_relabeling"] = True


def _build_state_set(
    *,
    cases: Sequence[dict[str, Any]],
    selected_records: Sequence[dict[str, Any]],
    policy_artifacts: BootstrapPolicyArtifacts,
    split_manifest: SplitManifest,
    config: ProductionDaggerConfig,
) -> dict[str, Any]:
    cases_by_seed = {int(case["seed"]): case for case in cases}
    state_cases: list[CurriculumStateCase] = []
    decision_occurrences: dict[str, set[int]] = {}
    for seed in sorted(cases_by_seed):
        case = cases_by_seed[seed]
        for record in case["decisions"]:
            if record["selected_for_relabeling"] is not True:
                continue
            decision_type = DecisionType(str(record["decision_type"]))
            occurrence = int(record["decision_occurrence"])
            decision_occurrences.setdefault(decision_type.value, set()).add(occurrence)
            state_cases.append(
                CurriculumStateCase(
                    state_id=(f"train-seed-{seed:06d}-{decision_type.value}-{occurrence:03d}"),
                    run_seed=seed,
                    decision_type=decision_type,
                    decision_index=occurrence,
                    expected_state_hash=str(record["source_state_hash"]),
                    expected_legal_actions=int(record["legal_action_count"]),
                    expected_source_floor=(
                        None if record["source_floor"] is None else int(record["source_floor"])
                    ),
                    expected_source_act=record["source_act"],
                )
            )
    discovery = {
        "schema_version": "bootstrap-curriculum-discovery-v2",
        "requested_runs": config.run_count,
        "run_offset": config.run_offset,
        "maximum_steps_per_run": config.maximum_decisions_per_run,
        "decision_occurrences": {
            key: sorted(values) for key, values in sorted(decision_occurrences.items())
        },
        "requested_coordinates": len(state_cases),
        "captured_coordinates": len(state_cases),
        "unreachable_coordinates": [],
        "terminal_runs": sum(case["terminal"] is True for case in cases),
        "step_limited_runs": sum(case["termination_reason"] == "decision_limit" for case in cases),
    }
    signal_spec = CurriculumSignalSpec(
        minimum_states=config.minimum_selected_states,
        minimum_source_floors=config.minimum_source_floors,
        minimum_decision_types=config.minimum_decision_types,
        minimum_effective_labeled_states=1.0,
        minimum_half_split_agreement=0.5,
        minimum_occupied_maximum_floor_bins=1,
    )
    temporary = CurriculumStateSet(
        state_set_id="pending",
        split_manifest_id=split_manifest.manifest_id,
        ruleset_manifest_id=split_manifest.ruleset_manifest_id,
        objective_id=split_manifest.objective_id,
        capture_policy_id=policy_artifacts.policy_id,
        partition=SplitName.TRAIN.value,
        selection_policy=f"{PRODUCTION_DAGGER_SELECTION_POLICY}:{config.config_id}",
        discovery=discovery,
        signal_spec=signal_spec,
        cases=tuple(state_cases),
        capture_policy=policy_artifacts.provenance(),
    )
    document = temporary.as_dict()
    body = {key: value for key, value in document.items() if key != "state_set_id"}
    document["state_set_id"] = manifest_identifier(body)
    return load_bootstrap_state_set_document(document).as_dict()


def _collection_summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    terminal = [case for case in completed if case["terminal"] is True]
    records = [record for case in completed for record in case["decisions"]]
    selected = [record for record in records if record["selected_for_relabeling"] is True]
    decision_histogram = Counter(str(record["decision_type"]) for record in selected)
    floor_histogram = Counter(str(record["source_floor"]) for record in selected)
    reason_histogram = Counter(
        reason for record in selected for reason in record["selection_reasons"]
    )
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
        "victories": sum(case["victory"] is True for case in terminal),
        "completion_rate": _artifact_float(len(completed) / max(1, len(cases))),
        "terminal_rate": _artifact_float(len(terminal) / max(1, len(cases))),
        "victory_rate": _artifact_float(
            sum(case["victory"] is True for case in terminal) / max(1, len(cases))
        ),
        "decisions": len(records),
        "selected_states": len(selected),
        "selected_unique_state_hashes": len(
            {str(record["source_state_hash"]) for record in selected}
        ),
        "selected_decision_type_histogram": dict(sorted(decision_histogram.items())),
        "selected_source_floor_histogram": dict(
            sorted(floor_histogram.items(), key=lambda item: item[0])
        ),
        "selection_reason_histogram": dict(sorted(reason_histogram.items())),
        "fallback_runs": sum(int(case["fallback"]["invocations"]) > 0 for case in completed),
        "fallback_invocations": sum(int(case["fallback"]["invocations"]) for case in completed),
        "suppressed_no_op_actions": sum(
            int(case["fallback"]["suppressed_actions"]) for case in completed
        ),
        "fallback_exhausted_states": sum(
            int(case["fallback"]["exhausted_states"]) for case in completed
        ),
        "mean_maximum_floor": _artifact_float(
            sum(int(case["maximum_floor"]) for case in completed) / max(1, len(completed))
        ),
    }


def _terminal_data_limitation(summary: dict[str, Any]) -> str | None:
    victories = int(summary["victories"])
    terminal_runs = int(summary["terminal_runs"])
    if victories == 0:
        return "collection contains no terminal victories"
    if victories == terminal_runs:
        return "collection contains no terminal defeats"
    return None


def _load_case(
    path: Path, *, seed: int, config: ProductionDaggerConfig, policy: ProductionPolicy
) -> dict[str, Any]:
    case = _load_case_document(path, seed=seed, config=config)
    if case.get("policy_id") != policy.policy_id or case.get("model_id") != policy.model_id:
        raise ValueError("Resumed production DAgger policy differs")
    return case


def _load_case_document(path: Path, *, seed: int, config: ProductionDaggerConfig) -> dict[str, Any]:
    case = _load_content_addressed(path, "case_id")
    expected = {
        "schema_version": PRODUCTION_DAGGER_CASE_SCHEMA_VERSION,
        "config_id": config.config_id,
        "seed": seed,
        "partition": SplitName.TRAIN.value,
        "model_id": config.model_id,
        "ruleset_manifest_id": config.ruleset_manifest_id,
    }
    if any(case.get(key) != value for key, value in expected.items()):
        raise ValueError("Production DAgger case provenance differs")
    return case


def _case_path(output_directory: Path, seed: int) -> Path:
    return output_directory / "cases" / f"seed-{seed:06d}.json"


def _normalized_entropy(probabilities: Sequence[float]) -> float:
    if len(probabilities) <= 1:
        return 0.0
    entropy = -sum(value * math.log(value) for value in probabilities if value > 0.0)
    return entropy / math.log(len(probabilities))


def _selection_priority(salt: str, seed: int, index: int, state_hash: str) -> str:
    return "sha256:" + hashlib.sha256(f"{salt}|{seed}|{index}|{state_hash}".encode()).hexdigest()


def _public_floor(observation: Observation) -> int | None:
    value = observation.public_state.get("floor")
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    run = observation.public_state.get("run")
    if isinstance(run, dict):
        value = run.get("floor")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _public_act(observation: Observation) -> int | str | None:
    value = observation.public_state.get("act")
    if isinstance(value, (int, str)) and not isinstance(value, bool):
        return value
    run = observation.public_state.get("run")
    if isinstance(run, dict):
        value = run.get("act")
        if isinstance(value, (int, str)) and not isinstance(value, bool):
            return value
    return None


def _act_rank(value: int | str | None) -> tuple[int, str]:
    if isinstance(value, int):
        return value, ""
    if isinstance(value, str):
        return 0, value
    return -1, ""


def _public_number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _artifact_float(value: float) -> float:
    return float(f"{value:.12g}")


def _write_idempotent(document: dict[str, Any], path: Path, *, label: str) -> None:
    encoded = json.dumps(document, indent=2, ensure_ascii=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise FileExistsError(f"Refusing to replace different {label}: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded, encoding="utf-8")


def _load_content_addressed(path: Path, identity_key: str) -> dict[str, Any]:
    document = _load_object(path, identity_key)
    identity = document.get(identity_key)
    body = {key: value for key, value in document.items() if key != identity_key}
    if identity != manifest_identifier(body):
        raise ValueError(f"{identity_key} identity mismatch")
    return document


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    return _mapping(value, label)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return dict(value)


def _list(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return list(value)


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
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
