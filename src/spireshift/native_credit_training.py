"""Explicit native PPO credit variant; ordinary on-policy verification comes first."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Sample
from spireshift.native_value_credit import (
    cross_fitted_predictions,
    prediction_metrics,
    value_run,
)
from spireshift.training_objective import TrainingScoreSpec

CREDIT_ID = "native-whole-run-crossfit-monte-carlo-v1"


def validate_credit_config(root: Path, credit: Any, score_id: str) -> None:
    if credit is None:
        return  # Historical Monte Carlo behavior-critic recipe, explicitly preserved.
    if (
        not isinstance(credit, dict)
        or set(credit)
        != {
            "id",
            "baseline",
            "regularization",
            "folds",
            "fold_salt",
            "discount",
            "trace_lambda",
            "value_study",
            "stored_critic_role",
        }
        or (
            credit["id"] != CREDIT_ID
            or credit["baseline"] != "public_residual_ridge"
            or credit["regularization"] != 0.001
            or credit["folds"] != 4
            or credit["fold_salt"] != "native-whole-run-value-crossfit-v1"
            or credit["discount"] != 1.0
            or credit["trace_lambda"] != 1.0
            or credit["stored_critic_role"] != "diagnostic_only_not_actor_credit"
        )
    ):
        raise ValueError("Native credit must freeze the tested cross-fit, full-return variant")
    ref = credit["value_study"]
    study = json.loads((root / ref["path"]).read_text())
    study_config = json.loads((root / ref["path"]).with_name("config-at-launch.json").read_text())
    if (
        study.get("schema_version") != "native-value-credit-study-v1"
        or study.get("report_id") != ref["id"]
        or study["report_id"]
        != manifest_identifier({k: v for k, v in study.items() if k != "report_id"})
        or study.get("config_id") != manifest_identifier(study_config)
        or study.get("value_control_pass") is not True
        or study.get("selected_baseline") != "public_residual_ridge:0.001"
        or study.get("confirmation_or_development_episodes_opened") != 0
        or study.get("training_runs") != 256
        or study_config["implementation_sha256"]["native_value_credit.py"]
        != _sha_file(root / "src/spireshift/native_value_credit.py")
    ):
        raise ValueError("Native credit does not bind its passed train-only value control")
    source = json.loads((root / study_config["experiment"]["path"]).read_text())
    if source["training_spec"]["id"] != score_id:
        raise ValueError("Credit comparison cannot change the declared bootstrap score")
    for name, digest in study["sources"].items():
        if _sha_file(root / name) != digest:
            raise ValueError("Value study source evidence changed")


def prepare_credit_samples(
    cases: list[dict[str, Any]],
    samples: list[Sample],
    credit: dict[str, Any] | None,
    score: TrainingScoreSpec,
    round: int,
) -> tuple[list[Sample], dict[str, Any] | None]:
    """Change only advantages; actions, old probabilities and critic targets stay exact.

    Fold models are refitted on OTHER whole training runs in this round. They
    never fit the credited game's outcome. The checkpoint's old hashed critic
    continues its identical diagnostic fit, but cannot inject noise into actor
    credit. Lambda=1 adds no TD bootstrap bias. No actor family is frozen.
    """
    if credit is None:
        return samples, None
    if credit.get("id") != CREDIT_ID or credit.get("trace_lambda") != 1:
        raise ValueError("Unvalidated or short-trace native action credit")
    runs = [
        value_run(c, c["score"]["seed"], round, score) for c in cases if c["status"] == "terminal"
    ]
    if len(runs) < 2 or sum(len(r.features) for r in runs) != len(samples):
        raise ValueError("Cross-fit credit needs at least two clean, fully verified whole runs")
    predictions, folds = cross_fitted_predictions(
        sorted(runs, key=lambda r: r.seed),
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    result, offset = [], 0
    for run in runs:
        for value in predictions[run.seed]:
            sample = samples[offset]
            if sample.target != run.target:
                raise ValueError("Credited run and verified PPO target order differ")
            result.append(replace(sample, advantage=run.target - value))
            offset += 1
    body = {
        "schema_version": CREDIT_ID,
        "config": credit,
        "round": round,
        "baseline_models": folds,
        "prediction_quality": prediction_metrics(sorted(runs, key=lambda r: r.seed), predictions),
        "behavior_critic_quality": prediction_metrics(
            sorted(runs, key=lambda r: r.seed), {r.seed: r.behavior_values for r in runs}
        ),
        "independent_training_runs": len(runs),
        "verified_decisions": len(samples),
        "discount": 1.0,
        "trace_lambda": 1.0,
        "target_or_behavior_probability_changed": False,
        "terminal_victory_probability_available": False,
        "claim_scope": "training_only_cross_fitted_return_baseline_not_policy_quality",
    }
    return result, {**body, "report_id": manifest_identifier(body)}
