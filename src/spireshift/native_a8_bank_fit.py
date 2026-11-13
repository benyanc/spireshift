"""World-balanced imitation of delivered public decisions, including ordered answers."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features, score_gradient
from spireshift.full_run_ppo_math import Adam, log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_structured_model import encode
from spireshift.native_win4_plan import PLAN
from spireshift.native_win_teacher import validate_student_input
from spireshift.neural_combat import _numpy
from spireshift.training_objective import TrainingScoreSpec

TEMPERATURE = 0.8
ACTOR_RATE = 0.001
GRADIENT_CLIP = 1.0


@dataclass(frozen=True, slots=True)
class Factor:
    rows: tuple[dict[int, float], ...]
    action: int
    input_id: str


@dataclass(frozen=True, slots=True)
class Decision:
    family: str
    factors: tuple[Factor, ...]


Worlds = dict[str, tuple[Decision, ...]]
Schedule = dict[str, tuple[int, ...]]


def encode_decision(
    label: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> Decision:
    grouped = "answer_factors" in label
    factors = label["answer_factors"] if grouped else [label]
    if grouped and (
        label["decision_contract"] != PLAN or label["label_weight"] != 1.0 or not factors
    ):
        raise ValueError("An ordered answer needs one complete, unit-weight label")
    encoded = []
    for index, factor in enumerate(factors):
        public, action = factor["public_input"], factor["action_index"]
        validate_student_input(public)
        if factor["public_input_id"] != manifest_identifier(public):
            raise ValueError("Saved public menu changed")
        if type(action) is not int or not 0 <= action < len(public["candidates"]):
            raise ValueError("Teacher action must be in the exact current menu")
        candidate = public["candidates"][action]
        surface = public["context"]["interaction"]["content"].get("surface", {})
        compact = surface.get("selection_contract") == PLAN
        if grouped:
            verbs = {"confirm", "cancel"} if index + 1 == len(factors) else {"select"}
            if (
                not compact
                or len(surface["answer_plan"]["selected"]) != index
                or factor["family"] != label["family"]
                or candidate["verb"] not in verbs
            ):
                raise ValueError(
                    "Ordered answers must contain every public prefix and native commit"
                )
        elif compact and candidate["verb"] in {"select", "confirm", "cancel"}:
            raise ValueError("A local ordered factor cannot be a standalone training decision")
        # A forced reinspection is excluded by the saved label reader. On a
        # retained shop choice the public inspected flag gives the exact menu.
        effective, indices, forced = ShopNavigation().view(public)
        if forced or action not in indices:
            raise ValueError("A forced shop action cannot enter the fitting dataset")
        rows, _ = encode(effective, model, score)
        encoded.append(Factor(rows, indices.index(action), manifest_identifier(effective)))
    return Decision(label["family"], tuple(encoded))


def world_schedule(worlds: Worlds, updates: int, salt: str) -> Schedule:
    """One draw per world per update, cycling shuffled choices within each world."""
    if not worlds or updates < 1 or any(not choices for choices in worlds.values()):
        raise ValueError("Fitting needs independent worlds with complete choices")
    schedule = {}
    for world, choices in sorted(worlds.items()):
        order: list[int] = []
        for cycle in range((updates + len(choices) - 1) // len(choices)):
            positions = list(range(len(choices)))
            random.Random(f"win-fit-v1/{salt}/{world}/{cycle}").shuffle(positions)
            order.extend(positions)
        schedule[world] = tuple(order[:updates])
    return schedule


def batch(worlds: Worlds, schedule: Schedule, update: int) -> tuple[Decision, ...]:
    return tuple(worlds[world][indices[update]] for world, indices in schedule.items())


def menu_rows(choices: tuple[Decision, ...]) -> tuple[dict[int, float], ...]:
    return tuple(row for choice in choices for factor in choice.factors for row in factor.rows)


def probabilities(
    model: CachedContextModel, choices: tuple[Decision, ...], rows: tuple[dict[int, float], ...]
) -> Iterator[tuple[tuple[tuple[float, ...], int], ...]]:
    logits = score_features(cast(Any, model.actor), rows)
    offset = 0
    for choice in choices:
        factors = []
        for factor in choice.factors:
            end = offset + len(factor.rows)
            factors.append((log_softmax(logits[offset:end], TEMPERATURE), factor.action))
            offset = end
        yield tuple(factors)


def loss_gradient(
    model: CachedContextModel, choices: tuple[Decision, ...]
) -> tuple[float, tuple[float, ...]]:
    """Mean joint negative log probability, with one label per native decision."""
    if not choices or any(not choice.factors for choice in choices):
        raise ValueError("An optimizer batch needs complete native decisions")
    rows = menu_rows(choices)
    np = _numpy()
    derivatives, losses = [], []
    for factors in probabilities(model, choices, rows):
        for logs, action in factors:
            probs = np.exp(logs)
            probs[action] -= 1.0
            derivatives.extend(probs)
            losses.append(-logs[action])
    scale = 1.0 / (len(choices) * TEMPERATURE)
    gradient = score_gradient(
        cast(Any, model.actor), rows, tuple(float(value) * scale for value in derivatives)
    )
    return math.fsum(losses) / len(choices), gradient + (0.0,) * len(model.value_weights)


def update(
    model: CachedContextModel, adam: Adam, choices: tuple[Decision, ...]
) -> tuple[CachedContextModel, Adam, float]:
    loss, gradient = loss_gradient(model, choices)
    changed, state, _ = adam.update(
        cast(Any, model),
        gradient,
        actor_rate=ACTOR_RATE,
        value_rate=0.0,
        maximum_norm=GRADIENT_CLIP,
    )
    if changed.value_weights != model.value_weights or state.steps != adam.steps + 1:
        raise ValueError("Action imitation must advance Adam once and preserve critic weights")
    return cast(CachedContextModel, changed), state, loss


def metrics(model: CachedContextModel, worlds: Worlds) -> dict[str, dict[str, int | float]]:
    """Teacher-conditioned diagnostics, with a separate mean for each world and family."""
    by_family: dict[str, list[tuple[float, float, int]]] = defaultdict(list)
    for choices in worlds.values():
        observations: dict[str, list[tuple[float, bool]]] = defaultdict(list)
        for choice, factors in zip(
            choices, probabilities(model, choices, menu_rows(choices)), strict=True
        ):
            loss = -math.fsum(logs[action] for logs, action in factors)
            top_one = all(
                max(range(len(logs)), key=logs.__getitem__) == action for logs, action in factors
            )
            category = "combat" if choice.family == "combat_turn" else "strategic"
            for name in ("all", category, choice.family):
                observations[name].append((loss, top_one))
        for name, values in observations.items():
            by_family[name].append(
                (
                    math.fsum(loss for loss, _ in values) / len(values),
                    sum(hit for _, hit in values) / len(values),
                    len(values),
                )
            )
    return {
        name: {
            "worlds": len(values),
            "decisions": sum(count for _, _, count in values),
            "mean_world_joint_nll": math.fsum(loss for loss, _, _ in values) / len(values),
            "mean_world_top_one_agreement": math.fsum(hit for _, hit, _ in values) / len(values),
        }
        for name, values in sorted(by_family.items())
    }
