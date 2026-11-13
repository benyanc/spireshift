from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_a8_action_credit_policy import CONTRACT, STRATA, alternate
from spireshift.native_a8_action_credit_session import matched_root, plan
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_flow_live_v12 import append


def test_alternative_uses_conditional_softmax_over_visibly_different_bindings() -> None:
    scores = [1000.0, 999.0, 0.0, math.log(3)]
    labels = ["Attack", "Attack", "Defend", "End Turn"]
    i, logp, unconditional = alternate(scores, labels, 0, 1.0, 0.20)
    assert i == 2
    assert math.exp(logp) == pytest.approx(0.25)
    assert unconditional < -999
    assert alternate(scores, labels, 0, 1.0, 0.30)[0] == 3
    with pytest.raises(ValueError, match="visibly different"):
        alternate(scores[:2], labels[:2], 0, 1.0, 0.20)


def test_collection_worlds_are_fresh_and_cover_both_initializers_and_all_strata() -> None:
    train, control = plan(False), plan(True)
    assert len(train) == len({row["key"] for row in train}) == 36
    seeds = {row["seed"] for row in train}
    assert len(seeds) == 18 and seeds.isdisjoint(row["seed"] for row in control)
    for seed in seeds:
        assert {row["player"] for row in train if row["seed"] == seed} == {2, 3}
    assert {row["stratum"] for row in train} == {row["stratum"] for row in control} == set(STRATA)


def test_exact_root_and_successor_are_required(tmp_path: Path) -> None:
    left, right = tmp_path / "left", tmp_path / "right"
    case = {"stratum": "route", "minimum_floor": 2}

    def frame(snapshot: str, floor: int) -> dict[str, Any]:
        return {
            "observation": {"snapshot_id": snapshot},
            "source_family": "map_navigation",
            "public_input": {
                "candidates": [{"label": "Fight"}, {"label": "Rest"}],
                "context": {
                    "persistent": {"run": {"floor": floor}},
                    "interaction": {"kind": "map_navigation", "content": {}},
                },
            },
        }

    def episode(path: Path, index: int, *, at: int = 2, ack: str = "next") -> None:
        path.mkdir(exist_ok=True)
        trace = path / TRACE
        trace.unlink(missing_ok=True)
        append(trace, {"kind": "policy_input", "frame": frame("root", at)})
        append(
            trace,
            {
                "kind": "policy_choice",
                "choice": {
                    "action_index": index,
                    "draw_key": "alternate" if index else "reference",
                    "credit_root": {
                        "contract": CONTRACT,
                        "stratum": "route",
                        "reference_action_index": 0,
                        "alternate": bool(index),
                        "reference_draw_key": "reference",
                    },
                },
                "receipt": {"delivery_domain": "native", "successor_snapshot_id": ack},
            },
        )
        append(trace, {"kind": "final_observation", "frame": frame("next", 3 + index)})

    episode(left, 0)
    episode(right, 1)
    root = matched_root(left, right, case)
    assert root is not None and root["different_public_successor"] is True
    episode(right, 1, at=3)
    with pytest.raises(ValueError, match="diverged"):
        matched_root(left, right, case)
    episode(right, 1, ack="wrong")
    with pytest.raises(ValueError, match="successor differs"):
        matched_root(left, right, case)
