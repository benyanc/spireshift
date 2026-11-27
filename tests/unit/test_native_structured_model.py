from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, cast

import pytest
from test_native_action_context import model, score
from test_native_tactical_learning import case

from spireshift.full_run_policy import score_features
from spireshift.full_run_ppo_math import Adam, Sample, log_softmax
from spireshift.native_context_cache import cached_model
from spireshift.native_policy_updates import gradient
from spireshift.native_structured_model import BASE, SupplementModel, encode, extend, resize
from spireshift.native_structured_policy import Chooser
from spireshift.native_structured_state import load, save
from spireshift.native_structured_vocabulary import facts, select_columns


def public() -> dict[str, Any]:
    p: dict[str, Any] = case("survive_turn")["public_input"]
    p["context"]["persistent"]["run"]["act_definition_id"] = "UNDERDOCKS"
    p["context"]["interaction"]["content"]["context"]["kind"] = "combat"
    p["context"]["interaction"]["content"]["context"]["statuses"] = [
        {"definition_id": "STRENGTH", "amount": 2},
        {"definition_id": "DEXTERITY", "amount": 7},
    ]
    return p


def columns(p: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted({n for row in facts(p) for n in row}))


@pytest.mark.parametrize("arm", ["unchanged", "hashed", "named"])
def test_initial_behavior_all_original_weights_and_every_Adam_moment_survive_extension(
    arm: str,
) -> None:
    parent = cached_model(model())
    adam = Adam(83, (0.001,) * parent.parameter_count, (0.002,) * parent.parameter_count)
    before = parent.as_dict(), adam.as_dict()
    p = public()
    after, opt = extend(parent, adam, columns(p), arm)
    assert opt.steps == 83
    assert resize(after.weights(), after.actor.dimension, BASE, 32) == parent.weights()
    assert resize(opt.first, after.actor.dimension, BASE, 32) == adam.first
    assert resize(opt.second, after.actor.dimension, BASE, 32) == adam.second
    x, s = encode(p, parent, score())
    y, t = encode(p, after, score())
    assert score_features(cast(Any, parent.actor), x) == pytest.approx(
        score_features(cast(Any, after.actor), y), abs=1e-12
    )
    assert after.value(t) == pytest.approx(parent.value(s), abs=1e-12)
    for a, b in zip(x, y, strict=True):
        assert {i: v for i, v in b.items() if i < BASE} == a
    assert (parent.as_dict(), adam.as_dict()) == before
    if arm != "unchanged":
        w, _, _, linear = after.actor.unpack()
        assert not w[:, BASE:].any() and not linear[BASE:].any()
        assert all(v == 0 for v in after.value_weights[BASE:-1])


def test_matched_supplements_have_identical_capacity_and_frozen_layout() -> None:
    parent = cached_model(model())
    m = [
        extend(parent, Adam.zero(parent.parameter_count), columns(public()), a)[0]
        for a in ("hashed", "named")
    ]
    assert m[0].parameter_count == m[1].parameter_count
    assert m[0].weights() == m[1].weights()
    assert m[0].model_id != m[1].model_id
    assert m[0].actor.hidden_units == parent.actor.hidden_units == 32


def test_named_columns_preserve_owner_amount_and_current_card_copy_cost() -> None:
    p = public()
    p["context"]["interaction"]["content"]["context"]["hand"] = [
        {"definition_id": "STRIKE_IRONCLAD", "cost": 0},
        {"definition_id": "STRIKE_IRONCLAD", "cost": 2},
    ]
    names = columns(p)
    parent = cached_model(model())
    m, _ = extend(parent, Adam.zero(parent.parameter_count), names, "named")
    original, _ = encode(p, m, score())
    changed = copy.deepcopy(p)
    statuses = changed["context"]["interaction"]["content"]["context"]["statuses"]
    statuses[0]["amount"], statuses[1]["amount"] = 7, 2
    swapped, _ = encode(changed, m, score())
    assert original != swapped
    assert any(original[0].get(i) != swapped[0].get(i) for i in range(BASE, m.actor.dimension))
    changed = copy.deepcopy(p)
    changed["context"]["interaction"]["content"]["context"]["hand"][0]["cost"] = 1
    discounted, _ = encode(changed, m, score())
    assert any(original[0].get(i) != discounted[0].get(i) for i in range(BASE, m.actor.dimension))


