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
from spireshift.core.manifest import RulesetIdentity, manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter, Policy
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION = "production-policy-evaluation-v1"
PRODUCTION_POLICY_CASE_SCHEMA_VERSION = "production-policy-evaluation-case-v1"
LEARNED_POLICY_KIND = "production_checkpoint"
BASELINE_POLICY_KIND = "progress_bootstrap_baseline"


@dataclass(frozen=True, slots=True)
class ProductionPolicyEvaluationResult:
    successful: bool
    report_path: Path
    report: dict[str, Any]


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
    resume: bool = False,
    now: Callable[[], str] | None = None,
) -> ProductionPolicyEvaluationResult:
    canonical_seeds = tuple(seeds)
    if not canonical_seeds or len(canonical_seeds) != len(set(canonical_seeds)):
        raise ValueError("Production evaluation seeds must be non-empty and unique")
    if any(split_manifest.split_for_seed(seed) is not SplitName.TEST for seed in canonical_seeds):
        raise ValueError("Production evaluation may use only frozen test seeds")
    if split_manifest.ruleset_manifest_id != ruleset.manifest_id:
        raise ValueError("Production evaluation split and environment rulesets differ")
    if split_manifest.objective_id != "terminal-victory-v1":
        raise ValueError("Production evaluation split does not use terminal victory")
    if learned_policy.ruleset != ruleset:
        raise ValueError("Production evaluation policy and environment rulesets differ")
    if learned_policy.split_manifest_id != split_manifest.manifest_id:
        raise ValueError("Production evaluation checkpoint and split identities differ")
    if workers <= 0:
        raise ValueError("Production evaluation workers must be positive")
    if maximum_decisions_per_run <= 0:
        raise ValueError("maximum_decisions_per_run must be positive")
    if output_directory.exists() and not resume:
        raise FileExistsError(f"Production evaluation output already exists: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    report_path = output_directory / "production-policy-evaluation.json"
    if report_path.exists():
        raise FileExistsError(f"Production evaluation report already exists: {report_path}")

    baseline_policy = ProgressBootstrapPolicy()
    policies: tuple[tuple[str, Policy, str | None], ...] = (
        (LEARNED_POLICY_KIND, learned_policy, learned_policy.model_id),
        (BASELINE_POLICY_KIND, baseline_policy, None),
    )
    started_at = (now or _utc_now)()
    cases: list[dict[str, Any]] = []
    pending: list[tuple[int, str, Policy, str | None, Path]] = []
    for seed in canonical_seeds:
        for policy_kind, policy, model_id in policies:
            case_path = _case_path(output_directory, seed, policy_kind)
            if case_path.exists():
                cases.append(
                    _load_case(
                        case_path,
                        seed=seed,
                        policy_kind=policy_kind,
                        policy_id=policy.policy_id,
                        model_id=model_id,
                        ruleset_manifest_id=ruleset.manifest_id,
                    )
                )
            else:
                pending.append((seed, policy_kind, policy, model_id, case_path))

    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(pending)))) as executor:
        future_to_task: dict[Future[dict[str, Any]], tuple[int, str, Policy, str | None, Path]] = {}
        for task in pending:
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
    baseline_cases = [case for case in ordered_cases if case["policy_kind"] == BASELINE_POLICY_KIND]
    body: dict[str, Any] = {
        "schema_version": PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        "started_at": started_at,
        "completed_at": (now or _utc_now)(),
        "model_id": learned_policy.model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TEST.value,
        "ruleset_manifest_id": ruleset.manifest_id,
        "patch_id": ruleset.patch_id,
        "objective_id": "terminal-victory-v1",
        "configuration": {
            "seeds": list(canonical_seeds),
            "workers": workers,
            "maximum_decisions_per_run": maximum_decisions_per_run,
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
        "summary": {
            "learned": _policy_summary(learned_cases),
            "baseline": _policy_summary(baseline_cases),
            "paired": _paired_summary(learned_cases, baseline_cases),
        },
        "claim_scope": "paired_frozen_test_policy_only_evaluation",
    }
    report = {**body, "report_id": manifest_identifier(body)}
    write_model_artifact(report, report_path, label="production policy evaluation")
    successful = all(case["status"] == "completed" for case in ordered_cases)
    return ProductionPolicyEvaluationResult(successful, report_path, report)


def load_production_policy_evaluation(
    path: Path,
    *,
    model_id: str,
    training_report_id: str,
    split_manifest: SplitManifest,
) -> dict[str, Any]:
    report = _load_object(path, "production policy evaluation")
    report_id = report.get("report_id")
    body = {key: item for key, item in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Production policy evaluation identity mismatch")
    expected_fields = {
        "schema_version": PRODUCTION_POLICY_EVALUATION_SCHEMA_VERSION,
        "model_id": model_id,
        "training_report_id": training_report_id,
        "split_manifest_id": split_manifest.manifest_id,
        "partition": SplitName.TEST.value,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "claim_scope": "paired_frozen_test_policy_only_evaluation",
    }
    if any(report.get(key) != value for key, value in expected_fields.items()):
        raise ValueError("Production policy evaluation provenance differs")
    configuration = report.get("configuration")
    if not isinstance(configuration, dict):
        raise ValueError("Production policy evaluation configuration is missing")
    raw_seeds = configuration.get("seeds")
    if not isinstance(raw_seeds, list):
        raise ValueError("Production policy evaluation seeds are missing")
    seeds = tuple(_integer(seed, "configuration.seeds[]") for seed in raw_seeds)
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Production policy evaluation seeds are invalid")
    if any(split_manifest.split_for_seed(seed) is not SplitName.TEST for seed in seeds):
        raise ValueError("Production policy evaluation contains a non-test seed")
    learned_policy_id = f"production-checkpoint-policy-v1:{model_id}"
    baseline_policy_id = ProgressBootstrapPolicy.policy_id
    if configuration.get("paired_policies") != [learned_policy_id, baseline_policy_id]:
        raise ValueError("Production policy evaluation policies differ")
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
        )
        if raw_reference.get("case_id") != case["case_id"]:
            raise ValueError("Production policy evaluation case reference identity mismatch")
        maximum_decisions = _integer(
            configuration.get("maximum_decisions_per_run"),
            "configuration.maximum_decisions_per_run",
        )
        if case["status"] == "completed" and int(case["decisions"]) > maximum_decisions:
            raise ValueError("Production policy evaluation case exceeded its decision limit")
        cases.append(case)
    expected_coordinates = {
        (seed, policy_kind)
        for seed in seeds
        for policy_kind in (LEARNED_POLICY_KIND, BASELINE_POLICY_KIND)
    }
    if coordinates != expected_coordinates:
        raise ValueError("Production policy evaluation paired case coverage differs")
    learned_cases = [case for case in cases if case["policy_kind"] == LEARNED_POLICY_KIND]
    baseline_cases = [case for case in cases if case["policy_kind"] == BASELINE_POLICY_KIND]
    expected_summary = {
        "learned": _policy_summary(learned_cases),
        "baseline": _policy_summary(baseline_cases),
        "paired": _paired_summary(learned_cases, baseline_cases),
    }
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
) -> dict[str, Any]:
    environment: EnvironmentAdapter | None = None
    try:
        environment = environment_factory()
        if environment.ruleset != ruleset:
            raise ValueError("Evaluation environment ruleset changed")
        observation = environment.reset(seed)
        maximum_floor = _public_integer(observation.public_state.get("floor")) or 0
        maximum_act = _public_integer(observation.public_state.get("act")) or 0
        decisions = 0
        decision_seconds: list[float] = []
        action_ids: list[str] = []
        terminal = bool(observation.public_state.get("terminal"))
        victory = bool(observation.public_state.get("victory")) if terminal else False
        while not terminal and decisions < maximum_decisions:
            actions = tuple(environment.legal_actions())
            if not actions:
                raise RuntimeError("Nonterminal evaluation state has no legal actions")
            started = time.perf_counter()
            if isinstance(policy, ProductionCheckpointPolicy):
                decision = policy.predict(observation, actions)
                action = decision.selected_action
                elapsed = decision.inference_seconds
            else:
                action = policy.choose_action(observation, actions)
                elapsed = time.perf_counter() - started
            if action not in actions:
                raise RuntimeError("Evaluation policy selected an illegal action")
            decision_seconds.append(elapsed)
            action_ids.append(action.action_id)
            transition = environment.step(action)
            observation = transition.next_observation
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
        body: dict[str, Any] = {
            "schema_version": PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
            "seed": seed,
            "partition": SplitName.TEST.value,
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
            "schema_version": PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
            "seed": seed,
            "partition": SplitName.TEST.value,
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
            "maximum_floor": None,
            "maximum_act": None,
            "final_state_hash": None,
            "action_trace_sha256": None,
            "total_decision_seconds": None,
            "median_decision_seconds": None,
            "maximum_decision_seconds": None,
        }
    finally:
        if environment is not None:
            close = getattr(environment, "close", None)
            if callable(close):
                close()
    return {**body, "case_id": manifest_identifier(body)}


def _policy_summary(cases: Sequence[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case["status"] == "completed"]
    terminal = [case for case in completed if case["terminal"] is True]
    victories = sum(case["victory"] is True for case in terminal)
    denominator = len(cases)
    decision_latencies = [float(case["total_decision_seconds"]) for case in completed]
    decisions = sum(int(case["decisions"]) for case in completed)
    return {
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


def _case_path(output_directory: Path, seed: int, policy_kind: str) -> Path:
    return output_directory / "cases" / f"seed-{seed:06d}-{policy_kind}.json"


def _load_case(
    path: Path,
    *,
    seed: int,
    policy_kind: str,
    policy_id: str,
    model_id: str | None,
    ruleset_manifest_id: str,
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
        "schema_version": PRODUCTION_POLICY_CASE_SCHEMA_VERSION,
        "seed": seed,
        "partition": SplitName.TEST.value,
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
    status = case.get("status")
    result_fields = (
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


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label.capitalize()} must be an object")
    return dict(value)


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
