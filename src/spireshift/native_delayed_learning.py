"""Production sampler, encoding, cross-fit ridge and PPO with diagnostic terminal targets.

The only arm difference is action-independent V: learned public ridge or exact
current-policy expectation in the privileged native tree. No optimal-action labels
enter the actor loss, and no diagnostic trajectory is ordinary full-run experience.
"""

from __future__ import annotations

import math
import random
from dataclasses import replace
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo_math import Sample
from spireshift.native_compact_training import pack
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_delayed_data import ARMS, HORIZON
from spireshift.native_delayed_evaluate import predictions
from spireshift.native_structured_policy import Chooser
from spireshift.native_value_credit import (
    ValueRun,
    fit_baseline,
    fold_assignment,
    prediction_metrics,
    public_value_features,
)
from spireshift.training_objective import TrainingScoreSpec


def learned_predictions(
    runs: list[ValueRun], owners: dict[int, int], credit: dict[str, Any]
) -> tuple[dict[int, tuple[float, ...]], list[dict[str, Any]]]:
    if set(owners) != {r.seed for r in runs} or len(set(owners.values())) < 2:
        raise ValueError("Require grouped complete native worlds for learned baseline fitting")
    representatives = {
        world: replace(next(r for r in runs if owners[r.seed] == world), seed=world)
        for world in set(owners.values())
    }
    assignment = fold_assignment(
        list(representatives.values()),
        min(credit["folds"], len(representatives)),
        credit["fold_salt"],
    )
    predicted: dict[int, tuple[float, ...]] = {}
    reports = []
    for fold in sorted(set(assignment.values())):
        fitting = [r for r in runs if assignment[owners[r.seed]] != fold]
        held = [r for r in runs if assignment[owners[r.seed]] == fold]
        baseline = fit_baseline(fitting, credit["baseline"], credit["regularization"])
        fit_worlds = sorted({owners[r.seed] for r in fitting})
        held_worlds = sorted({owners[r.seed] for r in held})
        if set(fit_worlds) & set(held_worlds):
            raise ValueError("Related families/repeats of a native world leaked across value folds")
        predicted.update({r.seed: baseline.predict(r) for r in held})
        reports.append(
            {
                **baseline.as_dict(),
                "fold": fold,
                "fitting_worlds": fit_worlds,
                "predicted_worlds": held_worlds,
                "predicted_episodes": [r.seed for r in held],
            }
        )
    return predicted, reports


def batch(
    model: CachedContextModel,
    trees: list[dict[str, Any]],
    score: TrainingScoreSpec,
    credit: dict[str, Any],
    arm: str,
    player: int,
    index: int,
) -> tuple[list[Sample], dict[str, Any]]:
    if (
        arm not in ARMS
        or not trees
        or 32 % len(trees)
        or any(t["task"]["seed"]["partition"] != "fit" for t in trees)
    ):
        raise ValueError(
            "Use only fitting worlds, balanced across 32 own-policy diagnostic episodes"
        )
    order = trees * (32 // len(trees))
    random.Random(f"delayed-balanced-worlds-{player}-{index}").shuffle(order)
    samples: list[Sample] = []
    runs: list[ValueRun] = []
    owners: dict[int, int] = {}
    exact: dict[int, tuple[float, ...]] = {}
    traces = []
    cached = (
        {t["task"]["key"]: predictions(model, t, score)[0] for t in trees} if arm == "exact" else {}
    )
    for slot, tree in enumerate(order):
        world = tree["task"]["seed"]["id"]
        episode = index * 1000 + slot
        chooser = Chooser(model, score, f"DELAY{world}P{player}R{index}S{slot}", True)
        name, selected, encoded, baseline_values, history = "root", [], [], [], []
        while not tree["nodes"][name]["terminal"]:
            node = tree["nodes"][name]
            choice = chooser(node["public_input"])
            if choice["navigation_only"] or choice["behavior"] != "sampled_softmax":
                raise ValueError("Every diagnostic decision must use the actual production sampler")
            assert chooser.last is not None
            rows, state, effective, forced = chooser.last
            if forced or effective != node["public_input"]:
                raise ValueError("Never prune or change a diagnostic native menu")
            selected.append(
                Sample(
                    rows, state, choice["effective_action_index"], choice["log_probability"], 0, 0
                )
            )
            encoded.append((public_value_features(effective, score), choice["value"], len(rows)))
            baseline_values.append(cached[tree["task"]["key"]][name] if arm == "exact" else 0.0)
            action = choice["action_index"]
            history.append({"public_input_id": node["public_input_id"], "choice": choice})
            name = node["children"][action]
            if len(history) > HORIZON:
                raise ValueError("A sampled diagnostic path exceeded its declared terminal horizon")
        target = float(tree["nodes"][name]["outcome"])
        runs.append(
            ValueRun(
                episode,
                index,
                target,
                tuple(x[0][0] for x in encoded),
                tuple(x[0][1] for x in encoded),
                tuple(x[1] for x in encoded),
                tuple(x[2] for x in encoded),
            )
        )
        owners[episode] = world
        exact[episode] = tuple(baseline_values)
        samples.extend(pack(replace(s, target=target)) for s in selected)
        traces.append(
            {
                "episode": episode,
                "world": world,
                "case": tree["task"]["key"],
                "history": history,
                "terminal_outcome": target,
                "leaf": name,
            }
        )
    if arm == "learned":
        values, folds = learned_predictions(runs, owners, credit)
    else:
        values, folds = exact, []
    flattened = [v for run in runs for v in values[run.seed]]
    samples = [replace(s, advantage=s.target - v) for s, v in zip(samples, flattened, strict=True)]
    if not all(math.isfinite(s.advantage) for s in samples):
        raise ValueError("Nonfinite delayed credit")
    return samples, {
        "arm": arm,
        "round": index,
        "episodes": len(runs),
        "native_worlds": len(set(owners.values())),
        "decisions": len(samples),
        "choice_decisions": sum(len(s.rows) > 1 for s in samples),
        "sampled_successes": sum(r.target for r in runs),
        "cross_fit": folds,
        "prediction_quality": prediction_metrics(runs, values),
        "sampled_trace_id": manifest_identifier(traces),
        "traces": traces,
        "discount": 1.0,
        "trace_lambda": 1.0,
        "native_game_attempts": 0,
        "ordinary_PPO_eligible": False,
        "student_inputs_public_only": True,
        "same_private_draw_schedule_across_arms": True,
        "baseline": "production_world_grouped_public_residual_ridge"
        if arm == "learned"
        else "exact_current_policy_value_in_privileged_native_tree",
    }
