from __future__ import annotations

import copy
from typing import Any

import pytest

from spireshift.native_gradient_study import train_panel


def test_only_predeclared_whole_train_rounds_are_eligible() -> None:
    recipe: dict[str, Any] = {"learning": {"rollout_panels": [list(range(1, 33))] * 8}}
    seeds = {i: {"partition": "train"} for i in range(1, 33)}
    old = copy.deepcopy(recipe)
    assert train_panel(recipe, 1, seeds)["partition"] == "train"
    assert train_panel(recipe, 8, seeds)["ids"] == list(range(1, 33))
    assert recipe == old
    for index in (0, 2, 7, 9, True):
        with pytest.raises(ValueError):
            train_panel(recipe, index, seeds)


@pytest.mark.parametrize("bad", ["confirmation", "development", "unknown", "duplicate"])
def test_reserved_unknown_or_duplicate_seed_is_rejected_before_episode_read(bad: str) -> None:
    recipe: dict[str, Any] = {"learning": {"rollout_panels": [list(range(1, 33))] * 8}}
    seeds = {i: {"partition": "train"} for i in range(1, 33)}
    if bad in ("confirmation", "development"):
        seeds[1]["partition"] = bad
    elif bad == "unknown":
        seeds.pop(1)
    else:
        recipe["learning"]["rollout_panels"][0][0] = 2
    with pytest.raises(ValueError, match="TRAIN"):
        train_panel(recipe, 1, seeds)
