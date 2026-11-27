"""Versioned public card-effect inputs for a copied shared scoring head."""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_neural import NativeActor, NativeActorCritic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import HeadModel, HeadState
from spireshift.native_a8_head_policy import load as load_legacy
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_model import BASE, resize
from spireshift.native_structured_model import encode as legacy_encode
from spireshift.training_objective import TrainingScoreSpec

HAND_VIEW = "interaction:/context/player/hand/*"
SCHEMA = "native-a8-current-card-display-checkpoint-v1"


def candidate_stats(public: dict[str, Any]) -> tuple[dict[str, float], ...]:
    """Read the current display of the physical card bound to each legal play."""
    interaction = public["context"]["interaction"]
    candidates = public["candidates"]
    if interaction["kind"] != "combat_turn":
        return tuple({} for _ in candidates)
    hand = interaction["content"]["context"]["player"]["hand"]
    by_slot = {card["entity_id"]["public_slot"]: card for card in hand}
    if len(by_slot) != len(hand):
        raise ValueError("The current hand must identify each physical card")

    result = []
    for candidate in candidates:
        stats: dict[str, float] = {}
        if candidate["verb"] == "play":
            subject = candidate["subject"]
            card = by_slot.get(subject["public_slot"])
            if (
                subject["role"] != "playable_card"
                or card is None
                or subject["properties"]["entity_id"] != card["entity_id"]
                or subject["properties"]["definition_id"] != card["definition_id"]
            ):
                raise ValueError("The legal play must refer to its exact current hand card")
            view = card.get("public_card_views", {}).get(HAND_VIEW, {})
            if view.get("can_play") is False:
                raise ValueError("The current card display disagrees with the legal play")
            for name, value in (view.get("stats") or {}).items():
                if type(value) in (int, float) and math.isfinite(value):
                    stats[name] = float(value)
        result.append(stats)
    return tuple(result)


def projection(stats: tuple[str, ...]) -> dict[str, Any]:
    return {
        "id": "native-current-hand-card-display-stats-v1",
        "owner": "combat_turn",
        "verb": "play",
        "public_scope": HAND_VIEW,
        "base_dimension": BASE,
        "columns": list(stats),
        "per_stat": ["presence", "asinh_current_value_divided_by_5"],
    }


def resized_model(parent: HeadModel, size: int) -> NativeActorCritic:
    actor = parent.actor
    weights = resize(parent.weights(), actor.dimension, size, actor.hidden_units)
    split = size * actor.hidden_units + 2 * actor.hidden_units + size
    return NativeActorCritic(
        NativeActor(
            actor.environment_id,
            size,
            actor.hidden_units,
            weights[:split],
            actor.input_normalization,
        ),
        weights[split:],
    )


@dataclass(frozen=True, kw_only=True)
class CardDisplayModel(HeadModel):
    stat_names: tuple[str, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            self.combat_actor is not None
            or not self.stat_names
            or tuple(sorted(set(self.stat_names))) != self.stat_names
            or any(not name or not isinstance(name, str) for name in self.stat_names)
            or self.actor.dimension != BASE + 2 * len(self.stat_names)
        ):
            raise ValueError("Require the declared public card display columns on a shared head")

    @cached_property
    def legacy_view(self) -> CachedContextModel:
        return CachedContextModel(resized_model(self, BASE), self.mode, self.feature_spec_id)

    def view(self, combat: bool) -> CachedContextModel:
        return self

    def body_dict(self) -> dict[str, Any]:
        return {**super().body_dict(), "card_display_encoding": projection(self.stat_names)}


@dataclass(frozen=True, slots=True)
class CardDisplayState(HeadState):
    def document(self) -> dict[str, Any]:
        if not isinstance(self.model, CardDisplayModel):
            raise ValueError("A card display checkpoint must keep its input specification")
        return {
            **HeadState.document(self),
            "schema_version": SCHEMA,
            "card_display_encoding": projection(self.model.stat_names),
        }


def extend(before: HeadState, names: tuple[str, ...]) -> CardDisplayState:
    parent = before.model
    if parent.actor.dimension != BASE or parent.arm != "shared":
        raise ValueError("Extend a 512-input shared parent on a disposable copy")
    size = BASE + 2 * len(names)
    model = CardDisplayModel(
        resized_model(parent, size), parent.mode, parent.feature_spec_id, stat_names=names
    )
    split = model.actor.parameter_count
    first = resize(
        before.actor_adam.first + before.value_adam.first, BASE, size, model.actor.hidden_units
    )
    second = resize(
        before.actor_adam.second + before.value_adam.second, BASE, size, model.actor.hidden_units
    )
    return CardDisplayState(
        model,
        Adam(before.actor_adam.steps, first[:split], second[:split]),
        None,
        Adam(before.value_adam.steps, first[split:], second[split:]),
    )


def load(path: Path) -> tuple[HeadState, str]:
    saved = identified(path, "state_id")
    if saved["schema_version"] != SCHEMA:
        return load_legacy(path)
    base = CachedContextModel.from_mapping(saved["base_model"])
    model = CardDisplayModel(
        base.native,
        base.mode,
        base.feature_spec_id,
        stat_names=tuple(saved["card_display_encoding"]["columns"]),
    )
    state = CardDisplayState(
        model,
        Adam.from_mapping(saved["actor_adam"], model.actor.parameter_count),
        None,
        Adam.from_mapping(saved["value_adam"], len(model.value_weights)),
    )
    if state.document() != {k: v for k, v in saved.items() if k != "state_id"}:
        raise ValueError("Copied card display model or full Adam differs")
    return state, str(saved["state_id"])


def encode(
    public: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...]]:
    if not isinstance(model, CardDisplayModel):
        return legacy_encode(public, model, score)
    rows, state = legacy_encode(public, model.legacy_view, score)
    result = []
    for row, stats in zip(rows, candidate_stats(public), strict=True):
        extra = {}
        for i, name in enumerate(model.stat_names):
            if name in stats:
                extra[BASE + 2 * i] = 1.0
                extra[BASE + 2 * i + 1] = math.asinh(stats[name]) / 5
        result.append({**row, **extra})
    return tuple(result), (*state[:-1], *([0.0] * (2 * len(model.stat_names))), state[-1])
