from __future__ import annotations

import copy
import math
import time
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_tactical_learning import case

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo_math import Adam, Sample, loss_gradient
from spireshift.native_context_cache import cached_model
from spireshift.native_delayed_data import CONTRACT, FAMILIES, ending, key, qualify
from spireshift.native_delayed_evaluate import coverage, evaluate, predictions
from spireshift.native_delayed_execute import execute
from spireshift.native_delayed_inputs import plan
from spireshift.native_delayed_learning import batch
from spireshift.native_policy_updates import SETTINGS
from spireshift.native_structured_model import encode
from spireshift.native_structured_state import load, save
from spireshift.native_tactical_cases import FAMILIES as OLD_FAMILIES

CREDIT = {
    "baseline": "public_residual_ridge",
    "regularization": 0.001,
    "folds": 4,
    "fold_salt": "native-whole-run-value-crossfit-v1",
}


def tree(family: str = FAMILIES[0], world: int = 1, partition: str = "fit") -> dict[str, Any]:
    """Synthetic numerical test graph, not claimed as native collection evidence."""
    original = copy.deepcopy(case(OLD_FAMILIES[0])["public_input"])
    original["context"]["persistent"]["run"]["act_definition_id"] = "TEST_ACT"
    original["context"]["interaction"]["content"]["context"]["kind"] = "combat"
    original["context"]["persistent"]["player"]["gold"] = 99 + world
    nodes: dict[str, Any] = {}

    def visit(prefix: list[int], played: list[int], remaining: list[int], end: bool) -> None:
        public = copy.deepcopy(original)
        cc = public["context"]["interaction"]["content"]["context"]
        cc["player"]["energy"] = 3 - len(played)
        cc["player"]["block"] = 5 * int(1 in played)
        cc["player"]["statuses"] = [{"name": "setup", "amount": int(0 in played)}]
        public["candidates"] = [original["candidates"][i] for i in remaining] + [
            original["candidates"][-1]
        ]
        if end:
            cc["round"] += 1
            if family == FAMILIES[1] and played != [0, 1]:
                public["context"]["persistent"]["player"]["hp"] = 0
        if family == FAMILIES[0] and played == [0, 1]:
            public["context"]["interaction"] = {"kind": "reward_claim", "content": {"context": {}}}
        terminal, outcome, boundary = ending(family, original, public, len(prefix))
        children = [] if terminal else [key([*prefix, i]) for i in range(len(public["candidates"]))]
        nodes[key(prefix)] = {
            "prefix": prefix,
            "public_input": public,
            "public_input_id": manifest_identifier(public),
            "terminal": terminal,
            "outcome": outcome,
            "boundary": boundary,
            "children": children,
        }
        if not terminal:
            for action, identity in enumerate(remaining):
                visit(
                    [*prefix, action],
                    [*played, identity],
                    [i for i in remaining if i != identity],
                    False,
                )
            visit([*prefix, len(remaining)], played, remaining, True)

    visit([], [], [0, 1], False)
    return {
        "contract": CONTRACT,
        "family": family,
        "nodes": nodes,
        "task": {
            "key": f"{world}-{family}",
            "family": family,
            "seed": {"id": world, "seed": f"WORLD{world}", "partition": partition, "variant": 0},
        },
    }


def fitting() -> list[dict[str, Any]]:
    return [tree(f, world) for world in (1, 2) for f in FAMILIES]


@pytest.mark.parametrize("family,delay", [(FAMILIES[0], 2), (FAMILIES[1], 3)])
def test_success_requires_delayed_native_boundary_and_complete_current_menus(
    family: str, delay: int
) -> None:
    result = qualify(tree(family))
    assert result["minimum_success_actions"] == delay and result["immediate_successes"] == 0
    assert result["every_legal_action_observed"]


@pytest.mark.parametrize("fault", ["pruned", "forged", "unreachable", "cycle", "early"])
def test_incomplete_or_guessed_native_tree_is_rejected(fault: str) -> None:
    t = tree()
    if fault == "pruned":
        t["nodes"]["root"]["children"].pop()
    elif fault == "forged":
        t["nodes"]["0"]["outcome"] = 1
    elif fault == "unreachable":
        t["nodes"]["extra"] = copy.deepcopy(t["nodes"]["0"])
    elif fault == "cycle":
        t["nodes"]["root"]["children"][0] = "root"
    else:
        n = t["nodes"]["0"]
        n["public_input"]["context"]["interaction"] = {"kind": "reward_claim"}
        n["public_input_id"] = manifest_identifier(n["public_input"])
        n.update(terminal=True, outcome=1, boundary="native_encounter_won", children=[])
    with pytest.raises(ValueError):
        qualify(t)


def test_exact_baseline_is_current_policy_expectation_not_the_best_action() -> None:
    m, s, t = cached_model(model()), score(), tree()
    v, probabilities = predictions(m, t, s)
    expected = probabilities["root"][0] * probabilities["0"][0]
    assert v["root"] == pytest.approx(expected)
    assert 0 < v["root"] < 1
    assert v["1"] == 0
    assert evaluate(m, [t], s)["mean_success_probability"] == pytest.approx(expected)