def test_unfamiliar_facts_and_free_text_still_reach_unchanged_public_base() -> None:
    p = public()
    parent = cached_model(model())
    m, _ = extend(parent, Adam.zero(parent.parameter_count), columns(p), "named")
    original, _ = encode(p, m, score())
    p["context"]["interaction"]["content"]["context"]["unfamiliar_mechanic"] = 14
    p["candidates"][0]["description"] = "A new public description"
    changed, _ = encode(p, m, score())
    assert original != changed
    assert all(
        {i: v for i, v in a.items() if i >= BASE} == {i: v for i, v in b.items() if i >= BASE}
        for a, b in zip(original, changed, strict=True)
    )
    assert not any("description" in n for f in facts(p) for n in f)


def test_private_future_or_unresolved_handle_cannot_enter_named_layout() -> None:
    p = public()
    p["context"]["rng_state"] = 123
    with pytest.raises(ValueError, match="Private"):
        facts(p)
    p = public()
    p["candidates"][0]["entity_id"] = "opaque-runtime-id"
    with pytest.raises(ValueError, match="Opaque"):
        facts(p)


def test_candidate_permutation_and_optional_skip_stay_learnable() -> None:
    p = public()
    p["candidates"].append({"verb": "skip", "label": "Skip", "subject": None, "arguments": []})
    parent = cached_model(model())
    for arm in ("hashed", "named"):
        m, _ = extend(parent, Adam.zero(parent.parameter_count), columns(p), arm)
        rows, state = encode(p, m, score())
        reversed_rows, reversed_state = encode(
            {**p, "candidates": p["candidates"][::-1]}, m, score()
        )
        assert reversed_rows == rows[::-1] and state == reversed_state
        assert len(rows) == 4
        logs = log_softmax(score_features(cast(Any, m.actor), rows), 0.8)
        g = gradient(m, [Sample(rows, state, 3, logs[3], 0.2, 1.0)])[1]
        assert any(abs(v) > 1e-12 for v in g[: m.actor.parameter_count])


def test_new_named_weights_receive_correct_derivatives_at_zero_start() -> None:
    p = public()
    parent = cached_model(model())
    m, _ = extend(parent, Adam.zero(parent.parameter_count), columns(p), "named")
    rows, state = encode(p, m, score())
    logs = log_softmax(score_features(cast(Any, m.actor), rows), 0.8)
    sample = Sample(rows, state, 0, logs[0], 0.2, 1.0)
    _, g, _ = gradient(m, [sample])
    positions = range(m.actor.dimension * 32 + 64 + BASE, m.actor.parameter_count)
    i = max(positions, key=lambda i: abs(g[i]))
    assert abs(g[i]) > 1e-8
    a, b = list(m.weights()), list(m.weights())
    a[i] += 1e-5
    b[i] -= 1e-5
    numeric = (
        gradient(m.with_weights(a), [sample])[0] - gradient(m.with_weights(b), [sample])[0]
    ) / 2e-5
    assert numeric == pytest.approx(g[i], abs=1e-8)


def test_model_and_full_warm_optimizer_roundtrip_are_exact(tmp_path: Path) -> None:
    parent = cached_model(model())
    m, adam = extend(
        parent,
        Adam(5, (0.1,) * parent.parameter_count, (0.2,) * parent.parameter_count),
        columns(public()),
        "named",
    )
    saved = save(tmp_path / "state.json", m, adam)
    restored, opt, sid = load(tmp_path / "state.json")
    assert restored.as_dict() == m.as_dict() and opt == adam and sid == saved["state_id"]
    assert isinstance(restored, SupplementModel)
    assert restored.with_weights(restored.weights()).model_id == restored.model_id
    with pytest.raises(FileExistsError):
        save(tmp_path / "state.json", m, adam)


def test_family_document_frequency_uses_rare_family_despite_many_combat_rows() -> None:
    from collections import Counter

    counts = {
        "combat": Counter({"common": 1000, "combat-only": 999}),
        "rest": Counter({"rare-rest": 1}),
    }
    assert select_columns(counts, 2) == ("common", "rare-rest")
    assert select_columns(dict(reversed(list(counts.items()))), 2) == ("common", "rare-rest")


def test_matched_initial_action_draws_are_identical_across_input_arms() -> None:
    parent = cached_model(model())
    for training in (True, False):
        choices = []
        for arm in ("unchanged", "hashed", "named"):
            m, _ = extend(parent, Adam.zero(parent.parameter_count), columns(public()), arm)
            choices.append(Chooser(m, score(), "SAMECAN0N1CALWORLD", training)(public()))
        assert len({r["action_index"] for r in choices}) == 1
        assert len({r["draw"] for r in choices}) == 1
        assert all(
            math.isclose(
                r["policy_log_probability"], choices[0]["policy_log_probability"], abs_tol=1e-12
            )
            for r in choices
        )
