"""Read the whole announced attack for every enemy bound to a legal action."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import (
    native_a8_archive_fit_inputs,
    native_a8_own_experience,
    native_structured_policy,
)
from spireshift import native_a8_card_display_model as display
from spireshift.engine_learning import identified
from spireshift.engine_neural import DIRECT
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_context_cache import CachedContextModel
from spireshift.training_objective import TrainingScoreSpec

SCHEMA = "native-a8-combat-intent-checkpoint-v1"
CONTRACT = "public_bound_enemy_announced_total_damage_v1"
TARGET_ATTACK = DIRECT.index("target_attack")


def intent_total(intent: dict[str, Any]) -> int:
    """Resolve the published attack amount, including conditional Death Blow."""
    damage, hits, total = (intent.get(name) for name in ("damage", "hits", "total_damage"))
    if any(
        type(value) is not int or value < 0 for value in (damage, hits, total) if value is not None
    ):
        raise ValueError("Invalid public enemy damage or hit count")
    if hits == 0 or (hits is not None and damage is None and total is None):
        raise ValueError("Incomplete public enemy hits")
    product = None if damage is None else damage * (1 if hits is None else hits)
    if total is not None:
        if hits is not None and product is not None and total != product:
            raise ValueError("Public enemy per-hit and total damage disagree")
        return int(total)
    if product is not None:
        return int(product)
    if intent.get("type") in {"Attack", "DeathBlow"}:
        raise ValueError("Damage is missing for an announced enemy attack")
    return 0


def candidate_attack(candidate: dict[str, Any]) -> int | None:
    """Sum only the visible intents of distinct, explicitly bound enemies."""
    amounts: dict[int, int] = {}
    for argument in candidate["arguments"]:
        entity = argument.get("entity")
        if argument["role"] != "target" or entity is None or entity["role"] != "enemy":
            continue
        slot = entity["public_slot"]
        amount = sum(intent_total(intent) for intent in entity["properties"]["intents"])
        if amounts.setdefault(slot, amount) != amount:
            raise ValueError("A bound target has conflicting public intent amounts")
    return sum(amounts.values()) if amounts else None


@dataclass(frozen=True, kw_only=True)
class CombatIntentModel(display.CardDisplayModel):
    def body_dict(self) -> dict[str, Any]:
        return {**super().body_dict(), "combat_intent_encoding": CONTRACT}


@dataclass(frozen=True, slots=True)
class CombatIntentState(display.CardDisplayState):
    def document(self) -> dict[str, Any]:
        if not isinstance(self.model, CombatIntentModel):
            raise ValueError("Require the corrected combat intent encoder")
        return {
            **display.CardDisplayState.document(self),
            "schema_version": SCHEMA,
            "combat_intent_encoding": CONTRACT,
        }


def copy_with_intents(parent: HeadState) -> CombatIntentState:
    model = parent.model
    if type(model) is not display.CardDisplayModel:
        raise ValueError("Start from the exact shared-head card display checkpoint")
    updated = CombatIntentModel(
        model.native, model.mode, model.feature_spec_id, stat_names=model.stat_names
    )
    return CombatIntentState(updated, parent.actor_adam, None, parent.value_adam)


def load(path: Path) -> tuple[HeadState, str]:
    saved = identified(path, "state_id")
    if saved["schema_version"] != SCHEMA:
        return display.load(path)
    base = CachedContextModel.from_mapping(saved["base_model"])
    model = CombatIntentModel(
        base.native,
        base.mode,
        base.feature_spec_id,
        stat_names=tuple(saved["card_display_encoding"]["columns"]),
    )
    state = CombatIntentState(
        model,
        Adam.from_mapping(saved["actor_adam"], model.actor.parameter_count),
        None,
        Adam.from_mapping(saved["value_adam"], len(model.value_weights)),
    )
    if state.document() != {key: value for key, value in saved.items() if key != "state_id"}:
        raise ValueError("Combat intent checkpoint identity or complete Adam differs")
    return state, str(saved["state_id"])


def encode(
    public: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec
) -> tuple[tuple[dict[int, float], ...], tuple[float, ...]]:
    rows, state = display.encode(public, model, score)
    if not isinstance(model, CombatIntentModel):
        return rows, state
    for row, candidate in zip(rows, public["candidates"], strict=True):
        total = candidate_attack(candidate)
        if total is not None:
            row[TARGET_ATTACK] = math.asinh(total) / 5
    return rows, state


@contextmanager
def using_intent_encoder() -> Iterator[None]:
    """Bind inference, native PPO reconstruction and archive fitting together."""
    with (
        patch.object(native_structured_policy, "encode", encode),
        patch.object(native_a8_own_experience, "encode", encode),
        patch.object(native_a8_archive_fit_inputs, "encode", encode),
    ):
        yield
