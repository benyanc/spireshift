from __future__ import annotations

import copy
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_rest_exploration import rest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input
from spireshift.native_combat_teacher import tasks
from spireshift.native_combat_teacher_data import (
    CONTRACT,
    INFORMATION,
    ReplayChooser,
    lesson,
    prefix_root,
    sampling_seed,
    sign_probability,
)
from spireshift.native_context_cache import cached_model
from spireshift.native_rest_exploration import verified_samples


def root() -> dict[str, Any]:
    p = rest()
    p["context"]["interaction"]["kind"] = "combat_turn"
    p["context"]["interaction"]["content"] = {
        "context": {"player": {"energy": 3, "block": 0}, "enemies": []}
    }
    p["candidates"] = p["candidates"][:2]
    body = {
        "public_input": p,
        "public_input_id": manifest_identifier(p),
        "prefix": [],
        "reference_action": 0,
    }
    return {**body, "root_id": manifest_identifier(body)}


def outcomes(n: int = 8) -> list[dict[str, Any]]:
    return [
        {
            "action": a,
            "repeat": r,
            "status": "terminal",
            "root_reached": True,
            "native_audit_valid": True,
            "training_return": 0.04 if a else 0.03,
            "maximum_floor": 10 if a else 8,
            "victory": False,
        }
        for r in range(n)
        for a in (0, 1)
    ]


def test_exact_public_prefix_root_and_continuation_have_separate_non_PPO_phases() -> None:
    r = root()
    prefix = copy.deepcopy(r["public_input"])
    prefix["context"]["persistent"]["player"]["gold"] += 1
    r["prefix"] = [{"public_input_id": manifest_identifier(prefix), "action_index": 1}]
    chooser = ReplayChooser(r, 0, 2, cached_model(model()), score(), 0.8)
    assert chooser(prefix)["teacher_phase"] == "verified_source_prefix"
    assert chooser(r["public_input"])["teacher_phase"] == "forced_counterfactual_root"
    assert chooser.root_reached
    c = chooser(r["public_input"])
    assert c["teacher_phase"] == "public_policy_continuation" and c["policy_contract"] == CONTRACT
    assert not any(k in r["public_input"] for k in ("native_seed", "repeat", "root_id"))
    validate_public_input(r["public_input"])
    with pytest.raises(ValueError, match="outside"):
        ReplayChooser(r, 10, 0, cached_model(model()), score(), 0.8)


def test_drifted_prefix_and_root_are_rejected_before_intervention() -> None:
    r = root()
    chooser = ReplayChooser(r, 0, 0, cached_model(model()), score(), 0.8)
    changed = copy.deepcopy(r["public_input"])
    changed["candidates"].reverse()
    with pytest.raises(ValueError, match="root mismatch"):
        chooser(changed)
    assert not chooser.root_reached
    r["prefix"] = [{"public_input_id": "different", "action_index": 0}]
    chooser = ReplayChooser(r, 0, 0, cached_model(model()), score(), 0.8)
    with pytest.raises(ValueError, match="prefix mismatch"):
        chooser(r["public_input"])


def test_teacher_data_cannot_be_reinterpreted_as_ordinary_on_policy_PPO() -> None:
    r = root()
    chooser = ReplayChooser(r, 0, 0, cached_model(model()), score(), 0.8)
    case: dict[str, Any] = {
        "status": "terminal",
        "seed": "TRAIN-SEED",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": [{"public_input": r["public_input"], "choice": chooser(r["public_input"])}],
    }
    with pytest.raises(ValueError):
        verified_samples(case, cached_model(model()), score(), 0.04, 0.8, 0.0)


def test_all_action_stream_cells_and_duplicate_control_are_planned_exactly_once() -> None:
    r = root()
    plan = tasks([r], 8, False)
    assert len(plan) == 16 and len({x["key"] for x in plan}) == 16
    assert {(x["action"], x["repeat"]) for x in plan} == {(a, n) for a in (0, 1) for n in range(8)}
    assert len(tasks([r], 2, True)) == 5
    assert sampling_seed(r["root_id"], 0) == sampling_seed(r["root_id"], 0)
    assert sampling_seed(r["root_id"], 0) != sampling_seed(r["root_id"], 1)


def test_lessons_keep_one_hidden_world_and_require_complete_action_coverage() -> None:
    r = root()
    result = lesson(r, outcomes(), 8)
    assert result["comparison_complete"] and result["eligible_for_experimental_value_supervision"]
    assert result["information_scope"] == INFORMATION and result["privileged_fixed_world_teacher"]
    assert not result["ordinary_PPO_eligible"] and not result["public_belief_search_eligible"]
    assert all(x["independent_hidden_worlds"] == 1 for x in result["actions"])
    assert result["preferences"][0]["admitted_exploratory_preference"]
    assert result["preferences"][0]["label_kind"] == "auxiliary_bootstrap_only"
    assert not lesson(r, outcomes()[:-1], 8)["comparison_complete"]
    failed = outcomes()
    failed[0]["status"] = "failed"
    assert not lesson(r, failed, 8)["eligible_for_experimental_value_supervision"]
    with pytest.raises(ValueError, match="repeats"):
        lesson(r, outcomes() + outcomes()[:1], 8)


def test_sign_test_excludes_ties_and_does_not_certify_two_sample_controls() -> None:
    assert sign_probability(8, 0) == pytest.approx(1 / 256)
    assert sign_probability(0, 0) == 1
    assert not lesson(root(), outcomes(2), 2)["preferences"][0]["admitted_exploratory_preference"]
    tied = outcomes()
    for x in tied:
        x["training_return"] = 0.03
    assert not lesson(root(), tied, 8)["preferences"][0]["admitted_exploratory_preference"]


def test_root_extraction_rejects_reserved_recovered_and_noncombat_sources() -> None:
    r = root()
    case: dict[str, Any] = {
        "status": "terminal",
        "seed": "TRAIN-SEED",
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "decisions": [
            {
                "public_input": r["public_input"],
                "choice": {"public_input_id": r["public_input_id"]},
            }
        ],
    }
    binding = {"partition": "train", "panel_purpose": "training", "native_seed": "TRAIN-SEED"}
    assert prefix_root(case, binding, 0)["public_input_id"] == r["public_input_id"]
    for fault in ("holdout", "recovered", "rest", "seed", "binding"):
        c, b = copy.deepcopy(case), dict(binding)
        if fault == "holdout":
            b["partition"] = "holdout"
        elif fault == "recovered":
            c["recovered"] = True
        elif fault == "rest":
            c["decisions"][0]["public_input"]["context"]["interaction"]["kind"] = "rest_site"
        elif fault == "seed":
            c["seed"] = "OTHER-SEED"
        else:
            c["decisions"][0]["choice"]["public_input_id"] = "changed"
        with pytest.raises(ValueError):
            prefix_root(c, b, 0)


def test_unplanned_streams_and_nonfinite_returns_cannot_supply_teacher_targets() -> None:
    for fault in ("unplanned", "infinite", "negative"):
        cells = outcomes()
        if fault == "unplanned":
            cells[0]["repeat"] = 100
        else:
            cells[0]["training_return"] = float("inf") if fault == "infinite" else -0.1
        with pytest.raises(ValueError):
            lesson(root(), cells, 8)
