from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.models import write_model_artifact
from spireshift.splits import SplitManifest, SplitName

READINESS_SPEC_SCHEMA_VERSION = "base-model-readiness-spec-v1"
READINESS_AUDIT_SCHEMA_VERSION = "production-model-readiness-audit-v1"
READINESS_REPORT_SCHEMA_VERSION = "base-model-readiness-report-v1"


def load_readiness_spec(path: Path, *, split_manifest: SplitManifest) -> dict[str, Any]:
    spec = _load_addressed(path, "scorecard_id", "base-model readiness specification")
    if spec.get("schema_version") != READINESS_SPEC_SCHEMA_VERSION:
        raise ValueError("Unsupported base-model readiness specification schema")
    if spec.get("claim_scope") != "frozen_validation_base_model_readiness_contract":
        raise ValueError("Base-model readiness specification claim scope differs")
    binding = _mapping(spec.get("binding"), "binding")
    if binding.get("split_manifest_id") != split_manifest.manifest_id:
        raise ValueError("Readiness specification and split manifest identities differ")
    if binding.get("ruleset_manifest_id") != split_manifest.ruleset_manifest_id:
        raise ValueError("Readiness specification and split rulesets differ")
    if binding.get("objective_id") != split_manifest.objective_id:
        raise ValueError("Readiness specification and split objectives differ")
    contract = _mapping(spec.get("evaluation_contract"), "evaluation_contract")
    if contract.get("partition") != SplitName.VALIDATION.value:
        raise ValueError("Base-model readiness must be owned by the validation partition")
    seeds = _integer_tuple(contract.get("seeds"), "evaluation_contract.seeds")
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Readiness evaluation seeds must be non-empty and unique")
    if any(split_manifest.split_for_seed(seed) is not SplitName.VALIDATION for seed in seeds):
        raise ValueError("Readiness evaluation includes a non-validation seed")
    if contract.get("minimum_runs") != len(seeds):
        raise ValueError("Readiness minimum run denominator must equal the frozen seed count")
    interval = _mapping(contract.get("confidence_interval"), "confidence_interval")
    if interval.get("method") != "wilson-score-v1":
        raise ValueError("Unsupported readiness confidence interval")
    confidence = _probability(interval.get("confidence_level"), "confidence_level")
    if confidence != 0.95:
        raise ValueError("Readiness confidence level must be 0.95")
    z = _finite_number(interval.get("z"), "confidence_interval.z")
    if abs(z - 1.95996398454) > 1e-12:
        raise ValueError("Readiness Wilson z value differs")
    _validate_thresholds(spec.get("thresholds"))
    return spec


def load_readiness_audit(
    path: Path,
    *,
    model_id: str,
    training_report_id: str,
    split_manifest: SplitManifest,
    validation_dataset_id: str,
) -> dict[str, Any]:
    audit = _load_addressed(path, "audit_id", "production readiness audit")
    if audit.get("schema_version") != READINESS_AUDIT_SCHEMA_VERSION:
        raise ValueError("Unsupported production readiness audit schema")
    expected = {
        "model_id": model_id,
        "training_report_id": training_report_id,
        "validation_dataset_id": validation_dataset_id,
        "split_manifest_id": split_manifest.manifest_id,
        "ruleset_manifest_id": split_manifest.ruleset_manifest_id,
        "objective_id": split_manifest.objective_id,
        "partition": SplitName.VALIDATION.value,
        "claim_scope": "independent_validation_calibration_and_failure_audit",
    }
    for field, expected_value in expected.items():
        if audit.get(field) != expected_value:
            raise ValueError(f"Production readiness audit {field} differs")
    calibration = _mapping(audit.get("calibration"), "calibration")
    if calibration.get("method") != "platt-logit-affine-v1":
        raise ValueError("Production readiness audit calibration method differs")
    fit_seeds = _integer_tuple(calibration.get("fit_run_seeds"), "fit_run_seeds")
    audit_seeds = _integer_tuple(calibration.get("audit_run_seeds"), "audit_run_seeds")
    if not fit_seeds or not audit_seeds or set(fit_seeds) & set(audit_seeds):
        raise ValueError("Production readiness calibration subfolds must be non-empty and disjoint")
    if any(
        split_manifest.split_for_seed(seed) is not SplitName.VALIDATION
        for seed in (*fit_seeds, *audit_seeds)
    ):
        raise ValueError("Production readiness audit uses a non-validation seed")
    configuration = _mapping(audit.get("configuration"), "configuration")
    records = _audit_records(audit.get("records"), audit_seeds)
    expected_summary = summarize_readiness_audit(records, configuration)
    if audit.get("summary") != expected_summary:
        raise ValueError("Production readiness audit summary differs from its records")
    return audit


