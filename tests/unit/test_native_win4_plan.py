from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path
from typing import Any, cast

import pytest

from spireshift.native_live_policy import LivePolicy
from spireshift.native_win4_plan import PLAN, AnswerPolicy, steps
from spireshift.native_win4_recovery import continuation_plan


class FakePolicy:
    def __init__(self) -> None:
        self.model, self.score = object(), object()
        self.pending: Any = None
        self.memory = 0

    def choose(self, frame: dict[str, Any]) -> dict[str, Any]:
        assert self.pending is None
        choice = {"action_index": 0, "log_probability": -0.25, "navigation_only": False}
        self.pending = choice
        return choice

    def acknowledge(self, receipt: dict[str, Any]) -> None:
        assert receipt["delivery"] == "delivered" and self.pending is not None
        self.pending = None
        self.memory += 1


def frame(prefix: list[int], verb: str) -> dict[str, Any]:
    return {
        "binding_id": "root" + str(prefix),
        "source_family": "card_selection",
        "actions": [{}, {}],
        "public_input": {
            "candidates": [{"verb": verb}, {}],
            "context": {
                "interaction": {
                    "content": {
                        "surface": {"selection_contract": PLAN, "answer_plan": {"selected": prefix}}
                    }
                }
            },
        },
    }


def test_atomic_memory_and_decision_count_commit_only_after_native_answer() -> None:
    core = FakePolicy()
    policy = AnswerPolicy(cast(LivePolicy, core))
    first = policy.choose(frame([], "select"))
    policy.acknowledge({"delivery": "delivered", "delivery_domain": "local_answer_factor"})
    assert core.memory == 0 and policy.decisions == 0 and policy.planning
    second = policy.choose(frame([3], "select"))
    policy.acknowledge({"delivery": "delivered", "delivery_domain": "local_answer_factor"})
    final = policy.choose(frame([3, 1], "confirm"))
    assert first["answer_plan"]["answer_id"] == second["answer_plan"]["answer_id"]
    assert final["answer_plan"]["joint_behavior_log_probability"] == -0.75
    assert core.memory == 0
    policy.acknowledge({"delivery": "delivered", "delivery_domain": "native"})
    assert policy.decisions == 1 and policy.local_factors == 2 and not policy.planning
    assert cast(Any, policy.core).memory == 3 and policy.pending is None


@pytest.mark.parametrize("verb", ["confirm", "cancel"])
def test_empty_commit_and_cancel_are_one_answer(verb: str) -> None:
    policy = AnswerPolicy(cast(LivePolicy, FakePolicy()))
    policy.choose(frame([], verb))
    policy.acknowledge({"delivery": "delivered", "delivery_domain": "native"})
    assert policy.decisions == 1 and policy.local_factors == 0


def test_local_ack_cannot_be_claimed_as_native_and_failure_cannot_retry() -> None:
    policy = AnswerPolicy(cast(LivePolicy, FakePolicy()))
    policy.choose(frame([], "select"))
    with pytest.raises(ValueError):
        policy.acknowledge({"delivery": "delivered", "delivery_domain": "native"})
    with pytest.raises(ValueError):
        policy.acknowledge({"delivery": "delivered", "delivery_domain": "local_answer_factor"})
    assert policy.decisions == 0


def test_no_resume_of_prefix_or_second_choice_before_ack() -> None:
    policy = AnswerPolicy(cast(LivePolicy, FakePolicy()))
    with pytest.raises(ValueError):
        policy.choose(frame([1], "select"))
    policy.choose(frame([], "select"))
    with pytest.raises(ValueError):
        policy.choose(frame([], "select"))


def test_training_labels_group_factors_and_reject_unfinished_answers(tmp_path: Path) -> None:
    rows: list[dict[str, Any]] = []
    for i, verb in enumerate(["select", "select", "confirm"]):
        rows.extend(
            [
                {"kind": "policy_input", "frame": frame([0, 1][:i], verb)},
                {
                    "kind": "policy_choice",
                    "choice": {
                        "action_index": 0,
                        "answer_plan": {
                            "contract": PLAN,
                            "answer_id": "answer",
                            "factor_index": i,
                            "complete": verb == "confirm",
                        },
                    },
                    "receipt": {
                        "delivery_domain": "native" if verb == "confirm" else "local_answer_factor"
                    },
                },
            ]
        )

    def save(value: list[dict[str, Any]]) -> None:
        with gzip.open(tmp_path / "shared-public.jsonl.gz", "wt") as handle:
            for row in value:
                handle.write(json.dumps(row) + "\n")

    save(rows)
    labels = steps(tmp_path, {"episode_directory": "."})
    assert len(labels) == 1 and len(labels[0]["answer_factors"]) == 3
    assert labels[0]["label_weight"] == 1
    save(rows[:-2])
    with pytest.raises(ValueError):
        steps(tmp_path, {"episode_directory": "."})
    bad = copy.deepcopy(rows)
    bad[-1]["receipt"]["delivery_domain"] = "local_answer_factor"
    save(bad)
    with pytest.raises(ValueError):
        steps(tmp_path, {"episode_directory": "."})


def test_only_case_32_is_replaced_with_disjoint_worlds() -> None:
    parent: dict[str, Any] = {
        "plan": {
            "fit": [{"key": f"fit-{i:03d}", "seed_pool": [f"OLD{i}"]} for i in range(1, 57)],
            "heldout": [{"key": "dev"}],
        }
    }
    new = continuation_plan(parent)
    assert new["fit"][:31] == parent["plan"]["fit"][:31]
    assert new["fit"][32:] == parent["plan"]["fit"][32:]
    assert new["heldout"] == parent["plan"]["heldout"]
    assert new["fit"][31]["key"] == "fit-032-replacement-1"
    assert len(set(new["fit"][31]["seed_pool"])) == 8


def test_root_belt_action_is_an_ordinary_native_decision() -> None:
    policy = AnswerPolicy(cast(LivePolicy, FakePolicy()))
    choice = policy.choose(frame([], "discard"))
    assert "answer_plan" not in choice
    policy.acknowledge({"delivery": "delivered", "delivery_domain": "native"})
    assert policy.decisions == 1 and not policy.planning
