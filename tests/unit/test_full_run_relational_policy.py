from __future__ import annotations

import copy
import math

import pytest
from test_full_run_public_policy import CATALOG, MenuRun, changed, environment

from spireshift.core.types import Observation
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax, loss_gradient
from spireshift.full_run_public_policy import (
    PublicFullRunModel,
    PublicFullRunPolicy,
    initial_public_full_run_model,
)
from spireshift.full_run_relational_math import ActorCritic, initialize_critic, state_features
from spireshift.full_run_relational_policy import (
    RelationalFullRunModel,
    RelationalFullRunPolicy,
    initial_relational_model,
    relational_tokens,
)


def status_probe(observation: Observation, strength: int, dexterity: int) -> Observation:
    state = copy.deepcopy(observation.public_state)
    state["observation_vector"][60:80] = [0, strength, 1, dexterity] + [0] * 16
    return changed(observation, state)


def test_status_owner_amount_and_relic_counter_swaps_are_distinguishable() -> None:
    env = environment(MenuRun(count=0))
    obs = env.reset(1)
    actions = env.legal_actions()
    v2 = PublicFullRunPolicy(
        env.ruleset, initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    )
    v3 = RelationalFullRunPolicy(
        env.ruleset, initial_relational_model(env.ruleset, CATALOG, "a" * 64)
    )
    a, b = status_probe(obs, 2, 7), status_probe(obs, 7, 2)
    assert v2.predict(a, actions).inputs.vectors == v2.predict(b, actions).inputs.vectors
    before, after = v3.predict(a, actions), v3.predict(b, actions)
    assert before.inputs.vectors != after.inputs.vectors
    assert before.inputs.source_action_ids == after.inputs.source_action_ids
    assert state_features(before.inputs.context, 256) != state_features(after.inputs.context, 256)
    relics = [
        {"relic_id": 11, "counter": 2, "used_up": False},
        {"relic_id": 12, "counter": 7, "used_up": False},
    ]
    s = {**obs.public_state, "relic_slots": relics}
    a = changed(obs, s)
    s = copy.deepcopy(s)
    s["relic_slots"][0]["counter"], s["relic_slots"][1]["counter"] = 7, 2
    b = changed(obs, s)
    assert v2.predict(a, actions).inputs.vectors == v2.predict(b, actions).inputs.vectors
    assert v3.predict(a, actions).inputs.vectors != v3.predict(b, actions).inputs.vectors
    env.close()


def test_card_upgrade_binding_is_retained_without_deck_order() -> None:
    # Identical printed properties make the old independent pooling lose which
    # card was upgraded. Identity-bound features retain that association.
    a = [{"card_id": 10, "upgraded": True}, {"card_id": 11, "upgraded": False}]
    b = [{"card_id": 10, "upgraded": False}, {"card_id": 11, "upgraded": True}]
    ta: dict[str, float] = {}
    tb: dict[str, float] = {}
    tr: dict[str, float] = {}
    relational_tokens(a, "state/deck", ta)
    relational_tokens(b, "state/deck", tb)
    relational_tokens(list(reversed(a)), "state/deck", tr)
    assert ta != tb and ta == tr


def test_complete_menus_and_selected_bundle_keep_all_candidates() -> None:
    env = environment(MenuRun(count=15))
    obs = env.reset(1)
    policy = RelationalFullRunPolicy(
        env.ruleset, initial_relational_model(env.ruleset, CATALOG, "a" * 64)
    )
    decision = policy.predict(obs, env.legal_actions())
    assert len(decision.logits) == 16
    assert len(decision.inputs.context["combat"]["selection_cards"]) == 15
    env.step(decision.selected_action)
    assert env._observation is not None
    policy.predict(env._observation, env.legal_actions())
    env.step(env.legal_actions()[0])
    assert env._observation is not None
    decision = policy.predict(env._observation, env.legal_actions())
    assert len(decision.logits) == 3
    env.close()


def test_versioned_models_round_trip_and_reject_historical_formats() -> None:
    env = environment(MenuRun(count=0))
    actor = initial_relational_model(env.ruleset, CATALOG, "a" * 64)
    assert actor.parameter_count == 4384
    assert RelationalFullRunModel.from_mapping(actor.as_dict()).as_dict() == actor.as_dict()
    model = initialize_critic(actor)
    assert ActorCritic.from_mapping(model.as_dict()).as_dict() == model.as_dict()
    assert isinstance(model.with_weights(model.weights()), ActorCritic)
    v2 = initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    assert v2.genome == actor.genome
    assert v2.model_id != actor.model_id
    with pytest.raises(ValueError):
        PublicFullRunModel.from_mapping(actor.as_dict())
    with pytest.raises(ValueError):
        RelationalFullRunModel.from_mapping(v2.as_dict())
    corrupted = actor.as_dict()
    corrupted["genome"][0] += 0.1
    with pytest.raises(ValueError, match="identity"):
        RelationalFullRunModel.from_mapping(corrupted)
    env.close()


def test_ppo_algebra_learns_opposing_preferences_from_entity_bound_inputs() -> None:
    # Exact expected policy gradient in a synthetic two-action bandit, not
    # labels that assert either move is best in the actual game. No games run.
    env = environment(MenuRun(count=0))
    observation = env.reset(1)
    model = initialize_critic(initial_relational_model(env.ruleset, CATALOG, "a" * 64))
    policy = RelationalFullRunPolicy(env.ruleset, model.actor)
    inputs = [
        policy.predict(status_probe(observation, a, b), env.legal_actions()).inputs
        for a, b in ((2, 7), (7, 2))
    ]
    rows = [(entry.vectors[0], entry.vectors[2]) for entry in inputs]
    states = [state_features(entry.context, model.actor.dimension) for entry in inputs]
    optimizer = Adam.zero(model.parameter_count)
    for _ in range(250):
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
        assert isinstance(updated, ActorCritic)
        model = updated
    assert all(
        math.exp(log_softmax(score_features(model.actor, x))[correct]) > 0.95
        for x, correct in zip(rows, (1, 0), strict=True)
    )
    assert isinstance(model.actor, RelationalFullRunModel)
    env.close()