def summarize_readiness_audit(
    records: tuple[dict[str, Any], ...], configuration: dict[str, Any]
) -> dict[str, Any]:
    bins = _positive_integer(configuration.get("calibration_bins"), "calibration_bins")
    confidence_threshold = _probability(
        configuration.get("policy_confidence_threshold"), "policy_confidence_threshold"
    )
    catastrophic_threshold = _probability(
        configuration.get("catastrophic_regret_threshold"),
        "catastrophic_regret_threshold",
    )
    false_safe_prediction = _probability(
        configuration.get("false_safe_predicted_risk_threshold"),
        "false_safe_predicted_risk_threshold",
    )
    false_safe_observed = _probability(
        configuration.get("false_safe_observed_risk_threshold"),
        "false_safe_observed_risk_threshold",
    )
    terminal_pairs: list[tuple[float, int]] = []
    tactical_pairs: list[tuple[float, int]] = []
    regrets: list[float] = []
    variation = 0
    high_confidence = 0
    catastrophic = 0
    false_safe = 0
    for record in records:
        selected_index = int(record["selected_candidate_index"])
        candidates = record["candidates"]
        if not isinstance(candidates, tuple):
            raise ValueError("Readiness audit candidates are not normalized")
        candidate_rates = [
            _mean(tuple(int(outcome) for outcome in candidate["terminal_outcomes"]))
            for candidate in candidates
        ]
        selected = candidates[selected_index]
        selected_rate = candidate_rates[selected_index]
        regret = max(candidate_rates) - selected_rate
        regrets.append(regret)
        variation += int(max(candidate_rates) > min(candidate_rates))
        terminal_pairs.extend(
            (float(selected["terminal_value_prediction"]), int(outcome))
            for outcome in selected["terminal_outcomes"]
        )
        tactical_pairs.extend(
            (float(candidate["tactical_risk_prediction"]), int(outcome))
            for candidate in candidates
            for outcome in candidate["tactical_death_outcomes"]
        )
        confidence = float(record["policy_confidence"])
        is_high_confidence = confidence >= confidence_threshold
        high_confidence += int(is_high_confidence)
        catastrophic += int(is_high_confidence and regret >= catastrophic_threshold)
        selected_risk = float(selected["tactical_risk_prediction"])
        observed_risk = _mean(
            tuple(int(outcome) for outcome in selected["tactical_death_outcomes"])
        )
        false_safe += int(
            selected_risk <= false_safe_prediction and observed_risk >= false_safe_observed
        )
    terminal_metrics = _calibration_metrics(terminal_pairs, bins)
    tactical_metrics = _calibration_metrics(tactical_pairs, bins)
    return {
        "decisions": len(records),
        "terminal_samples": len(terminal_pairs),
        "terminal_victories": sum(outcome for _, outcome in terminal_pairs),
        "terminal_defeats": len(terminal_pairs) - sum(outcome for _, outcome in terminal_pairs),
        "action_value_variation_decisions": variation,
        "terminal_value": terminal_metrics,
        "tactical_death_risk": tactical_metrics,
        "independent_value_regret": {
            "mean": _artifact_float(_mean(tuple(regrets))),
            "p95": _artifact_float(_percentile(regrets, 0.95)),
        },
        "failure_analysis": {
            "high_confidence_decisions": high_confidence,
            "high_confidence_catastrophic_errors": catastrophic,
            "high_confidence_catastrophic_rate": _artifact_float(
                catastrophic / high_confidence if high_confidence else 0.0
            ),
            "false_safe_tactical_risk_errors": false_safe,
            "false_safe_tactical_risk_rate": _artifact_float(false_safe / len(records)),
        },
    }


