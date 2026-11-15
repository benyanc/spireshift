from __future__ import annotations

import copy
import random
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_full_run_public_policy import CATALOG, MenuRun, environment

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_a8_experience import (
    choose_sample,
    collect_a8_episode,
    episode_binding,
    load_a8_episode,
    verified_samples,
)
from spireshift.full_run_experience import save_episode
from spireshift.full_run_ppo import load_ppo_config
from spireshift.full_run_ppo_math import initialize_critic
from spireshift.full_run_public_policy import PublicFullRunPolicy, initial_public_full_run_model
from spireshift.splits import SplitManifest, SplitName
from spireshift.training_objective import RunStatus

CONFIG = Path("configs/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v1.json")


def setup() -> tuple[Any, Any, Any, Any]:
    config = load_ppo_config(CONFIG)
    env = environment(MenuRun())
    body = config.splits.body_dict()
    body["ruleset_manifest_id"] = env.ruleset.manifest_id
    splits = SplitManifest.from_mapping({**body, "manifest_id": manifest_identifier(body)})
    score = replace(
        config.score, scope=replace(config.score.scope, ruleset_manifest_id=env.ruleset.manifest_id)
    )
    actor = initial_public_full_run_model(env.ruleset, CATALOG, "a" * 64)
    return env, splits, score, initialize_critic(actor)


def test_sampling_distribution_is_real_and_deterministic() -> None:
    rng = random.Random(7)
    observations = [choose_sample([0.1, 0.7, 0.2], rng) for _ in range(10000)]
    assert observations.count(1) / len(observations) == pytest.approx(0.7, abs=0.02)
    assert choose_sample([0.1, 0.7, 0.2], random.Random(42)) == choose_sample(
        [0.1, 0.7, 0.2], random.Random(42)
    )


def test_menu_collection_records_non_argmax_and_true_probability(tmp_path: Path) -> None:
    env, splits, score, model = setup()
    seed = splits.seeds(SplitName.TRAIN)[0]
    greedy = (
        PublicFullRunPolicy(env.ruleset, model.actor)
        .predict(env.reset(seed), env.legal_actions())
        .candidate_index
    )
    # This deterministic sampler picks a real non-argmax menu card.
    case, trace = collect_a8_episode(
        lambda: env,
        env.ruleset,
        model,
        score,
        splits,
        seed=seed,
        partition="train",
        behavior="sampled_softmax",
        sampling_seed=7,
        maximum_decisions=30,
    )
    assert trace[0]["selected_index"] != greedy
    assert (
        trace[0]["behavior_probability"] == trace[0]["policy_softmax"][trace[0]["selected_index"]]
    )
    assert 0 < trace[0]["behavior_probability"] < 1
    assert case["outcome"]["status"] == RunStatus.LOSS
    assert all(d["environment_reward"] == 0 for d in trace)
    path = tmp_path / "case.json"
    save_episode(path, case, trace)
    saved, decoded = load_a8_episode(path, case["binding"])
    samples = verified_samples(saved, decoded, env.ruleset, model, score)
    assert len(samples) == len(trace)
    assert all(s.target == case["score"]["training_return"] for s in samples)
    tampered = copy.deepcopy(decoded)
    tampered[0]["behavior_probability"] = 1.0
    with pytest.raises(ValueError, match="probability"):
        verified_samples(saved, tampered, env.ruleset, model, score)
    with pytest.raises(ValueError, match="scope"):
        load_a8_episode(path, {**case["binding"], "behavior": "greedy_argmax"})


def test_invalid_scope_and_reserved_seeds_stop_before_any_environment_open() -> None:
    env, splits, score, model = setup()
    calls = []

    def factory() -> Any:
        calls.append(True)
        return env

    with pytest.raises(ValueError, match="sealed"):
        collect_a8_episode(
            factory,
            env.ruleset,
            model,
            score,
            splits,
            seed=splits.seeds(SplitName.TEST)[0],
            partition="train",
            behavior="sampled_softmax",
            sampling_seed=0,
        )
    wrong = replace(score, scope=replace(score.scope, ascension=0))
    with pytest.raises(ValueError, match="difficulty"):
        episode_binding(
            env.ruleset,
            model,
            wrong,
            splits,
            splits.seeds(SplitName.TRAIN)[0],
            "train",
            30,
            "sampled_softmax",
            1,
            0,
        )
    assert not calls


def test_greedy_traces_are_explicitly_ineligible_for_ppo() -> None:
    env, splits, score, model = setup()
    case, trace = collect_a8_episode(
        lambda: env,
        env.ruleset,
        model,
        score,
        splits,
        seed=splits.seeds(SplitName.TRAIN)[0],
        partition="train",
        behavior="greedy_argmax",
        sampling_seed=0,
    )
    assert all(d["behavior_probability"] == 1.0 for d in trace)
    with pytest.raises(ValueError, match="genuinely sampled"):
        verified_samples(case, trace, env.ruleset, model, score)
