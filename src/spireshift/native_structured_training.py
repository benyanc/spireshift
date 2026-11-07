"""The same whole-game cross-fitted credit, applied only to each arm's own games."""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.full_run_ppo_math import Sample
from spireshift.native_compact_training import pack
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_policy import CONTRACT, reconstruct
from spireshift.native_value_credit import (
    ValueRun,
    cross_fitted_predictions,
    prediction_metrics,
    public_value_features,
)
from spireshift.training_objective import TrainingScoreSpec


def prepare(
    paths: list[Path],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    cfg: dict[str, Any],
    seed_rows: list[dict[str, Any]],
    index: int,
) -> tuple[list[Sample], dict[str, Any]]:
    expected = {s["id"]: s["seed"] for s in seed_rows}
    if len(expected) != len(seed_rows):
        raise ValueError("Duplicate scheduled game in PPO fitting batch")
    observed: set[int] = set()
    runs: list[ValueRun] = []
    samples: list[Sample] = []
    families: Counter[str] = Counter()
    for path in paths:
        header = json.loads(path.read_text())
        bound = header["binding"]
        if (
            bound["config_id"] != manifest_identifier(cfg)
            or bound["seed_manifest_id"] != cfg["seed_manifest"]["id"]
            or bound["partition"] != "train"
            or bound["panel_purpose"] != "training"
            or bound["model_id"] != model.model_id
            or bound["environment_id"] != model.actor.environment_id
            or bound["training_spec_id"] != score.spec_id
            or bound["policy_contract"] != CONTRACT
            or expected.get(bound["seed_id"]) != bound["native_seed"]
            or bound["seed_id"] in observed
        ):
            raise ValueError("Reject stale, greedy, held-out, duplicated or foreign PPO data")
        observed.add(bound["seed_id"])
        case = read_native_episode(path, bound)
        if case["status"] != "terminal":
            continue
        if not case["native_ending_evidence_agrees"] or case["privileged_fixed_world_teacher"]:
            raise ValueError("Never admit privileged, recovered or unverified PPO episodes")
        outcome = score_episode(case, bound["seed_id"], score)
        if not outcome["completed"]:
            raise ValueError("Do not fit an episode beyond the full-run compute budget")
        original, normalized = reconstruct(
            case, model, score, bound["native_seed"], True, outcome["training_return"]
        )
        features = [public_value_features(r["public_input"], score) for r in normalized]
        runs.append(
            ValueRun(
                bound["seed_id"],
                index,
                outcome["training_return"],
                tuple(x for x, _ in features),
                tuple(p for _, p in features),
                tuple(r["choice"]["value"] for r in normalized),
                tuple(len(r["public_input"]["candidates"]) for r in normalized),
            )
        )
        families.update(r["public_input"]["context"]["interaction"]["kind"] for r in normalized)
        samples.extend(pack(s) for s in original)
        del case, original, normalized, features
    if observed != set(expected) or len(runs) < 2:
        raise ValueError("Require every scheduled attempt and at least two clean whole games")
    credit = cfg["credit"]
    predictions, folds = cross_fitted_predictions(
        sorted(runs, key=lambda r: r.seed),
        credit["baseline"],
        credit["regularization"],
        min(credit["folds"], len(runs)),
        credit["fold_salt"],
    )
    values = [v for run in runs for v in predictions[run.seed]]
    samples = [replace(s, advantage=s.target - v) for s, v in zip(samples, values, strict=True)]
    if not all(math.isfinite(s.advantage) for s in samples):
        raise ValueError("Nonfinite whole-game credit")
    return samples, {
        "round": index,
        "clean_complete_training_games": len(runs),
        "scheduled_games": len(paths),
        "decisions": len(samples),
        "choice_decisions": sum(len(s.rows) > 1 for s in samples),
        "decision_families": dict(families),
        "cross_fit": folds,
        "prediction_quality": prediction_metrics(sorted(runs, key=lambda r: r.seed), predictions),
        "discount": 1.0,
        "trace_lambda": 1.0,
        "oracle_labels": 0,
        "credit_predictor_unchanged": True,
        "hand_written_HP_rewards": False,
        "maximum_raw_episode_histories_retained": 1,
    }
