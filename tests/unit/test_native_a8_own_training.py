from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Sample, log_softmax
from spireshift.full_run_ppo_math import loss_gradient as discrete_loss
from spireshift.native_a8_own_experience import groups, samples
from spireshift.native_a8_own_policy import CONTRACT
from spireshift.native_a8_own_ppo import Decision, Factor, loss_gradient
from spireshift.native_a8_own_training_inputs import schedule
from spireshift.native_a8_rescue_game import TRACE, receipt
from spireshift.native_context_cache import cached_model
from spireshift.native_flow_live_v12 import append
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_win4_plan import PLAN


def test_single_factor_matches_existing_discrete_ppo() -> None:
    m = cached_model(model())
    rows = ({0: 0.5, 1: 1.0}, {2: 0.7}, {1: 0.1, 3: -0.5})
    factor = Factor(rows, 1)
    state = (1.0, *((0.0,) * (len(m.value_weights) - 1)))
    d = Decision((factor,), state, -1.2, 0.27, 0.9)
    total, gradient, stats = loss_gradient(m, [d], SETTINGS)
    expected, original_gradient, original_stats = discrete_loss(
        cast(Any, m),
        [Sample(rows, state, factor.action, d.old_log_probability, d.target, d.advantage)],
        clip=SETTINGS["clip"],
        entropy_coefficient=SETTINGS["entropy_coefficient"],
        value_coefficient=SETTINGS["value_coefficient"],
        temperature=SETTINGS["temperature"],
    )
    assert total == pytest.approx(expected, abs=1e-13)
    assert gradient == pytest.approx(original_gradient, abs=1e-13)
    assert stats["approximate_joint_kl"] == pytest.approx(original_stats["approximate_kl"])


def test_grouped_log_ratio_gradient_and_critic_use_one_native_decision() -> None:
    m = cached_model(model())
    factors = (Factor(({0: 1.0}, {1: 1.0}), 0), Factor(({2: 1.0}, {3: 1.0}), 1))
    old_logp = math.fsum(
        log_softmax(score_features(cast(Any, m.actor), f.rows), SETTINGS["temperature"])[f.action]
        for f in factors
    )
    state = (1.0, *((0.0,) * (len(m.value_weights) - 1)))
    d = Decision(factors, state, old_logp, 0.27, 0.9)
    _, gradient, stats = loss_gradient(m, [d], SETTINGS)
    assert stats["policy_loss"] == pytest.approx(-0.9)
    assert stats["approximate_joint_kl"] == pytest.approx(0.0, abs=1e-13)
    for index in (0, 1, 2, 3, m.actor.parameter_count - 1, m.actor.parameter_count):
        plus, minus = list(m.weights()), list(m.weights())
        plus[index] += 1e-5
        minus[index] -= 1e-5
        estimate = (
            loss_gradient(cached_model(m.with_weights(plus)), [d], SETTINGS)[0]
            - loss_gradient(cached_model(m.with_weights(minus)), [d], SETTINGS)[0]
        ) / 2e-5
        assert gradient[index] == pytest.approx(estimate, abs=1e-8)
    # Each factor can move by 15 percent and the *answer* still crosses the clip.
    changed = replace(d, old_log_probability=old_logp - 2 * math.log(1.15))
    settings = {**SETTINGS, "entropy_coefficient": 0, "value_coefficient": 0}
    _, clipped, stats = loss_gradient(m, [changed], settings)
    assert stats["clipped_fraction"] == 1.0
    assert not any(clipped)


def trace(tmp_path: Path, defect: str | None) -> None:
    raw_path = tmp_path / "worker/public-observations.jsonl.gz"
    raw_path.parent.mkdir()
    trace_path = tmp_path / TRACE
    answer_id = manifest_identifier({"atomic_answer_origin": "binding-0"})
    verbs = ("select", "confirm", "play") if defect != "unfinished" else ("select",)
    for index, verb in enumerate(verbs):
        bindings = [
            {"bound_action_id": f"bound-{index}-{action}", "raw_index": action}
            for action in range(2)
        ]
        frame = {
            "binding_id": f"binding-{index}",
            "observation": {"snapshot_id": str(index), "runtime_instance_id": "native"},
            "actions": bindings,
            "public_input": {"candidates": [{"verb": verb}, {"verb": "cancel"}]},
        }
        choice: dict[str, Any] = {
            "policy_contract": CONTRACT,
            "model_id": "foreign" if defect == "foreign" else "behavior",
            "behavior": "sampled_softmax",
            "draw_used": True,
            "navigation_only": False,
            "optimizer_updates": 0,
            "effective_input_id": "public",
            "public_input_id": "public",
            "action_index": 0,
            "effective_action_index": 0,
            "log_probability": -0.5,
            "bound_action_id": bindings[0]["bound_action_id"],
        }
        if verb != "play":
            choice["answer_plan"] = {
                "contract": PLAN,
                "factor_index": index,
                "answer_id": answer_id,
                "standalone_game_decision": False,
                "complete": verb == "confirm",
                "joint_behavior_log_probability": -0.5 * (index + 1) if defect != "joint" else -2,
            }
        domain = "local_answer_factor" if verb == "select" and defect != "domain" else "native"
        ack = receipt(frame, choice, domain, str(index + (2 if defect == "successor" else 1)))
        native = bindings if defect != "omitted" else [*bindings, {"bound_action_id": "omitted"}]
        append(
            raw_path,
            {
                "snapshot": {
                    "snapshot_id": str(index),
                    "bound_actions": {
                        "status": "complete",
                        "total_count": len(native),
                        "actions": native,
                    },
                }
            },
        )
        append(trace_path, {"kind": "policy_input", "frame": frame})
        append(trace_path, {"kind": "policy_choice", "choice": choice, "receipt": ack})
    final = {"observation": {"snapshot_id": str(len(verbs))}}
    append(trace_path, {"kind": "final_observation", "frame": final})
    append(raw_path, {"snapshot": {"snapshot_id": str(len(verbs))}})


def test_stream_groups_one_committed_answer_and_one_ordinary_move(tmp_path: Path) -> None:
    trace(tmp_path, None)
    actions = list(groups(tmp_path, "behavior"))
    assert [len(group) for group in actions] == [2, 1]
    assert math.fsum(choice["log_probability"] for _, choice in actions[0]) == -1.0


@pytest.mark.parametrize(
    "defect", ["unfinished", "foreign", "joint", "domain", "successor", "omitted"]
)
def test_stream_rejects_unverifiable_experience(tmp_path: Path, defect: str) -> None:
    trace(tmp_path, defect)
    with pytest.raises(ValueError):
        list(groups(tmp_path, "behavior"))


def test_worlds_are_disjoint_and_development_cannot_train(tmp_path: Path) -> None:
    study, control = schedule(), schedule(control=True)
    seeds = {t["seed"] for t in study["training"] + control["training"]}
    assert len(seeds) == 52
    assert seeds.isdisjoint(study["development"] + control["reload"])
    with pytest.raises(ValueError, match="held-out"):
        samples(
            tmp_path,
            {"task": {"partition": "development"}},
            cached_model(model()),
            cast(Any, None),
            "train",
            1,
        )
