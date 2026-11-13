"""Public complete-turn proposals and exact replay, separate from ordinary PPO."""

from __future__ import annotations

import hashlib
import json
import math
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
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "native_fixed_world_complete_turn_comparison_v1"
MAX_STEPS = 64
MAX_PLAN_BYTES = 1_000_000
POST_COMBAT = {"reward_flow", "reward", "map", "rest", "shop", "treasure", "event"}


def random_seed(root_id: str, namespace: str, number: int) -> int:
    if namespace not in {"proposal", "continuation"} or type(number) is not int or number < 0:
        raise ValueError("Declare a separate finite proposal or continuation stream")
    value = f"native-complete-turn-v1|{root_id}|{namespace}|{number}"
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big")


def room(public: dict[str, Any]) -> tuple[int, int, str]:
    value = public["context"]["persistent"]["run"]
    act, floor, definition = value["act"], value["floor"], value["act_definition_id"]
    if type(act) is not int or type(floor) is not int or not isinstance(definition, str):
        raise ValueError("Complete-turn boundaries require explicit public room ownership")
    return act, floor, definition


def round_number(public: dict[str, Any]) -> int:
    context = public["context"]["interaction"]["content"]["context"]
    value = context.get("round")
    if context.get("kind") != "combat" or type(value) is not int or value < 1:
        raise ValueError("Complete-turn boundaries require an explicit native public round")
    return value


def boundary(
    root_public: dict[str, Any], public: dict[str, Any], *, end_turn_sent: bool = False
) -> dict[str, Any] | None:
    """Selections remain in the plan until a public combat/room boundary is visible.

    End-turn-triggered choices are included. A kill/automatic end does not need an
    invented end-turn action. No hidden combat ID, draw order or private owner is read.
    """
    validate_public_input(public)
    interaction = public["context"]["interaction"]
    kind = interaction["kind"]
    context = interaction.get("content", {}).get("context", {})
    reason = None
    if room(public) != room(root_public):
        reason = "public_room_changed"
    elif kind == "combat_turn":
        if round_number(public) != round_number(root_public):
            reason = "native_public_round_changed"
        elif end_turn_sent:
            reason = "native_end_turn_returned_to_combat"
    elif context.get("kind") == "selection":
        return None
    elif context.get("kind") in POST_COMBAT or kind == "game_over":
        reason = "public_postcombat_menu"
    else:
        raise ValueError(f"Unknown complete-turn boundary ownership: {kind}")
    return {"kind": reason, "public_input_id": manifest_identifier(public)} if reason else None


def validate_plan(plan: dict[str, Any], root: dict[str, Any]) -> None:
    if set(plan) != {
        "schema_version",
        "root_id",
        "public_input_id",
        "steps",
        "boundary",
        "plan_id",
        "information_scope",
        "ordinary_PPO_eligible",
        "student_inputs_public_only",
    } or (
        plan.get("schema_version") != "native-complete-turn-plan-v1"
        or plan.get("root_id") != root["root_id"]
        or plan.get("public_input_id") != root["public_input_id"]
        or plan.get("information_scope") != INFORMATION
        or plan.get("ordinary_PPO_eligible") is not False
        or plan.get("student_inputs_public_only") is not True
        or plan.get("plan_id")
        != manifest_identifier({k: v for k, v in plan.items() if k != "plan_id"})
    ):
        raise ValueError("Frozen complete-turn plan identity or information scope differs")
    if not 1 <= len(plan["steps"]) <= MAX_STEPS:
        raise ValueError("A complete turn needs its bounded, nonempty public action trace")
    if len(json.dumps(plan, ensure_ascii=False).encode()) > MAX_PLAN_BYTES:
        raise ValueError("Complete-turn public plan exceeds its finite storage bound")
    end_turn_sent = False
    for i, step in enumerate(plan["steps"]):
        if set(step) != {"public_input", "public_input_id", "action_index"}:
            raise ValueError("Only public observations and legal choices belong in a turn plan")
        p, a = step["public_input"], step["action_index"]
        validate_public_input(p)
        if (
            step["public_input_id"] != manifest_identifier(p)
            or type(a) is not int
            or not 0 <= a < len(p["candidates"])
            or boundary(root["public_input"], p, end_turn_sent=end_turn_sent) is not None
            or (i == 0 and p != root["public_input"])
        ):
            raise ValueError("Frozen plan has a changed root, illegal choice or cross-turn action")
        end_turn_sent |= p["candidates"][a]["verb"] == "end_turn"
    end = plan["boundary"]
    if not isinstance(end, dict) or (
        set(end) != {"kind", "public_input_id"}
        if end.get("kind") != "native_terminal"
        else set(end) != {"kind", "terminal_public_key", "victory"}
    ):
        raise ValueError("Freeze an explicit public turn boundary")
    if end["kind"] not in {
        "public_room_changed",
        "native_public_round_changed",
        "native_end_turn_returned_to_combat",
        "public_postcombat_menu",
        "native_terminal",
    }:
        raise ValueError("Unknown frozen turn boundary")
    if end["kind"] == "native_terminal":
        if not isinstance(end["terminal_public_key"], str) or type(end["victory"]) is not bool:
            raise ValueError("Terminal turn boundaries need their public ending and binary outcome")
    elif not isinstance(end["public_input_id"], str):
        raise ValueError("Turn boundaries need their exact public observation identity")