def assess_base_model_readiness(
    *,
    spec: dict[str, Any],
    checkpoint: dict[str, Any],
    training_report: dict[str, Any],
    split_manifest: SplitManifest,
    inference_smoke: dict[str, Any] | None,
    policy_evaluation: dict[str, Any] | None,
    readiness_audit: dict[str, Any] | None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    binding = _mapping(spec.get("binding"), "binding")
    thresholds = _mapping(spec.get("thresholds"), "thresholds")
    contract = _mapping(spec.get("evaluation_contract"), "evaluation_contract")

    actual_binding = {
        "model_id": checkpoint.get("model_id"),
        "training_report_id": training_report.get("report_id"),
        "train_dataset_id": checkpoint.get("train_dataset_id"),
        "validation_dataset_id": training_report.get("validation_dataset_id"),
        "split_manifest_id": checkpoint.get("split_manifest_id"),
        "ruleset_manifest_id": checkpoint.get("ruleset_manifest_id"),
        "objective_id": checkpoint.get("objective_id"),
        "representation_encoder_id": checkpoint.get("representation_encoder_id"),
        "calibration_id": (
            None
            if readiness_audit is None
            else _mapping(readiness_audit.get("calibration"), "calibration").get("calibration_id")
        ),
    }
    _check(
        checks,
        "identity.frozen_binding",
        actual_binding == binding,
        actual_binding,
        binding,
        "checkpoint, datasets, objective, ruleset, split, encoder, and report are frozen",
    )
    policy = _mapping(
        _mapping(training_report.get("held_out_metrics"), "held_out_metrics").get("policy"),
        "held_out_metrics.policy",
    )
    policy_thresholds = _mapping(thresholds.get("policy"), "thresholds.policy")
    auxiliary = _mapping(policy.get("auxiliary_policy_gate"), "auxiliary_policy_gate")
    policy_observed = {
        "auxiliary_gate_passed": auxiliary.get("passed"),
        "decisive_pair_accuracy": policy.get("decisive_pair_accuracy"),
        "weighted_pairwise_cross_entropy": policy.get("weighted_pairwise_cross_entropy"),
        "mean_progress_utility_regret": policy.get("mean_progress_utility_regret"),
    }
    policy_pass = (
        auxiliary.get("passed") is True
        and _at_least(
            policy.get("decisive_pair_accuracy"),
            policy_thresholds,
            "minimum_decisive_pair_accuracy",
        )
        and _at_most(
            policy.get("weighted_pairwise_cross_entropy"),
            policy_thresholds,
            "maximum_pairwise_cross_entropy",
        )
        and _at_most(
            policy.get("mean_progress_utility_regret"),
            policy_thresholds,
            "maximum_mean_progress_regret",
        )
    )
    _check(
        checks,
        "auxiliary.policy_quality",
        policy_pass,
        policy_observed,
        policy_thresholds,
        "held-out pairwise policy evidence clears every frozen auxiliary threshold",
    )
    risk = _mapping(
        _mapping(training_report.get("held_out_metrics"), "held_out_metrics").get(
            "tactical_death_risk"
        ),
        "held_out_metrics.tactical_death_risk",
    )
    risk_observed = {
        "brier_skill_score": risk.get("brier_skill_score"),
        "expected_calibration_error": risk.get("expected_calibration_error"),
    }
    risk_pass = _at_least(
        risk.get("brier_skill_score"), policy_thresholds, "minimum_tactical_risk_brier_skill"
    ) and _at_most(
        risk.get("expected_calibration_error"), policy_thresholds, "maximum_tactical_risk_ece"
    )
    _check(
        checks,
        "auxiliary.tactical_risk_calibration",
        risk_pass,
        risk_observed,
        {
            "minimum_brier_skill": policy_thresholds["minimum_tactical_risk_brier_skill"],
            "maximum_ece": policy_thresholds["maximum_tactical_risk_ece"],
        },
        "tactical-risk prediction improves on a constant-rate predictor",
    )
    terminal_status = _mapping(
        training_report.get("terminal_value_status"), "terminal_value_status"
    )
    _check(
        checks,
        "terminal.value_head_available",
        terminal_status.get("promoted") is True,
        terminal_status,
        {"promoted": True},
        "a terminal-victory value head is trained from nondegenerate outcomes",
    )
    _assess_smoke(checks, inference_smoke, thresholds)
    _assess_audit(checks, readiness_audit, contract, thresholds)
    _assess_full_runs(checks, policy_evaluation, contract, thresholds)

    blockers = [
        str(check["check_id"]) for check in checks if check["status"] in {"failed", "missing"}
    ]
    evidence = {
        "training_report_id": training_report.get("report_id"),
        "inference_smoke_report_id": (
            None if inference_smoke is None else inference_smoke.get("report_id")
        ),
        "policy_evaluation_report_id": (
            None if policy_evaluation is None else policy_evaluation.get("report_id")
        ),
        "readiness_audit_id": None if readiness_audit is None else readiness_audit.get("audit_id"),
        "calibration_id": (
            None
            if readiness_audit is None
            else _mapping(readiness_audit.get("calibration"), "calibration").get("calibration_id")
        ),
    }
    progress_diagnostics: dict[str, Any] = {
        "held_out_mean_progress_utility_regret": policy.get("mean_progress_utility_regret"),
        "held_out_decisive_pair_accuracy": policy.get("decisive_pair_accuracy"),
        "note": "auxiliary progress diagnostics cannot satisfy terminal-victory readiness",
    }
    if policy_evaluation is not None:
        paired = _mapping(
            _mapping(policy_evaluation.get("summary"), "evaluation.summary").get("paired"),
            "evaluation.summary.paired",
        )
        progress_diagnostics["mean_maximum_floor_difference"] = paired.get(
            "mean_maximum_floor_difference"
        )
    body: dict[str, Any] = {
        "schema_version": READINESS_REPORT_SCHEMA_VERSION,
        "scorecard_id": spec["scorecard_id"],
        "model_id": checkpoint.get("model_id"),
        "evidence": evidence,
        "checks": checks,
        "ready": not blockers,
        "blocking_check_ids": blockers,
        "progress_diagnostics": progress_diagnostics,
        "claim_scope": "frozen_validation_base_model_readiness_assessment",
    }
    return {**body, "report_id": manifest_identifier(body)}


def load_readiness_report(path: Path, *, scorecard_id: str, model_id: str) -> dict[str, Any]:
    report = _load_addressed(path, "report_id", "base-model readiness report")
    if report.get("schema_version") != READINESS_REPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported base-model readiness report schema")
    if report.get("scorecard_id") != scorecard_id or report.get("model_id") != model_id:
        raise ValueError("Base-model readiness report binding differs")
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("Base-model readiness report has no checks")
    blockers = [
        str(check.get("check_id"))
        for check in checks
        if isinstance(check, dict) and check.get("status") in {"failed", "missing"}
    ]
    if report.get("blocking_check_ids") != blockers or report.get("ready") is not (not blockers):
        raise ValueError("Base-model readiness decision differs from its checks")
    return report


def write_readiness_artifact(document: dict[str, Any], path: Path, *, label: str) -> None:
    write_model_artifact(document, path, label=label)


def _assess_smoke(
    checks: list[dict[str, Any]], smoke: dict[str, Any] | None, thresholds: dict[str, Any]
) -> None:
    inference_thresholds = _mapping(thresholds.get("inference"), "thresholds.inference")
    if smoke is None:
        _missing(checks, "inference.candidate_alignment_and_latency", inference_thresholds)
        return
    summary = _mapping(smoke.get("summary"), "smoke.summary")
    observed = {
        "decisions": summary.get("decisions"),
        "candidate_alignment_pass": summary.get("candidate_alignment_pass"),
        "legal_selection_pass": summary.get("legal_selection_pass"),
        "public_state_only": summary.get("public_state_only"),
        "p95_inference_seconds": summary.get("p95_inference_seconds"),
    }
    passed = (
        summary.get("candidate_alignment_pass") is True
        and summary.get("legal_selection_pass") is True
        and summary.get("public_state_only") is True
        and _at_least(summary.get("decisions"), inference_thresholds, "minimum_decisions")
        and _at_most(
            summary.get("p95_inference_seconds"),
            inference_thresholds,
            "maximum_p95_inference_seconds",
        )
    )
    _check(
        checks,
        "inference.candidate_alignment_and_latency",
        passed,
        observed,
        inference_thresholds,
        "public-state inference preserves legal candidate order within the latency budget",
    )


def _assess_audit(
    checks: list[dict[str, Any]],
    audit: dict[str, Any] | None,
    contract: dict[str, Any],
    thresholds: dict[str, Any],
) -> None:
    audit_contract = _mapping(contract.get("calibration_audit"), "calibration_audit")
    calibration_thresholds = _mapping(thresholds.get("calibration"), "thresholds.calibration")
    failure_thresholds = _mapping(thresholds.get("failures"), "thresholds.failures")
    check_ids = (
        "terminal.independent_signal_sufficiency",
        "terminal.value_calibration",
        "terminal.independent_action_regret",
        "terminal.confident_catastrophic_errors",
        "terminal.false_safe_tactical_risk",
    )
    if audit is None:
        missing_thresholds = (
            audit_contract,
            calibration_thresholds,
            calibration_thresholds,
            failure_thresholds,
            failure_thresholds,
        )
        for check_id, threshold in zip(check_ids, missing_thresholds, strict=True):
            _missing(checks, check_id, threshold)
        return
    calibration = _mapping(audit.get("calibration"), "audit.calibration")
    configuration = _mapping(audit.get("configuration"), "audit.configuration")
    summary = _mapping(audit.get("summary"), "audit.summary")
    config_observed = {
        "method": calibration.get("method"),
        "fit_fraction": calibration.get("fit_fraction"),
        "split_salt": calibration.get("split_salt"),
        **configuration,
    }
    config_expected = {
        "method": audit_contract["calibration_method"],
        "fit_fraction": audit_contract["fit_fraction"],
        "split_salt": audit_contract["split_salt"],
        "calibration_bins": audit_contract["calibration_bins"],
        "policy_confidence_threshold": failure_thresholds["policy_confidence_threshold"],
        "catastrophic_regret_threshold": failure_thresholds["catastrophic_regret_threshold"],
        "false_safe_predicted_risk_threshold": failure_thresholds[
            "false_safe_predicted_risk_threshold"
        ],
        "false_safe_observed_risk_threshold": failure_thresholds[
            "false_safe_observed_risk_threshold"
        ],
    }
    sufficient = config_observed == config_expected and all(
        _number(summary.get(observed)) >= _number(audit_contract[threshold])
        for observed, threshold in (
            ("decisions", "minimum_decisions"),
            ("terminal_samples", "minimum_terminal_samples"),
            ("terminal_victories", "minimum_positive_outcomes"),
            ("terminal_defeats", "minimum_negative_outcomes"),
            (
                "action_value_variation_decisions",
                "minimum_action_value_variation_decisions",
            ),
        )
    )
    _check(
        checks,
        "terminal.independent_signal_sufficiency",
        sufficient,
        {**config_observed, **summary_counts(summary)},
        {**config_expected, **audit_contract},
        "independent validation outcomes vary across outcomes and legal actions",
    )
    terminal = _mapping(summary.get("terminal_value"), "audit.summary.terminal_value")
    calibration_pass = _at_least(
        terminal.get("brier_skill_score"),
        calibration_thresholds,
        "minimum_terminal_brier_skill",
    ) and _at_most(
        terminal.get("expected_calibration_error"),
        calibration_thresholds,
        "maximum_terminal_ece",
    )
    _check(
        checks,
        "terminal.value_calibration",
        calibration_pass,
        terminal,
        calibration_thresholds,
        "terminal value beats a constant-rate predictor and is calibrated",
    )
    regret = _mapping(summary.get("independent_value_regret"), "independent_value_regret")
    regret_pass = _at_most(
        regret.get("mean"), calibration_thresholds, "maximum_mean_independent_regret"
    ) and _at_most(regret.get("p95"), calibration_thresholds, "maximum_p95_independent_regret")
    _check(
        checks,
        "terminal.independent_action_regret",
        regret_pass,
        regret,
        calibration_thresholds,
        "policy choices have bounded regret under independent terminal rollouts",
    )
    failure = _mapping(summary.get("failure_analysis"), "failure_analysis")
    catastrophe_pass = (
        _number(failure.get("high_confidence_decisions"))
        >= _number(failure_thresholds["minimum_high_confidence_decisions"])
        and _number(failure.get("high_confidence_catastrophic_errors"))
        <= _number(failure_thresholds["maximum_high_confidence_catastrophic_errors"])
        and _number(failure.get("high_confidence_catastrophic_rate"))
        <= _number(failure_thresholds["maximum_high_confidence_catastrophic_rate"])
    )
    _check(
        checks,
        "terminal.confident_catastrophic_errors",
        catastrophe_pass,
        failure,
        failure_thresholds,
        "high-confidence choices rarely have catastrophic independent regret",
    )
    false_safe_pass = _number(failure.get("false_safe_tactical_risk_rate")) <= _number(
        failure_thresholds["maximum_false_safe_tactical_risk_rate"]
    )
    _check(
        checks,
        "terminal.false_safe_tactical_risk",
        false_safe_pass,
        failure,
        failure_thresholds,
        "apparently safe actions rarely have high independently observed tactical risk",
    )


def _assess_full_runs(
    checks: list[dict[str, Any]],
    evaluation: dict[str, Any] | None,
    contract: dict[str, Any],
    thresholds: dict[str, Any],
) -> None:
    run_thresholds = _mapping(thresholds.get("full_run"), "thresholds.full_run")
    if evaluation is None:
        coverage_threshold = {
            "partition": contract["partition"],
            "seeds": contract["seeds"],
            "minimum_runs": contract["minimum_runs"],
            "completion_rate": 1.0,
            "terminal_rate": 1.0,
            "failed_runs": 0,
            "truncated_runs": 0,
            "liveness_pass": True,
            "fallback_exhausted_states": 0,
        }
        for check_id in (
            "full_run.validation_coverage_and_liveness",
            "full_run.terminal_outcome_variation",
            "full_run.victory_advantage",
        ):
            _missing(
                checks,
                check_id,
                coverage_threshold if "coverage" in check_id else run_thresholds,
            )
        return
    configuration = _mapping(evaluation.get("configuration"), "evaluation.configuration")
    summary = _mapping(evaluation.get("summary"), "evaluation.summary")
    learned = _mapping(summary.get("learned"), "evaluation.summary.learned")
    baseline = _mapping(summary.get("baseline"), "evaluation.summary.baseline")
    expected_seeds = tuple(contract["seeds"])
    actual_seeds = _integer_tuple(configuration.get("seeds"), "evaluation.configuration.seeds")
    coverage_observed = {
        "partition": evaluation.get("partition"),
        "seeds_match": actual_seeds == expected_seeds,
        "benchmark_denominator": learned.get("benchmark_denominator"),
        "completion_rate": learned.get("completion_rate"),
        "terminal_rate": learned.get("terminal_rate"),
        "failed_runs": learned.get("failed_runs"),
        "truncated_runs": learned.get("truncated_runs"),
        "liveness_pass": learned.get("liveness_pass"),
        "fallback_exhausted_states": learned.get("fallback_exhausted_states"),
    }
    coverage_pass = (
        evaluation.get("partition") == SplitName.VALIDATION.value
        and actual_seeds == expected_seeds
        and learned.get("benchmark_denominator") == contract.get("minimum_runs")
        and learned.get("completion_rate") == 1.0
        and learned.get("terminal_rate") == 1.0
        and learned.get("failed_runs") == 0
        and learned.get("truncated_runs") == 0
        and learned.get("liveness_pass") is True
        and learned.get("fallback_exhausted_states") == 0
    )
    _check(
        checks,
        "full_run.validation_coverage_and_liveness",
        coverage_pass,
        coverage_observed,
        {
            "partition": "validation",
            "seeds": list(expected_seeds),
            "minimum_runs": contract["minimum_runs"],
            "completion_rate": 1.0,
            "terminal_rate": 1.0,
            "failed_runs": 0,
            "truncated_runs": 0,
            "liveness_pass": True,
            "fallback_exhausted_states": 0,
        },
        "every frozen validation seed terminates without execution or liveness failure",
    )
    victories = int(learned.get("victories", 0))
    denominator = int(learned.get("benchmark_denominator", 0))
    defeats = max(0, denominator - victories)
    variation_pass = (
        learned.get("nondegenerate_terminal_outcomes") is True
        and victories >= int(run_thresholds["minimum_victories"])
        and defeats >= int(run_thresholds["minimum_defeats"])
    )
    _check(
        checks,
        "full_run.terminal_outcome_variation",
        variation_pass,
        {"victories": victories, "defeats": defeats},
        {
            "minimum_victories": run_thresholds["minimum_victories"],
            "minimum_defeats": run_thresholds["minimum_defeats"],
        },
        "terminal outcomes contain enough victories and defeats to measure run value",
    )
    interval = _mapping(contract.get("confidence_interval"), "confidence_interval")
    z = float(interval["z"])
    learned_low, learned_high = _wilson_interval(victories, denominator, z)
    baseline_victories = int(baseline.get("victories", 0))
    baseline_denominator = int(baseline.get("benchmark_denominator", 0))
    baseline_low, baseline_high = _wilson_interval(baseline_victories, baseline_denominator, z)
    advantage_low = learned_low - baseline_high
    performance_observed = {
        "learned_victory_rate": learned.get("victory_rate"),
        "baseline_victory_rate": baseline.get("victory_rate"),
        "learned_victory_rate_interval": [learned_low, learned_high],
        "baseline_victory_rate_interval": [baseline_low, baseline_high],
        "conservative_victory_advantage_lower_bound": _artifact_float(advantage_low),
    }
    performance_pass = learned_low >= _number(
        run_thresholds["minimum_learned_victory_rate_lower_bound"]
    ) and advantage_low >= _number(run_thresholds["minimum_conservative_advantage_lower_bound"])
    _check(
        checks,
        "full_run.victory_advantage",
        performance_pass,
        performance_observed,
        run_thresholds,
        "95% Wilson bounds support useful terminal performance over the lower-bound policy",
    )


def _audit_records(value: object, audit_seeds: tuple[int, ...]) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("Production readiness audit records must be non-empty")
    records: list[dict[str, Any]] = []
    coordinates: set[tuple[int, int]] = set()
    for offset, raw in enumerate(value):
        record = _mapping(raw, f"records[{offset}]")
        record_id = record.get("record_id")
        body = {key: item for key, item in record.items() if key != "record_id"}
        if record_id != manifest_identifier(body):
            raise ValueError("Production readiness audit record identity mismatch")
        seed = _positive_or_zero_integer(record.get("run_seed"), "run_seed")
        index = _positive_or_zero_integer(record.get("decision_index"), "decision_index")
        if seed not in audit_seeds or (seed, index) in coordinates:
            raise ValueError("Production readiness audit record coordinate differs")
        coordinates.add((seed, index))
        confidence = _probability(record.get("policy_confidence"), "policy_confidence")
        candidates_raw = record.get("candidates")
        if not isinstance(candidates_raw, list) or len(candidates_raw) < 2:
            raise ValueError("Production readiness audit requires at least two candidates")
        candidates: list[dict[str, Any]] = []
        for candidate in candidates_raw:
            candidate_mapping = _mapping(candidate, "candidate")
            terminal_outcomes = _binary_tuple(
                candidate_mapping.get("terminal_outcomes"), "terminal_outcomes"
            )
            tactical_outcomes = _binary_tuple(
                candidate_mapping.get("tactical_death_outcomes"),
                "tactical_death_outcomes",
            )
            candidates.append(
                {
                    **candidate_mapping,
                    "terminal_value_prediction": _probability(
                        candidate_mapping.get("terminal_value_prediction"),
                        "terminal_value_prediction",
                    ),
                    "tactical_risk_prediction": _probability(
                        candidate_mapping.get("tactical_risk_prediction"),
                        "tactical_risk_prediction",
                    ),
                    "terminal_outcomes": terminal_outcomes,
                    "tactical_death_outcomes": tactical_outcomes,
                }
            )
        selected = _positive_or_zero_integer(
            record.get("selected_candidate_index"), "selected_candidate_index"
        )
        if selected >= len(candidates):
            raise ValueError("Production readiness audit selected candidate is invalid")
        records.append(
            {
                **record,
                "policy_confidence": confidence,
                "selected_candidate_index": selected,
                "candidates": tuple(candidates),
            }
        )
    return tuple(records)


def _calibration_metrics(pairs: list[tuple[float, int]], bins: int) -> dict[str, Any]:
    if not pairs:
        raise ValueError("Calibration metrics require samples")
    base_rate = _mean(tuple(outcome for _, outcome in pairs))
    brier = _mean(tuple((prediction - outcome) ** 2 for prediction, outcome in pairs))
    baseline_brier = base_rate * (1.0 - base_rate)
    populated: list[dict[str, Any]] = []
    weighted_gap = 0.0
    for bin_index in range(bins):
        members = [
            (prediction, outcome)
            for prediction, outcome in pairs
            if min(int(prediction * bins), bins - 1) == bin_index
        ]
        if not members:
            continue
        mean_prediction = _mean(tuple(prediction for prediction, _ in members))
        observed = _mean(tuple(outcome for _, outcome in members))
        weighted_gap += len(members) * abs(mean_prediction - observed)
        populated.append(
            {
                "bin": bin_index,
                "count": len(members),
                "mean_prediction": _artifact_float(mean_prediction),
                "observed_frequency": _artifact_float(observed),
            }
        )
    return {
        "samples": len(pairs),
        "outcome_prevalence": _artifact_float(base_rate),
        "brier_score": _artifact_float(brier),
        "constant_rate_brier_score": _artifact_float(baseline_brier),
        "brier_skill_score": (
            None if baseline_brier == 0.0 else _artifact_float(1.0 - brier / baseline_brier)
        ),
        "expected_calibration_error": _artifact_float(weighted_gap / len(pairs)),
        "calibration_bins": populated,
    }


def _validate_thresholds(value: object) -> None:
    thresholds = _mapping(value, "thresholds")
    for section in ("policy", "inference", "full_run", "calibration", "failures"):
        if not isinstance(thresholds.get(section), dict):
            raise ValueError(f"Readiness thresholds.{section} must be an object")
    for section in thresholds.values():
        if not isinstance(section, dict):
            raise ValueError("Readiness threshold section must be an object")
        for name, raw in section.items():
            if not isinstance(raw, (int, float)) or isinstance(raw, bool) or not math.isfinite(raw):
                raise ValueError(f"Readiness threshold {name} must be finite")


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    observed: object,
    threshold: object,
    detail: str,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "passed" if passed else "failed",
            "observed": observed,
            "threshold": threshold,
            "detail": detail,
        }
    )


