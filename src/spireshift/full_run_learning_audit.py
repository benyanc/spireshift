"""Bounded train-only input audit and synthetic learnability check; no native games."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.full_run_a8_admission import identified_document
from spireshift.full_run_a8_experience import _observation, load_a8_episode
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_policy import dense_features, score_features
from spireshift.full_run_ppo import load_actor_critic, load_ppo_config
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax, loss_gradient
from spireshift.full_run_public_policy import PublicFullRunPolicy
from spireshift.full_run_relational_math import ActorCritic, initialize_critic, state_features
from spireshift.full_run_relational_policy import RelationalFullRunPolicy, initial_relational_model
from spireshift.neural_combat import _numpy


def changed_public(observation: Observation, state: dict[str, Any]) -> Observation:
    digest = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return replace(observation, public_state=state, state_hash=digest)


def status_probe(observation: Observation, strength: int, dexterity: int) -> Observation:
    state = copy.deepcopy(observation.public_state)
    state["observation_vector"][60:80] = [0, strength, 1, dexterity] + [0] * 16
    return changed_public(observation, state)


def synthetic_contrast(
    model: ActorCritic,
    rows: list[tuple[dict[int, float], ...]],
    states: list[tuple[float, ...]],
    *,
    steps: int = 250,
) -> dict[str, Any]:
    """Exact expected gradients on two opposite *synthetic* bandit preferences.

    Refresh behavior probabilities each step and enumerate both actions. This
    tests whether the actual numerical actor can use the input distinction;
    it supplies no game-optimality labels and runs no game engine.
    """
    if (
        len(rows) != 2
        or len(states) != 2
        or any(len(x) != 2 for x in rows)
        or not 1 <= steps <= 500
    ):
        raise ValueError("Synthetic contrast requires two states, two actions and a finite cap")

    def correct_probabilities(player: ActorCritic) -> list[float]:
        return [
            math.exp(log_softmax(score_features(player.actor, x))[correct])
            for x, correct in zip(rows, (1, 0), strict=True)
        ]

    before = correct_probabilities(model)
    optimizer = Adam.zero(model.parameter_count)
    for _ in range(steps):
        samples = []
        for x, state, correct in zip(rows, states, (1, 0), strict=True):
            logs = log_softmax(score_features(model.actor, x))
            p = [math.exp(log) for log in logs]
            for action in range(2):
                reward = float(action == correct)
                samples.append(
                    Sample(
                        x,
                        state,
                        action,
                        logs[action],
                        reward,
                        2 * p[action] * (reward - p[correct]),
                    )
                )
        _, gradient, _ = loss_gradient(
            model, samples, clip=0.2, entropy_coefficient=0, value_coefficient=0, temperature=1
        )
        updated, optimizer, _ = optimizer.update(
            model, gradient, actor_rate=0.01, value_rate=0.0, maximum_norm=5
        )
        if not isinstance(updated, ActorCritic):
            raise ValueError("Synthetic optimizer changed model version")
        model = updated
    after = correct_probabilities(model)
    return {
        "task": "two_opposite_synthetic_bandit_preferences_not_game_optimality",
        "before_correct_action_probabilities": before,
        "after_correct_action_probabilities": after,
        "synthetic_optimizer_steps": optimizer.steps,
        "both_preferences_learned": min(after) > 0.95,
        "model_saved_or_promoted": False,
    }


def audit(config_path: Path, source: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("Learning audit output is immutable; choose a new path")
    config = load_ppo_config(config_path)
    report = identified_document(source / "ppo-report.json")
    initial = load_actor_critic(source / "models" / (report["initial_model_id"][7:] + ".json"))
    trained = load_actor_critic(source / "models" / (report["champion_model_id"][7:] + ".json"))
    legacy = PublicFullRunPolicy(config.ruleset, initial.actor)
    relational_actor = initial_relational_model(
        config.ruleset,
        initial.actor.catalog,
        initial.actor.card_source_sha256,
        dimension=initial.actor.dimension,
        hidden_units=initial.actor.hidden_units,
        initialization_seed=config.document["network"]["initialization_seed"],
    )
    if relational_actor.genome != initial.actor.genome:
        raise ValueError("Input-only audit initialization weights differ")
    relational = RelationalFullRunPolicy(config.ruleset, relational_actor)
    refs: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    probe: tuple[Observation, tuple[LegalAction, ...], int, int] | None = None
    for ref in report["cases"]:
        path = source / ref["path"]
        if not path.resolve().is_relative_to(source.resolve()):
            raise ValueError("Source case escapes the experiment")
        case = json.loads(path.read_text())
        binding = case["binding"]
        if (
            binding["partition"] != "train"
            or binding["behavior"] != "sampled_softmax"
            or binding["model_id"] != initial.model_id
        ):
            continue
        if binding["seed"] not in config.document["learning"]["rollout_seed_panels"][0]:
            raise ValueError("Audited seed is not an initial sampled training run")
        case, trace = load_a8_episode(path, binding)
        if case["case_id"] != ref["case_id"]:
            raise ValueError("Audited source case identity differs")
        refs.append({"case_id": ref["case_id"], "seed": binding["seed"]})
        selected = trace[:: max(1, len(trace) // 48)][:48]
        for entry in selected:
            obs = _observation(entry["observation"])
            actions = tuple(
                LegalAction(a["action_id"], a["kind"], a["payload"])
                for a in entry["legal_candidates"]
            )
            old, new = legacy.predict(obs, actions), relational.predict(obs, actions)
            if (
                old.inputs.source_action_ids != new.inputs.source_action_ids
                or old.inputs.bindings != new.inputs.bindings
            ):
                raise ValueError("Input repair changed the legal candidate binding")
            matrix = dense_features(old.inputs.vectors, initial.actor.dimension)
            w, b, _, _ = trained.actor.unpack()
            hidden = _numpy().tanh(matrix @ w.T + b)
            measurements.append(
                {
                    "phase": old.inputs.context["phase"],
                    "candidates": len(actions),
                    "legacy_clamped_coordinates": sum(
                        abs(v) == 5 for v in old.inputs.vectors[0].values()
                    ),
                    "trained_hidden_saturated_fraction": float((abs(hidden) > 0.99).mean()),
                    "legacy_distinct_binding_alias_pairs": sum(
                        old.inputs.vectors[i] == old.inputs.vectors[j]
                        and old.inputs.bindings[i] != old.inputs.bindings[j]
                        for i in range(len(actions))
                        for j in range(i)
                    ),
                    "relational_distinct_binding_alias_pairs": sum(
                        new.inputs.vectors[i] == new.inputs.vectors[j]
                        and new.inputs.bindings[i] != new.inputs.bindings[j]
                        for i in range(len(actions))
                        for j in range(i)
                    ),
                }
            )
            if probe is None and old.inputs.context["phase"] == "combat":
                attack = next(
                    (i for i, row in enumerate(old.inputs.vectors) if row.get(2, 0) > 0), None
                )
                block = next(
                    (
                        i
                        for i, row in enumerate(old.inputs.vectors)
                        if row.get(5, 0) > 0 and i != attack
                    ),
                    None,
                )
                if attack is not None and block is not None:
                    probe = obs, actions, attack, block
        if len(refs) == 4:
            break
    if len(refs) != 4 or probe is None:
        raise ValueError("Audit requires four saved training runs and a normal two-choice combat")
    obs, actions, attack, block = probe
    first, second = status_probe(obs, 2, 7), status_probe(obs, 7, 2)
    oa, ob = legacy.predict(first, actions), legacy.predict(second, actions)
    na, nb = relational.predict(first, actions), relational.predict(second, actions)
    relic_state = copy.deepcopy(obs.public_state)
    relic_state["relic_slots"] = [
        {"relic_id": 11, "counter": 2, "used_up": False},
        {"relic_id": 12, "counter": 7, "used_up": False},
    ]
    relic_first = changed_public(obs, relic_state)
    relic_state = copy.deepcopy(relic_state)
    relic_state["relic_slots"][0]["counter"], relic_state["relic_slots"][1]["counter"] = 7, 2
    relic_second = changed_public(obs, relic_state)
    contrasts = synthetic_contrast(
        initialize_critic(relational_actor),
        [(x.inputs.vectors[attack], x.inputs.vectors[block]) for x in (na, nb)],
        [state_features(x.inputs.context, relational_actor.dimension) for x in (na, nb)],
    )
    body = {
        "schema_version": "public-a8-learning-input-audit-v1",
        "source_report_id": report["report_id"],
        "source_config_id": config.config_id,
        "ruleset_manifest_id": config.ruleset.manifest_id,
        "split_manifest_id": config.splits.manifest_id,
        "initial_actor_id": initial.actor.model_id,
        "relational_initial_actor_id": relational_actor.model_id,
        "source_cases": refs,
        "sampled_states": len(measurements),
        "phase_counts": dict(Counter(m["phase"] for m in measurements)),
        "actual_saved_state_alias_pairs": {
            name: sum(m[f"{name}_distinct_binding_alias_pairs"] for m in measurements)
            for name in ("legacy", "relational")
        },
        "mean_legacy_clamped_coordinates": sum(
            m["legacy_clamped_coordinates"] for m in measurements
        )
        / len(measurements),
        "mean_trained_hidden_saturated_fraction": sum(
            m["trained_hidden_saturated_fraction"] for m in measurements
        )
        / len(measurements),
        "counterfactual_probes": {
            "claim_scope": "synthetic_public_input_sensitivity_not_engine_outcomes",
            "status_amount_swap_v2_indistinguishable": oa.inputs.vectors == ob.inputs.vectors,
            "status_amount_swap_v3_distinguished": na.inputs.vectors != nb.inputs.vectors,
            "relic_counter_swap_v2_indistinguishable": legacy.predict(
                relic_first, actions
            ).inputs.vectors
            == legacy.predict(relic_second, actions).inputs.vectors,
            "relic_counter_swap_v3_distinguished": relational.predict(
                relic_first, actions
            ).inputs.vectors
            != relational.predict(relic_second, actions).inputs.vectors,
            "v2_balanced_contrast_expected_accuracy_upper_bound": 0.5,
        },
        "synthetic_learnability": contrasts,
        "network": {
            "feature_dimension": relational_actor.dimension,
            "hidden_units": relational_actor.hidden_units,
            "actor_parameters": relational_actor.parameter_count,
        },
        "engine_games_replayed": 0,
        "game_training_optimizer_steps": 0,
        "final_test_opened": False,
        "checkpoint_promoted": False,
        "foundation_readiness_established": False,
        "claim_scope": (
            "bounded_train_only_input_repair_evidence_not_playing_strength_or_cause_of_all_losses"
        ),
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.config, args.source, args.output), indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
