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

from spireshift.agents.baseline import ProgressBootstrapPolicy
from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.combat_confirmation import CLAIM, CombatConfirmationConfig
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter, Policy
from spireshift.liveness import PUBLIC_NO_OP_FALLBACK_SCHEMA_VERSION, PublicNoOpActionGuard
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName
from spireshift.starting_evidence import _publish_json
from spireshift.trajectory_search import Act1Milestones

LEGACY_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION = "production-policy-evaluation-v1"
LEGACY_PRODUCTION_POLICY_CASE_SCHEMA_VERSION = "production-policy-evaluation-case-v1"
LIVENESS_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION = "production-policy-evaluation-v2"
LIVENESS_PRODUCTION_POLICY_CASE_SCHEMA_VERSION = "production-policy-evaluation-case-v2"
PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION = "production-policy-evaluation-v3"
PRODUCTION_POLICY_CASE_SCHEMA_VERSION = "production-policy-evaluation-case-v3"
REFERENCE_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION = "production-policy-evaluation-v4"
REFERENCE_PRODUCTION_POLICY_CASE_SCHEMA_VERSION = "production-policy-evaluation-case-v4"
FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION = "production-policy-evaluation-v5"
FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION = "production-policy-evaluation-case-v5"
POLICY_LIVENESS_SCHEMA_VERSION = "policy-liveness-diagnostic-v1"
DEFAULT_CYCLE_REPETITION_THRESHOLD = 8
DEFAULT_LIVENESS_TAIL_LENGTH = 16
DEFAULT_NO_OP_FALLBACK_THRESHOLD = 2
LEARNED_POLICY_KIND = "production_checkpoint"
BASELINE_POLICY_KIND = "progress_bootstrap_baseline"
REFERENCE_POLICY_KIND = "reference_production_checkpoint"


@dataclass(frozen=True, slots=True)
class ProductionPolicyEvaluationResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]
    new_runs: int = 0
    new_transitions: int = 0


