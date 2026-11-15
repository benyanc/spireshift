"""Root-balanced categorical imitation; never regress action scores onto returns."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax
from spireshift.native_conditional_control import teaching_gradient
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_natural_data import ARMS
from spireshift.native_natural_teacher import fight
from spireshift.native_structured_model import encode
from spireshift.training_objective import TrainingScoreSpec


def lessons(
    root: Path, context: dict[str, Any], teacher: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    control = context["config"]["stage"] == "short_control"
    admitted = set(teacher["gate"]["usable_fitting_roots"])
    if control:
        admitted = {
            s["root_id"]
            for s in teacher["summaries"]
            if s["partition"] == "fit" and s["verified"] and s["selected_outcome"] == "win"
        }
    by_id = {r["root_id"]: r for r in context["roots"]}
    result: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for s in teacher["summaries"]:
        if s["root_id"] not in admitted:
            continue
        r = by_id[s["root_id"]]
        if r["partition"] != "fit":
            raise ValueError("Held-out goals, branches and choices cannot fit a student")
        for arm, field in zip(ARMS, ("reference_fight_id", "selected_fight_id"), strict=True):
            saved = next(v for v in teacher["fights"].values() if v["fight_id"] == s[field])
            plan = fight(root, saved)
            if plan["root_id"] != r["root_id"] or plan["status"] != "complete":
                raise ValueError("Bind complete verified labels to their original natural world")
            steps = [step for step in plan["steps"] if len(step["public_input"]["candidates"]) > 1]
            if not steps:
                raise ValueError("A curriculum root needs actual choices")
            result[arm].append({"root_id": r["root_id"], "world": r["world"], "steps": steps})
    if not result[ARMS[0]]:
        raise ValueError("No verified successful natural fitting encounter; preserve evidence")
    if {r["world"] for r in result[ARMS[0]]} != {r["world"] for r in result[ARMS[1]]}:
        raise ValueError("Teacher and reference cloning must use the same fitting worlds")
    return result


def examples(
    model: CachedContextModel,
    roots: list[dict[str, Any]],
    score: TrainingScoreSpec,
    count: int,
    seed: str,
) -> tuple[list[Sample], list[int]]:
    if not roots or count < len(roots):
        raise ValueError("Require bounded root-balanced natural teaching examples")
    ordered = sorted(roots, key=lambda r: r["root_id"])
    rng = random.Random(seed)
    samples, labels = [], []
    for i in range(count):
        # Both arms visit the same worlds. Independent within-world position draws
        # avoid weighting a long fight more merely because it has more decisions.
        selected = ordered[i % len(ordered)]
        step = rng.choice(selected["steps"])
        public, label = step["public_input"], step["action_index"]
        if step["public_input_id"] != manifest_identifier(public):
            raise ValueError("Changed public teaching menu")
        rows, state = encode(public, model, score)
        if type(label) is not int or not 0 <= label < len(rows):
            raise ValueError("Teacher label lies outside the exact current legal menu")
        logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
        samples.append(Sample(rows, state, label, logs[label], 0.0, 0.0))
        labels.append(label)
    return samples, labels


def metrics(
    model: CachedContextModel, roots: list[dict[str, Any]], score: TrainingScoreSpec
) -> dict[str, float]:
    losses, probabilities = [], []
    for r in roots:
        values = []
        for s in r["steps"]:
            rows, _ = encode(s["public_input"], model, score)
            logs = log_softmax(score_features(cast(Any, model.actor), rows), 0.8)
            values.append(logs[s["action_index"]])
        losses.append(-math.fsum(values) / len(values))
        probabilities.append(math.fsum(math.exp(v) for v in values) / len(values))
    return {
        "root_equal_cross_entropy": math.fsum(losses) / len(losses),
        "root_equal_label_probability": math.fsum(probabilities) / len(probabilities),
    }


def epoch(
    model: CachedContextModel,
    adam: Adam,
    roots: list[dict[str, Any]],
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    number: int,
    player: int,
    target: Path,
) -> tuple[CachedContextModel, Adam, dict[str, Any]]:
    before, initial = adam.steps, metrics(model, roots, score)
    for step in range(settings["steps_per_epoch"]):
        samples, labels = examples(
            model,
            roots,
            score,
            settings["batch_choices"],
            f"natural-root-balanced-{player}-{number}-{step}",
        )
        config = {
            "temperature": settings["temperature"],
            "clip": 0.2,
            "entropy_coefficient": 0.0,
            "value_coefficient": 0.0,
        }
        _, gradient, _ = teaching_gradient(cast(Any, model), samples, labels, config)
        value_weights = model.value_weights
        updated, adam, _ = adam.update(
            cast(Any, model),
            gradient,
            actor_rate=settings["actor_learning_rate"],
            value_rate=0.0,
            maximum_norm=settings["gradient_clip"],
        )
        model = cast(CachedContextModel, updated)
        if model.value_weights != value_weights:
            raise ValueError("Categorical imitation must not fit the full-run value head")
    work = {
        "epoch": number,
        "initial": initial,
        "final": metrics(model, roots, score),
        "new_optimizer_steps": adam.steps - before,
        "loss": "categorical_cross_entropy",
        "return_regression": False,
        "heldout_used": False,
        "critic_weights_unchanged": True,
    }
    atomic_json(target / "work.json", work)
    return model, adam, work