class TurnChooser:
    def __init__(
        self,
        root: dict[str, Any],
        model: CachedContextModel,
        score: TrainingScoreSpec,
        *,
        first_action: int | None,
        repeat: int,
        temperature: float,
        proposal_temperature: float,
        plan: dict[str, Any] | None = None,
        on_plan: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if first_action is not None and (
            type(first_action) is not int
            or not 0 <= first_action < len(root["public_input"]["candidates"])
        ):
            raise ValueError("Proposal first action is outside the full legal root menu")
        validate_public_input(root["public_input"])
        round_number(root["public_input"])
        if plan is not None:
            validate_plan(plan, root)
        self.root, self.model, self.score = root, model, score
        self.first_action, self.expected, self.on_plan = first_action, plan, on_plan
        self.temperature, self.proposal_temperature = temperature, proposal_temperature
        self.proposal_rng = random.Random(
            random_seed(root["root_id"], "proposal", first_action or 0)
        )
        self.continuation_rng = random.Random(random_seed(root["root_id"], "continuation", repeat))
        self.navigation = ShopNavigation()
        self.index = self.turn_index = 0
        self.root_reached = self.turn_complete = False
        self.end_turn_sent = False
        self.steps: list[dict[str, Any]] = []
        self.plan: dict[str, Any] | None = None

    def _freeze(self, end: dict[str, Any]) -> None:
        if self.expected is not None:
            if self.turn_index != len(self.expected["steps"]) or end != self.expected["boundary"]:
                raise ValueError("Frozen complete turn reached a different public boundary")
            self.plan = self.expected
        else:
            body = {
                "schema_version": "native-complete-turn-plan-v1",
                "root_id": self.root["root_id"],
                "public_input_id": self.root["public_input_id"],
                "steps": self.steps,
                "boundary": end,
                "information_scope": INFORMATION,
                "ordinary_PPO_eligible": False,
                "student_inputs_public_only": True,
            }
            proposed = {**body, "plan_id": manifest_identifier(body)}
            validate_plan(proposed, self.root)
            if self.on_plan is not None:
                self.on_plan(proposed)  # Freeze before the first continuation choice/outcome.
            self.plan = proposed
        self.turn_complete = True

    def finish(self, case: dict[str, Any]) -> None:
        if self.turn_complete:
            return
        if self.root_reached and case["status"] == "terminal":
            self._freeze(
                {
                    "kind": "native_terminal",
                    "terminal_public_key": case["terminal_public_key"],
                    "victory": case["victory"],
                }
            )

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        identity, index = manifest_identifier(public), self.index
        self.index += 1
        prefix = self.root["prefix"]
        if index < len(prefix):
            saved = prefix[index]
            if saved["public_input_id"] != identity:
                raise ValueError(f"Complete-turn source prefix mismatch at decision {index}")
            action, phase = saved["action_index"], "verified_source_prefix"
        else:
            if index == len(prefix):
                if public != self.root["public_input"] or identity != self.root["public_input_id"]:
                    raise ValueError("Complete-turn public root mismatch")
                self.root_reached = True
            if not self.turn_complete:
                end = boundary(self.root["public_input"], public, end_turn_sent=self.end_turn_sent)
                if end is not None:
                    self._freeze(end)
                elif self.expected is not None:
                    if self.turn_index >= len(self.expected["steps"]):
                        raise ValueError("Truncated plan has not completed the native turn")
                    saved = self.expected["steps"][self.turn_index]
                    if saved["public_input"] != public or saved["public_input_id"] != identity:
                        raise ValueError("Frozen complete-turn observation or target order differs")
                    action, phase = saved["action_index"], "forced_frozen_turn"
                    self.turn_index += 1
                else:
                    if self.turn_index >= MAX_STEPS:
                        raise ValueError(
                            "Complete-turn decision cap; no forced end or partial label"
                        )
                    if self.turn_index == 0 and self.first_action is not None:
                        action = self.first_action
                    else:
                        _, _, logs = policy(
                            public, self.model, self.score, self.proposal_temperature
                        )
                        if self.first_action is None:
                            action = max(range(len(logs)), key=lambda j: (logs[j], -j))
                        else:
                            draw, cumulative, action = (
                                self.proposal_rng.random(),
                                0.0,
                                len(logs) - 1,
                            )
                            for j, logp in enumerate(logs):
                                cumulative += math.exp(logp)
                                if draw < cumulative:
                                    action = j
                                    break
                    self.steps.append(
                        {
                            "public_input": public,
                            "public_input_id": identity,
                            "action_index": action,
                        }
                    )
                    if len(json.dumps(self.steps, ensure_ascii=False).encode()) > MAX_PLAN_BYTES:
                        raise ValueError("Complete-turn plan storage cap; preserve this attempt")
                    self.turn_index += 1
                    phase = "candidate_turn_generation"
            if self.turn_complete:
                selected = choose(
                    self.model,
                    self.score,
                    public,
                    self.navigation,
                    self.continuation_rng,
                    self.temperature,
                    0.0,
                )
                return {
                    **selected,
                    "policy_contract": CONTRACT,
                    "teacher_phase": "public_policy_continuation",
                    "ordinary_PPO_eligible": False,
                }
        if type(action) is not int or not 0 <= action < len(public["candidates"]):
            raise ValueError("Complete-turn action is no longer publicly offered")
        if index >= len(prefix):
            self.end_turn_sent |= public["candidates"][action]["verb"] == "end_turn"
        self.navigation.advance(public, action)
        return {
            "action_index": action,
            "public_input_id": identity,
            "policy_contract": CONTRACT,
            "teacher_phase": phase,
            "ordinary_PPO_eligible": False,
        }
