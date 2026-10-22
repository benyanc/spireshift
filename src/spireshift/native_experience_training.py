"""Same cross-fitted credit and PPO; measure useful whole-game coverage without rewards."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from spireshift.engine_experience import read_native_episode
from spireshift.full_run_ppo_math import Sample
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_structured_training import prepare as original_prepare
from spireshift.training_objective import TrainingScoreSpec


def prepare(
    paths: list[Path],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    cfg: dict[str, Any],
    seeds: list[dict[str, Any]],
    index: int,
    outcomes: list[dict[str, Any]],
) -> tuple[list[Sample], dict[str, Any]]:
    samples, credit = original_prepare(paths, model, score, cfg, seeds, index)
    if sorted(r["seed_id"] for r in outcomes) != sorted(s["id"] for s in seeds):
        raise ValueError("Experience coverage must retain the complete planned denominator")
    cards = sorted({d for r in outcomes for d in r["owned_card_definitions"]})
    relics = sorted({d for r in outcomes for d in r["owned_relic_definitions"]})
    by_size: dict[int, list[float]] = defaultdict(list)
    for s in samples:
        by_size[len(s.rows)].append(s.advantage)
    by_family: dict[str, list[float]] = defaultdict(list)
    sampled = iter(samples)
    for path in paths:
        binding = json.loads(path.read_text())["binding"]
        case = read_native_episode(path, binding)
        if case["status"] != "terminal":
            continue
        navigation = ShopNavigation()
        for row in case["decisions"]:
            public, indices, forced = navigation.view(row["public_input"])
            navigation.advance(row["public_input"], row["choice"]["action_index"])
            if forced:
                continue
            sample = next(sampled)
            if len(sample.rows) != len(indices) or sample.action != indices.index(
                row["choice"]["action_index"]
            ):
                raise ValueError("Per-family credit labels lost their exact sampled decision")
            if len(indices) > 1:
                by_family[public["context"]["interaction"]["kind"]].append(sample.advantage)
        del case
    if next(sampled, None) is not None:
        raise ValueError("Per-family credit scan did not consume the full learning batch")
    credit["experience"] = {
        "independent_planned_worlds": len(seeds),
        "clean_independent_games": credit["clean_complete_training_games"],
        "full_wins": sum(r["status"] == "terminal" and r["victory"] for r in outcomes),
        "act_clearing_games": sum(
            r["status"] == "terminal" and r["completed_acts"] > 0 for r in outcomes
        ),
        "games_reaching_floor_17": sum(
            r["status"] == "terminal" and r["maximum_floor"] >= 17 for r in outcomes
        ),
        "owned_card_definitions": cards,
        "owned_relic_definitions": relics,
        "distinct_owned_card_definitions": len(cards),
        "distinct_owned_relic_definitions": len(relics),
        "credit_by_legal_menu_size": {
            str(n): {
                "decisions": len(v),
                "raw_mean": statistics.fmean(v),
                "negative": sum(a < 0 for a in v),
                "positive": sum(a > 0 for a in v),
            }
            for n, v in sorted(by_size.items())
        },
        "choice_credit_by_family": {
            f: {
                "choice_decisions": len(v),
                "raw_mean": statistics.fmean(v),
                "negative": sum(a < 0 for a in v),
                "positive": sum(a > 0 for a in v),
            }
            for f, v in sorted(by_family.items())
        },
        "coverage_or_HP_added_as_rewards": False,
        "observed_card_relic_interactions_exhaustively_verified": False,
        "selected_logit_coefficients_are_counterfactual_action_quality": False,
    }
    if not all(math.isfinite(s.advantage) for s in samples):
        raise ValueError("Invalid experience credit")
    return samples, credit
