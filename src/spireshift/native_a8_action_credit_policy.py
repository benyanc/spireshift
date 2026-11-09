"""Sample one model-owned alternative at a predeclared native decision."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from typing import Any, cast

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import log_softmax
from spireshift.native_a8_own_policy import AllActions, OwnPolicy
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_policy import Chooser
from spireshift.native_win4_plan import PLAN, AnswerPolicy

CONTRACT = "native_a8_paired_action_credit_v1"
STRATA = {
    "combat": {"combat_turn"},
    "route": {"map_navigation"},
    "resources": {
        "reward_claim",
        "card_reward_selection",
        "shop_room",
        "shop_inventory",
        "rest_site",
        "event_option",
        "treasure_room",
        "card_bundle_selection",
    },
}
ARMS = ("reference", "alternate")


def eligible(public: dict[str, Any], case: dict[str, Any]) -> bool:
    ctx = public["context"]
    interaction = ctx["interaction"]
    return (
        ctx["persistent"]["run"]["floor"] >= case["minimum_floor"]
        and interaction["kind"] in STRATA[case["stratum"]]
        and interaction["content"].get("surface", {}).get("selection_contract") != PLAN
        and len({candidate["label"] for candidate in public["candidates"]}) > 1
    )


def alternate(
    scores: Sequence[float], labels: Sequence[str], previous: int, temperature: float, draw: float
) -> tuple[int, float, float]:
    """Sample the same logits conditional on a visibly different choice."""
    if len(scores) != len(labels) or not 0 <= previous < len(scores) or not 0 <= draw < 1:
        raise ValueError("Alternative sampling requires a different legal action")
    indices = [i for i, label in enumerate(labels) if label != labels[previous]]
    if not indices:
        raise ValueError("No visibly different legal action is offered")
    logs = log_softmax([scores[i] for i in indices], temperature)
    mass = 0.0
    for i, logp in zip(indices, logs, strict=True):
        mass += math.exp(logp)
        if draw < mass or i == indices[-1]:
            return i, logp, log_softmax(scores, temperature)[i]
    raise ValueError("Missing eligible alternative")


class ProbeChooser(Chooser):
    def __init__(
        self, model: CachedContextModel, ctx: dict[str, Any], start: dict[str, Any]
    ) -> None:
        super().__init__(model, ctx["score"], start["seed"], training=True)
        self.navigation = AllActions()
        self.case = start["scenario"]
        self.root_seen = False

    def __call__(self, public: dict[str, Any]) -> dict[str, Any]:
        choice = super().__call__(public)
        if self.root_seen or not eligible(public, self.case):
            return choice
        self.root_seen = True
        reference_index = choice["action_index"]
        alternative = self.case["arm"] == "alternate"
        choice["credit_root"] = {
            "contract": CONTRACT,
            "stratum": self.case["stratum"],
            "reference_action_index": reference_index,
            "alternate": alternative,
            "reference_draw_key": choice["draw_key"],
        }
        if alternative:
            assert self.last is not None
            rows, _, effective, forced = self.last
            if effective != public or forced or len(rows) != len(public["candidates"]):
                raise ValueError("Credit probes require the complete public menu")
            key = manifest_identifier({"contract": CONTRACT, "reference_draw": choice["draw_key"]})
            draw = random.Random(int(key.removeprefix("sha256:")[:16], 16)).random()
            i, conditional, unconditional = alternate(
                score_features(cast(Any, self.model.actor), rows),
                [candidate["label"] for candidate in public["candidates"]],
                reference_index,
                choice["temperature"],
                draw,
            )
            choice.update(
                action_index=i,
                effective_action_index=i,
                log_probability=conditional,
                policy_log_probability=unconditional,
                draw=draw,
                draw_key=key,
            )
        return choice


def policy(
    context: dict[str, Any], start: dict[str, Any], variant: str, model: CachedContextModel
) -> AnswerPolicy:
    case = start["scenario"]
    if (
        variant != "own_policy"
        or start["kind"] != "natural_training"
        or start["save_path"] is not None
        or case["partition"] not in {"credit_train", "credit_control"}
        or case["arm"] not in ARMS
        or case["stratum"] not in STRATA
    ):
        raise ValueError("Action credit requires fresh training-only normal starts")
    actor = OwnPolicy(model, context["score"], start["seed"])
    actor.chooser = ProbeChooser(model, context, start)
    return AnswerPolicy(actor)
