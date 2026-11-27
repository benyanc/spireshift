"""Known-answer diagnostic learning; no privileged case is ordinary full-run PPO.

PPO samples a contextual bandit backed by observed native action branches. Its
exact action-independent baseline deliberately removes critic estimation noise.
Direct teaching receives the unique native-success action and matches actual
PPO optimizer work. Neither experiment changes the production reward or players.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, fit_round, log_softmax
from spireshift.native_action_context import encode
from spireshift.native_conditional_control import teach_round, teaching_gradient
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import save_state
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_tactical_cases import FAMILIES, qualify_case
from spireshift.training_objective import TrainingScoreSpec


def lessons(root: Path, done: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for value in done.values():
        if value.get("kind") != "tactical_case":
            continue
        saved = json.loads((root / value["lesson_path"]).read_text())
        label = qualify_case(saved["public_input"], [b["outcome"] for b in saved["branches"]])
        if (
            label != saved["best"]
            or manifest_identifier(saved["public_input"]) != value["public_input_id"]
            or value["privileged_fixture"] is not True
            or value["ordinary_PPO_eligible"] is not False
        ):
            raise ValueError("Tactical labels lost their verified native/public ownership")
        result.append({**value, **saved})
    return result


def evaluate(
    model: CachedContextModel, cases: list[dict[str, Any]], score: TrainingScoreSpec
) -> dict[str, Any]:
    rows = []
    for case in cases:
        features, _ = encode(case["public_input"], model, score)
        logs = log_softmax(
            score_features(cast(Any, model.actor), features), SETTINGS["temperature"]
        )
        reversed_logs = log_softmax(
            score_features(cast(Any, model.actor), tuple(reversed(features))),
            SETTINGS["temperature"],
        )
        if any(
            not math.isclose(a, b, rel_tol=0, abs_tol=1e-10)
            for a, b in zip(logs, reversed(reversed_logs), strict=True)
        ):
            raise ValueError("Tactical action probabilities changed under menu permutation")
        label = case["best"]
        rows.append(
            {
                "key": case["task"]["key"],
                "family": case["task"]["family"],
                "public_input_id": case["public_input_id"],
                "correct_probability": math.exp(logs[label]),
                "greedy_correct": max(range(len(logs)), key=lambda i: (logs[i], -i)) == label,
            }
        )
    if not rows:
        raise ValueError("Evaluate a nonempty declared tactical partition")
    return {
        "cases": len(rows),
        "mean_success_probability": math.fsum(r["correct_probability"] for r in rows) / len(rows),
        "minimum_success_probability": min(r["correct_probability"] for r in rows),
        "greedy_accuracy": sum(r["greedy_correct"] for r in rows) / len(rows),
        "candidate_permutation_control_passed": True,
        "families": {
            family: {
                "cases": sum(r["family"] == family for r in rows),
                "mean_success_probability": math.fsum(
                    r["correct_probability"] for r in rows if r["family"] == family
                )
                / sum(r["family"] == family for r in rows),
            }
            for family in FAMILIES
        },
        "rows": rows,
    }


def sample_bandit(
    model: CachedContextModel,
    cases: list[dict[str, Any]],
    score: TrainingScoreSpec,
    count: int,
    seed: str,
) -> tuple[list[Sample], list[int]]:
    """Fresh action samples; oracle state baseline never depends on chosen action."""
    rng = random.Random(seed)
    samples, labels = [], []
    encoded = [encode(c["public_input"], model, score) for c in cases]
    for _ in range(count):
        pos = rng.randrange(len(cases))
        case = cases[pos]
        native_rows, state = encoded[pos]
        order = list(range(len(native_rows)))
        rng.shuffle(order)
        rows = tuple(native_rows[i] for i in order)
        logs = log_softmax(score_features(cast(Any, model.actor), rows), SETTINGS["temperature"])
        draw, cumulative, action = rng.random(), 0.0, len(rows) - 1
        for index, logp in enumerate(logs):
            cumulative += math.exp(logp)
            if draw < cumulative:
                action = index
                break
        outcomes = [case["branches"][i]["outcome"] for i in order]
        value = math.fsum(math.exp(p) * y for p, y in zip(logs, outcomes, strict=True))
        samples.append(
            Sample(rows, state, action, logs[action], outcomes[action], outcomes[action] - value)
        )
        labels.append(order.index(case["best"]))
    return samples, labels


def diagnostic_update(
    model: CachedContextModel,
    optimizer: Adam,
    samples: list[Sample],
    settings: dict[str, Any],
    index: int,
) -> tuple[CachedContextModel, Adam, dict[str, Any]]:
    mean = math.fsum(s.advantage for s in samples) / len(samples)
    variance = math.fsum((s.advantage - mean) ** 2 for s in samples) / len(samples)
    if variance <= 1e-16:
        return (
            model,
            optimizer,
            {
                "sampled_decisions": len(samples),
                "optimizer_steps": 0,
                "epochs_completed": 0,
                "stop_reason": "no_centered_credit_preserve_full_warm_state",
            },
        )
    after, adam, work = fit_round(cast(Any, model), optimizer, samples, settings, index)
    return cast(CachedContextModel, after), adam, work


def fit(
    cfg: dict[str, Any],
    original: CachedContextModel,
    optimizer: Adam,
    score: TrainingScoreSpec,
    cases: list[dict[str, Any]],
    player: int,
    target: Path,
) -> dict[str, Any]:
    from spireshift.full_run_experience import atomic_json

    fitting = [c for c in cases if c["task"]["seed"]["partition"] == "fit"]
    held = [c for c in cases if c["task"]["seed"]["partition"] == "heldout"]
    if {c["task"]["seed"]["id"] for c in fitting} & {c["task"]["seed"]["id"] for c in held}:
        raise ValueError("Never train on a held-out complete native seed")
    before = manifest_identifier({"model": original.as_dict(), "optimizer": optimizer.as_dict()})
    models: dict[str, CachedContextModel] = {
        name: cast(CachedContextModel, original.with_weights(original.weights()))
        for name in ("ppo", "teaching")
    }
    optimizers = {
        name: Adam.from_mapping(optimizer.as_dict(), original.parameter_count) for name in models
    }
    initial = {
        "fit": evaluate(original, fitting, score),
        "heldout": evaluate(original, held, score),
    }
    settings = {
        **SETTINGS,
        "value_coefficient": 0.0,
        "value_learning_rate": 0.0,
        "minibatch_decisions": 64,
    }
    probe, gold = sample_bandit(original, fitting, score, 8, f"tactical-frozen-{player}")
    _, gradient, _ = teaching_gradient(cast(Any, original), probe, gold, settings)
    frozen, _, _ = optimizer.update(
        cast(Any, original), gradient, actor_rate=0.0, value_rate=0.0, maximum_norm=1.0
    )
    if frozen.weights() != original.weights():
        raise ValueError("Frozen-rate negative control moved a saved player")
    curves: list[dict[str, Any]] = []
    for index in range(1, cfg["rounds"] + 1):
        samples, labels = sample_bandit(
            models["ppo"],
            fitting,
            score,
            cfg["sampled_choices_per_round"],
            f"tactical-{player}-{index}",
        )
        ppo, adam, work = diagnostic_update(
            models["ppo"], optimizers["ppo"], samples, settings, index
        )
        if work["optimizer_steps"]:
            teacher, teacher_adam, teacher_work = teach_round(
                cast(Any, models["teaching"]),
                optimizers["teaching"],
                samples,
                labels,
                settings,
                index,
                work,
            )
        else:
            teacher, teacher_adam, teacher_work = (
                cast(Any, models["teaching"]),
                optimizers["teaching"],
                dict(work),
            )
        if work["optimizer_steps"] != teacher_work["optimizer_steps"]:
            raise ValueError("Teaching and sampled-reward diagnostics lost matched actual work")
        models = {
            "ppo": ppo,
            "teaching": cast(CachedContextModel, teacher),
        }
        optimizers = {"ppo": adam, "teaching": teacher_adam}
        curves.append(
            {
                "round": index,
                "fit": {name: evaluate(m, fitting, score) for name, m in models.items()},
                "PPO_work": work,
                "teaching_work": teacher_work,
            }
        )
        if index % 16 == 0 or index == cfg["rounds"]:
            print(
                f"Tactical player {player}, round {index}/{cfg['rounds']}: "
                + "; ".join(
                    f"{name} fitting success probability "
                    f"{curves[-1]['fit'][name]['mean_success_probability']:.1%}"
                    for name in models
                )
                + ". No held-out selection or full-run training.",
                flush=True,
            )
    results = {}
    for name, model in models.items():
        save_state(target / f"{name}-state.json", model, optimizers[name])
        fitting_result, held_result = evaluate(model, fitting, score), evaluate(model, held, score)
        results[name] = {
            "fit": fitting_result,
            "heldout": held_result,
            "criterion_passed": fitting_result["minimum_success_probability"] >= 0.8
            and held_result["minimum_success_probability"] >= 0.75
            and held_result["greedy_accuracy"] == 1.0,
            "model_id": model.model_id,
            "optimizer_steps": optimizers[name].steps,
            "new_optimizer_steps": optimizers[name].steps - optimizer.steps,
        }
    if (
        manifest_identifier({"model": original.as_dict(), "optimizer": optimizer.as_dict()})
        != before
    ):
        raise ValueError("Tactical fitting mutated an original model or optimizer")
    atomic_json(target / "fitting-curves.json", {"initial": initial, "rounds": curves})
    return {
        "kind": "tactical_fit",
        "player": player,
        "initial": initial,
        "methods": results,
        "frozen_actor_control_passed": True,
        "original_full_state_and_Adam_unchanged": True,
        "PPO_baseline": "exact_action_independent_oracle_value_of_native_diagnostic_bandit",
        "ordinary_full_run_PPO_eligible": False,
        "heldout_used_for_selection": False,
        "checkpoint_promoted": False,
    }
