"""Sample the full advertised native menu without strategic routing."""

from __future__ import annotations

from typing import Any

from spireshift.native_context_cache import CachedContextModel
from spireshift.native_live_policy import LivePolicy
from spireshift.native_shop_policy import ShopNavigation
from spireshift.native_structured_policy import Chooser
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "native_a8_all_advertised_actions_own_policy_v1"


class AllActions(ShopNavigation):
    def view(self, public: dict[str, Any]) -> tuple[dict[str, Any], list[int], bool]:
        return public, list(range(len(public["candidates"]))), False

    def advance(self, public: dict[str, Any], action: int) -> None:
        # Public history remains in the observation. No routing state restricts the menu.
        return None


class OwnPolicy(LivePolicy):
    def __init__(self, model: CachedContextModel, score: TrainingScoreSpec, seed: str) -> None:
        super().__init__(model, score, seed)
        self.chooser = Chooser(model, score, seed, training=True)
        self.chooser.navigation = AllActions()

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        selected = super().choose(frame)
        assert self.pending is not None
        trial = self.pending[2]
        assert trial.last is not None
        rows, _, effective, forced = trial.last
        if (
            forced
            or effective != frame["public_input"]
            or len(rows) != len(frame["actions"])
            or selected["effective_input_id"] != selected["public_input_id"]
            or selected["action_index"] != selected["effective_action_index"]
            or selected["behavior"] != "sampled_softmax"
            or selected["draw_used"] is not True
        ):
            raise ValueError("The model must sample over every advertised action")
        selected["policy_contract"] = CONTRACT
        return selected
