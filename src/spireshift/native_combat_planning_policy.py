"""Bounded fixed-world combat shooting and exact replay; never ordinary PPO."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.native_action_context import policy
from spireshift.native_combat_teacher_data import INFORMATION
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_rest_exploration import choose
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_turn_teacher_policy import (
    POST_COMBAT,
    TurnChooser,
    random_seed,
    room,
    round_number,
    validate_plan,
)
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "native_fixed_world_bounded_combat_shooting_v1"
MAX_STEPS = 512
MAX_BYTES = 8_000_000
RANKING = "public_encounter_exit_alive_then_public_remaining_hp_then_proposal_order_v1"


def search_seed(root_id: str, turn_id: str, sample: int) -> int:
    if type(sample) is not int or not 0 <= sample < 4:
        raise ValueError("Freeze four outcome-blind combat proposal streams")
    value = f"native-combat-shooting-v1|{root_id}|{turn_id}|{sample}"
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big")


def combat_exit(origin: dict[str, Any], public: dict[str, Any]) -> dict[str, Any] | None:
    """Observe an alive exit, including escape; never infer a combat victory from HP."""
    validate_public_input(public)
    interaction = public["context"]["interaction"]
    context = interaction.get("content", {}).get("context", {})
    reason = None
    if room(public) != room(origin):
        reason = "public_room_changed"
    elif interaction["kind"] == "combat_turn":
        round_number(public)
    elif context.get("kind") == "selection":
        return None  # End-turn and card-generated choices still belong to this encounter.
    elif context.get("kind") in POST_COMBAT:
        reason = "public_postcombat_menu"
    elif interaction["kind"] == "game_over":
        reason = "public_game_over"
    else:
        raise ValueError(f"Unknown combat-plan boundary ownership: {interaction['kind']}")
    if reason is None:
        return None
    player = public["context"]["persistent"]["player"]
    hp, maximum = player["hp"], player["max_hp"]
    if any(type(v) is not int for v in (hp, maximum)) or maximum <= 0 or hp > maximum:
        raise ValueError("Combat-plan ranking requires explicit public health")
    return {
        "kind": reason,
        "public_input_id": manifest_identifier(public),
        "combat_survived": hp > 0 and reason != "public_game_over",
        "exit_hp": hp,
        "exit_max_hp": maximum,
    }


def validate_fight(plan: dict[str, Any], root: dict[str, Any], turn: dict[str, Any]) -> None:
    validate_plan(turn, root)
    if set(plan) != {
        "schema_version",
        "root_id",
        "initial_turn_id",
        "steps",
        "exit",
        "plan_id",
        "information_scope",
        "ordinary_PPO_eligible",
        "student_inputs_public_only",
    } or (
        plan.get("schema_version") != "native-combat-remainder-plan-v1"
        or plan.get("root_id") != root["root_id"]
        or plan.get("initial_turn_id") != turn["plan_id"]
        or plan.get("information_scope") != INFORMATION
        or plan.get("ordinary_PPO_eligible") is not False
        or plan.get("student_inputs_public_only") is not True
        or plan.get("plan_id")
        != manifest_identifier({k: v for k, v in plan.items() if k != "plan_id"})
    ):
        raise ValueError("Frozen combat remainder identity or scope differs")
    if not isinstance(plan["steps"], list) or len(plan["steps"]) > MAX_STEPS:
        raise ValueError("A combat plan must fit its finite decision cap")
    if len(json.dumps(plan, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("A combat plan must fit its finite storage cap")
    for i, step in enumerate(plan["steps"]):
        if set(step) != {"public_input", "public_input_id", "action_index"}:
            raise ValueError("Combat plans contain only current public inputs and legal actions")
        p, a = step["public_input"], step["action_index"]
        validate_public_input(p)
        if (
            manifest_identifier(p) != step["public_input_id"]
            or type(a) is not int
            or not 0 <= a < len(p["candidates"])
            or combat_exit(root["public_input"], p) is not None
            or (i == 0 and step["public_input_id"] != turn["boundary"].get("public_input_id"))
        ):
            raise ValueError(
                "Combat plan changes its anchor, crosses its exit or uses an illegal action"
            )
    end = plan["exit"]
    terminal = isinstance(end, dict) and end.get("kind") == "native_terminal"
    expected = (
        {"kind", "combat_survived", "exit_hp", "exit_max_hp", "terminal_public_key"}
        if terminal
        else {
            "kind",
            "combat_survived",
            "exit_hp",
            "exit_max_hp",
            "public_input_id",
        }
    )
    if (
        not isinstance(end, dict)
        or set(end) != expected
        or type(end["combat_survived"]) is not bool
    ):
        raise ValueError("Freeze an explicit encounter exit, not a partial combat label")
    if terminal:
        if (
            end["exit_hp"] is not None
            or end["exit_max_hp"] is not None
            or not isinstance(end["terminal_public_key"], str)
        ):
            raise ValueError("Do not invent unobserved HP at a native terminal boundary")
    elif (
        end["kind"] not in {"public_room_changed", "public_postcombat_menu", "public_game_over"}
        or not isinstance(end["public_input_id"], str)
        or any(type(end[k]) is not int for k in ("exit_hp", "exit_max_hp"))
        or end["exit_max_hp"] <= 0
        or end["exit_hp"] > end["exit_max_hp"]
        or end["combat_survived"] != (end["exit_hp"] > 0 and end["kind"] != "public_game_over")
    ):
        raise ValueError("Invalid public encounter exit or HP")
    if not plan["steps"] and (
        (
            turn["boundary"]["kind"] == "native_terminal"
            and (
                not terminal
                or end["terminal_public_key"] != turn["boundary"]["terminal_public_key"]
                or end["combat_survived"] != turn["boundary"]["victory"]
            )
        )
        or (
            turn["boundary"]["kind"] != "native_terminal"
            and end.get("public_input_id") != turn["boundary"]["public_input_id"]
        )
    ):
        raise ValueError("An empty combat remainder must end at the original turn boundary")


class FightChooser:
    def __init__(
        self,
        root: dict[str, Any],
        turn: dict[str, Any],
        model: CachedContextModel,
        score: TrainingScoreSpec,
        *,
        mode: str,
        sample: int,
        repeat: int,
        plan: dict[str, Any] | None = None,
        on_plan: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if mode not in {"search", "evaluation", "baseline"} or (mode == "evaluation") != (
            plan is not None
        ):
            raise ValueError("Declare combat proposal, forced evaluation or unchanged baseline")
        if plan is not None:
            validate_fight(plan, root, turn)
        self.root, self.turn, self.model, self.score = root, turn, model, score
        self.mode, self.sample, self.expected, self.on_plan = mode, sample, plan, on_plan
        self.prefix = TurnChooser(
            root,
            model,
            score,
            first_action=None,
            repeat=repeat,
            temperature=0.8,
            proposal_temperature=1.2,
            plan=turn,
        )
        self.rng = random.Random(random_seed(root["root_id"], "continuation", repeat))
        self.proposal_rng = random.Random(search_seed(root["root_id"], turn["plan_id"], sample))
        self.navigation = ShopNavigation()
        self.steps: list[dict[str, Any]] = []
        self.plan: dict[str, Any] | None = None
        self.index = 0

    def _freeze(self, end: dict[str, Any]) -> None:
        if self.expected is not None:
            if self.index != len(self.expected["steps"]) or end != self.expected["exit"]:
                raise ValueError("Forced combat remainder reached a different native exit")
            frozen = self.expected
        else:
            body = {
                "schema_version": "native-combat-remainder-plan-v1",
                "root_id": self.root["root_id"],
                "initial_turn_id": self.turn["plan_id"],
                "steps": self.steps,
                "exit": end,
                "information_scope": INFORMATION,
                "ordinary_PPO_eligible": False,
                "student_inputs_public_only": True,
            }
            frozen = {**body, "plan_id": manifest_identifier(body)}
            validate_fight(frozen, self.root, self.turn)
        if self.on_plan is not None:
            self.on_plan(frozen)  # Persist before choosing any postcombat action.
        self.plan = frozen

    def finish(self, case: dict[str, Any]) -> None:
        self.prefix.finish(case)
        if self.plan is None and self.prefix.turn_complete and case["status"] == "terminal":
            self._freeze(
                {
                    "kind": "native_terminal",
                    "terminal_public_key": case["terminal_public_key"],
                    "combat_survived": case["victory"],
                    "exit_hp": None,
                    "exit_max_hp": None,
                }
            )

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        validate_public_input(public)
        if not self.prefix.turn_complete:
            original = self.prefix(public)
            if not self.prefix.turn_complete:
                self.navigation.advance(public, original["action_index"])
                return {
                    **original,
                    "policy_contract": CONTRACT,
                    "combat_phase": "verified_initial_turn",
                }
        if self.plan is None:
            end = combat_exit(self.root["public_input"], public)
            if end is not None:
                self._freeze(end)
            elif self.mode == "evaluation":
                assert self.expected is not None
                if self.index >= len(self.expected["steps"]):
                    raise ValueError("Truncated combat plan has not reached its native exit")
                saved = self.expected["steps"][self.index]
                if saved["public_input"] != public:
                    raise ValueError("Combat replay changed a public observation, cost or target")
                _, indices, forced = self.navigation.view(public)
                if saved["action_index"] not in indices:
                    raise ValueError("Combat replay disagrees with current navigation ownership")
                if not forced:
                    self.rng.random()  # Same draw convention as the original continuation.
                action = saved["action_index"]
                self.navigation.advance(public, action)
                self.index += 1
                return {
                    "action_index": action,
                    "public_input_id": manifest_identifier(public),
                    "policy_contract": CONTRACT,
                    "combat_phase": "forced_combat_remainder",
                    "ordinary_PPO_eligible": False,
                }
            else:
                if self.index >= MAX_STEPS:
                    raise ValueError("Combat decision cap; no partial plan or invented exit")
                if self.mode == "search" and self.sample == 0:
                    effective, indices, _ = self.navigation.view(public)
                    logs = policy(effective, self.model, self.score, 1.2)[2]
                    action = indices[max(range(len(logs)), key=lambda j: (logs[j], -j))]
                    selected = {
                        "action_index": action,
                        "public_input_id": manifest_identifier(public),
                        "behavior": "greedy_combat_proposal",
                    }
                    self.navigation.advance(public, action)
                else:
                    selected = choose(
                        self.model,
                        self.score,
                        public,
                        self.navigation,
                        self.proposal_rng if self.mode == "search" else self.rng,
                        1.2 if self.mode == "search" else 0.8,
                        0.0,
                    )
                self.steps.append(
                    {
                        "public_input": public,
                        "public_input_id": manifest_identifier(public),
                        "action_index": selected["action_index"],
                    }
                )
                if len(json.dumps(self.steps, ensure_ascii=False).encode()) > MAX_BYTES:
                    raise ValueError("Combat plan storage cap; preserve the incomplete attempt")
                self.index += 1
                return {
                    **selected,
                    "policy_contract": CONTRACT,
                    "combat_phase": "combat_proposal"
                    if self.mode == "search"
                    else "baseline_combat",
                    "ordinary_PPO_eligible": False,
                }
        selected = choose(self.model, self.score, public, self.navigation, self.rng, 0.8, 0.0)
        return {
            **selected,
            "policy_contract": CONTRACT,
            "combat_phase": "postcombat_continuation",
            "ordinary_PPO_eligible": False,
        }
