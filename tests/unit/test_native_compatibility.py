from __future__ import annotations

import copy
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_ppo_math import Adam
from spireshift.native_compatibility import run_guarded
from spireshift.native_compatibility_contract import (
    CONTRACT,
    ENVIRONMENT_SCOPE,
    LIVE_SCOPE,
    REPLAY_SCOPE,
    SCHEMA,
    checkpoint,
    compare_inputs,
    difference_paths,
    local,
    require_receipt,
)
from spireshift.native_context_cache import cached_model
from spireshift.native_learning_control import TASKS, public_input
from spireshift.native_structured_state import save


def pair() -> dict[str, Any]:
    public = public_input(TASKS[0], False)
    return {
        "key": "matched",
        "family": "event_option",
        "native_input": public,
        "official_input": copy.deepcopy(public),
        "native_action_keys": ["commit", "decline"],
        "official_action_keys": ["commit", "decline"],
        "missing_native_reads": [],
        "missing_official_reads": [],
    }


def test_same_checkpoint_matches_equivalent_inputs_without_updating_weights() -> None:
    m = cached_model(model())
    before = m.as_dict()
    result = compare_inputs(m, score(), pair())
    assert result["passed"] and result["maximum_probability_difference"] == 0
    assert result["maximum_feature_difference"] == 0
    assert m.as_dict() == before


def test_semantic_action_alignment_accepts_menu_permutation() -> None:
    p = pair()
    p["official_input"]["candidates"].reverse()
    p["official_action_keys"].reverse()
    result = compare_inputs(cached_model(model()), score(), p)
    assert result["passed"] and result["distributions_equal"]


def test_full_menu_gap_cannot_hide_behind_matching_common_mechanics() -> None:
    p = pair()
    p["official_input"]["candidates"].pop()
    p["official_action_keys"].pop()
    result = compare_inputs(cached_model(model()), score(), p)
    assert result["missing_official_actions"] == ["decline"]
    assert not result["passed"] and not result["distributions_equal"]


def test_different_public_input_fails_even_if_flat_policy_still_ranks_the_same() -> None:
    p = pair()
    p["native_input"]["context"]["persistent"]["player"]["relics"] = [{"id": "A"}]
    p["official_input"]["context"]["persistent"]["player"]["relics"] = [{"id": "B"}]
    result = compare_inputs(cached_model(model()), score(), p)
    assert not result["context_equal"] and not result["features_equal_on_common_actions"]
    assert not result["passed"]
    assert "/persistent/player/relics/0/id" in result["context_difference_paths"]


@pytest.mark.parametrize("host", ["native", "official"])
def test_incomplete_recorded_reads_block_equivalence(host: str) -> None:
    p = pair()
    p[f"missing_{host}_reads"] = ["combat_piles"]
    result = compare_inputs(cached_model(model()), score(), p)
    assert result["features_equal_on_common_actions"]
    assert not result["all_advertised_reads_present"] and not result["passed"]


def test_ambiguous_action_mapping_is_rejected() -> None:
    p = pair()
    p["official_action_keys"] = ["same", "same"]
    with pytest.raises(ValueError, match="Ambiguous"):
        compare_inputs(cached_model(model()), score(), p)


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_nonfinite_or_hidden_inputs_are_not_normalized_into_a_pass(value: float) -> None:
    p = pair()
    p["official_input"]["context"]["persistent"]["player"]["hp"] = value
    with pytest.raises(ValueError, match="Nonfinite"):
        compare_inputs(cached_model(model()), score(), p)
    p = pair()
    p["official_input"]["context"]["rng"] = 1
    with pytest.raises(ValueError, match="Private"):
        compare_inputs(cached_model(model()), score(), p)


