"""Saved forecast restoration and descriptive summaries, without refitting or gameplay."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from spireshift.native_inventory_credit_math import METHODS, SALT, runs
from spireshift.native_residual_value import CorrectedValue
from spireshift.native_value_credit import ValueBaseline, fold_assignment
from spireshift.neural_combat import _numpy


def restore_forecasts(
    directory: Path, metadata: dict[str, Any], coarse_folds: list[dict[str, Any]], round: int
) -> dict[str, Any]:
    """Independently restore model arrays; never call a baseline/correction fitter."""
    np = _numpy()
    with np.load(directory / "extracted.npz", allow_pickle=False) as source:
        data = {k: source[k] for k in source.files}
    names = metadata["names"]
    source_runs = runs(data, round)
    assignment = fold_assignment(source_runs, 4, SALT)
    rebuilt = {k: np.full(len(data["world"]), np.nan) for k in (*METHODS, "constant")}
    for fold, saved in enumerate(coarse_folds):
        fitting = tuple(r.seed for r in source_runs if assignment[r.seed] != fold)
        held = [r for r in source_runs if assignment[r.seed] == fold]
        if (
            saved["fold"] != fold
            or set(saved["fitting_runs"]) != set(fitting)
            or saved["predicted_runs"] != [r.seed for r in held]
            or set(fitting) & {r.seed for r in held}
        ):
            raise ValueError("Restored forecast ownership differs")
        baseline = ValueBaseline(
            saved["kind"], saved["regularization"], tuple(saved["weights"]), fitting
        )
        held_mask = np.asarray([assignment[int(g)] == fold for g in data["world"]])
        for run in held:
            rebuilt["current"][data["world"] == run.seed] = baseline.predict(run)
        targets = [r.target for r in source_runs if r.seed in fitting]
        rebuilt["constant"][held_mask] = math.fsum(targets) / len(targets)
        for method in METHODS[1:]:
            with np.load(directory / f"fold-{fold}-{method}.npz", allow_pickle=False) as source:
                arrays = {k: source[k] for k in source.files}
            indices = arrays.pop("indices")
            prefixes = ("deck/", "relic/") if method == "deck_relic" else (method + "/",)
            train = ~held_mask
            expected = np.flatnonzero(
                np.asarray([n.startswith(prefixes) for n in names])
                & np.any(data["inventory_present"][train], axis=0)
            )
            if not np.array_equal(indices, expected):
                raise ValueError("Held-only or unrelated features entered the saved predictor")
            model = CorrectedValue.restore(arrays)
            if model.baseline.as_dict() != baseline.as_dict():
                raise ValueError("Restored inventory correction changed coarse coefficients")
            extra = data["inventory"][:, indices] if len(indices) else np.zeros((len(train), 1))
            inputs = np.column_stack((data["coarse"], extra))
            # Preserve the original matrix batch as well as its rows/columns.
            # A held-only BLAS call can differ by a few ULPs despite equal math.
            rebuilt[method][held_mask] = np.clip(model.forecast(inputs, data["potential"]), 0, 1)[
                held_mask
            ]
    with np.load(directory / "forecasts.npz", allow_pickle=False) as source:
        if set(source.files) != set(rebuilt) or any(
            not np.array_equal(source[k], v) for k, v in rebuilt.items()
        ):
            raise ValueError("Saved out-of-fold forecasts do not restore bit-for-bit")
    return {
        "restored_models": 12,
        "whole_world_ownership_checked": True,
        "all_forecasts_restored_bit_for_bit": True,
        "baseline_or_inventory_refits": 0,
        "player_or_Adam_updates": 0,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"completed_cohorts": 0}
    per_cohort, games = [], []
    for row in rows:
        means = row["forecast"]["prediction"]["mse"]
        per_cohort.append(
            {
                "cohort": row["cohort"],
                "behavior_model_id": row["behavior_model_id"],
                "games": len(row["outcomes"]),
                "mean_squared_error": means,
                "deck_relic_minus_current_mse": means["deck_relic"] - means["current"],
                "inventory_aliases": row["aliases"],
            }
        )
        outcomes = {r["world"]: r for r in row["outcomes"]}
        unfamiliar = {
            g
            for f in row["forecast"]["folds"]
            for g in f["variants"]["deck_relic"]["held_worlds_with_unfamiliar_features"]
        }
        for game in row["forecast"]["prediction"]["per_game"]:
            games.append(
                {
                    **outcomes[game["game"]],
                    "mse": game["mse"],
                    "cohort": row["cohort"],
                    "unfamiliar_inventory_features": game["game"] in unfamiliar,
                }
            )
    methods = (*METHODS, "constant")

    def group(selected: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "cohort_game_observations": len(selected),
            "distinct_worlds": len({g["world"] for g in selected}),
            "mean_squared_error": {
                m: math.fsum(g["mse"][m] for g in selected) / len(selected) if selected else None
                for m in methods
            },
        }

    return {
        "completed_cohorts": len(rows),
        "cohorts": per_cohort,
        "equal_cohort_game_summary": group(games),
        "outcome_groups": {
            "act_clear": group([g for g in games if g["completed_acts"] > 0]),
            "no_act_clear": group([g for g in games if g["completed_acts"] == 0]),
            "floor_ge_17": group([g for g in games if g["maximum_floor"] >= 17]),
            "floor_lt_17": group([g for g in games if g["maximum_floor"] < 17]),
            "unfamiliar_inventory_features": group(
                [g for g in games if g["unfamiliar_inventory_features"]]
            ),
            "all_inventory_features_seen_in_fitting": group(
                [g for g in games if not g["unfamiliar_inventory_features"]]
            ),
        },
        "largest_current_errors": sorted(games, key=lambda g: -g["mse"]["current"])[:8],
        "training_attempts": len(games),
        "distinct_training_worlds": len({g["world"] for g in games}),
        "training_decisions": sum(r["decisions"] for r in rows),
        "wins_in_source_training_games": sum(g["victory"] for g in games),
        "descriptive_only_not_independent_training_replicates": True,
        "matched_first_round_traces_repeat_across_input_arms": True,
        "overlapping_fold_errors_are_not_untouched_confirmation": True,
        "production_baseline_changed": False,
        "stronger_play_or_better_causal_action_credit_established": False,
    }