def run_production_policy_evaluation(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    learned_policy: ProductionCheckpointPolicy,
    split_manifest: SplitManifest,
    training_report_id: str,
    seeds: Sequence[int],
    workers: int,
    maximum_decisions_per_run: int,
    output_directory: Path,
    reference_policy: ProductionCheckpointPolicy | None = None,
    reference_training_report_id: str | None = None,
    partition: SplitName = SplitName.TEST,
    cycle_repetition_threshold: int = DEFAULT_CYCLE_REPETITION_THRESHOLD,
    liveness_tail_length: int = DEFAULT_LIVENESS_TAIL_LENGTH,
    no_op_fallback_threshold: int = DEFAULT_NO_OP_FALLBACK_THRESHOLD,
    resume: bool = False,
    now: Callable[[], str] | None = None,
    confirmation: CombatConfirmationConfig | None = None,
    progress: Callable[[int, int], None] | None = None,
    record_activity: Callable[[int, int], None] | None = None,
) -> ProductionPolicyEvaluationResult:
    canonical_seeds = tuple(seeds)
    if not canonical_seeds or len(canonical_seeds) != len(set(canonical_seeds)):
        raise ValueError("Production evaluation seeds must be non-empty and unique")
    if partition is SplitName.TRAIN and confirmation is not None:
        confirmation = CombatConfirmationConfig.from_mapping(confirmation.document)
        confirmation.validate_evaluation(
            model_id=learned_policy.model_id,
            report_id=training_report_id,
            reference_model_id=reference_policy.model_id if reference_policy else None,
            reference_report_id=reference_training_report_id,
            split=split_manifest,
            ruleset_manifest_id=ruleset.manifest_id,
            patch_id=ruleset.patch_id,
            seeds=canonical_seeds,
            workers=workers,
            maximum_decisions=maximum_decisions_per_run,
            cycle_threshold=cycle_repetition_threshold,
            tail_length=liveness_tail_length,
            fallback_threshold=no_op_fallback_threshold,
        )
    elif partition not in (SplitName.VALIDATION, SplitName.TEST) or confirmation is not None:
        raise ValueError("Production evaluation partition must be validation or test")
    if any(split_manifest.split_for_seed(seed) is not partition for seed in canonical_seeds):
        raise ValueError(f"Production evaluation may use only {partition.value} seeds")
    if split_manifest.ruleset_manifest_id != ruleset.manifest_id:
        raise ValueError("Production evaluation split and environment rulesets differ")
    if split_manifest.objective_id != "terminal-victory-v1":
        raise ValueError("Production evaluation split does not use terminal victory")
    if learned_policy.ruleset != ruleset:
        raise ValueError("Production evaluation policy and environment rulesets differ")
    if learned_policy.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Production evaluation checkpoint and split identities differ")
    if (reference_policy is None) != (reference_training_report_id is None):
        raise ValueError("Reference policy and training report identity must be provided together")
    if reference_policy is not None:
        if reference_policy.ruleset != ruleset:
            raise ValueError("Production reference policy and environment rulesets differ")
        if reference_policy.split_manifest_id != split_manifest.manifest_id:
            raise ValueError("Production reference checkpoint and split identities differ")
        if reference_policy.model_id == learned_policy.model_id:
            raise ValueError("Production candidate and reference model identities must differ")
    if workers <= 0:
        raise ValueError("Production evaluation workers must be positive")
    if maximum_decisions_per_run <= 0:
        raise ValueError("maximum_decisions_per_run must be positive")
    if cycle_repetition_threshold < 2:
        raise ValueError("cycle_repetition_threshold must be at least two")
    if liveness_tail_length <= 0:
        raise ValueError("liveness_tail_length must be positive")
    if no_op_fallback_threshold <= 0:
        raise ValueError("no_op_fallback_threshold must be positive")
    if output_directory.exists() and not resume:
        raise FileExistsError(f"Production evaluation output already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "production-policy-evaluation.json"
    if report_path.exists():
        raise FileExistsError(f"Production evaluation report already exists: {report_path}")
    if confirmation is not None:
        plan_path = output_directory / "confirmation-plan.json"
        if plan_path.exists():
            if _load_object(plan_path, "confirmation plan") != confirmation.document:
                raise ValueError("Resumed confirmation plan differs")
        elif resume and any((output_directory / "cases").glob("*.json")):
            raise ValueError("Resumed fresh cases have no frozen confirmation plan")
        else:
            _publish_json(plan_path, confirmation.document)

    reference_comparison = reference_policy is not None
    evaluation_schema_version = (
        REFERENCE_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION
        if reference_comparison
        else PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION
    )
    case_schema_version = (
        REFERENCE_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
        if reference_comparison
        else PRODUCTION_POLICY_CASE_SCHEMA_VERSION
    )
    if confirmation is not None:
        evaluation_schema_version = FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION
        case_schema_version = FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
    if reference_policy is None:
        baseline_policy = ProgressBootstrapPolicy()
        policies: tuple[tuple[str, Policy, str | None], ...] = (
            (LEARNED_POLICY_KIND, learned_policy, learned_policy.model_id),
            (BASELINE_POLICY_KIND, baseline_policy, None),
        )
    else:
        policies = (
            (LEARNED_POLICY_KIND, learned_policy, learned_policy.model_id),
            (REFERENCE_POLICY_KIND, reference_policy, reference_policy.model_id),
        )
    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, str, Policy, str | None, Path]] = []
    for seed in canonical_seeds:
        for policy_kind, policy, model_id in policies:
            case_path = _case_path(output_directory, seed, policy_kind)
            if case_path.exists():
                resumed_case = _load_case(
                    case_path,
                    seed=seed,
                    policy_kind=policy_kind,
                    policy_id=policy.policy_id,
                    model_id=model_id,
                    ruleset_manifest_id=ruleset.manifest_id,
                    partition=partition,
                    schema_version=case_schema_version,
                )
                if resumed_case["status"] == "completed" and (
                    resumed_case["liveness"]["repetition_threshold"] != cycle_repetition_threshold
                    or resumed_case["liveness"]["tail_limit"] != liveness_tail_length
                ):
                    raise ValueError("Production evaluation resumed liveness config differs")
                if resumed_case["status"] == "completed" and (
                    resumed_case["fallback"]["repetition_threshold"] != no_op_fallback_threshold
                    or resumed_case["fallback"]["event_limit"] != liveness_tail_length
                ):
                    raise ValueError("Production evaluation resumed fallback config differs")
                cases.append(resumed_case)
                if confirmation is not None:
                    _validate_fresh_case(resumed_case, confirmation)
            else:
                pending.append((seed, policy_kind, policy, model_id, case_path))

    new_transitions = 0
    new_runs = 0
    if confirmation is not None:
        # Serial process CPU measures this run alone, including native simulator CPU.
        for seed, policy_kind, policy, model_id, case_path in pending:
            case = _evaluate_case(
                environment_factory=environment_factory,
                ruleset=ruleset,
                seed=seed,
                policy_kind=policy_kind,
                policy=policy,
                model_id=model_id,
                maximum_decisions=maximum_decisions_per_run,
                partition=partition,
                cycle_repetition_threshold=cycle_repetition_threshold,
                liveness_tail_length=liveness_tail_length,
                no_op_fallback_threshold=no_op_fallback_threshold,
                schema_version=case_schema_version,
                confirmation=confirmation,
            )
            _validate_fresh_case(case, confirmation)
            _publish_json(case_path, case)
            cases.append(case)
            new_runs += 1
            new_transitions += case["activity"]["completed_transitions"]
            if record_activity is not None:
                record_activity(new_runs, new_transitions)
            if progress is not None:
                progress(len(cases), len(canonical_seeds) * 2)
    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(pending)))) as executor:
        future_to_task: dict[Future[dict[str, Any]], tuple[int, str, Policy, str | None, Path]] = {}
        for task in () if confirmation is not None else pending:
            seed, policy_kind, policy, model_id, _ = task
            future = executor.submit(
                _evaluate_case,
                environment_factory=environment_factory,
                ruleset=ruleset,
                seed=seed,
                policy_kind=policy_kind,
                policy=policy,
                model_id=model_id,
                maximum_decisions=maximum_decisions_per_run,
                partition=partition,
                cycle_repetition_threshold=cycle_repetition_threshold,
                liveness_tail_length=liveness_tail_length,
                no_op_fallback_threshold=no_op_fallback_threshold,
                schema_version=case_schema_version,
            )
            future_to_task[future] = task
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            case = future.result()
            write_model_artifact(case, task[-1], label="production policy evaluation case")
            cases.append(case)

    ordered_cases = sorted(
        cases,
        key=lambda case: (int(case["seed"]), str(case["policy_kind"])),
    )
    expected_cases = len(canonical_seeds) * len(policies)
    if len(ordered_cases) != expected_cases:
        raise RuntimeError("Production evaluation did not produce every paired case")
    learned_cases = [case for case in ordered_cases if case["policy_kind"] == LEARNED_POLICY_KIND]
    comparison_kind = REFERENCE_POLICY_KIND if reference_comparison else BASELINE_POLICY_KIND
    comparison_cases = [case for case in ordered_cases if case["policy_kind"] == comparison_kind]
    body: dict[str, Any] = {
        "schema_version": evaluation_schema_version,
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "model_id": learned_policy.model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": partition.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "configuration": {
            "seeds": list(canonical_seeds),
            "workers": workers,
            "maximum_decisions_per_run": maximum_decisions_per_run,
            "cycle_repetition_threshold": cycle_repetition_threshold,
            "liveness_tail_length": liveness_tail_length,
            "no_op_fallback_controller_id": PublicNoOpActionGuard.controller_id,
            "no_op_fallback_threshold": no_op_fallback_threshold,
            "paired_policies": [policy.policy_id for _, policy, _ in policies],
        },
        "cases": [
            {
                "seed": case["seed"],
                "policy_kind": case["policy_kind"],
                "path": str(
                    _case_path(
                        output_directory, int(case["seed"]), str(case["policy_kind"])
                    ).relative_to(output_directory)
                ),
                "case_id": case["case_id"],
            }
            for case in ordered_cases
        ],
        "claim_scope": CLAIM if confirmation is not None else _claim_scope(partition),
    }
    if reference_policy is None:
        body["summary"] = {
            "learned": _policy_summary(learned_cases, include_liveness=True, include_fallback=True),
            "baseline": _policy_summary(
                comparison_cases, include_liveness=True, include_fallback=True
            ),
            "paired": _paired_summary(learned_cases, comparison_cases),
        }
    else:
        body["reference_model_id"] = reference_policy.model_id
        body["reference_training_report_id"] = reference_training_report_id
        body["summary"] = {
            "candidate": _policy_summary(
                learned_cases, include_liveness=True, include_fallback=True
            ),
            "reference": _policy_summary(
                comparison_cases, include_liveness=True, include_fallback=True
            ),
            "paired": _reference_paired_summary(learned_cases, comparison_cases),
        }
    if confirmation is not None:
        body["confirmation_config"] = confirmation.document
        body["objective"] = confirmation.document["objective"]
        body["claim_scope"] = CLAIM
        body["summary"] = _fresh_summary(learned_cases, comparison_cases)
        body["decision"] = {
            "checkpoint_promoted": False,
            "foundation_ready": False,
            "adaptive_controller_allowed": False,
            "next_step": "owner_result_review_before_any_follow_up",
        }
    report = {**body, "report_id": manifest_identifier(body)}
    if confirmation is not None:
        _publish_json(report_path, report)
    else:
        write_model_artifact(report, report_path, label="production policy evaluation")
    successful = all(case["status"] == "completed" for case in ordered_cases)
    return ProductionPolicyEvaluationResult(
        successful, report_path, report, len(pending), new_transitions
    )


