"""Compare assigned feedback on identical shared TRAIN histories, never optimal-action labels."""

from __future__ import annotations

import math
import statistics
from typing import Any


def matched_feedback(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons = []
    cells = {(r["player"], r["arm"]): r for r in results}
    for player in (2, 3):
        if any((player, arm) not in cells for arm in ("batch32", "batch128")):
            continue
        small, large = (cells[player, a] for a in ("batch32", "batch128"))
        s = {r["seed_id"]: r for r in small["per_game_feedback"]}
        b = {r["seed_id"]: r for r in large["per_game_feedback"]}
        shared = sorted(set(s) & set(b))
        matched = [
            k
            for k in shared
            if s[k]["learning_trace_id"] == b[k]["learning_trace_id"]
            and s[k]["choice_mask"] == b[k]["choice_mask"]
        ]
        same = small["before_model_id"] == large["before_model_id"]
        complete = (
            len(s) == small["planned_games"]
            and len(b) == large["planned_games"]
            and set(s) <= set(b)
            and len(matched) == len(s)
            and same
        )
        errors, flips, decisions = [], [], 0
        if complete:
            for seed in matched:
                a, z = s[seed]["raw_advantages"], b[seed]["raw_advantages"]
                mask = s[seed]["choice_mask"]
                if not len(a) == len(z) == len(mask) or not any(mask):
                    raise ValueError("Matched feedback has different choice denominators")
                pair = []
                signs = []
                for result, values in ((small, a), (large, z)):
                    m = result["normalization_and_game_weighting"]
                    if any(type(v) not in (float, int) or not math.isfinite(v) for v in values):
                        raise ValueError("Matched feedback must be finite")
                    pair.append(
                        statistics.fmean(
                            v * v for v, choice in zip(values, mask, strict=True) if choice
                        )
                    )
                    scale = max(m["raw_advantage_std"], 1e-8)
                    signs.append(
                        [
                            1
                            if (v - m["raw_advantage_mean"]) / scale > 0
                            else -1
                            if (v - m["raw_advantage_mean"]) / scale < 0
                            else 0
                            for v in values
                        ]
                    )
                errors.append(pair)
                flips.append(
                    sum(x != y for x, y, choice in zip(*signs, mask, strict=True) if choice)
                )
                decisions += sum(mask)
        comparisons.append(
            {
                "player": player,
                "same_initial_behavior_model": same,
                "shared_clean_worlds": len(shared),
                "identical_learning_histories": len(matched),
                "all_small_batch_games_matched": complete,
                "matched_choice_decisions": decisions if complete else None,
                "normalized_feedback_sign_disagreement_fraction": sum(flips) / decisions
                if decisions
                else None,
                "small_baseline_mse_on_shared_games": statistics.fmean(p[0] for p in errors)
                if errors
                else None,
                "large_baseline_mse_on_shared_games": statistics.fmean(p[1] for p in errors)
                if errors
                else None,
                "mse_weighting": "equal_shared_game_then_equal_choice",
                "scope": "saved_cross_fitted_feedback_not_action_quality_or_new_game_performance",
                "independent_training_replicates": False,
            }
        )
    return comparisons
