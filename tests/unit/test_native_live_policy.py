from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score

from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_learning_control import TASKS, public_input
from spireshift.native_live_policy import CONTRACT, LivePolicy, import_checkpoint
from spireshift.native_structured_state import load, save


def frame() -> dict[str, Any]:
    public = public_input(TASKS[0], False)
    public["context"]["persistent"]["run"]["act_definition_id"] = "UNDERDOCKS"
    return {
        "schema_version": "shared-public-decision-v1",
        "contract": CONTRACT,
        "terminal": False,
        "binding_id": "current-frame",
        "observation": {"runtime_instance_id": "runtime", "snapshot_id": "snapshot"},
        "public_input": public,
        "actions": [
            {"key": f"action-{i}", "bound_action_id": f"bound-{i}", "raw_index": i}
            for i in range(len(public["candidates"]))
        ],
    }


def ack(f: dict[str, Any], choice: dict[str, Any]) -> dict[str, Any]:
    return {
        "binding_id": f["binding_id"],
        "delivery": "delivered",
        "bound_action_id": choice["bound_action_id"],
        "runtime_instance_id": "runtime",
        "before_snapshot_id": "snapshot",
        "successor_snapshot_id": "next-snapshot",
    }


def test_live_inference_uses_current_policy_without_mutating_weights_or_advancing_early() -> None:
    m = cached_model(model())
    original = m.as_dict()
    policy = LivePolicy(m, score(), "TESTSEED")
    f = frame()
    choice = policy.choose(f)
    assert choice["public_input_id"] and choice["model_id"] == m.model_id
    assert policy.chooser.visits == {} and policy.decisions == 0
    assert policy.pending is not None and policy.pending[2].visits
    assert policy.pending[2].model is m
    with pytest.raises(ValueError, match="unacknowledged"):
        policy.choose(f)
    policy.acknowledge(ack(f, choice))
    assert policy.chooser.visits and policy.decisions == 1 and policy.pending is None
    assert m.as_dict() == original
    with pytest.raises(ValueError, match="duplicate"):
        policy.acknowledge(ack(f, choice))


@pytest.mark.parametrize(
    "field,value",
    [
        ("delivery", "unknown"),
        ("runtime_instance_id", "wrong"),
        ("before_snapshot_id", "stale"),
        ("bound_action_id", "wrong"),
        ("binding_id", "old"),
        ("successor_snapshot_id", None),
    ],
)
def test_uncertain_delivery_poisoning_prevents_retry(field: str, value: Any) -> None:
    policy = LivePolicy(cached_model(model()), score(), "TESTSEED")
    f = frame()
    choice = policy.choose(f)
    receipt = ack(f, choice)
    receipt[field] = value
    with pytest.raises(ValueError, match="no retry"):
        policy.acknowledge(receipt)
    assert policy.chooser.visits == {} and policy.decisions == 0
    with pytest.raises(ValueError, match="uncertain"):
        policy.choose(f)


def test_explicit_metadata_import_preserves_every_weight_and_full_Adam(tmp_path: Path) -> None:
    original = cached_model(model())
    optimizer = Adam.zero(original.parameter_count)
    optimizer = Adam(
        17, tuple(0.01 for _ in optimizer.first), tuple(0.02 for _ in optimizer.second)
    )
    source = tmp_path / "original.json"
    state = save(source, original, optimizer)
    before = source.read_bytes()
    ref = {"path": "original.json", "sha256": _sha_file(source), "state_id": state["state_id"]}
    environment = {
        "parent_environment_id": original.actor.environment_id,
        "manifest_id": "sha256:" + "c" * 64,
    }
    imported, adam, receipt = import_checkpoint(
        tmp_path, ref, environment, score(), tmp_path / "imports/p2.json"
    )
    assert imported.weights() == original.weights() and adam.as_dict() == optimizer.as_dict()
    assert (
        source.read_bytes() == before
        and imported.actor.environment_id == environment["manifest_id"]
    )
    assert receipt["numeric_weights_exact"] and receipt["all_Adam_moments_and_counter_exact"]
    assert receipt["initial_policy_behavior_unchanged_claimed"] is False
    assert (
        import_checkpoint(tmp_path, ref, environment, score(), tmp_path / "imports/p2.json")[2]
        == receipt
    )
    restored, moments, _ = load(tmp_path / "imports/p2.json")
    assert restored.weights() == original.weights() and moments.as_dict() == optimizer.as_dict()


def test_hidden_input_and_ambiguous_legal_menus_never_get_a_choice() -> None:
    p = LivePolicy(cached_model(model()), score(), "TESTSEED")
    f = frame()
    f["actions"][1] = copy.deepcopy(f["actions"][0])
    with pytest.raises(ValueError, match="ambiguous"):
        p.choose(f)
    f = frame()
    f["public_input"]["context"]["rng"] = 2
    with pytest.raises(ValueError, match="Private"):
        p.choose(f)
