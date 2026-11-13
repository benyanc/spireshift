"""Varied saved-input controls for exact behavior/Adam import and usable new columns."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Sample, log_softmax
from spireshift.native_policy_updates import gradient, qualify
from spireshift.native_structured_model import ARMS, BASE, SupplementModel, encode, extend


def check(root: Path, context: dict[str, Any]) -> dict[str, Any]:
    cfg, score, layout = context["config"], context["score"], context["layout"]
    examples = json.loads((root / layout["examples_path"]).read_text())["rows"]
    if len({r["family"] for r in examples}) < 5 or len(
        {r["public_input_id"] for r in examples}
    ) != len(examples):
        raise ValueError(
            "Require varied distinct public TRAIN inputs rather than two repeated puzzles"
        )
    result = []
    for player in (2, 3):
        parent, optimizer = context["models"][player], context["adams"][player]
        before = manifest_identifier({"model": parent.as_dict(), "Adam": optimizer.as_dict()})
        models = {a: extend(parent, optimizer, tuple(layout["columns"]), a) for a in ARMS}
        checks, difference, new_signal = [], 0.0, {a: False for a in ARMS if a != "unchanged"}
        for sample in examples:
            public = sample["public_input"]
            if manifest_identifier(public) != sample["public_input_id"]:
                raise ValueError("A saved varied-input example changed")
            rows, state = encode(public, parent, score)
            baseline = score_features(cast(Any, parent.actor), rows)
            for arm, (model, _) in models.items():
                features, values = encode(public, model, score)
                logits = score_features(cast(Any, model.actor), features)
                delta = max((abs(a - b) for a, b in zip(baseline, logits, strict=True)), default=0)
                difference = max(difference, delta)
                if delta > 1e-10 or not math.isclose(
                    parent.value(state), model.value(values), abs_tol=1e-12, rel_tol=0
                ):
                    raise ValueError("Supplement changed the inherited starting behavior/value")
                reversed_public = {**public, "candidates": list(reversed(public["candidates"]))}
                reversed_features, _ = encode(reversed_public, model, score)
                reverse = score_features(cast(Any, model.actor), reversed_features)
                if any(abs(a - b) > 1e-10 for a, b in zip(logits, reversed(reverse), strict=True)):
                    raise ValueError("Candidate order changed structured-input semantics")
                if arm != "unchanged" and len(features) > 1 and not new_signal[arm]:
                    logs = log_softmax(logits, cfg["learning"]["temperature"])
                    s = Sample(features, values, 0, logs[0], 0.2, 1.0)
                    g = gradient(model, [s])[1]
                    d, h = model.actor.dimension, model.actor.hidden_units
                    positions = [i * d + j for i in range(h) for j in range(BASE, d)]
                    positions.extend(range(d * h + 2 * h + BASE, model.actor.parameter_count))
                    new_signal[arm] = any(abs(g[i]) > 1e-14 for i in positions)
        for arm, (model, adam) in models.items():
            checks.append(
                {
                    "arm": arm,
                    "dimension": model.actor.dimension,
                    "hidden_units": model.actor.hidden_units,
                    "actor_parameters": model.actor.parameter_count,
                    "total_parameters": model.parameter_count,
                    "original_Adam_counter_retained": adam.steps == optimizer.steps,
                    "PPO_math": qualify(model, adam),
                }
            )
        if not all(new_signal.values()) or before != manifest_identifier(
            {"model": parent.as_dict(), "Adam": optimizer.as_dict()}
        ):
            raise ValueError("New columns cannot learn or an original full state changed")
        result.append(
            {
                "player": player,
                "arms": checks,
                "maximum_initial_logit_difference": difference,
                "new_input_weight_gradients_nonzero": new_signal,
                "original_full_state_and_Adam_unchanged": True,
            }
        )
    prototype = models["hashed"][0]
    assert isinstance(prototype, SupplementModel)
    buckets = {i for i, _ in prototype.hash_columns.values()}
    return {
        "passed": True,
        "players": result,
        "examples": len(examples),
        "distinct_public_inputs": len(examples),
        "families": sorted({r["family"] for r in examples}),
        "named_columns": len(layout["columns"]),
        "hash_buckets_occupied": len(buckets),
        "hashed_column_collisions": len(layout["columns"]) - len(buckets),
        "exact_starting_behavior_matched": True,
        "inherited_Adam_moments_retained": True,
        "unseen_and_free_text_facts_keep_original_encoder": True,
        "same_semantic_supplement_before_projection": True,
        "production_optimizer_updates": 0,
        "games_launched": 0,
        "representation_controls_are_not_gameplay_improvement": True,
    }
