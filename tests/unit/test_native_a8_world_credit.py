from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from spireshift.native_a8_own_policy import AllActions
from spireshift.native_a8_world_credit import DRAWS, advantages, policy, sampler_seed
from spireshift.native_a8_world_credit_reload import corrected_study
from spireshift.native_a8_world_credit_reload import tasks as reload_tasks
from spireshift.native_a8_world_credit_session import schedule, tally
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_context_journal import ChunkJournal


def test_peer_credit_uses_other_draws_and_the_pooled_control_excludes_the_world() -> None:
    returns = {"a": [0.1, 0.2, 0.3], "b": [0.4, 0.4, 0.4]}
    credit = advantages(returns)
    assert credit["within_world"]["a"] == pytest.approx([-0.15, 0, 0.15])
    assert credit["within_world"]["b"] == [0.0, 0.0, 0.0]
    assert credit["pooled"]["a"] == pytest.approx([-0.3, -0.2, -0.1])
    assert credit["pooled"]["b"] == pytest.approx([0.2, 0.2, 0.2])
    with pytest.raises(ValueError, match="complete independent draws"):
        advantages({"a": [0.1, 0.2], "b": returns["b"]})


def test_world_repeats_change_only_the_policy_rng_and_keep_full_menu_ownership() -> None:
    train = schedule(False)["training"]
    same_world = [
        task for task in train if task["seed"] == train[0]["seed"] and task["player"] == 2
    ]
    assert len(same_world) == DRAWS
    model = cast(CachedContextModel, object())
    observed = set()
    for task in same_world:
        start = {
            "scenario": task,
            "seed": task["seed"],
            "kind": "natural_training",
            "save_path": None,
        }
        actor = policy({"score": object()}, start, "own_policy", model)
        chooser = actor.core.chooser
        assert isinstance(chooser.navigation, AllActions)
        assert chooser.training is True
        assert actor.model is model
        assert chooser.seed == sampler_seed(task["seed"], task["draw"])
        observed.add(chooser.seed)
    assert len(observed) == DRAWS


def test_gate_reporting_keeps_failed_and_unstarted_cells() -> None:
    study = schedule(False)
    control = schedule(True)
    assert len(study["training"]) == len(study["evaluation"]) == 48
    scopes = [
        {row["seed"] for row in tasks} for plan in (study, control) for tasks in plan.values()
    ]
    assert sum(map(len, scopes)) == len(set().union(*scopes))
    tasks = study["evaluation"]
    result = tally(tasks, {tasks[0]["key"]: {"outcome": "loss"}}, tasks[1]["key"])
    assert result == {"win": 0, "loss": 1, "capped": 0, "failed": 1, "unattempted": 46}


def test_owner_and_reload_case_keys_can_be_sealed(tmp_path: Path) -> None:
    original = schedule(False)
    corrected = corrected_study({"study": original})
    assert corrected["study"]["training"] == original["training"]
    for before, after in zip(original["evaluation"], corrected["study"]["evaluation"], strict=True):
        assert {**before, "key": after["key"]} == after
    journal = ChunkJournal(tmp_path, corrected)
    keys = [row["key"] for rows in corrected["study"].values() for row in rows]
    keys.extend(task["key"] for task in reload_tasks())
    assert len(keys) == len(set(keys))
    assert all(journal.path(key).name == key for key in keys)
