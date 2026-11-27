"""Finite input and numerical-teaching controls; never native optimal-action labels.

Changing a public fact should survive encoding. An arbitrary, explicitly synthetic
label then tests whether a copy of the current actor/Adam can change its preference.
Neither test establishes which native action is good or promotes a checkpoint.
"""

from __future__ import annotations

import copy
import math
from typing import Any, cast

from spireshift.full_run_ppo_math import Adam, Sample
from spireshift.native_action_context import encode, policy
from spireshift.native_conditional_control import teaching_gradient
from spireshift.native_context_cache import CachedContextModel
from spireshift.training_objective import TrainingScoreSpec


def distance(a: dict[int, float], b: dict[int, float]) -> float:
    return math.sqrt(math.fsum((a.get(i, 0) - b.get(i, 0)) ** 2 for i in a.keys() | b.keys()))


def input_checks(
    public: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> dict[str, Any]:
    rows, _ = encode(public, model, score)
    changed = copy.deepcopy(public)
    changed["candidates"].reverse()
    reordered, _ = encode(changed, model, score)
    probes: list[dict[str, Any]] = []

    def probe(name: str, changed: dict[str, Any]) -> None:
        other, _ = encode(changed, model, score)
        diffs = [distance(a, b) for a, b in zip(rows, other, strict=True)]
        # Shared score offsets cannot express a changed action preference by
        # themselves. This measures distinguishability, not the correct direction.
        contrast = max(
            (
                distance(
                    {i: b.get(i, 0) - a.get(i, 0) for i in a.keys() | b.keys()},
                    {i: d.get(i, 0) - c.get(i, 0) for i in c.keys() | d.keys()},
                )
                for a, b in zip(rows[:1], other[:1], strict=True)
                for c, d in zip(rows[1:], other[1:], strict=True)
            ),
            default=0.0,
        )
        probes.append(
            {"fact": name, "maximum_row_change": max(diffs), "relative_row_change": contrast}
        )

    changed = copy.deepcopy(public)
    player = changed["context"]["persistent"]["player"]
    player["hp"] = player["max_hp"] if player["hp"] < player["max_hp"] else 1
    probe("current_health", changed)
    combat = (
        public["context"]["interaction"].get("content", {}).get("context", {}).get("player", {})
    )
    if type(combat.get("energy")) in (int, float):
        changed = copy.deepcopy(public)
        changed["context"]["interaction"]["content"]["context"]["player"]["energy"] += 1
        probe("current_energy", changed)
    for i, candidate in enumerate(public["candidates"]):
        properties = (candidate.get("subject") or {}).get("properties", {})
        cost = properties.get("cost")
        if type(cost) in (int, float) or isinstance(cost, str) and cost.isdigit():
            changed = copy.deepcopy(public)
            changed["candidates"][i]["subject"]["properties"]["cost"] = (
                str(int(cost) + 1) if isinstance(cost, str) else cost + 1
            )
            probe("current_card_cost", changed)
            break
    for i, candidate in enumerate(public["candidates"]):
        match = next(
            (
                j
                for j, a in enumerate(candidate["arguments"])
                if a.get("role") == "target"
                and a.get("entity")
                and type(a["entity"].get("properties", {}).get("hp")) in (int, float)
            ),
            None,
        )
        if match is not None:
            changed = copy.deepcopy(public)
            changed["candidates"][i]["arguments"][match]["entity"]["properties"]["hp"] += 1
            probe("current_target_health", changed)
            break
    for name in ("damage", "block"):
        for i, candidate in enumerate(public["candidates"]):
            stats = (candidate.get("subject") or {}).get("properties", {}).get("stats") or {}
            if type(stats.get(name)) in (int, float):
                changed = copy.deepcopy(public)
                changed["candidates"][i]["subject"]["properties"]["stats"][name] += 1
                probe(f"current_card_{name}", changed)
                break
    return {
        "candidate_order_equivariant": reordered == tuple(reversed(rows)),
        "probes": probes,
        "all_exercised_facts_distinguished": all(p["maximum_row_change"] > 0 for p in probes),
        "scope": "finite_encoder_perturbations_not_native_effect_or_optimal_action_proof",
    }


def teaching_check(
    public: dict[str, Any],
    model: CachedContextModel,
    optimizer: Adam,
    score: TrainingScoreSpec,
    settings: dict[str, Any],
    steps: int = 64,
) -> dict[str, Any]:
    """Teach one invented label on one saved input, using a disposable full-state copy.

    This deliberately stresses the least likely legal action. No native outcome
    or human assessment supplies its label; it is an artificial memorization task.
    All Adam moments are imported, not reset, and no resulting state is saved.
    """
    if type(steps) is not int or not 1 <= steps <= 64:
        raise ValueError("Freeze at most 64 diagnostic numerical updates")
    rows, state, logs = policy(public, model, score, settings["temperature"])
    if len(rows) < 2:
        raise ValueError("A teaching control needs a genuine choice")
    label = min(range(len(logs)), key=lambda i: (logs[i], i))
    before_id, before_adam = model.model_id, optimizer.as_dict()
    sample = Sample(rows, state, label, logs[label], 0.5, 0.0)
    options = {**settings, "entropy_coefficient": 0.0, "value_coefficient": 0.0}
    current, adam = model, optimizer
    for _ in range(steps):
        _, gradient, _ = teaching_gradient(cast(Any, current), [sample], [label], options)
        updated, adam, _ = adam.update(
            cast(Any, current),
            gradient,
            actor_rate=settings["actor_learning_rate"],
            value_rate=0.0,
            maximum_norm=settings["gradient_clip"],
        )
        if not isinstance(updated, CachedContextModel):
            raise ValueError("Teaching control lost its current model identity")
        current = updated
    _, _, after = policy(public, current, score, settings["temperature"])
    original = model.model_id == before_id and optimizer.as_dict() == before_adam
    return {
        "label_source": "invented_known_answer_memorization_control_only",
        "native_action_quality_label": False,
        "label_index": label,
        "label_probability_before": math.exp(logs[label]),
        "label_probability_after": math.exp(after[label]),
        "fixed_steps": steps,
        "starting_optimizer_steps": optimizer.steps,
        "ending_optimizer_steps": adam.steps,
        "probability_increased": after[label] > logs[label],
        "memorization_criterion_passed": math.exp(after[label]) >= 0.75,
        "criterion": "at_least_75_percent_on_one_artificial_label_after_64_steps",
        "source_model_and_all_Adam_state_unchanged": original,
        "diagnostic_model_id": current.model_id,
        "production_optimizer_steps": 0,
        "synthetic_optimizer_steps": adam.steps - optimizer.steps,
        "model_saved_or_promoted": False,
        "not_a_PPO_or_native_gameplay_learning_test": True,
    }
