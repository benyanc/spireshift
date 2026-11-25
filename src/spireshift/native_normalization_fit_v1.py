"""Unchanged PPO with bounded measurements of the trainable correction."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_fit_v1 as original
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_head_policy import HeadState, OwnedDecision
from spireshift.native_a8_head_training import training_examples
from spireshift.native_learning_health_v1 import selected_examples
from spireshift.native_normalized_actor_v1 import (
    CorrectionActor,
    activations,
    reference_scores,
    score_features,
    using_correction_scoring,
)
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec


def geometry(state: HeadState, examples: list[OwnedDecision], temperature: float) -> dict[str, Any]:
    actor = state.model.actor
    if not isinstance(actor, CorrectionActor) or not examples:
        raise ValueError("Require sampled native decisions and the declared correction actor")
    np = _numpy()
    totals = np.zeros(5)
    factors = 0
    for example in examples:
        values = []
        for factor in example.decision.factors:
            _, _, h, _, _, _ = activations(actor, factor.rows)
            scores = np.asarray(score_features(actor, factor.rows))
            reference = np.asarray(reference_scores(actor.reference, factor.rows))
            logs = np.asarray(log_softmax(tuple(map(float, scores)), temperature))
            values.append(
                (
                    float(np.mean(np.abs(h) > 0.95)),
                    float(np.mean(np.ptp(h, axis=0))),
                    -float(np.exp(logs) @ logs) / math.log(len(logs)) if len(logs) > 1 else 0.0,
                    float(np.ptp(reference)),
                    float(np.ptp(scores - reference)),
                )
            )
            factors += 1
        if not values:
            raise ValueError("A delivered native choice needs at least one policy factor")
        totals += np.mean(values, axis=0)
    return {
        "sampled_native_decisions": len(examples),
        "sampled_policy_factors": factors,
        **dict(
            zip(
                (
                    "hidden_saturation_above_abs_0_95",
                    "hidden_range_across_choices",
                    "entropy_fraction_of_uniform",
                    "reference_logit_range",
                    "correction_logit_range",
                ),
                map(float, totals / len(examples)),
                strict=True,
            )
        ),
        "compound_answer_weight": 1,
        "diagnostics_used_as_labels": False,
    }


def fit(
    state: HeadState,
    games: list[tuple[Path, dict[str, Any]]],
    score: TrainingScoreSpec,
    credit: dict[str, Any],
    settings: dict[str, Any],
    round_index: int,
    seed: int,
    deadline: float,
    *,
    control_steps: int | None = None,
) -> tuple[HeadState, dict[str, Any]]:
    sampled = []

    def capture(*args: Any) -> tuple[list[OwnedDecision], dict[str, Any]]:
        examples, evidence = training_examples(*args)
        sampled.extend(selected_examples(examples, games, 4))
        return examples, evidence

    with using_correction_scoring(), patch.object(original, "training_examples", capture):
        after, work = original.fit(
            state,
            games,
            score,
            credit,
            settings,
            round_index,
            seed,
            deadline,
            control_steps=control_steps,
        )
        work["correction_geometry_before"] = geometry(state, sampled, settings["temperature"])
        work["correction_geometry_after"] = geometry(after, sampled, settings["temperature"])
    if not isinstance(after.model.actor, CorrectionActor) or not isinstance(
        state.model.actor, CorrectionActor
    ):
        raise ValueError("PPO dropped the declared correction architecture")
    if after.model.actor.reference != state.model.actor.reference:
        raise ValueError("A copied update changed the frozen reference actor")
    work["reference_actor_unchanged"] = True
    return after, work
