"""Public-only shop navigation, separate from learned purchases and consumables.

Keep every raw observation/action/delivery for the unchanged native auditor. The
effective learner menu removes only reopening the inventory after finishing it.
A consumed merchant potion permits a fresh inspection of the changed shop.
"""

from __future__ import annotations

import math
import random
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo_math import Sample
from spireshift.native_action_context import ActionContextModel, policy
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "public_shop_navigation_once_with_merchant_potion_reinspection_v1"


class ShopNavigation:
    def __init__(self) -> None:
        self.reinspect: tuple[int, int] | None = None

    @staticmethod
    def visit(public: dict[str, Any]) -> tuple[int, int]:
        run = public["context"]["persistent"]["run"]
        return run["act"], run["floor"]

    def view(self, public: dict[str, Any]) -> tuple[dict[str, Any], list[int], bool]:
        candidates = public["candidates"]
        interaction = public["context"]["interaction"]
        if interaction["kind"] != "shop_inventory":
            return public, list(range(len(candidates))), False
        surface = interaction["content"]["surface"]
        if surface["inventory_open"] is not False:
            return public, list(range(len(candidates))), False
        opens = [
            i
            for i, c in enumerate(candidates)
            if c["verb"] == "activate"
            and c["label"] == "Open inventory"
            and c["subject"] is None
            and not c["arguments"]
        ]
        leaves = [
            i
            for i, c in enumerate(candidates)
            if c["verb"] == "close"
            and c["label"] == "Leave shop"
            and c["subject"] is None
            and not c["arguments"]
        ]
        if len(opens) != 1 or len(leaves) != 1:
            raise ValueError("Shop navigation requires the current public open and leave controls")
        history = [c.get("history", {}).get("shop_inspected") for c in candidates]
        if any(type(h) is not bool or h != history[0] for h in history):
            raise ValueError("Shop inspection history is missing or inconsistent")
        force_open = not history[0] or self.reinspect == self.visit(public)
        indices = opens if force_open else [i for i in range(len(candidates)) if i not in opens]
        return {**public, "candidates": [candidates[i] for i in indices]}, indices, force_open

    def advance(self, public: dict[str, Any], action: int) -> None:
        visit = self.visit(public)
        if self.reinspect is not None and self.reinspect != visit:
            self.reinspect = None
        c = public["candidates"][action]
        if c["verb"] == "activate" and c["label"] == "Open inventory":
            self.reinspect = None
        subject = c.get("subject") or {}
        if (
            c["verb"] == "use"
            and subject.get("properties", {}).get("definition_id") == "FOUL_POTION"
            and any((a.get("entity") or {}).get("role") == "merchant" for a in c["arguments"])
        ):
            # Our own chosen public action, never a hidden native flag. Any uncertain
            # delivery ends the episode; the caller cannot reset/reuse this router.
            self.reinspect = visit


def choose(
    model: ActionContextModel,
    score: TrainingScoreSpec,
    public: dict[str, Any],
    navigation: ShopNavigation,
    rng: random.Random,
    temperature: float,
) -> dict[str, Any]:
    effective, indices, forced = navigation.view(public)
    rows, state, logs = policy(effective, model, score, temperature)
    if not rows:
        raise ValueError("Shop routing cannot create an empty strategic menu")
    selected = 0
    if not forced:
        draw, cumulative, selected = rng.random(), 0.0, len(rows) - 1
        for i, logp in enumerate(logs):
            cumulative += math.exp(logp)
            if draw < cumulative:
                selected = i
                break
    action = indices[selected]
    result = {
        "action_index": action,
        "log_probability": logs[selected],
        "value": model.value(state),
        "model_id": model.model_id,
        "public_input_id": manifest_identifier(public),
        "effective_input_id": manifest_identifier(effective),
        "effective_action_index": selected,
        "policy_contract": CONTRACT,
        "navigation_only": forced,
        "behavior": "deterministic_navigation" if forced else "sampled_softmax",
        "temperature": temperature,
    }
    navigation.advance(public, action)
    return result


def verified_samples(
    case: dict[str, Any],
    model: ActionContextModel,
    score: TrainingScoreSpec,
    training_return: float,
    temperature: float,
) -> tuple[list[Sample], list[dict[str, Any]]]:
    if (
        case.get("status") != "terminal"
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or not math.isfinite(training_return)
        or not 0 <= training_return <= 1
    ):
        raise ValueError("Only clean complete games under the shop contract supply PPO")
    samples, normalized = [], []
    navigation = ShopNavigation()
    for row in case["decisions"]:
        public, saved = row["public_input"], row["choice"]
        effective, indices, forced = navigation.view(public)
        rows, state, logs = policy(effective, model, score, temperature)
        action = saved["action_index"]
        if type(action) is not int or action not in indices:
            raise ValueError("Saved action differs from the public navigation contract")
        selected = indices.index(action)
        if (
            saved.get("policy_contract") != CONTRACT
            or saved.get("model_id") != model.model_id
            or saved.get("public_input_id") != manifest_identifier(public)
            or saved.get("effective_input_id") != manifest_identifier(effective)
            or saved.get("effective_action_index") != selected
            or saved.get("navigation_only") is not forced
            or saved.get("behavior")
            != ("deterministic_navigation" if forced else "sampled_softmax")
            or saved.get("temperature") != temperature
            or not math.isclose(saved["log_probability"], logs[selected], rel_tol=0, abs_tol=1e-10)
            or not math.isclose(saved["value"], model.value(state), rel_tol=0, abs_tol=1e-10)
        ):
            raise ValueError("Shop behavior probability, navigation or policy identity differs")
        navigation.advance(public, action)
        if forced:
            continue
        samples.append(
            Sample(
                rows,
                state,
                selected,
                logs[selected],
                training_return,
                training_return - saved["value"],
            )
        )
        normalized.append({**row, "public_input": effective})
    if not samples:
        raise ValueError("A clean game must contain strategic learning decisions")
    return samples, normalized