def load_production_policy_evaluation(
    path: Path,
    *,
    model_id: str,
    training_report_id: str,
    split_manifest: SplitManifest,
    reference_model_id: str | None = None,
    reference_training_report_id: str | None = None,
) -> dict[str, Any]:
    report = _load_object(path, "production policy evaluation")
    report_id = report.get("report_id")
    body = {key: item for key, item in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Production policy evaluation identity mismatch")
    schema_version = report.get("schema_version")
    if schema_version == LEGACY_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION:
        partition = SplitName.TEST
        case_schema_version = LEGACY_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
        include_liveness = False
        include_fallback = False
        include_reference = False
    elif schema_version in (
        LIVENESS_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        REFERENCE_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
    ):
        raw_partition = report.get("partition")
        if not isinstance(raw_partition, str):
            raise ValueError("Production policy evaluation partition differs")
        try:
            partition = SplitName(raw_partition)
        except (TypeError, ValueError) as error:
            raise ValueError("Production policy evaluation partition differs") from error
        if partition not in (SplitName.VALIDATION, SplitName.TEST) and not (
            schema_version == FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION
            and partition is SplitName.TRAIN
        ):
            raise ValueError("Production policy evaluation partition differs")
        include_liveness = True
        include_fallback = schema_version in (
            PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
            REFERENCE_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
            FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        )
        include_reference = schema_version in (
            REFERENCE_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
            FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        )
        case_schema_version = (
            REFERENCE_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
            if include_reference
            else PRODUCTION_POLICY_CASE_SCHEMA_VERSION
            if include_fallback
            else LIVENESS_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
        )
        if schema_version == FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION:
            case_schema_version = FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
    else:
        raise ValueError("Production policy evaluation schema differs")
    expected_fields = {
        "model_id": model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": partition.value,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "claim_scope": (
            "paired_frozen_test_policy_only_evaluation"
            if not include_liveness
            else CLAIM
            if schema_version == FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION
            else _claim_scope(partition)
        ),
    }
    if any(report.get(key) != value for key, value in expected_fields.items()):
        raise ValueError("Production policy evaluation provenance differs")
    if include_reference:
        if reference_model_id is None or reference_training_report_id is None:
            raise ValueError("Production reference evaluation identities are required")
        if (
            report.get("reference_model_id") != reference_model_id
            or report.get("reference_training_report_id") != reference_training_report_id
        ):
            raise ValueError("Production reference evaluation provenance differs")
    elif reference_model_id is not None or reference_training_report_id is not None:
        raise ValueError("Production evaluation does not contain a reference checkpoint")
    configuration = report.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("Production policy evaluation configuration is missing")
    raw_seeds = configuration.get("seeds")
    if not isinstance(raw_seeds, list):
        raise ValueError("Production policy evaluation seeds are missing")
    seeds = tuple(_integer(seed, "configuration.seeds[]") for seed in raw_seeds)
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Production policy evaluation seeds are invalid")
    if any(split_manifest.split_for_seed(seed) is not partition for seed in seeds):
        raise ValueError(f"Production policy evaluation contains a non-{partition.value} seed")
    learned_policy_id = f"production-checkpoint-policy-v1:{model_id}"
    baseline_policy_id = ProgressBootstrapPolicy.policy_id
    comparison_policy_id = (
        f"production-checkpoint-policy-v1:{reference_model_id}"
        if include_reference
        else baseline_policy_id
    )
    if configuration.get("paired_policies") != [learned_policy_id, comparison_policy_id]:
        raise ValueError("Production policy evaluation policies differ")
    maximum_decisions = _integer(
        configuration.get("maximum_decisions_per_run"),
        "configuration.maximum_decisions_per_run",
    )
    if maximum_decisions <= 0:
        raise ValueError("Production policy evaluation decision limit must be positive")
    cycle_repetition_threshold: int | None = None
    liveness_tail_length: int | None = None
    no_op_fallback_threshold: int | None = None
    if include_liveness:
        cycle_repetition_threshold = _integer(
            configuration.get("cycle_repetition_threshold"),
            "configuration.cycle_repetition_threshold",
        )
        liveness_tail_length = _integer(
            configuration.get("liveness_tail_length"),
            "configuration.liveness_tail_length",
        )
        if cycle_repetition_threshold < 2 or liveness_tail_length <= 0:
            raise ValueError("Production policy evaluation liveness configuration differs")
    if include_fallback:
        if configuration.get("no_op_fallback_controller_id") != PublicNoOpActionGuard.controller_id:
            raise ValueError("Production policy evaluation fallback controller differs")
        no_op_fallback_threshold = _integer(
            configuration.get("no_op_fallback_threshold"),
            "configuration.no_op_fallback_threshold",
        )
        if no_op_fallback_threshold <= 0:
            raise ValueError("Production policy evaluation fallback threshold differs")
    confirmation = None
    if schema_version == FRESH_PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION:
        confirmation = CombatConfirmationConfig.from_mapping(report.get("confirmation_config"))
        confirmation.validate_evaluation(
            model_id=model_id,
            report_id=training_report_id,
            reference_model_id=reference_model_id,
            reference_report_id=reference_training_report_id,
            split=split_manifest,
            ruleset_manifest_id=split_manifest.ruleset_manifest_id,
            patch_id=str(report["patch_id"]),
            seeds=seeds,
            workers=_integer(configuration.get("workers"), "workers"),
            maximum_decisions=maximum_decisions,
            cycle_threshold=cycle_repetition_threshold or 0,
            tail_length=liveness_tail_length or 0,
            fallback_threshold=no_op_fallback_threshold or 0,
        )
        if report.get("objective") != confirmation.document["objective"]:
            raise ValueError("Fresh evaluation objective differs")
        if (
            _load_object(path.parent / "confirmation-plan.json", "confirmation plan")
            != confirmation.document
        ):
            raise ValueError("Fresh evaluation saved plan differs")
        if report.get("decision") != {
            "checkpoint_promoted": False,
            "foundation_ready": False,
            "adaptive_controller_allowed": False,
            "next_step": "owner_result_review_before_any_follow_up",
        }:
            raise ValueError("Fresh evaluation cannot automatically promote a model")
    raw_references = report.get("cases")
    if not isinstance(raw_references, list):
        raise ValueError("Production policy evaluation cases are missing")
    root = path.parent.resolve()
    cases: list[dict[str, Any]] = []
    coordinates: set[tuple[int, str]] = set()
    for raw_reference in raw_references:
        if not isinstance(raw_reference, dict):
            raise ValueError("Production policy evaluation case reference must be an object")
        seed = _integer(raw_reference.get("seed"), "cases[].seed")
        policy_kind = _string(raw_reference.get("policy_kind"), "cases[].policy_kind")
        coordinate = (seed, policy_kind)
        if coordinate in coordinates:
            raise ValueError("Production policy evaluation repeats a case")
        coordinates.add(coordinate)
        relative_path = Path(_string(raw_reference.get("path"), "cases[].path"))
        case_path = (root / relative_path).resolve()
        if root not in case_path.parents:
            raise ValueError("Production policy evaluation case escapes its root")
        if policy_kind == LEARNED_POLICY_KIND:
            policy_id, case_model_id = learned_policy_id, model_id
        elif policy_kind == REFERENCE_POLICY_KIND and include_reference:
            policy_id = comparison_policy_id
            case_model_id = _string(reference_model_id, "reference model ID")
        elif policy_kind == BASELINE_POLICY_KIND:
            policy_id, case_model_id = baseline_policy_id, None
        else:
            raise ValueError("Production policy evaluation policy kind differs")
        case = _load_case(
            case_path,
            seed=seed,
            policy_kind=policy_kind,
            policy_id=policy_id,
            model_id=case_model_id,
            ruleset_manifest_id=split_manifest.ruleset_manifest_id,
            partition=partition,
            schema_version=case_schema_version,
        )
        if raw_reference.get("case_id") != case["case_id"]:
            raise ValueError("Production policy evaluation case reference identity mismatch")
        if case["status"] == "completed" and int(case["decisions"]) > maximum_decisions:
            raise ValueError("Production policy evaluation case exceeded its decision limit")
        if include_liveness and case["status"] == "completed":
            liveness = case["liveness"]
            if (
                liveness["repetition_threshold"] != cycle_repetition_threshold
                or liveness["tail_limit"] != liveness_tail_length
            ):
                raise ValueError("Production policy evaluation case liveness config differs")
        if include_fallback and case["status"] == "completed":
            fallback = case["fallback"]
            if (
                fallback["controller_id"] != PublicNoOpActionGuard.controller_id
                or fallback["repetition_threshold"] != no_op_fallback_threshold
                or fallback["event_limit"] != liveness_tail_length
            ):
                raise ValueError("Production policy evaluation case fallback config differs")
        cases.append(case)
        if confirmation is not None:
            _validate_fresh_case(case, confirmation)
    expected_coordinates = {
        (seed, policy_kind)
        for seed in seeds
        for policy_kind in (
            LEARNED_POLICY_KIND,
            REFERENCE_POLICY_KIND if include_reference else BASELINE_POLICY_KIND,
        )
    }
    if coordinates != expected_coordinates:
        raise ValueError("Production policy evaluation paired case coverage differs")
    learned_cases = [case for case in cases if case["policy_kind"] == LEARNED_POLICY_KIND]
    comparison_kind = REFERENCE_POLICY_KIND if include_reference else BASELINE_POLICY_KIND
    comparison_cases = [case for case in cases if case["policy_kind"] == comparison_kind]
    if include_reference:
        expected_summary = {
            "candidate": _policy_summary(
                learned_cases,
                include_liveness=include_liveness,
                include_fallback=include_fallback,
            ),
            "reference": _policy_summary(
                comparison_cases,
                include_liveness=include_liveness,
                include_fallback=include_fallback,
            ),
            "paired": _reference_paired_summary(learned_cases, comparison_cases),
        }
    else:
        expected_summary = {
            "learned": _policy_summary(
                learned_cases,
                include_liveness=include_liveness,
                include_fallback=include_fallback,
            ),
            "baseline": _policy_summary(
                comparison_cases,
                include_liveness=include_liveness,
                include_fallback=include_fallback,
            ),
            "paired": _paired_summary(learned_cases, comparison_cases),
        }
    if confirmation is not None:
        expected_summary = _fresh_summary(learned_cases, comparison_cases)
    if report.get("summary") != expected_summary:
        raise ValueError("Production policy evaluation summary differs from its cases")
    return report