def receipt(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    source = root / "source.py"
    source.write_text("unchanged\n")
    binding = {"checkpoint_state_ids": ["checkpoint"], "environment_id": "environment"}
    body = {
        "schema_version": SCHEMA,
        "contract": CONTRACT,
        "binding": binding,
        "sources": {"source.py": _sha_file(source)},
        "gates": {ENVIRONMENT_SCOPE: True, REPLAY_SCOPE: True, LIVE_SCOPE: False},
        "claim_scope": "checkpoint_bound_recorded_public_input_regression_only",
        "official_checkpoint_action_delivery_exercised": False,
        "new_games_launched": 0,
    }
    return {**body, "report_id": manifest_identifier(body)}, binding


def test_recorded_pass_cannot_certify_current_official_action_delivery(tmp_path: Path) -> None:
    report, binding = receipt(tmp_path)
    require_receipt(tmp_path, report, binding, required_scopes=(REPLAY_SCOPE,))
    with pytest.raises(ValueError, match=LIVE_SCOPE):
        require_receipt(tmp_path, report, binding)


def test_scope_forgery_is_rejected_even_with_a_recomputed_identifier(tmp_path: Path) -> None:
    report, binding = receipt(tmp_path)
    report["gates"][LIVE_SCOPE] = True
    report["report_id"] = manifest_identifier({k: v for k, v in report.items() if k != "report_id"})
    with pytest.raises(ValueError, match="cannot certify"):
        require_receipt(tmp_path, report, binding)


def test_changed_checkpoint_or_evidence_invalidates_receipt(tmp_path: Path) -> None:
    report, binding = receipt(tmp_path)
    with pytest.raises(ValueError, match="different inputs"):
        require_receipt(tmp_path, report, {**binding, "checkpoint_state_ids": ["new"]})
    (tmp_path / "source.py").write_text("changed\n")
    with pytest.raises(ValueError, match="evidence or implementation changed"):
        require_receipt(tmp_path, report, binding, required_scopes=(REPLAY_SCOPE,))


def test_recorded_receipt_cannot_relabel_itself_as_a_live_receipt(tmp_path: Path) -> None:
    report, binding = receipt(tmp_path)
    report["claim_scope"] = "live_checkpoint_delivery"
    report["gates"][LIVE_SCOPE] = True
    report["report_id"] = manifest_identifier({k: v for k, v in report.items() if k != "report_id"})
    with pytest.raises(ValueError, match="different compatibility scope"):
        require_receipt(tmp_path, report, binding)


def test_gate_blocks_the_command_before_any_training_can_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report, binding = receipt(tmp_path)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Blocked compatibility must not start even the first child command")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="blocks new training"):
        run_guarded(tmp_path, {"binding": binding}, report, ["train"])


def test_checkpoint_reader_preserves_full_state_and_refuses_implicit_migration(
    tmp_path: Path,
) -> None:
    m = cached_model(model())
    path = tmp_path / "state.json"
    state = save(path, m, Adam.zero(m.parameter_count))
    ref = {"path": "state.json", "sha256": _sha_file(path), "state_id": state["state_id"]}
    before = path.read_bytes()
    loaded, identity = checkpoint(tmp_path, ref, m.actor.environment_id, score().spec_id)
    assert loaded.as_dict() == m.as_dict() and identity["optimizer_steps"] == 0
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="no implicit migration"):
        checkpoint(tmp_path, ref, "other environment", score().spec_id)
    ref["optimizer_steps"] = 9
    with pytest.raises(ValueError, match="optimizer identity changed"):
        checkpoint(tmp_path, ref, m.actor.environment_id, score().spec_id)


def test_difference_witnesses_are_bounded_and_ownership_sensitive() -> None:
    assert difference_paths({"strength": 2, "dexterity": 7}, {"strength": 7, "dexterity": 2}) == [
        "/dexterity",
        "/strength",
    ]
    assert len(difference_paths({str(i): i for i in range(50)}, {}, limit=3)) == 3
    assert difference_paths({"x": 1}, {}, limit=0) == []


def test_path_aliases_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "source").write_text("x")
    (tmp_path / "alias").symlink_to(tmp_path / "source")
    for name in ("../source", "/tmp/source", "alias"):
        with pytest.raises(ValueError, match="without aliases"):
            local(tmp_path, name)


def test_recipe_binds_all_projection_and_python_dependencies() -> None:
    from spireshift.native_compatibility_inputs import ENTRY, SOURCES, python_dependencies

    root = Path(__file__).resolve().parents[2]
    names = python_dependencies(root)
    assert {f"src/spireshift/{n}" for n in SOURCES} <= names
    assert "src/spireshift/native_structured_vocabulary.py" in names
    assert ENTRY == "check-native-compatibility-v1.mjs"
    # Inventorying source dependencies is read-only and independent of saved artifacts.
    assert json.dumps(sorted(names))


def test_projection_contract_in_node() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not installed")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", "scripts/check-native-compatibility-v1.test.mjs"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
