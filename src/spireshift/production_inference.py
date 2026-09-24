from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from spireshift.agents.learned import ProductionCheckpointPolicy
from spireshift.core.manifest import manifest_identifier
from spireshift.core.protocols import EnvironmentAdapter
from spireshift.models import write_model_artifact

PRODUCTION_INFERENCE_SMOKE_SCHEMA_VERSION = "production-model-inference-smoke-v1"


def run_production_inference_smoke(
    *,
    environment: EnvironmentAdapter,
    policy: ProductionCheckpointPolicy,
    training_report_id: str,
    seeds: tuple[int, ...],
    maximum_decisions_per_seed: int,
) -> dict[str, Any]:
    if not seeds or any(seed < 0 for seed in seeds):
        raise ValueError("Inference smoke seeds must be non-negative and non-empty")
    if len(seeds) != len(set(seeds)):
        raise ValueError("Inference smoke seeds must be unique")
    if maximum_decisions_per_seed <= 0:
        raise ValueError("maximum_decisions_per_seed must be positive")
    if environment.ruleset != policy.ruleset:
        raise ValueError("Inference smoke environment differs from policy ruleset")
    records: list[dict[str, Any]] = []
    terminal_seeds = 0
    for seed in seeds:
        observation = environment.reset(seed)
        for decision_index in range(maximum_decisions_per_seed):
            if bool(observation.public_state.get("terminal")):
                terminal_seeds += 1
                break
            actions = tuple(environment.legal_actions())
            decision = policy.predict(observation, actions)
            if decision.selected_action not in actions:
                raise RuntimeError("Production policy selected an action outside the legal set")
            records.append(
                {
                    "run_seed": seed,
                    "decision_index": decision_index,
                    "decision_type": observation.decision_type.value,
                    "state_hash": observation.state_hash,
                    "representation_hash": decision.representation_hash,
                    "candidate_action_ids": list(decision.source_action_ids),
                    "selected_candidate_index": decision.selected_candidate_index,
                    "selected_action_id": decision.selected_action.action_id,
                    "selected_policy_probability": _artifact_float(
                        decision.policy[decision.selected_candidate_index]
                    ),
                    "selected_tactical_death_risk": _artifact_float(
                        decision.tactical_death_risk[decision.selected_candidate_index]
                    ),
                    "inference_seconds": _artifact_float(decision.inference_seconds),
                }
            )
            transition = environment.step(decision.selected_action)
            observation = transition.next_observation
            if transition.terminal:
                terminal_seeds += 1
                break
    if not records:
        raise ValueError("Inference smoke observed no actionable decisions")
    latencies = sorted(float(record["inference_seconds"]) for record in records)
    body: dict[str, Any] = {
        "schema_version": PRODUCTION_INFERENCE_SMOKE_SCHEMA_VERSION,
        "model_id": policy.model_id,
        "training_report_id": training_report_id,
        "policy_id": policy.policy_id,
        "ruleset_manifest_id": environment.ruleset.manifest_id,
        "patch_id": environment.patch_id,
        "information_policy_id": environment.ruleset.interface.information_policy_id,
        "seeds": list(seeds),
        "maximum_decisions_per_seed": maximum_decisions_per_seed,
        "records": records,
        "summary": {
            "decisions": len(records),
            "terminal_seeds": terminal_seeds,
            "candidate_alignment_pass": True,
            "legal_selection_pass": True,
            "public_state_only": True,
            "median_inference_seconds": _artifact_float(_percentile(latencies, 0.5)),
            "p95_inference_seconds": _artifact_float(_percentile(latencies, 0.95)),
            "maximum_inference_seconds": _artifact_float(max(latencies)),
        },
        "claim_scope": "admitted_backend_inference_smoke_only",
    }
    return {**body, "report_id": manifest_identifier(body)}


