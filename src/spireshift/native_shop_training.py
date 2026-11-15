"""Compact PPO from whole games under the versioned shop navigation contract."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.full_run_ppo_math import Sample
from spireshift.native_compact_training import pack
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_shop_policy import CONTRACT, verified_samples
from spireshift.native_value_credit import (
    ValueRun,
    cross_fitted_predictions,
    prediction_metrics,
    public_value_features,
)
from spireshift.training_objective import TrainingScoreSpec


def prepare_compact(
    paths: list[Path],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    credit: dict[str, Any],
    index: int,
) -> tuple[list[Sample], dict[str, Any]]:
    runs = []
    samples: list[Sample] = []
    for path in paths:
        header = json.loads(path.read_text())
        binding = header["binding"]
        if (
            binding["partition"] not in {"train", "control"}
            or binding["panel_purpose"] != "training"
            or binding["model_id"] != model.model_id
            or binding["environment_id"] != model.actor.environment_id
            or binding["training_spec_id"] != score.spec_id
            or binding.get("policy_contract") != CONTRACT
        ):
            raise ValueError("Compact training requires its own current-behavior training games")
        case = read_native_episode(path, binding)
        if case["status"] != "terminal":
            continue
        case["score"] = score_episode(case, binding["seed_id"], score)
        # Never retain raw public/native histories across games.
        original, normalized = verified_samples(
            case, model, score, case["score"]["training_return"], settings["temperature"]
        )
        features = [public_value_features(row["public_input"], score) for row in normalized]
        runs.append(
            ValueRun(
                binding["seed_id"],
                index,
                case["score"]["training_return"],
                tuple(x for x, _ in features),
                tuple(p for _, p in features),
                tuple(row["choice"]["value"] for row in normalized),
                tuple(len(row["public_input"]["candidates"]) for row in normalized),
            )
        )
        samples.extend(pack(s) for s in original)
        del case, original, normalized, features
    if len(runs) < 2 or len({r.seed for r in runs}) != len(runs):
        raise ValueError("Compact cross-fitting needs distinct clean whole games")
    predictions, folds = cross_fitted_predictions(
        sorted(runs, key=lambda r: r.seed),
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    values = [v for run in runs for v in predictions[run.seed]]
    samples = [replace(s, advantage=s.target - v) for s, v in zip(samples, values, strict=True)]
    body = {
        "round": index,
        "clean_complete_training_games": len(runs),
        "decisions": len(samples),
        "choice_decisions": sum(len(s.rows) > 1 for s in samples),
        "cross_fit": folds,
        "prediction_quality": prediction_metrics(sorted(runs, key=lambda r: r.seed), predictions),
        "no_self_outcome_fitting": all(
            set(f["fitting_runs"]).isdisjoint(f["predicted_runs"]) for f in folds
        ),
        "discount": 1.0,
        "trace_lambda": 1.0,
        "hand_written_HP_rewards": False,
        "oracle_labels": 0,
        "row_storage": "readonly_sparse_uint16_float64_v1",
        "maximum_raw_episode_histories_retained": 1,
        "all_source_decisions_retained": False,
        "automatic_inventory_opening_excluded_from_PPO": True,
        "raw_delivery_history_preserved": True,
        "policy_contract": CONTRACT,
    }
    return samples, {**body, "report_id": manifest_identifier(body)}
