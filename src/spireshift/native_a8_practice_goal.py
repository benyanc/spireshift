"""Verify attainable room outcomes from public decisions in prepared practice."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from spireshift.native_a8_own_experience import groups
from spireshift.native_a8_own_policy import OwnPolicy
from spireshift.native_a8_own_training import State
from spireshift.native_win4_plan import AnswerPolicy

KIND = "model_owned_prepared_practice_only"
VARIANT = "own_practice"
TWO_ROOMS = "two_native_combat_reward_transitions"
BOSS_ROOM = "native_boss_reward_transition"


class PracticeGoal:
    def __init__(self, goal: str, act: int) -> None:
        if goal not in {TWO_ROOMS, BOSS_ROOM}:
            raise ValueError("Unknown prepared-practice goal")
        self.goal, self.act = goal, act
        self.room: tuple[int, str] | None = None
        self.completed: dict[int, str] = {}

    def __call__(self, frame: dict[str, Any], start: dict[str, Any]) -> tuple[bool, bool]:
        if start["kind"] != KIND:
            raise ValueError("Prepared practice requires its own training scope")
        if frame["terminal"]:
            if frame["ending"]["victory"] is not False:
                raise ValueError("Prepared practice must finish before a full-run victory")
            return True, False
        context = frame["public_input"]["context"]
        run, player = context["persistent"]["run"], context["persistent"]["player"]
        interaction = context["interaction"]
        facts = interaction["content"].get("context", {})
        floor = run["floor"]
        if run["act"] != self.act:
            raise ValueError("Prepared practice left its declared act before the native goal")
        if self.room is not None and floor != self.room[0]:
            self.room = None
        if interaction["kind"] == "combat_turn":
            self.room = floor, facts["encounter_type"]
        elif (
            self.room is not None
            and interaction["kind"] == "reward_claim"
            and facts.get("reward_kind") == "room_rewards"
            and player["hp"] > 0
        ):
            old = self.completed.setdefault(*self.room)
            if old != self.room[1]:
                raise ValueError("Multiple combat owners share the prepared room outcome")
            self.room = None
        success = (
            len(self.completed) == 2
            if self.goal == TWO_ROOMS
            else ("boss" in self.completed.values())
        )
        return success, success


def policy(ctx: dict[str, Any], start: dict[str, Any], variant: str, model: Any) -> AnswerPolicy:
    if variant != VARIANT or start["kind"] != KIND or start["evaluation_eligible"] is not False:
        raise ValueError("Require a model-only policy on the declared training-only start")
    return AnswerPolicy(OwnPolicy(model, ctx["score"], start["seed"]))


def verify_delivery_counts(state: State, target: Path, episode: dict[str, Any]) -> tuple[int, int]:
    delivered = factors = 0
    for group in groups(target, state[0].model_id):
        delivered += 1
        factors += len(group) - 1
    if (
        delivered != episode["actual_deliveries_independently_verified"]
        or factors != episode["local_answer_factors"]
        or episode["optimizer_updates"] != 0
        or episode["full_run_win"]
    ):
        raise ValueError("Practice choices or their native delivery proof differ")
    return delivered, factors
