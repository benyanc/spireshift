"""Explicit teacher forcing and a separately declared noncombat routing ablation.

Only acknowledged deliveries commit navigation, combat ownership and RNG visits.
Every genuine legal option remains present. Routing is an experimental control,
not a permanent restriction on learned policies.
"""

from __future__ import annotations

import copy
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_live_policy import LivePolicy
from spireshift.native_structured_model import encode
from spireshift.native_structured_policy import Chooser
from spireshift.training_objective import TrainingScoreSpec


class RoutedChooser(Chooser):
    def __init__(
        self,
        taught: CachedContextModel,
        original: CachedContextModel,
        score: TrainingScoreSpec,
        seed: str,
    ) -> None:
        super().__init__(taught, score, seed, False)
        self.taught, self.original = taught, original

    def __deepcopy__(self, memo: dict[int, Any]) -> RoutedChooser:
        memo.update(
            {
                id(self.taught): self.taught,
                id(self.original): self.original,
                id(self.score): self.score,
            }
        )
        result = type(self).__new__(type(self))
        memo[id(self)] = result
        result.__dict__.update(copy.deepcopy(self.__dict__, memo))
        return result

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        # Ownership is public and includes nested card/potion selections. Calling
        # it again inside the inherited chooser is idempotent at this boundary.
        self.model = self.taught if self.combat(public) else self.original
        result = super().__call__(public)
        result["routing_contract"] = "taught_combat_original_noncombat_diagnostic_v1"
        result["routed_actor"] = "taught" if result["combat_owned"] else "original"
        return result


class RoutedPolicy(LivePolicy):
    def __init__(
        self,
        taught: CachedContextModel,
        original: CachedContextModel,
        score: TrainingScoreSpec,
        seed: str,
    ) -> None:
        super().__init__(taught, score, seed)
        self.chooser = RoutedChooser(taught, original, score, seed)


class ForcedPolicy(LivePolicy):
    """Declared privileged branch operands; never ordinary PPO/evaluation behavior."""

    def __init__(
        self,
        model: CachedContextModel,
        score: TrainingScoreSpec,
        seed: str,
        forced: list[dict[str, Any]],
        original: CachedContextModel | None = None,
    ) -> None:
        super().__init__(model, score, seed)
        if original is not None:
            self.chooser = RoutedChooser(model, original, score, seed)
        self.forced = forced
        self.seen = 0

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        index = self.decisions
        if index < len(self.forced) and self.forced[index][
            "public_input_id"
        ] != manifest_identifier(frame["public_input"]):
            raise ValueError("Privileged observed plan prefix changed; no guessed binding or retry")
        result = super().choose(frame)
        assert self.pending is not None
        if index >= len(self.forced):
            return result
        action = self.forced[index]["action_index"]
        if type(action) is not int or not 0 <= action < len(frame["actions"]):
            raise ValueError("A teacher operand must be in the exact current public menu")
        _, result, trial = self.pending
        # The inherited trial advanced navigation using its own sampled choice.
        # Restore only that part before committing the explicit legal operand.
        trial.navigation = copy.deepcopy(self.chooser.navigation)
        trial.navigation.advance(frame["public_input"], action)
        logs = action_logs(trial.model, frame["public_input"], self.score)
        result.update(
            action_index=action,
            effective_action_index=action,
            bound_action_id=frame["actions"][action]["bound_action_id"],
            behavior="privileged_observed_legal_plan",
            log_probability=0.0,
            policy_log_probability=logs[action],
            ordinary_PPO_eligible=False,
        )
        self.pending = frame, result, trial
        self.seen = max(self.seen, index + 1)
        return result


def action_logs(
    model: CachedContextModel, public: dict[str, Any], score: TrainingScoreSpec
) -> list[float]:
    rows, _ = encode(public, model, score)
    return list(log_softmax(score_features(cast(Any, model.actor), rows), 0.8))


def policy(
    context: dict[str, Any], player: int, variant: str, seed: str, finals: dict[str, Any]
) -> LivePolicy:
    from spireshift.native_structured_state import load

    root = context["qualification"].root

    def restored(name: str) -> CachedContextModel:
        bound = finals[f"p{player}-{name}"]
        model, adam, sid = load(root / bound["state_path"])
        if (
            sid != bound["state_id"]
            or model.model_id != bound["model_id"]
            or manifest_identifier(adam.as_dict()) != bound["optimizer_id"]
        ):
            raise ValueError(
                "A policy cannot borrow a different final's checkpoint/Adam live scope"
            )
        return model

    model = restored("teacher" if variant == "teacher_original_noncombat" else variant)
    if variant == "teacher_original_noncombat":
        original = restored("original")
        return RoutedPolicy(model, original, context["score"], seed)
    return LivePolicy(model, context["score"], seed)
