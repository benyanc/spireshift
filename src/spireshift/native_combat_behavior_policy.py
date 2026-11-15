"""Public combat-only greediness with matched, room-local noncombat randomness."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.native_action_context import policy
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_turn_teacher_policy import POST_COMBAT, room, round_number
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "public_combat_greedy_vs_sampled_matched_noncombat_v1"
RNG = "world_room_family_visit_separate_combat_noncombat_v1"
ARMS = ("sampled", "greedy")
TEMPERATURE = 0.8


class Chooser:
    def __init__(
        self, model: CachedContextModel, score: TrainingScoreSpec, seed: str, arm: str
    ) -> None:
        if arm not in ARMS or not isinstance(seed, str) or not seed:
            raise ValueError("Declare a fixed combat arm and game sampling seed")
        self.model, self.score, self.seed, self.arm = model, score, seed, arm
        self.navigation = ShopNavigation()
        self.active: tuple[int, int, str] | None = None
        self.visits: dict[tuple[bool, tuple[int, int, str], str], int] = {}

    def combat(self, public: dict[str, Any]) -> bool:
        current = room(public)
        interaction = public["context"]["interaction"]
        kind = interaction["kind"]
        context = interaction.get("content", {}).get("context", {})
        if kind == "combat_turn":
            round_number(public)
            self.active = current
            return True
        if self.active != current:
            self.active = None
        if self.active is not None:
            if context.get("kind") == "selection":
                return True
            if context.get("kind") not in POST_COMBAT and kind != "game_over":
                raise ValueError(f"Unknown public combat ownership: {kind}")
            self.active = None
        return False

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        validate_public_input(public)
        combat = self.combat(public)
        effective, indices, forced = self.navigation.view(public)
        rows, _, logs = policy(effective, self.model, self.score, TEMPERATURE)
        if not rows:
            raise ValueError("Combat comparison cannot invent an empty-menu action")
        family = public["context"]["interaction"]["kind"]
        key = (combat, room(public), family)
        visit = self.visits.get(key, 0)
        # Navigation consumes no policy randomness. Combat never advances a
        # noncombat counter; an extra reward cannot shift next floor's rest draw.
        identity = manifest_identifier(
            {
                "rng": RNG,
                "seed": self.seed,
                "combat": combat,
                "room": list(key[1]),
                "family": family,
                "visit": visit,
            }
        )
        draw: float | None = None
        if not forced:
            self.visits[key] = visit + 1
            salt = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big")
            draw = random.Random(salt).random()
        greedy = combat and self.arm == "greedy" and not forced
        selected = 0
        if greedy:
            selected = max(range(len(rows)), key=lambda i: (logs[i], -i))
        elif not forced:
            assert draw is not None
            cumulative, selected = 0.0, len(rows) - 1
            for i, logp in enumerate(logs):
                cumulative += math.exp(logp)
                if draw < cumulative:
                    selected = i
                    break
        action = indices[selected]
        result = {
            "action_index": action,
            "policy_contract": CONTRACT,
            "model_id": self.model.model_id,
            "public_input_id": manifest_identifier(public),
            "effective_input_id": manifest_identifier(effective),
            "effective_action_index": selected,
            "combat_owned": combat,
            "nested_combat_selection": combat and family != "combat_turn",
            "navigation_only": forced,
            "behavior": "deterministic_navigation"
            if forced
            else "greedy_combat"
            if greedy
            else "sampled_combat"
            if combat
            else "sampled_noncombat",
            "temperature": TEMPERATURE,
            "log_probability": 0.0 if greedy or forced else logs[selected],
            "policy_log_probability": logs[selected],
            "draw_key": identity,
            "draw": draw,
            "draw_used": not forced and not greedy,
            "ordinary_PPO_eligible": False,
        }
        self.navigation.advance(public, action)
        return result


def reconstruct(
    case: dict[str, Any], model: CachedContextModel, score: TrainingScoreSpec, seed: str, arm: str
) -> dict[str, Any]:
    if (
        case.get("policy_contract") != CONTRACT
        or case.get("ordinary_PPO_eligible") is not False
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("privileged_fixed_world_teacher") is not False
    ):
        raise ValueError("Combat behavior verification requires unprivileged evaluation episodes")
    chooser = Chooser(model, score, seed, arm)
    counts: dict[str, int] = {}
    noncombat = []
    nested = 0
    for row in case["decisions"]:
        expected, saved = chooser(row["public_input"]), row["choice"]
        if set(saved) != set(expected):
            raise ValueError("Saved combat behavior fields changed")
        for key, value in expected.items():
            same = (
                type(saved[key]) is float
                and math.isclose(saved[key], value, abs_tol=1e-10, rel_tol=0)
                if type(value) is float
                else type(saved[key]) is type(value) and saved[key] == value
            )
            if not same:
                raise ValueError(f"Saved combat choice, ownership or randomness differs: {key}")
        behavior = saved["behavior"]
        counts[behavior] = counts.get(behavior, 0) + 1
        nested += saved["nested_combat_selection"]
        if behavior == "sampled_noncombat":
            noncombat.append(
                {
                    k: saved[k]
                    for k in (
                        "draw_key",
                        "draw",
                        "effective_input_id",
                        "action_index",
                        "policy_log_probability",
                    )
                }
            )
    return {
        "counts": counts,
        "nested_combat_selections": nested,
        "decisions_reconstructed": len(case["decisions"]),
        "noncombat": noncombat,
    }