def test_expected_delayed_policy_gradient_matches_finite_difference_of_terminal_success() -> None:
    m, s, t = cached_model(model()), score(), tree(FAMILIES[1])
    v, probs = predictions(m, t, s)
    total = [0.0] * m.actor.parameter_count

    def visit(name: str, probability: float, path: list[tuple[str, int]]) -> None:
        node = t["nodes"][name]
        if not node["terminal"]:
            for action, child in enumerate(node["children"]):
                visit(child, probability * probs[name][action], [*path, (name, action)])
            return
        for parent, action in path:
            rows, state = encode(t["nodes"][parent]["public_input"], m, s)
            sample = Sample(
                rows,
                state,
                action,
                math.log(probs[parent][action]),
                node["outcome"],
                node["outcome"] - v[parent],
            )
            _, g, _ = loss_gradient(
                cast(Any, m),
                [sample],
                clip=0.2,
                entropy_coefficient=0,
                value_coefficient=0,
                temperature=0.8,
            )
            for i in range(len(total)):
                total[i] += probability * g[i]

    visit("root", 1.0, [])
    active = sorted(range(len(total)), key=lambda i: abs(total[i]), reverse=True)[:3]
    assert all(abs(total[i]) > 1e-4 for i in active)
    # Check coordinates with an actual delayed-return gradient, as well as the
    # common-score-shift coordinate. Two inactive coordinates would be vacuous.
    for coordinate in [0, *active]:
        plus, minus = list(m.weights()), list(m.weights())
        plus[coordinate] += 1e-5
        minus[coordinate] -= 1e-5
        derivative = (
            predictions(cast(Any, m.with_weights(plus)), t, s)[0]["root"]
            - predictions(cast(Any, m.with_weights(minus)), t, s)[0]["root"]
        ) / 2e-5
        assert total[coordinate] == pytest.approx(-derivative, abs=1e-7)


def test_only_baselines_differ_on_matched_initial_own_policy_multi_step_batches() -> None:
    m, s, ts = cached_model(model()), score(), fitting()
    before = m.as_dict()
    learned, a = batch(m, ts, s, CREDIT, "learned", 2, 1)
    exact, b = batch(m, ts, s, CREDIT, "exact", 2, 1)
    assert a["sampled_trace_id"] == b["sampled_trace_id"]
    assert len(learned) > 32 and len(exact) == len(learned)
    for x, y in zip(learned, exact, strict=True):
        assert (x.rows, x.state, x.action, x.target, x.old_log_probability) == (
            y.rows,
            y.state,
            y.action,
            y.target,
            y.old_log_probability,
        )
    assert any(x.advantage != y.advantage for x, y in zip(learned, exact, strict=True))
    assert m.as_dict() == before and a["ordinary_PPO_eligible"] is False
    for fold in a["cross_fit"]:
        assert not set(fold["fitting_worlds"]) & set(fold["predicted_worlds"])
        episodes = set(fold["predicted_episodes"])
        for trace in a["traces"]:
            assert (trace["episode"] in episodes) == (trace["world"] in fold["predicted_worlds"])


def test_learned_arm_never_uses_exact_tree_values(monkeypatch: pytest.MonkeyPatch) -> None:
    import spireshift.native_delayed_learning as learning

    monkeypatch.setattr(
        learning, "predictions", lambda *_a: pytest.fail("No oracle in learned credit")
    )
    batch(cached_model(model()), fitting(), score(), CREDIT, "learned", 2, 1)


def test_heldout_cases_cannot_enter_credit_fitting_or_look_like_fresh_roots() -> None:
    t = tree(partition="heldout")
    with pytest.raises(ValueError, match="fitting worlds"):
        batch(cached_model(model()), [t], score(), CREDIT, "learned", 2, 1)
    result = coverage([tree()], [t])
    assert result["heldout_roots_already_seen_in_fitting"] == 1
    assert result["genuinely_unseen_heldout_public_roots"] == 0
    assert not result["broad_generalization_established"]


def test_restart_preserves_complete_Adam_and_identical_subsequent_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_delayed_execute as module

    m, s = cached_model(model()), score()
    adam = Adam(7, (0.001,) * m.parameter_count, (0.01,) * m.parameter_count)
    original = m.as_dict(), adam.as_dict()
    cfg = {"credit": CREDIT}
    context = {"config": cfg, "score": s, "models": {2: m}, "adams": {2: adam}}
    monkeypatch.setattr(module, "trees", lambda *_a: fitting())
    state = save(tmp_path / "initial.json", m, adam)
    initial = {
        "state_path": "initial.json",
        "state_id": state["state_id"],
        "model_id": m.model_id,
        "optimizer_steps": adam.steps,
    }
    done = {"initial": initial}
    task = {
        "kind": "fit",
        "player": 2,
        "arm": "learned",
        "state": "initial",
        "start_round": 1,
        "end_round": 4,
    }
    for n in ("whole", "part1", "part2"):
        (tmp_path / n).mkdir()
    whole = execute(tmp_path, context, task, done, tmp_path / "whole", time.monotonic() + 30)
    first = execute(
        tmp_path, context, {**task, "end_round": 2}, done, tmp_path / "part1", time.monotonic() + 30
    )
    second = execute(
        tmp_path,
        context,
        {**task, "state": "first", "start_round": 3},
        {**done, "first": first},
        tmp_path / "part2",
        time.monotonic() + 30,
    )
    w, wa, _ = load(tmp_path / whole["state_path"])
    r, ra, _ = load(tmp_path / second["state_path"])
    assert w.as_dict() == r.as_dict() and wa == ra
    assert (m.as_dict(), adam.as_dict()) == original
    assert wa.steps > adam.steps


def test_all_finals_are_fixed_before_any_heldout_evaluation() -> None:
    tasks = plan({"seeds": [{"id": i} for i in range(3)], "rounds": 16, "chunk_rounds": 8})
    kinds = [t["kind"] for t in tasks]
    assert max(i for i, k in enumerate(kinds) if k == "fit") < min(
        i for i, k in enumerate(kinds) if k == "evaluate"
    )
    assert len([t for t in tasks if t["kind"] == "evaluate"]) == 4
    assert SETTINGS["value_coefficient"] == 0.5 and SETTINGS["minibatch_decisions"] == 128
