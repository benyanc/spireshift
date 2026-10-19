"""On-policy rest-site exploration; native legal actions and episode return are unchanged."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo_math import Sample as BaseSample
from spireshift.native_action_context import ActionContextModel, policy
from spireshift.native_shop_policy import ShopNavigation
from spireshift.training_objective import TrainingScoreSpec

CONTRACT = "public_shop_navigation_with_rest_uniform_mixture_v1"


@dataclass(frozen=True, slots=True)
class Sample(BaseSample):
    epsilon: float = 0.0


def mixed_logs(logs: tuple[float, ...], epsilon: float) -> tuple[float, ...]:
    if not 0 <= epsilon < 1 or not math.isfinite(epsilon) or not logs:
        raise ValueError("Use a finite mixture weight below one")
    if not epsilon:
        return logs
    return tuple(math.log((1 - epsilon) * math.exp(v) + epsilon / len(logs)) for v in logs)


def exploration(public: dict[str, Any], weight: float) -> float:
    if not math.isfinite(weight) or not 0 <= weight < 1:
        raise ValueError("Invalid frozen exploration weight")
    return weight if public["context"]["interaction"]["kind"] == "rest_site" else 0.0


def choose(
    model: ActionContextModel,
    score: TrainingScoreSpec,
    public: dict[str, Any],
    navigation: ShopNavigation,
    rng: random.Random,
    temperature: float,
    uniform_weight: float,
) -> dict[str, Any]:
    effective, indices, forced = navigation.view(public)
    rows, state, logs = policy(effective, model, score, temperature)
    if not rows:
        raise ValueError("Exploration cannot create an empty legal menu")
    epsilon = 0.0 if forced else exploration(effective, uniform_weight)
    behavior = mixed_logs(logs, epsilon)
    selected = 0
    if not forced:
        draw, cumulative, selected = rng.random(), 0.0, len(rows) - 1
        for i, logp in enumerate(behavior):
            cumulative += math.exp(logp)
            if draw < cumulative:
                selected = i
                break
    action = indices[selected]
    result = {
        "action_index": action,
        "log_probability": behavior[selected],
        "unmixed_log_probability": logs[selected],
        "exploration_epsilon": epsilon,
        "value": model.value(state),
        "model_id": model.model_id,
        "public_input_id": manifest_identifier(public),
        "effective_input_id": manifest_identifier(effective),
        "effective_action_index": selected,
        "policy_contract": CONTRACT,
        "navigation_only": forced,
        "behavior": "deterministic_navigation"
        if forced
        else "sampled_rest_uniform_mixture"
        if epsilon
        else "sampled_softmax",
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
    uniform_weight: float,
) -> tuple[list[Sample], list[dict[str, Any]]]:
    if (
        case.get("status") != "terminal"
        or case.get("privileged_fixture") is not False
        or case.get("recovered") is not False
        or case.get("native_ending_evidence_agrees") is not True
        or not math.isfinite(training_return)
        or not 0 <= training_return <= 1
    ):
        raise ValueError("Exploration PPO requires clean unrecovered genuine endings")
    navigation = ShopNavigation()
    samples, normalized = [], []
    for row in case["decisions"]:
        public, saved = row["public_input"], row["choice"]
        effective, indices, forced = navigation.view(public)
        rows, state, logs = policy(effective, model, score, temperature)
        action = saved["action_index"]
        if type(action) is not int or action not in indices:
            raise ValueError("Saved exploration action is outside the legal menu")
        selected = indices.index(action)
        epsilon = 0.0 if forced else exploration(effective, uniform_weight)
        behavior = mixed_logs(logs, epsilon)
        if (
            saved.get("policy_contract") != CONTRACT
            or saved.get("model_id") != model.model_id
            or saved.get("public_input_id") != manifest_identifier(public)
            or saved.get("effective_input_id") != manifest_identifier(effective)
            or saved.get("effective_action_index") != selected
            or saved.get("navigation_only") is not forced
            or saved.get("temperature") != temperature
            or saved.get("exploration_epsilon") != epsilon
            or saved.get("behavior")
            != (
                "deterministic_navigation"
                if forced
                else "sampled_rest_uniform_mixture"
                if epsilon
                else "sampled_softmax"
            )
            or not math.isclose(
                saved["log_probability"], behavior[selected], rel_tol=0, abs_tol=1e-10
            )
            or not math.isclose(
                saved["unmixed_log_probability"], logs[selected], rel_tol=0, abs_tol=1e-10
            )
            or not math.isclose(saved["value"], model.value(state), rel_tol=0, abs_tol=1e-10)
        ):
            raise ValueError("Exploration probability/behavior/predecessor does not reconstruct")
        navigation.advance(public, action)
        if forced:
            continue
        samples.append(
            Sample(
                rows,
                state,
                selected,
                behavior[selected],
                training_return,
                training_return - saved["value"],
                epsilon,
            )
        )
        normalized.append({**row, "public_input": effective})
    if not samples:
        raise ValueError("A complete training episode needs strategic choices")
    return samples, normalized