def _evaluate_case(
    *,
    environment_factory: Callable[[], EnvironmentAdapter],
    ruleset: RulesetIdentity,
    seed: int,
    policy_kind: str,
    policy: Policy,
    model_id: str | None,
    maximum_decisions: int,
    partition: SplitName,
    cycle_repetition_threshold: int,
    liveness_tail_length: int,
    no_op_fallback_threshold: int,
    schema_version: str = PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
    confirmation: CombatConfirmationConfig | None = None,
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    setup_cpu = time.process_time() if confirmation else 0.0
    setup_wall = time.perf_counter() if confirmation else 0.0
    run_cpu: float | None = None
    run_wall: float | None = None
    initialization_cpu = initialization_wall = run_cpu_used = run_wall_used = 0.0
    attempted = completed_transitions = 0
    completed_inference_seconds: list[float] = []
    budget_exhausted = False
    observed_terminal = observed_victory = False
    observed_act_floors: dict[str, int] = {}

    def out_of_budget() -> bool:
        return (
            confirmation is not None
            and run_cpu is not None
            and time.process_time() - run_cpu
            >= confirmation.document["objective"]["whole_run_budget"]
        )

    def observe_public_progress(obs: Any) -> None:
        act = obs.public_state.get("act")
        if isinstance(act, (str, int)) and not isinstance(act, bool):
            key = str(act)
            observed_act_floors[key] = max(
                observed_act_floors.get(key, 0), _public_integer(obs.public_state.get("floor")) or 0
            )

    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Evaluation environment ruleset changed")
        observation = environment.reset(seed)
        if confirmation is not None:
            run_cpu = time.process_time()
            run_wall = time.perf_counter()
            initialization_cpu = run_cpu - setup_cpu
            initialization_wall = run_wall - setup_wall
            observe_public_progress(observation)
        maximum_floor = _public_integer(observation.public_state.get("floor")) or 0
        maximum_act = _public_integer(observation.public_state.get("act")) or 0
        decisions = 0
        decision_seconds: list[float] = []
        action_ids: list[str] = []
        no_op_guard = PublicNoOpActionGuard(
            repetition_threshold=no_op_fallback_threshold,
            event_limit=liveness_tail_length,
        )
        trace_tail: list[dict[str, Any]] = []
        state_action_counts: dict[tuple[str, str], int] = {}
        transition_occurrences: dict[tuple[str, str, str], list[int]] = {}
        unchanged_transition_counts: dict[tuple[str, str, str], int] = {}
        maximum_state_action_repetitions = 0
        maximum_public_transition_repetitions = 0
        detected_transition: tuple[str, str, str] | None = None
        detected_occurrences: list[int] = []
        detected_decision_type: str | None = None
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        while not terminal and decisions < maximum_decisions:
            if out_of_budget():
                break
            legal_actions = tuple(environment.legal_actions())
            if not legal_actions:
                raise RuntimeError("Nonterminal evaluation state has no legal actions")
            actions = no_op_guard.eligible_actions(observation, legal_actions)
            started = time.perf_counter()
            attempted += 1
            if isinstance(policy, ProductionCheckpointPolicy):
                decision = policy.predict(observation, actions)
                action = decision.selected_action
                elapsed = decision.inference_seconds
            else:
                action = policy.choose_action(observation, actions)
                elapsed = time.perf_counter() - started
            if confirmation is not None:
                completed_inference_seconds.append(elapsed)
            if out_of_budget():
                break
            if action not in actions or action not in legal_actions:
                raise RuntimeError("Evaluation policy selected an illegal action")
            decision_seconds.append(elapsed)
            action_ids.append(action.action_id)
            source_state_hash = observation.state_hash
            decision_type = observation.decision_type.value
            source_observation = observation
            transition = environment.step(action)
            observation = transition.next_observation
            completed_transitions += 1
            if confirmation is not None:
                observe_public_progress(observation)
            no_op_guard.observe_transition(
                observation=source_observation,
                action=action,
                next_observation=observation,
                decision_index=decisions,
            )
            next_state_hash = observation.state_hash
            trace_tail.append(
                {
                    "decision_index": decisions,
                    "state_hash": source_state_hash,
                    "decision_type": decision_type,
                    "action_id": action.action_id,
                    "next_state_hash": next_state_hash,
                    "public_state_changed": source_state_hash != next_state_hash,
                }
            )
            if len(trace_tail) > liveness_tail_length:
                del trace_tail[0]
            state_action = (source_state_hash, action.action_id)
            state_action_counts[state_action] = state_action_counts.get(state_action, 0) + 1
            maximum_state_action_repetitions = max(
                maximum_state_action_repetitions, state_action_counts[state_action]
            )
            public_transition = (source_state_hash, action.action_id, next_state_hash)
            occurrences = transition_occurrences.setdefault(public_transition, [])
            occurrences.append(decisions)
            if source_state_hash == next_state_hash:
                unchanged_transition_counts[public_transition] = (
                    unchanged_transition_counts.get(public_transition, 0) + 1
                )
            maximum_public_transition_repetitions = max(
                maximum_public_transition_repetitions, len(occurrences)
            )
            decisions += 1
            maximum_floor = max(
                maximum_floor,
                _public_integer(observation.public_state.get("floor")) or 0,
            )
            maximum_act = max(
                maximum_act,
                _public_integer(observation.public_state.get("act")) or 0,
            )
            terminal = transition.terminal
            victory = transition.victory
            if out_of_budget():
                break
            if not terminal and len(occurrences) >= cycle_repetition_threshold:
                detected_transition = public_transition
                detected_occurrences = list(occurrences)
                detected_decision_type = decision_type
                break
        if confirmation is not None:
            observed_terminal, observed_victory = terminal, victory if terminal else False
            budget_exhausted = out_of_budget()
            if budget_exhausted:
                terminal = victory = False
                detected_transition = None
        if budget_exhausted:
            termination_reason = "cpu_budget"
        elif terminal:
            termination_reason = "terminal"
        elif detected_transition is not None:
            termination_reason = "policy_cycle"
        else:
            termination_reason = "decision_limit"
        body: dict[str, Any] = {
            "schema_version": schema_version,
            "seed": seed,
            "partition": partition.value,
            "policy_kind": policy_kind,
            "policy_id": policy.policy_id,
            "model_id": model_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "completed",
            "error": None,
            "decisions": decisions,
            "terminal": terminal,
            "victory": victory if terminal else False,
            "truncated": not terminal,
            "termination_reason": termination_reason,
            "liveness": _liveness_diagnostic(
                detected_transition=detected_transition,
                detected_occurrences=detected_occurrences,
                detected_decision_type=detected_decision_type,
                unchanged_transition_counts=unchanged_transition_counts,
                maximum_state_action_repetitions=maximum_state_action_repetitions,
                maximum_public_transition_repetitions=maximum_public_transition_repetitions,
                cycle_repetition_threshold=cycle_repetition_threshold,
                liveness_tail_length=liveness_tail_length,
                trace_tail=trace_tail,
            ),
            "fallback": no_op_guard.as_dict(),
            "maximum_floor": maximum_floor,
            "maximum_act": maximum_act,
            "final_state_hash": observation.state_hash,
            "action_trace_sha256": "sha256:"
            + hashlib.sha256("\n".join(action_ids).encode()).hexdigest(),
            "total_decision_seconds": _artifact_float(sum(decision_seconds)),
            "median_decision_seconds": _artifact_float(_median(decision_seconds)),
            "maximum_decision_seconds": _artifact_float(max(decision_seconds, default=0.0)),
        }
    except Exception as error:
        body = {
            "schema_version": schema_version,
            "seed": seed,
            "partition": partition.value,
            "policy_kind": policy_kind,
            "policy_id": policy.policy_id,
            "model_id": model_id,
            "ruleset_manifest_id": ruleset.manifest_id,
            "status": "failed",
            "error": f"{type(error).__name__}: {error}",
            "decisions": None,
            "terminal": None,
            "victory": None,
            "truncated": None,
            "termination_reason": None,
            "liveness": None,
            "fallback": None,
            "maximum_floor": None,
            "maximum_act": None,
            "final_state_hash": None,
            "action_trace_sha256": None,
            "total_decision_seconds": None,
            "median_decision_seconds": None,
            "maximum_decision_seconds": None,
        }
    finally:
        if confirmation is not None:
            end_cpu, end_wall = time.process_time(), time.perf_counter()
            if run_cpu is not None and run_wall is not None:
                run_cpu_used, run_wall_used = end_cpu - run_cpu, end_wall - run_wall
            else:
                initialization_cpu, initialization_wall = end_cpu - setup_cpu, end_wall - setup_wall
        cleanup_cpu = time.process_time() if confirmation else 0.0
        cleanup_wall = time.perf_counter() if confirmation else 0.0
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as error:
                    if confirmation is None:
                        raise
                    body["status"] = "failed"
                    body["error"] = f"Cleanup {type(error).__name__}: {error}"
                    for key in set(body) - {
                        "schema_version",
                        "seed",
                        "partition",
                        "policy_kind",
                        "policy_id",
                        "model_id",
                        "ruleset_manifest_id",
                        "status",
                        "error",
                    }:
                        body[key] = None
    cleanup_cpu_used = time.process_time() - cleanup_cpu if confirmation else 0.0
    cleanup_wall_used = time.perf_counter() - cleanup_wall if confirmation else 0.0
    if confirmation is not None:
        cap = confirmation.document["objective"]["whole_run_budget"]
        budget_exhausted = run_cpu_used >= cap
        # A terminal result crossing the cooperative cap is never counted as a budgeted win.
        if body["status"] == "completed" and run_cpu_used >= cap:
            budget_exhausted = True
            body.update(
                terminal=False, victory=False, truncated=True, termination_reason="cpu_budget"
            )
            body["liveness"]["cycle_detected"] = False
            if detected_transition is not None:
                body["liveness"] = _liveness_diagnostic(
                    detected_transition=None,
                    detected_occurrences=[],
                    detected_decision_type=None,
                    unchanged_transition_counts=unchanged_transition_counts,
                    maximum_state_action_repetitions=maximum_state_action_repetitions,
                    maximum_public_transition_repetitions=maximum_public_transition_repetitions,
                    cycle_repetition_threshold=cycle_repetition_threshold,
                    liveness_tail_length=liveness_tail_length,
                    trace_tail=trace_tail,
                )
        milestone = Act1Milestones.from_mapping(confirmation.document["milestones"])
        body.update(
            confirmation_config_id=confirmation.document["config_id"],
            compute={
                "cpu_budget_seconds": cap,
                "run_cpu_seconds": _artifact_float(run_cpu_used),
                "run_wall_seconds": _artifact_float(run_wall_used),
                "initialization_cpu_seconds": _artifact_float(initialization_cpu),
                "initialization_wall_seconds": _artifact_float(initialization_wall),
                "cleanup_cpu_seconds": _artifact_float(cleanup_cpu_used),
                "cleanup_wall_seconds": _artifact_float(cleanup_wall_used),
                "budget_exhausted": budget_exhausted,
                "observed_terminal": observed_terminal,
                "observed_victory": observed_victory,
            },
            activity={
                "attempted_decisions": attempted,
                "completed_transitions": completed_transitions,
                "p95_completed_inference_seconds": _artifact_float(
                    sorted(completed_inference_seconds)[
                        max(0, math.ceil(0.95 * len(completed_inference_seconds)) - 1)
                    ]
                )
                if completed_inference_seconds
                else 0.0,
            },
            public_progress={
                "maximum_floor_by_act": observed_act_floors,
                "act1_boss_reached": any(
                    observed_act_floors.get(act, 0) >= milestone.boss_floor
                    for act in milestone.first_act_ids
                ),
                "act1_cleared": milestone.next_act_id in observed_act_floors,
            },
            failure_kind=(
                "unsupported_public_combat"
                if body["status"] == "failed"
                and "combat" in str(body["error"]).lower()
                and any(s in str(body["error"]).lower() for s in ("unsupported", "not supported"))
                else "runtime_error"
                if body["status"] == "failed"
                else None
            ),
        )
    return {**body, "case_id": manifest_identifier(body)}


def _liveness_diagnostic(
    *,
    detected_transition: tuple[str, str, str] | None,
    detected_occurrences: Sequence[int],
    detected_decision_type: str | None,
    unchanged_transition_counts: dict[tuple[str, str, str], int],
    maximum_state_action_repetitions: int,
    maximum_public_transition_repetitions: int,
    cycle_repetition_threshold: int,
    liveness_tail_length: int,
    trace_tail: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    cycle_detected = detected_transition is not None
    source_hash, action_id, next_hash = (
        detected_transition if detected_transition is not None else (None, None, None)
    )
    return {
        "schema_version": POLICY_LIVENESS_SCHEMA_VERSION,
        "cycle_detected": cycle_detected,
        "classification": (
            "unchanged_public_state_action"
            if cycle_detected and source_hash == next_hash
            else "repeated_public_transition"
            if cycle_detected
            else None
        ),
        "repetition_threshold": cycle_repetition_threshold,
        "tail_limit": liveness_tail_length,
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
            unchanged_transition_counts.get(detected_transition, 0)
            if detected_transition is not None
            else None
        ),
        "tail": list(trace_tail),
    }


def _policy_summary(
    cases: Sequence[dict[str, Any]],
    *,
    include_liveness: bool = False,
    include_fallback: bool = False,
) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    terminal = [case for case in completed if case["terminal"] is True]
    victories = sum(case["victory"] is True for case in terminal)
    denominator = len(cases)
    decision_latencies = [float(case["total_decision_seconds"]) for case in completed]
    decisions = sum(int(case["decisions"]) for case in completed)
    summary: dict[str, Any] = {
        "benchmark_denominator": denominator,
        "completed_runs": len(completed),
        "failed_runs": denominator - len(completed),
        "terminal_runs": len(terminal),
        "truncated_runs": len(completed) - len(terminal),
        "victories": victories,
        "victory_rate": _artifact_float(victories / denominator),
        "completion_rate": _artifact_float(len(completed) / denominator),
        "terminal_rate": _artifact_float(len(terminal) / denominator),
        "mean_maximum_floor": _artifact_float(
            sum(int(case["maximum_floor"]) for case in completed) / max(1, len(completed))
        ),
        "decisions": decisions,
        "total_decision_seconds": _artifact_float(sum(decision_latencies)),
        "mean_seconds_per_decision": _artifact_float(sum(decision_latencies) / max(1, decisions)),
        "nondegenerate_terminal_outcomes": 0 < victories < len(terminal),
    }
    if include_liveness:
        policy_cycles = sum(case.get("termination_reason") == "policy_cycle" for case in completed)
        decision_limits = sum(
            case.get("termination_reason") == "decision_limit" for case in completed
        )
        summary.update(
            {
                "policy_cycle_runs": policy_cycles,
                "decision_limit_runs": decision_limits,
                "liveness_pass": policy_cycles == 0 and decision_limits == 0,
            }
        )
    if include_fallback:
        fallback_cases = [case["fallback"] for case in completed]
        fallback_invocations = sum(int(fallback["invocations"]) for fallback in fallback_cases)
        summary.update(
            {
                "fallback_runs": sum(
                    int(fallback["invocations"]) > 0 for fallback in fallback_cases
                ),
                "fallback_invocations": fallback_invocations,
                "suppressed_no_op_actions": sum(
                    int(fallback["suppressed_actions"]) for fallback in fallback_cases
                ),
                "fallback_exhausted_states": sum(
                    int(fallback["exhausted_states"]) for fallback in fallback_cases
                ),
            }
        )
    return summary


def _paired_summary(
    learned_cases: Sequence[dict[str, Any]], baseline_cases: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    learned_by_seed = {int(case["seed"]): case for case in learned_cases}
    baseline_by_seed = {int(case["seed"]): case for case in baseline_cases}
    paired = [
        (learned_by_seed[seed], baseline_by_seed[seed])
        for seed in sorted(learned_by_seed.keys() & baseline_by_seed.keys())
        if learned_by_seed[seed]["status"] == "completed"
        and baseline_by_seed[seed]["status"] == "completed"
    ]
    return {
        "completed_pairs": len(paired),
        "learned_only_victories": sum(
            learned["victory"] is True and baseline["victory"] is not True
            for learned, baseline in paired
        ),
        "baseline_only_victories": sum(
            baseline["victory"] is True and learned["victory"] is not True
            for learned, baseline in paired
        ),
        "mean_maximum_floor_difference": _artifact_float(
            sum(
                int(learned["maximum_floor"]) - int(baseline["maximum_floor"])
                for learned, baseline in paired
            )
            / max(1, len(paired))
        ),
    }


def _reference_paired_summary(
    candidate_cases: Sequence[dict[str, Any]], reference_cases: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    legacy = _paired_summary(candidate_cases, reference_cases)
    return {
        "completed_pairs": legacy["completed_pairs"],
        "candidate_only_victories": legacy["learned_only_victories"],
        "reference_only_victories": legacy["baseline_only_victories"],
        "mean_maximum_floor_difference": legacy["mean_maximum_floor_difference"],
    }


def _case_path(output_directory: Path, seed: int, policy_kind: str) -> Path:
    return output_directory / "cases" / f"seed-{seed:06d}-{policy_kind}.json"


def _validate_fresh_case(case: dict[str, Any], config: CombatConfirmationConfig) -> None:
    _validate_case(case)
    if case.get("confirmation_config_id") != config.document["config_id"]:
        raise ValueError("Fresh evaluation case confirmation identity differs")
    compute = case.get("compute")
    if not isinstance(compute, dict) or set(compute) != {
        "cpu_budget_seconds",
        "run_cpu_seconds",
        "run_wall_seconds",
        "initialization_cpu_seconds",
        "initialization_wall_seconds",
        "cleanup_cpu_seconds",
        "cleanup_wall_seconds",
        "budget_exhausted",
        "observed_terminal",
        "observed_victory",
    }:
        raise ValueError("Fresh evaluation compute accounting is missing")
    cap = config.document["objective"]["whole_run_budget"]
    if compute["cpu_budget_seconds"] != cap:
        raise ValueError("Fresh case whole-run budget differs")
    for key, value in compute.items():
        if key.endswith("seconds") and (
            not isinstance(value, (float, int))
            or isinstance(value, bool)
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("Fresh case timing must be finite and non-negative")
    for key in ("budget_exhausted", "observed_terminal", "observed_victory"):
        if type(compute[key]) is not bool:
            raise ValueError("Fresh case compute outcomes must be boolean")
    exhausted = compute["budget_exhausted"]
    if not math.isclose(compute["run_cpu_seconds"], cap, abs_tol=1e-9) and exhausted is not (
        compute["run_cpu_seconds"] >= cap
    ):
        raise ValueError("Fresh case budget outcome differs from measured CPU")
    if compute["observed_victory"] and not compute["observed_terminal"]:
        raise ValueError("Fresh case observed victory is nonterminal")
    if case["status"] == "completed":
        if exhausted and (
            case["termination_reason"] != "cpu_budget"
            or case["victory"]
            or case["terminal"]
            or not case["truncated"]
        ):
            raise ValueError("Over-budget result cannot count as a victory")
        if not exhausted and (
            case["termination_reason"] == "cpu_budget"
            or case["terminal"] != compute["observed_terminal"]
            or case["victory"] != compute["observed_victory"]
        ):
            raise ValueError("Fresh case public outcomes differ")
    activity = case.get("activity")
    if not isinstance(activity, dict) or set(activity) != {
        "attempted_decisions",
        "completed_transitions",
        "p95_completed_inference_seconds",
    }:
        raise ValueError("Fresh case partial-work accounting is missing")
    attempted = _integer(activity["attempted_decisions"], "attempted decisions")
    completed = _integer(activity["completed_transitions"], "completed transitions")
    if not 0 <= completed <= attempted <= config.document["maximum_decisions_per_run"]:
        raise ValueError("Fresh case partial-work counts differ")
    if case["status"] == "completed" and completed != case["decisions"]:
        raise ValueError("Fresh case transitions differ from completed decisions")
    latency = activity["p95_completed_inference_seconds"]
    if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
        raise ValueError("Fresh case inference latency differs")
    progress = case.get("public_progress")
    if not isinstance(progress, dict) or set(progress) != {
        "maximum_floor_by_act",
        "act1_boss_reached",
        "act1_cleared",
    }:
        raise ValueError("Fresh case public milestones are missing")
    floors = progress["maximum_floor_by_act"]
    if not isinstance(floors, dict) or any(
        not isinstance(k, str) or type(v) is not int or v < 0 for k, v in floors.items()
    ):
        raise ValueError("Fresh case public floor inventory differs")
    milestones = Act1Milestones.from_mapping(config.document["milestones"])
    if progress["act1_boss_reached"] is not any(
        floors.get(a, 0) >= milestones.boss_floor for a in milestones.first_act_ids
    ) or progress["act1_cleared"] is not (milestones.next_act_id in floors):
        raise ValueError("Fresh case milestone flags differ from public acts/floors")
    if (
        case["status"] == "completed"
        and case.get("failure_kind") is not None
        or case["status"] == "failed"
        and case.get("failure_kind") not in ("unsupported_public_combat", "runtime_error")
    ):
        raise ValueError("Fresh case failure classification differs")


def _fresh_summary(
    candidate: Sequence[dict[str, Any]], reference: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    def arm(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
        result = _policy_summary(cases, include_liveness=True, include_fallback=True)
        n, wins = len(cases), result["victories"]
        z = 1.959963984540054
        center = (wins / n + z * z / (2 * n)) / (1 + z * z / n)
        half = (
            z * math.sqrt((wins / n) * (1 - wins / n) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        )
        result.update(
            victory_rate_interval_95=[
                _artifact_float(max(0.0, center - half)),
                _artifact_float(min(1.0, center + half)),
            ],
            interval_method="wilson_score_approximate_seed_sampling",
            cpu_budget_runs=sum(c["compute"]["budget_exhausted"] for c in cases),
            unsupported_public_combat_runs=sum(
                c["failure_kind"] == "unsupported_public_combat" for c in cases
            ),
            act1_boss_reaches=sum(c["public_progress"]["act1_boss_reached"] for c in cases),
            act1_clears=sum(c["public_progress"]["act1_cleared"] for c in cases),
            total_run_cpu_seconds=_artifact_float(
                sum(c["compute"]["run_cpu_seconds"] for c in cases)
            ),
            total_initialization_cpu_seconds=_artifact_float(
                sum(c["compute"]["initialization_cpu_seconds"] for c in cases)
            ),
            total_run_wall_seconds=_artifact_float(
                sum(c["compute"]["run_wall_seconds"] for c in cases)
            ),
            attempted_decisions=sum(c["activity"]["attempted_decisions"] for c in cases),
            completed_transitions=sum(c["activity"]["completed_transitions"] for c in cases),
            maximum_case_p95_inference_seconds=max(
                c["activity"]["p95_completed_inference_seconds"] for c in cases
            ),
        )
        return result

    by_reference = {c["seed"]: c for c in reference}
    pairs = [(c, by_reference[c["seed"]]) for c in candidate]
    n = len(pairs)
    candidate_only = sum(c["victory"] is True and r["victory"] is not True for c, r in pairs)
    reference_only = sum(r["victory"] is True and c["victory"] is not True for c, r in pairs)
    difference = (candidate_only - reference_only) / n
    radius = math.sqrt(2 * math.log(2 / 0.05) / n)
    paired = _reference_paired_summary(candidate, reference)
    paired.update(
        benchmark_denominator=n,
        all_seed_candidate_only_victories=candidate_only,
        all_seed_reference_only_victories=reference_only,
        victory_rate_difference=_artifact_float(difference),
        victory_difference_interval_95=[
            _artifact_float(max(-1.0, difference - radius)),
            _artifact_float(min(1.0, difference + radius)),
        ],
        interval_method="bounded_paired_seed_hoeffding_independent_seed_assumption",
        failed_runs_count_as_non_victory=True,
        paired_action_trace_changes=sum(
            c["action_trace_sha256"] != r["action_trace_sha256"]
            for c, r in pairs
            if c["status"] == r["status"] == "completed"
        ),
    )
    return {"candidate": arm(candidate), "reference": arm(reference), "paired": paired}


def _load_case(
    path: Path,
    *,
    seed: int,
    policy_kind: str,
    policy_id: str,
    model_id: str | None,
    ruleset_manifest_id: str,
    partition: SplitName,
    schema_version: str,
) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot resume production evaluation case {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Production evaluation case must be an object")
    case = dict(value)
    case_id = case.get("case_id")
    body = {key: item for key, item in case.items() if key != "case_id"}
    if case_id != manifest_identifier(body):
        raise ValueError("Production evaluation case identity mismatch")
    expected = {
        "schema_version": schema_version,
        "seed": seed,
        "partition": partition.value,
        "policy_kind": policy_kind,
        "policy_id": policy_id,
        "model_id": model_id,
        "ruleset_manifest_id": ruleset_manifest_id,
    }
    if any(case.get(key) != item for key, item in expected.items()):
        raise ValueError("Production evaluation resumed case configuration differs")
    _validate_case(case)
    return case


def _validate_case(case: dict[str, Any]) -> None:
    schema_version = case.get("schema_version")
    if schema_version not in (
        LEGACY_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        LIVENESS_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        REFERENCE_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
    ):
        raise ValueError("Production evaluation case schema differs")
    include_liveness = schema_version in (
        LIVENESS_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        REFERENCE_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
    )
    include_fallback = schema_version in (
        PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        REFERENCE_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
    )
    status = case.get("status")
    result_fields: tuple[str, ...] = (
        "decisions",
        "terminal",
        "victory",
        "truncated",
        "maximum_floor",
        "maximum_act",
        "final_state_hash",
        "action_trace_sha256",
        "total_decision_seconds",
        "median_decision_seconds",
        "maximum_decision_seconds",
    )
    if include_liveness:
        result_fields += ("termination_reason", "liveness")
    if include_fallback:
        result_fields += ("fallback",)
    if status == "failed":
        if not isinstance(case.get("error"), str) or not case["error"]:
            raise ValueError("Failed production evaluation case has no error")
        if any(case.get(field) is not None for field in result_fields):
            raise ValueError("Failed production evaluation case contains result metrics")
        return
    if status != "completed" or case.get("error") is not None:
        raise ValueError("Production evaluation case status differs")
    decisions = _integer(case.get("decisions"), "case.decisions")
    maximum_floor = _integer(case.get("maximum_floor"), "case.maximum_floor")
    maximum_act = _integer(case.get("maximum_act"), "case.maximum_act")
    if min(decisions, maximum_floor, maximum_act) < 0:
        raise ValueError("Production evaluation case counts must be non-negative")
    terminal = case.get("terminal")
    victory = case.get("victory")
    truncated = case.get("truncated")
    if not all(isinstance(value, bool) for value in (terminal, victory, truncated)):
        raise ValueError("Production evaluation case outcomes must be boolean")
    if truncated is terminal or (victory is True and terminal is not True):
        raise ValueError("Production evaluation case terminal outcomes are inconsistent")
    if include_liveness:
        termination_reason = case.get("termination_reason")
        allowed_reasons = (
            ("terminal", "policy_cycle", "decision_limit", "cpu_budget")
            if schema_version == FRESH_PRODUCTION_POLICY_CASE_SCHEMA_VERSION
            else ("terminal", "policy_cycle", "decision_limit")
        )
        if not isinstance(termination_reason, str) or termination_reason not in allowed_reasons:
            raise ValueError("Production evaluation case termination reason differs")
        if terminal and termination_reason != "terminal":
            raise ValueError("Production evaluation case termination reason is inconsistent")
        if not terminal and termination_reason == "terminal":
            raise ValueError("Production evaluation case termination reason is inconsistent")
        liveness = case.get("liveness")
        if not isinstance(liveness, dict):
            raise ValueError("Production evaluation case liveness diagnostic is missing")
        _validate_liveness(liveness, termination_reason=termination_reason, decisions=decisions)
    if include_fallback:
        fallback = case.get("fallback")
        if not isinstance(fallback, dict):
            raise ValueError("Production evaluation fallback diagnostic is missing")
        _validate_fallback(fallback, decisions=decisions)
    for field in ("final_state_hash", "action_trace_sha256"):
        _string(case.get(field), f"case.{field}")
    for field in (
        "total_decision_seconds",
        "median_decision_seconds",
        "maximum_decision_seconds",
    ):
        value = case.get(field)
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
            or float(value) < 0.0
        ):
            raise ValueError(f"Production evaluation case {field} must be finite and non-negative")


def _validate_liveness(
    liveness: dict[str, Any], *, termination_reason: str, decisions: int
) -> None:
    if liveness.get("schema_version") != POLICY_LIVENESS_SCHEMA_VERSION:
        raise ValueError("Production evaluation liveness schema differs")
    cycle_detected = liveness.get("cycle_detected")
    if not isinstance(cycle_detected, bool):
        raise ValueError("Production evaluation cycle flag must be boolean")
    if cycle_detected is not (termination_reason == "policy_cycle"):
        raise ValueError("Production evaluation cycle outcome is inconsistent")
    repetition_threshold = _integer(
        liveness.get("repetition_threshold"), "case.liveness.repetition_threshold"
    )
    tail_limit = _integer(liveness.get("tail_limit"), "case.liveness.tail_limit")
    maximum_pair = _integer(
        liveness.get("maximum_state_action_repetitions"),
        "case.liveness.maximum_state_action_repetitions",
    )
    maximum_transition = _integer(
        liveness.get("maximum_public_transition_repetitions"),
        "case.liveness.maximum_public_transition_repetitions",
    )
    if repetition_threshold < 2 or tail_limit <= 0 or min(maximum_pair, maximum_transition) < 0:
        raise ValueError("Production evaluation liveness counts are invalid")
    tail = liveness.get("tail")
    if not isinstance(tail, list) or len(tail) > tail_limit:
        raise ValueError("Production evaluation liveness tail is invalid")
    previous_index = -1
    for entry in tail:
        if not isinstance(entry, dict):
            raise ValueError("Production evaluation liveness tail entry must be an object")
        index = _integer(entry.get("decision_index"), "case.liveness.tail[].decision_index")
        if index <= previous_index or index >= decisions:
            raise ValueError("Production evaluation liveness tail indices are invalid")
        previous_index = index
        for field in ("state_hash", "decision_type", "action_id", "next_state_hash"):
            _string(entry.get(field), f"case.liveness.tail[].{field}")
        if not isinstance(entry.get("public_state_changed"), bool):
            raise ValueError("Production evaluation liveness state-change flag must be boolean")
    repeated_fields = (
        "classification",
        "repeated_state_hash",
        "repeated_action_id",
        "repeated_next_state_hash",
        "decision_type",
        "first_occurrence_decision",
        "first_repeat_decision",
        "detection_decision",
        "repeated_transition_occurrences",
        "unchanged_transition_occurrences",
    )
    if not cycle_detected:
        if any(liveness.get(field) is not None for field in repeated_fields):
            raise ValueError("Production evaluation non-cycle contains cycle diagnostics")
        return
    if liveness.get("classification") not in (
        "unchanged_public_state_action",
        "repeated_public_transition",
    ):
        raise ValueError("Production evaluation cycle classification differs")
    for field in (
        "repeated_state_hash",
        "repeated_action_id",
        "repeated_next_state_hash",
        "decision_type",
    ):
        _string(liveness.get(field), f"case.liveness.{field}")
    first = _integer(
        liveness.get("first_occurrence_decision"),
        "case.liveness.first_occurrence_decision",
    )
    first_repeat = _integer(
        liveness.get("first_repeat_decision"), "case.liveness.first_repeat_decision"
    )
    detection = _integer(liveness.get("detection_decision"), "case.liveness.detection_decision")
    repeated = _integer(
        liveness.get("repeated_transition_occurrences"),
        "case.liveness.repeated_transition_occurrences",
    )
    unchanged = _integer(
        liveness.get("unchanged_transition_occurrences"),
        "case.liveness.unchanged_transition_occurrences",
    )
    if not (0 <= first < first_repeat <= detection < decisions):
        raise ValueError("Production evaluation cycle locations are invalid")
    if repeated < repetition_threshold or maximum_transition < repeated:
        raise ValueError("Production evaluation cycle repetition count is invalid")
    if unchanged < 0 or unchanged > repeated:
        raise ValueError("Production evaluation unchanged transition count is invalid")


def _validate_fallback(fallback: dict[str, Any], *, decisions: int) -> None:
    if fallback.get("schema_version") != PUBLIC_NO_OP_FALLBACK_SCHEMA_VERSION:
        raise ValueError("Production evaluation fallback schema differs")
    if fallback.get("controller_id") != PublicNoOpActionGuard.controller_id:
        raise ValueError("Production evaluation fallback controller differs")
    repetition_threshold = _integer(
        fallback.get("repetition_threshold"), "case.fallback.repetition_threshold"
    )
    event_limit = _integer(fallback.get("event_limit"), "case.fallback.event_limit")
    invocations = _integer(fallback.get("invocations"), "case.fallback.invocations")
    suppressed_actions = _integer(
        fallback.get("suppressed_actions"), "case.fallback.suppressed_actions"
    )
    exhausted_states = _integer(fallback.get("exhausted_states"), "case.fallback.exhausted_states")
    if repetition_threshold <= 0 or event_limit <= 0:
        raise ValueError("Production evaluation fallback config is invalid")
    if min(invocations, suppressed_actions, exhausted_states) < 0:
        raise ValueError("Production evaluation fallback counts are invalid")
    events = fallback.get("events")
    if not isinstance(events, list) or len(events) > event_limit:
        raise ValueError("Production evaluation fallback events are invalid")
    previous_index = -1
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Production evaluation fallback event must be an object")
        index = _integer(event.get("decision_index"), "case.fallback.events[].decision_index")
        if index <= previous_index or index >= decisions:
            raise ValueError("Production evaluation fallback event indices are invalid")
        previous_index = index
        for field in ("state_hash", "decision_type", "action_id"):
            _string(event.get(field), f"case.fallback.events[].{field}")
        unchanged = _integer(
            event.get("unchanged_occurrences"),
            "case.fallback.events[].unchanged_occurrences",
        )
        if unchanged != repetition_threshold:
            raise ValueError("Production evaluation fallback event threshold differs")
    if suppressed_actions < len(events):
        raise ValueError("Production evaluation fallback event coverage is invalid")


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label.capitalize()} must be an object")
    return dict(value)


def _claim_scope(partition: SplitName) -> str:
    if partition is SplitName.TEST:
        return "paired_frozen_test_policy_only_evaluation"
    if partition is SplitName.VALIDATION:
        return "paired_validation_policy_liveness_evaluation"
    raise ValueError("Production evaluation partition has no claim scope")


def _public_integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Production policy evaluation {label} must be an integer")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Production policy evaluation {label} must be a non-empty string")
    return value


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _artifact_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Production evaluation metric must be finite")
    return round(value, 12)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
