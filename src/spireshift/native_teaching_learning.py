"""Fixed categorical teaching on copied warm states with changed-choice diagnostics."""

from __future__ import annotations

import math
from typing import Any, cast

from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_natural_learning import metrics
from spireshift.native_structured_model import encode
from spireshift.training_objective import TrainingScoreSpec


def diagnostics(
    model: CachedContextModel, bank: dict[str, Any], score: TrainingScoreSpec
) -> dict[str, Any]:
    roots = [r["changed_choices"] for r in bank["lessons"]]
    per_world = []
    for r in roots:
        values = []
        for s in r["steps"]:
            rows, _ = encode(s["public_input"], model, score)
            logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
            action = s["action_index"]
            values.append(
                {
                    "public_input_id": s["public_input_id"],
                    "target_action": action,
                    "target_probability": math.exp(logs[action]),
                    "greedy_matches_target": max(range(len(logs)), key=lambda i: (logs[i], -i))
                    == action,
                }
            )
        per_world.append({"world": r["world"], "changed_choices": values})
    return {
        "reference_plans": metrics(
            model, [r["plans"]["reference_clone"] for r in bank["lessons"]], score
        ),
        "teacher_plans": metrics(
            model, [r["plans"]["teacher_clone"] for r in bank["lessons"]], score
        ),
        "changed_choices": metrics(model, roots, score),
        "per_world_changed_choices": per_world,
        "heldout_inputs_or_outcomes_used": False,
    }
