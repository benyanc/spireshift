"""One public encoder and critic with a shared or a combat-routed actor."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_own_experience, native_win4_game
from spireshift.engine_learning import identified
from spireshift.engine_neural import NativeActor, NativeActorCritic
from spireshift.full_run_ppo_math import Adam
from spireshift.native_a8_own_policy import AllActions
from spireshift.native_a8_own_ppo import Decision
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_policy import Chooser
from spireshift.native_systematic_selectors_v2 import SelectorBridge, SelectorWorker
from spireshift.native_turn_teacher_policy import room
from spireshift.native_win4_plan import AnswerPolicy
from spireshift.training_objective import TrainingScoreSpec

ARMS = ("shared", "split")
CHECKPOINT_SCHEMA = "native-a8-scoring-heads-state-v1"


@dataclass(frozen=True)
class HeadModel(CachedContextModel):
    combat_actor: NativeActor | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        actor = self.combat_actor
        if actor is not None and (
            actor.environment_id,
            actor.dimension,
            actor.hidden_units,
            actor.input_normalization,
        ) != (
            self.actor.environment_id,
            self.actor.dimension,
            self.actor.hidden_units,
            self.actor.input_normalization,
        ):
            raise ValueError("Both scoring heads require the same frozen public encoding")

    @property
    def arm(self) -> str:
        return "split" if self.combat_actor is not None else "shared"

    @cached_property
    def base_view(self) -> CachedContextModel:
        return CachedContextModel(self.native, self.mode, self.feature_spec_id)

    @cached_property
    def combat_view(self) -> CachedContextModel:
        if self.combat_actor is None:
            return self.base_view
        return CachedContextModel(
            NativeActorCritic(self.combat_actor, self.value_weights),
            self.mode,
            self.feature_spec_id,
        )

    def view(self, combat: bool) -> CachedContextModel:
        return self.combat_view if combat else self.base_view

    def head(self, combat: bool) -> str:
        return "shared" if self.combat_actor is None else "combat" if combat else "strategy"

    def body_dict(self) -> dict[str, Any]:
        body = super().body_dict()
        if self.combat_actor is not None:
            body = {**body, "combat_actor": self.combat_actor.as_dict()}
        return body


@dataclass(frozen=True, slots=True)
class HeadState:
    model: HeadModel
    actor_adam: Adam
    combat_adam: Adam | None
    value_adam: Adam

    def __post_init__(self) -> None:
        actor, combat = self.model.actor, self.model.combat_actor
        if (
            (combat is None) != (self.combat_adam is None)
            or len(self.actor_adam.first) != actor.parameter_count
            or len(self.actor_adam.second) != actor.parameter_count
            or len(self.value_adam.first) != len(self.model.value_weights)
            or len(self.value_adam.second) != len(self.model.value_weights)
            or (
                self.combat_adam is not None
                and (
                    len(self.combat_adam.first) != actor.parameter_count
                    or len(self.combat_adam.second) != actor.parameter_count
                )
            )
        ):
            raise ValueError("Every scoring head and the critic require their full Adam state")

    def document(self) -> dict[str, Any]:
        actor = self.model.combat_actor
        return {
            "schema_version": CHECKPOINT_SCHEMA,
            "arm": self.model.arm,
            "base_model": self.model.base_view.as_dict(),
            "combat_actor": None if actor is None else actor.as_dict(),
            "model_id": self.model.model_id,
            "actor_adam": self.actor_adam.as_dict(),
            "combat_adam": None if self.combat_adam is None else self.combat_adam.as_dict(),
            "value_adam": self.value_adam.as_dict(),
        }


def initialize(model: CachedContextModel, adam: Adam, arm: str) -> HeadState:
    if arm not in ARMS or len(adam.first) != model.parameter_count:
        raise ValueError("Require one exact frozen checkpoint with full Adam")
    n = model.actor.parameter_count
    actor_adam = Adam(adam.steps, adam.first[:n], adam.second[:n])
    value_adam = Adam(adam.steps, adam.first[n:], adam.second[n:])
    split = arm == "split"
    return HeadState(
        HeadModel(model.native, model.mode, model.feature_spec_id, model.actor if split else None),
        actor_adam,
        actor_adam if split else None,
        value_adam,
    )


def save(path: Path, state: HeadState) -> str:
    return str(native_win4_game.write(path, state.document(), "state_id")["state_id"])


def load(path: Path) -> tuple[HeadState, str]:
    row = identified(path, "state_id")
    base = CachedContextModel.from_mapping(row["base_model"])
    n = base.actor.parameter_count
    combat = row["combat_actor"]
    combat_adam = row["combat_adam"]
    state = HeadState(
        HeadModel(
            base.native,
            base.mode,
            base.feature_spec_id,
            None if combat is None else NativeActor.from_mapping(combat),
        ),
        Adam.from_mapping(row["actor_adam"], n),
        None if combat_adam is None else Adam.from_mapping(combat_adam, n),
        Adam.from_mapping(row["value_adam"], len(base.value_weights)),
    )
    if state.document() != {name: value for name, value in row.items() if name != "state_id"}:
        raise ValueError("Scoring heads or their complete optimizer state differ")
    return state, str(row["state_id"])


class HeadChooser(Chooser):
    def __init__(self, model: HeadModel, score: TrainingScoreSpec, seed: str) -> None:
        super().__init__(model, score, seed, training=True)
        self.navigation = AllActions()

    def combat(self, public: dict[str, Any]) -> bool:
        interaction = public["context"]["interaction"]
        context = interaction["content"].get("context", {})
        # The repaired projection keeps the visible combat context on an owned
        # card selector, including every local factor of a large answer.
        if interaction["kind"] == "card_selection" and context.get("kind") == "combat":
            self.active = room(public)
            return True
        return super().combat(public)

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        model = self.model
        if not isinstance(model, HeadModel):
            raise ValueError("Require the exact routed checkpoint")
        combat = self.combat(public)
        self.model = model.view(combat)
        try:
            choice = super().__call__(public)
        finally:
            self.model = model
        if choice["combat_owned"] is not combat:
            raise ValueError("A public decision cannot change scoring owner during inference")
        return {**choice, "model_id": model.model_id, "scoring_head": model.head(combat)}


def policy(
    ctx: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
) -> AnswerPolicy:
    if not isinstance(model, HeadModel):
        raise ValueError("Scoring-head study requires a versioned head checkpoint")
    # Reuse the normal-start and exact delivery guards on both comparison arms.
    result = _normal_policy(ctx, start, variant, model)
    result.core.chooser = HeadChooser(model, ctx["score"], start["seed"])
    return result


_normal_policy = native_a8_own_experience.policy


def play(
    ctx: dict[str, Any],
    task: dict[str, Any],
    directory: Path,
    state: HeadState,
    deadline: float,
) -> dict[str, Any]:
    with (
        patch.multiple(native_a8_own_experience, worker=SelectorWorker, policy=policy),
        patch.object(native_win4_game, "JsonLines", SelectorBridge),
    ):
        return native_a8_own_experience.play(ctx, task, directory, state.model, deadline)


@dataclass(frozen=True, slots=True)
class OwnedDecision:
    combat: bool
    decision: Decision


def owned_decisions(
    directory: Path, model: HeadModel, samples: Sequence[Decision]
) -> Iterator[OwnedDecision]:
    groups = native_a8_own_experience.groups(directory, model.model_id)
    for decision, group in zip(samples, groups, strict=True):
        combat = group[0][1]["combat_owned"]
        if type(combat) is not bool or any(
            choice["combat_owned"] is not combat or choice["scoring_head"] != model.head(combat)
            for _, choice in group
        ):
            raise ValueError("A native decision or ordered answer crossed scoring heads")
        yield OwnedDecision(combat, decision)
