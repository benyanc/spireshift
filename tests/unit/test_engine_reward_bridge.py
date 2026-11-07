from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from spireshift import engine_reward_bridge as bridge
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import (
    _evaluate_connector_checkpoint,
    _fresh_reward_profile_required,
)
from spireshift.engine_connector_build import validate_connector_build_proposal
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_qualification_cli import add_engine_parser
from spireshift.engine_reward_bridge import SCENARIOS, validate_reward_cases


def cases() -> dict[str, Any]:
    return {
        "cases": [
            {"case_id": f"seed-{seed}-repeat-{repeat}", "seed": f"SEED{seed}", "scenario": scenario}
            for seed, scenario in enumerate(sorted(SCENARIOS), 1)
            for repeat in (1, 2)
        ]
    }


def test_reward_repeat_denominator_is_four_seed_scenario_pairs() -> None:
    actual = validate_reward_cases(cases())
    assert len(actual) == 8
    assert len({(row["seed"], row["scenario"]) for row in actual}) == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_id", "../escape"),
        ("case_id", ""),
        ("seed", "bad seed"),
        ("scenario", "unknown"),
        ("scenario", True),
    ],
)
def test_unbound_reward_cases_are_refused(field: str, value: Any) -> None:
    document = cases()
    document["cases"][0][field] = value
    with pytest.raises(ValueError):
        validate_reward_cases(document)


def test_missing_duplicate_or_unbalanced_reward_cases_are_refused() -> None:
    for change in ("missing", "duplicate", "scenario", "seed"):
        document = cases()
        if change == "missing":
            document["cases"].pop()
        elif change == "duplicate":
            document["cases"][1] = deepcopy(document["cases"][0])
        else:
            document["cases"][0][change] = document["cases"][2][change]
        with pytest.raises(ValueError):
            validate_reward_cases(document)


def test_reward_admission_requires_delivery_effects_and_fresh_profile_checks() -> None:
    required = _evaluate_connector_checkpoint({}, reward_bridge=True)["errors"]
    checks = {key: True for key in required}
    assert (
        _evaluate_connector_checkpoint(checks, reward_bridge=True)["status"]
        == "shipped_checkpoint_input_pass"
    )
    for key in (
        "reward_all_snapshots_match",
        "reward_pickup_capacity_and_skip_effects",
        "fresh_shop_progress_absent_before_launch",
        "reward_fresh_tutorials_preserve_facts",
    ):
        changed = {**checks, key: False}
        assert _evaluate_connector_checkpoint(changed, reward_bridge=True)["errors"] == [key]
    with pytest.raises(ValueError):
        _evaluate_connector_checkpoint({}, reward_bridge=True, bundle_bridge=True)


def test_reward_commands_are_explicit_scopes_with_required_node_and_recipe() -> None:
    parser = argparse.ArgumentParser()
    add_engine_parser(parser.add_subparsers(dest="command", required=True))
    for name in (
        "compare-reward-bridge",
        "compare-reward-bridges",
        "preflight-reward-bridges",
        "verify-reward-bridges",
    ):
        args = parser.parse_args(
            ["engine", name, "qualification.json", "recipe.json", "--node", "/node"]
        )
        assert args.engine_command == name


@pytest.mark.parametrize("field", ["build_config", "build_config_id", "build_report"])
def test_host_proposal_refuses_a_copied_historical_lineage_before_building(field: str) -> None:
    document = {"output_report": "artifacts/new-report.json", "patch_sha256": "new-patch"}
    local = {
        "build_config": "new-recipe.json",
        "build_config_id": manifest_identifier(document),
        "build_report": document["output_report"],
    }
    validate_connector_build_proposal({"local_build": local}, document, "new-recipe.json")
    with pytest.raises(ValueError, match="exact recipe"):
        validate_connector_build_proposal(
            {"local_build": {**local, field: "old-lineage"}}, document, "new-recipe.json"
        )


@pytest.mark.parametrize(
    "mode", ["shop_bridge_v1", "reward_bridge_v1", "reward_bridge_v2", "reward_bridge_v3"]
)
def test_every_qualified_reward_recipe_records_its_fresh_profile(mode: str) -> None:
    assert _fresh_reward_profile_required(mode)
    assert not _fresh_reward_profile_required("rest_bridge_v1")
    assert not _fresh_reward_profile_required(None)


def test_changing_host_recipe_patch_invalidates_its_old_local_identity() -> None:
    document = {"output_report": "artifacts/report.json", "patch_sha256": "original"}
    local = {
        "build_config": "recipe.json",
        "build_config_id": manifest_identifier(document),
        "build_report": document["output_report"],
    }
    with pytest.raises(ValueError):
        validate_connector_build_proposal(
            {"local_build": local}, {**document, "patch_sha256": "changed"}, "recipe.json"
        )


def test_first_failed_reward_case_stops_without_changing_the_denominator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    qualification = EngineQualificationConfig({"frozen": "synthetic"}, tmp_path)
    document = {"max_wall_seconds": 900}
    planned = validate_reward_cases(cases())
    workspace = tmp_path / "batch"
    monkeypatch.setattr(
        bridge,
        "preflight_reward_bridges",
        lambda *args, **kwargs: {"config_id": manifest_identifier(document)},
    )
    monkeypatch.setattr(
        bridge,
        "_batch_inputs",
        lambda *args: (document, planned, tmp_path / "template.json", {}, workspace),
    )
    called: list[str] = []

    def compare(*args: Any, **kwargs: Any) -> dict[str, Any]:
        called.append(kwargs["override"]["seed"])
        if len(called) == 3:
            raise ValueError("unsupported current mechanic")
        return {"status": "reward_action_comparison_pass"}

    monkeypatch.setattr(bridge, "compare_reward_bridge", compare)
    result = bridge.compare_reward_bridges(
        qualification, tmp_path / "batch.json", node=tmp_path / "node"
    )
    assert len(called) == 3
    assert result["completed_cases"] == 2
    assert result["failed_cases"] == 1
    assert result["not_attempted_cases"] == 5
    assert result["planned_cases"] == 8
    assert result["training_allowed"] is False
    assert json.loads((workspace / "batch.json").read_text()) == result
    assert (workspace / "progress-02.json").is_file()