def load_production_inference_smoke(
    path: Path,
    *,
    model_id: str | None = None,
    training_report_id: str | None = None,
) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load production inference smoke {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("Production inference smoke must be a JSON object")
    report = dict(value)
    report_id = report.get("report_id")
    body = {key: item for key, item in report.items() if key != "report_id"}
    if report_id != manifest_identifier(body):
        raise ValueError("Production inference smoke identity mismatch")
    if report.get("schema_version") != PRODUCTION_INFERENCE_SMOKE_SCHEMA_VERSION:
        raise ValueError("Unsupported production inference smoke schema")
    if model_id is not None and report.get("model_id") != model_id:
        raise ValueError("Production inference smoke references another model")
    if training_report_id is not None and report.get("training_report_id") != training_report_id:
        raise ValueError("Production inference smoke references another training report")
    _validate_production_inference_smoke(report)
    return report


def _validate_production_inference_smoke(report: dict[str, Any]) -> None:
    model_id = _required_string(report.get("model_id"), "model_id")
    if report.get("policy_id") != f"production-checkpoint-policy-v1:{model_id}":
        raise ValueError("Production inference smoke policy identity mismatch")
    if report.get("information_policy_id") != "public-state-v1":
        raise ValueError("Production inference smoke does not use public state")
    if report.get("claim_scope") != "admitted_backend_inference_smoke_only":
        raise ValueError("Production inference smoke claim scope differs")
    seeds = _integer_list(report.get("seeds"), "seeds")
    if not seeds or any(seed < 0 for seed in seeds) or len(seeds) != len(set(seeds)):
        raise ValueError("Production inference smoke seeds are invalid")
    maximum_decisions = _integer(
        report.get("maximum_decisions_per_seed"), "maximum_decisions_per_seed"
    )
    if maximum_decisions <= 0:
        raise ValueError("Production inference smoke decision limit must be positive")
    raw_records = report.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        raise ValueError("Production inference smoke has no decision records")
    latencies: list[float] = []
    coordinates: set[tuple[int, int]] = set()
    for offset, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, dict):
            raise ValueError(f"Production inference smoke record[{offset}] must be an object")
        seed = _integer(raw_record.get("run_seed"), f"records[{offset}].run_seed")
        decision_index = _integer(
            raw_record.get("decision_index"), f"records[{offset}].decision_index"
        )
        coordinate = (seed, decision_index)
        if seed not in seeds or not 0 <= decision_index < maximum_decisions:
            raise ValueError("Production inference smoke record coordinate is outside its bounds")
        if coordinate in coordinates:
            raise ValueError("Production inference smoke repeats a decision coordinate")
        coordinates.add(coordinate)
        raw_action_ids = raw_record.get("candidate_action_ids")
        if not isinstance(raw_action_ids, list) or not raw_action_ids:
            raise ValueError("Production inference smoke record has no candidate actions")
        action_ids = tuple(
            _required_string(value, f"records[{offset}].candidate_action_ids[]")
            for value in raw_action_ids
        )
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("Production inference smoke candidate actions are not unique")
        selected_index = _integer(
            raw_record.get("selected_candidate_index"),
            f"records[{offset}].selected_candidate_index",
        )
        if not 0 <= selected_index < len(action_ids):
            raise ValueError("Production inference smoke selected candidate index is invalid")
        if raw_record.get("selected_action_id") != action_ids[selected_index]:
            raise ValueError("Production inference smoke selected action is not candidate-aligned")
        for field in ("selected_policy_probability", "selected_tactical_death_risk"):
            probability = _finite_number(raw_record.get(field), f"records[{offset}].{field}")
            if not 0.0 <= probability <= 1.0:
                raise ValueError(f"Production inference smoke {field} is not a probability")
        latency = _finite_number(
            raw_record.get("inference_seconds"), f"records[{offset}].inference_seconds"
        )
        if latency < 0.0:
            raise ValueError("Production inference smoke latency must be non-negative")
        latencies.append(latency)
    summary = report.get("summary")
    if not isinstance(summary, dict) or not all(
        summary.get(field) is True
        for field in (
            "candidate_alignment_pass",
            "legal_selection_pass",
            "public_state_only",
        )
    ):
        raise ValueError("Production inference smoke did not pass its safety checks")
    if _integer(summary.get("decisions"), "summary.decisions") != len(raw_records):
        raise ValueError("Production inference smoke decision count differs")
    terminal_seeds = _integer(summary.get("terminal_seeds"), "summary.terminal_seeds")
    if not 0 <= terminal_seeds <= len(seeds):
        raise ValueError("Production inference smoke terminal seed count is invalid")
    sorted_latencies = sorted(latencies)
    expected_latency_metrics = {
        "median_inference_seconds": _artifact_float(_percentile(sorted_latencies, 0.5)),
        "p95_inference_seconds": _artifact_float(_percentile(sorted_latencies, 0.95)),
        "maximum_inference_seconds": _artifact_float(max(sorted_latencies)),
    }
    for field, expected in expected_latency_metrics.items():
        actual = _finite_number(summary.get(field), f"summary.{field}")
        if actual != expected:
            raise ValueError(f"Production inference smoke {field} differs from its records")


def write_production_inference_smoke(document: dict[str, Any], path: Path) -> None:
    write_model_artifact(document, path, label="production inference smoke")


def _artifact_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Inference smoke metric must be finite")
    return round(value, 12)


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Percentile requires values")
    index = max(0, math.ceil(probability * len(values)) - 1)
    return values[index]


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Production inference smoke {label} must be a non-empty string")
    return value


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Production inference smoke {label} must be an integer")
    return value


def _integer_list(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Production inference smoke {label} must be an array")
    return tuple(_integer(item, f"{label}[]") for item in value)


def _finite_number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Production inference smoke {label} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Production inference smoke {label} must be finite")
    return number
