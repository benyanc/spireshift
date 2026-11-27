"""All-family sampled training and greedy-combat evaluation with exact replay."""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Sample, log_softmax
from spireshift.native_combat_behavior_policy import Chooser as CombatOwnership
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_structured_model import encode
from spireshift.native_turn_teacher_policy import room
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "native_structured_all_family_own_policy_v1"
RNG = "structured_world_room_family_visit_separate_combat_noncombat_v1"


class Chooser(CombatOwnership):
    def __init__(
        self, model: CachedContextModel, score: TrainingScoreSpec, seed: str, training: bool
    ) -> None:
        super().__init__(model, score, seed, "sampled" if training else "greedy")
        self.training = training
        self.last: tuple[Any, Any, Any, bool] | None = None

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        combat = self.combat(public)
        effective, indices, forced = self.navigation.view(public)
        rows, state = encode(effective, self.model, self.score)
        logs = log_softmax(
            score_features(cast(Any, self.model.actor), rows), SETTINGS["temperature"]
        )
        if not rows:
            raise ValueError("Never invent an action for an empty public menu")
        family = public["context"]["interaction"]["kind"]
        slot = combat, room(public), family
        visit = self.visits.get(slot, 0)
        key = manifest_identifier(
            {
                "rng": RNG,
                "seed": self.seed,
                "combat": combat,
                "room": list(slot[1]),
                "family": family,
                "visit": visit,
            }
        )
        draw = None
        if not forced:
            self.visits[slot] = visit + 1
            draw = random.Random(
                int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
            ).random()
        greedy = combat and not self.training and not forced
        selected = 0
        if greedy:
            selected = max(range(len(rows)), key=lambda i: (logs[i], -i))
        elif not forced:
            cumulative, selected = 0.0, len(rows) - 1
            assert draw is not None
            for i, logp in enumerate(logs):
                cumulative += math.exp(logp)
                if draw < cumulative:
                    selected = i
                    break
        action = indices[selected]
        result = {
            "action_index": action,
            "model_id": self.model.model_id,
            "public_input_id": manifest_identifier(public),
            "effective_input_id": manifest_identifier(effective),
            "effective_action_index": selected,
            "navigation_only": forced,
            "combat_owned": combat,
            "policy_contract": CONTRACT,
            "training": self.training,
            "behavior": "deterministic_navigation"
            if forced
            else "greedy_combat"
            if greedy
            else "sampled_softmax",
            "temperature": SETTINGS["temperature"],
            "log_probability": 0.0 if greedy or forced else logs[selected],
            "policy_log_probability": logs[selected],
            "value": self.model.value(state),
            "draw_key": key,
            "draw": draw,
            "draw_used": not forced and not greedy,
        }
        self.last = rows, state, effective, forced
        self.navigation.advance(public, action)
        return result


def reconstruct(
    case: dict[str, Any],
    model: CachedContextModel,
    score: TrainingScoreSpec,
    seed: str,
    training: bool,
    training_return: float,
) -> tuple[list[Sample], list[dict[str, Any]]]:
    if (
        case.get("policy_contract") != CONTRACT
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("ordinary_PPO_eligible") is not (training and case.get("status") == "terminal")
        or case.get("privileged_fixed_world_teacher") is True
        or not math.isfinite(training_return)
        or not 0 <= training_return <= 1
    ):
        raise ValueError("Reconstruct only this public-only own-policy contract")
    chooser = Chooser(model, score, seed, training)
    samples, normalized = [], []
    for row in case["decisions"]:
        expected, saved = chooser(row["public_input"]), row["choice"]
        if set(expected) != set(saved):
            raise ValueError("Saved structured policy fields differ")
        for key, value in expected.items():
            equal = (
                type(saved[key]) is float
                and math.isclose(saved[key], value, rel_tol=0, abs_tol=1e-10)
                if type(value) is float
                else type(saved[key]) is type(value) and saved[key] == value
            )
            if not equal:
                raise ValueError(f"Structured behavior/ownership/probability changed: {key}")
        assert chooser.last is not None
        rows, state, effective, forced = chooser.last
        if not forced:
            normalized.append({**row, "public_input": effective})
            if training:
                if saved["behavior"] != "sampled_softmax":
                    raise ValueError("Greedy decisions are never ordinary PPO experience")
                samples.append(
                    Sample(
                        rows,
                        state,
                        saved["effective_action_index"],
                        saved["log_probability"],
                        training_return,
                        training_return - saved["value"],
                    )
                )
    return samples, normalized