def _missing(checks: list[dict[str, Any]], check_id: str, threshold: object) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "missing",
            "observed": None,
            "threshold": threshold,
            "detail": "required validation evidence was not provided",
        }
    )


def _at_least(observed: object, thresholds: dict[str, Any], name: str) -> bool:
    return _number(observed) >= _number(thresholds[name])


def _at_most(observed: object, thresholds: dict[str, Any], name: str) -> bool:
    return _number(observed) <= _number(thresholds[name])


def _wilson_interval(successes: int, total: int, z: float) -> tuple[float, float]:
    if total <= 0 or not 0 <= successes <= total:
        return 0.0, 1.0
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return _artifact_float(max(0.0, center - radius)), _artifact_float(min(1.0, center + radius))


def summary_counts(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        field: summary.get(field)
        for field in (
            "decisions",
            "terminal_samples",
            "terminal_victories",
            "terminal_defeats",
            "action_value_variation_decisions",
        )
    }


def _load_addressed(path: Path, id_field: str, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load {label} {path}: {error}") from error
    document = _mapping(value, label)
    identifier = document.get(id_field)
    body = {key: item for key, item in document.items() if key != id_field}
    if identifier != manifest_identifier(body):
        raise ValueError(f"{label.capitalize()} identity mismatch")
    return document


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Readiness {label} must be an object")
    return value


def _integer_tuple(value: object, label: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"Readiness {label} must be an array")
    return tuple(_positive_or_zero_integer(item, label) for item in value)


def _binary_tuple(value: object, label: str) -> tuple[int, ...]:
    outcomes = _integer_tuple(value, label)
    if not outcomes or any(outcome not in (0, 1) for outcome in outcomes):
        raise ValueError(f"Readiness {label} must be a non-empty binary array")
    return outcomes


def _positive_integer(value: object, label: str) -> int:
    result = _positive_or_zero_integer(value, label)
    if result <= 0:
        raise ValueError(f"Readiness {label} must be positive")
    return result


def _positive_or_zero_integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"Readiness {label} must be a non-negative integer")
    return value


def _probability(value: object, label: str) -> float:
    result = _finite_number(value, label)
    if not 0.0 <= result <= 1.0:
        raise ValueError(f"Readiness {label} must be a probability")
    return result


def _number(value: object) -> float:
    return _finite_number(value, "metric")


def _finite_number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Readiness {label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Readiness {label} must be finite")
    return result


def _mean(values: tuple[int | float, ...]) -> float:
    if not values:
        raise ValueError("Readiness mean requires values")
    return sum(values) / len(values)


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("Readiness percentile requires values")
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def _artifact_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("Readiness metric must be finite")
    return round(value, 12)
