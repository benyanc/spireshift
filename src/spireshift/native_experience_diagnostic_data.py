"""Restore saved credit and behavior from one sealed TRAIN episode at a time; no fits."""

from __future__ import annotations

import json
import math
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import read_native_episode, score_episode
from spireshift.full_run_ppo_math import Sample
from spireshift.native_compact_training import pack
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_inventory_credit_data import verify_binding
from spireshift.native_inventory_credit_features import inventory
from spireshift.native_structured_policy import reconstruct
from spireshift.native_training_diagnostics import decision_meta
from spireshift.native_value_credit import (
    ValueBaseline,
    ValueRun,
    fold_assignment,
    prediction_metrics,
    public_value_features,
)
from spireshift.training_objective import TrainingScoreSpec


def restore_predictions(
    runs: list[ValueRun], rows: list[dict[str, Any]], credit: dict[str, Any]
) -> dict[int, tuple[float, ...]]:
    """Require the original whole-game folds; no outcome fits its own baseline."""
    runs = sorted(runs, key=lambda r: r.seed)
    n = min(credit["folds"], len(runs))
    owners = fold_assignment(runs, n, credit["fold_salt"])
    if len(rows) != n or [r["fold"] for r in rows] != list(range(n)):
        raise ValueError("Saved credit folds are incomplete or duplicated")
    predictions = {}
    for row in rows:
        held = [r for r in runs if owners[r.seed] == row["fold"]]
        fitting = tuple(r.seed for r in runs if owners[r.seed] != row["fold"])
        weights = tuple(row["weights"])
        if any(type(w) not in (int, float) or not math.isfinite(w) for w in weights):
            raise ValueError("Saved baseline coefficients must be finite")
        model = ValueBaseline(credit["baseline"], credit["regularization"], weights, fitting)
        if row != {
            **model.as_dict(),
            "fold": row["fold"],
            "predicted_runs": [r.seed for r in held],
        }:
            raise ValueError("Saved baseline ownership, features or regularization differs")
        predictions.update({r.seed: model.predict(r) for r in held})
    return predictions


def prepare(
    root: Path,
    cfg: dict[str, Any],
    task: dict[str, Any],
    paths: list[str],
    before: CachedContextModel,
    score: TrainingScoreSpec,
    saved_credit: dict[str, Any],
    deadline: float,
) -> tuple[list[Sample], list[dict[str, Any]], dict[str, Any]]:
    expected = {s["id"]: s["seed"] for s in task["seeds"]}
    observed: set[int] = set()
    samples: list[Sample] = []
    runs: list[ValueRun] = []
    metadata, outcomes, failures = [], [], []
    traces: dict[int, str] = {}
    cards, relics, decks, relic_states = set(), set(), set(), set()
    for name in paths:
        if time.monotonic() >= deadline:
            raise TimeoutError("Saved TRAIN diagnostic reached its finite cap")
        path = root / name
        binding = json.loads(path.read_text())["binding"]
        verify_binding(binding, cfg, before.model_id, expected)
        seed = binding["seed_id"]
        if seed in observed or binding["environment_id"] != before.actor.environment_id:
            raise ValueError("Duplicate game or foreign observation environment")
        observed.add(seed)
        case = read_native_episode(path, binding)
        if case["seed"] != expected[seed]:
            raise ValueError("Saved native world differs from the bound TRAIN world")
        if case["status"] != "terminal":
            failures.append(seed)  # The sealed collector accounts for these; never fit them.
            del case
            continue
        outcome = score_episode(case, seed, score)
        if not outcome["completed"] or case.get("native_ending_evidence_agrees") is not True:
            raise ValueError("Do not diagnose incomplete or over-budget games as clean TRAIN data")
        original, normalized = reconstruct(
            case, before, score, expected[seed], True, outcome["training_return"]
        )
        features = [public_value_features(r["public_input"], score) for r in normalized]
        runs.append(
            ValueRun(
                seed,
                task["round"],
                outcome["training_return"],
                tuple(x for x, _ in features),
                tuple(p for _, p in features),
                tuple(r["choice"]["value"] for r in normalized),
                tuple(len(r["public_input"]["candidates"]) for r in normalized),
            )
        )
        samples.extend(pack(s) for s in original)
        traces[seed] = manifest_identifier(
            [
                [r["choice"]["effective_input_id"], r["choice"]["effective_action_index"]]
                for r in normalized
            ]
        )
        for i, row in enumerate(normalized):
            public = row["public_input"]
            m = decision_meta(public, row["choice"]["effective_action_index"])
            metadata.append({**m, "seed_id": seed, "decision": i})
            if len(public["candidates"]) > 1:
                owned = inventory(public)
                cards.update(owned["deck_definitions"])
                relics.update(owned["relic_definitions"])
                decks.add(owned["deck_signature"])
                relic_states.add(owned["relic_signature"])
        last = decision_meta(
            case["decisions"][-1]["public_input"], case["decisions"][-1]["choice"]["action_index"]
        )
        outcomes.append(
            {
                "seed_id": seed,
                "victory": case["victory"],
                "maximum_floor": case["maximum_floor"],
                "completed_acts": case["completed_acts"],
                "decisions": len(case["decisions"]),
                "last_public_family": last["family"],
                "last_public_hp_fraction": last["hp_fraction"],
                "last_public_encounter_type": last["encounter_type"],
                "last_public_enemies": last["enemies"],
                "causal_death_reason_available": False,
            }
        )
        del case, original, normalized, features
    if observed != set(expected) or len(runs) < 2:
        raise ValueError("Preserve every scheduled attempt and at least two clean games")
    predicted = restore_predictions(runs, saved_credit["cross_fit"], cfg["credit"])
    values = [v for run in runs for v in predicted[run.seed]]
    samples = [replace(s, advantage=s.target - v) for s, v in zip(samples, values, strict=True)]
    metrics = prediction_metrics(sorted(runs, key=lambda r: r.seed), predicted)
    if (
        len(samples) != saved_credit["decisions"]
        or sum(len(s.rows) > 1 for s in samples) != saved_credit["choice_decisions"]
        or len(runs) != saved_credit["clean_complete_training_games"]
        or len(paths) != saved_credit["scheduled_games"]
        or any(
            not math.isclose(v, saved_credit["prediction_quality"][k], abs_tol=1e-12, rel_tol=0)
            if type(v) in (float, int)
            else v != saved_credit["prediction_quality"][k]
            for k, v in metrics.items()
        )
    ):
        raise ValueError(
            "Saved sample denominator or original credit prediction does not reconstruct"
        )
    return (
        samples,
        metadata,
        {
            "planned_games": len(expected),
            "games": len(runs),
            "failed_source_seed_ids": failures,
            "wins": sum(r["victory"] for r in outcomes),
            "outcomes": outcomes,
            "credit_reconstruction": {
                "prediction_quality": metrics,
                "folds_restored": len(saved_credit["cross_fit"]),
                "baseline_refits": 0,
                "own_outcome_fits": 0,
            },
            "inventory_coverage": {
                "distinct_deck_signatures": len(decks),
                "distinct_relic_signatures": len(relic_states),
                "distinct_card_definitions": len(cards),
                "distinct_relic_definitions": len(relics),
            },
            "per_game_feedback": [
                {
                    "seed_id": run.seed,
                    "learning_trace_id": traces[run.seed],
                    "raw_advantages": [run.target - v for v in predicted[run.seed]],
                    "choice_mask": [n > 1 for n in run.choices],
                }
                for run in runs
            ],
            "maximum_raw_episode_histories_retained": 1,
        },
    )
