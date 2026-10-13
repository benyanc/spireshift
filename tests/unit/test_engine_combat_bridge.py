from __future__ import annotations

import argparse
import copy
import json
from typing import Any

import pytest

from spireshift.engine_combat_bridge import SCENARIOS, SEEDS, validate_combat_cases
from spireshift.engine_connector import (
    _evaluate_connector_checkpoint,
    _validate_benchmark_fixture_scope,
)
from spireshift.engine_qualification_cli import add_engine_parser


def panel() -> dict[str, Any]:
    return {
        "cases": [
            {"case_id": f"seed-{index}-{scene}-repeat-{repeat}", "seed": seed, "scenario": scene}
            for index, seed in enumerate(SEEDS)
            for scene in sorted(SCENARIOS)
            for repeat in (1, 2)
        ]
    }


def test_combat_panel_has_four_pairs_across_two_independent_seeds() -> None:
    assert len(validate_combat_cases(panel())) == 8


@pytest.mark.parametrize("change", ["missing", "duplicate", "seed", "scenario", "path", "repeats"])
def test_combat_panel_keeps_missing_unknown_and_duplicate_cases_in_the_denominator(
    change: str,
) -> None:
    document = panel()
    if change == "missing":
        document["cases"].pop()
    elif change == "duplicate":
        document["cases"][1] = copy.deepcopy(document["cases"][0])
    elif change in {"seed", "scenario"}:
        document["cases"][0][change] = "unknown"
    elif change == "path":
        document["cases"][0]["case_id"] = "../other"
    else:
        document["cases"][0]["scenario"] = "temporary-stats"
    with pytest.raises(ValueError):
        validate_combat_cases(document)


@pytest.mark.parametrize(
    "missing",
    [
        "benchmark_profile_bound_before_launch",
        "combat_all_snapshots_match",
        "combat_all_actions_delivered",
        "combat_effect_signals_verified",
        "combat_fresh_tutorials_preserve_facts",
        "natural_shutdown",
    ],
)
def test_combat_scoped_verdict_requires_real_effect_delivery_profile_and_tutorial_checks(
    missing: str,
) -> None:
    required = _evaluate_connector_checkpoint({}, combat_bridge=True)["errors"]
    checks = {key: True for key in required}
    assert (
        _evaluate_connector_checkpoint(checks, combat_bridge=True)["status"]
        == "shipped_checkpoint_input_pass"
    )
    checks[missing] = False
    verdict = _evaluate_connector_checkpoint(checks, combat_bridge=True)
    assert verdict["status"] == "shipped_checkpoint_input_incomplete"
    assert missing in verdict["errors"]


def test_combat_verdict_cannot_inherit_a_different_comparison_scope() -> None:
    with pytest.raises(ValueError):
        _evaluate_connector_checkpoint({}, combat_bridge=True, profile_text=True)


def test_invalid_benchmark_scope_is_refused_before_worker_preparation() -> None:
    with pytest.raises(ValueError):
        _validate_benchmark_fixture_scope(
            {"comparison_mode": "other", "benchmark_progress": "progress"}
        )
    _validate_benchmark_fixture_scope(
        {"comparison_mode": "combat_bridge_v4", "benchmark_progress": "progress"}
    )


@pytest.mark.parametrize(
    "name",
    [
        "compare-combat-bridge",
        "compare-combat-bridges",
        "preflight-combat-bridges",
        "verify-combat-bridges",
        "probe-cli-combat-bridge",
    ],
)
def test_combat_cli_requires_a_pinned_recipe_and_node_runtime(name: str) -> None:
    parser = argparse.ArgumentParser()
    add_engine_parser(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(
        ["engine", name, "qualification.json", "recipe.json", "--node", "/node"]
    )
    assert args.engine_command == name
    assert str(args.node) == "/node"


@pytest.mark.parametrize("field", ["seed", "scenario"])
def test_non_string_combat_case_is_refused(field: str) -> None:
    document = panel()
    document["cases"][0][field] = []
    with pytest.raises(ValueError):
        validate_combat_cases(document)


def test_repeated_combat_prefixes_compare_action_semantics_and_effect_amounts(
    tmp_path: Any,
) -> None:
    from spireshift.core.manifest import manifest_identifier
    from spireshift.engine_combat_bridge import repeated_combat_prefixes

    rows = panel()["cases"]
    for row in rows:
        directory = tmp_path / row["case_id"]
        directory.mkdir()
        report: dict[str, Any] = {
            "probe": {"journey": [{"facts": {"strength": 7, "dexterity": 2}, "action": "play"}]}
        }
        report["report_id"] = manifest_identifier(report)
        (directory / "native-report.json").write_text(json.dumps(report))
    assert repeated_combat_prefixes(rows, tmp_path)
    report["probe"]["journey"][0]["facts"]["strength"] = 2
    report["probe"]["journey"][0]["facts"]["dexterity"] = 7
    report.pop("report_id")
    report["report_id"] = manifest_identifier(report)
    (directory / "native-report.json").write_text(json.dumps(report))
    assert not repeated_combat_prefixes(rows, tmp_path)
    assert not repeated_combat_prefixes(rows[:-1], tmp_path)


def test_combat_batch_stops_on_first_failure_and_keeps_full_denominator(
    tmp_path: Any, monkeypatch: Any
) -> None:
    import spireshift.engine_combat_bridge as bridge
    from spireshift.engine_qualification import EngineQualificationConfig

    cases = validate_combat_cases(panel())
    monkeypatch.setattr(
        bridge,
        "_combat_batch",
        lambda *a: ({"max_wall_seconds": 900}, cases, tmp_path / "recipe", tmp_path / "batch"),
    )
    monkeypatch.setattr(bridge, "preflight_combat_bridges", lambda *a, **k: {})
    monkeypatch.setattr(bridge, "combat_bridge_inputs", lambda *a: ({}, tmp_path / "recipe", {}))
    calls = []

    def fail(*a: Any, **k: Any) -> dict[str, str]:
        calls.append(k["case"])
        return {"status": "combat_comparison_incomplete", "error": "changed cost"}

    monkeypatch.setattr(bridge, "compare_combat_bridge", fail)
    result = bridge.compare_combat_bridges(
        EngineQualificationConfig({}, tmp_path), tmp_path / "recipe", node=tmp_path / "node"
    )
    assert len(calls) == 1
    assert result["completed_cases"] == 0
    assert result["failed_cases"] == 1
    assert result["not_attempted_cases"] == 7
    assert result["status"] == "combat_comparisons_incomplete"
    assert not (tmp_path / "batch/in-progress.json").exists()


@pytest.mark.parametrize(
    "missing", ["combat_full_potion_action_menu_compared", "combat_exact_slot_discard_effects"]
)
def test_discard_verdict_requires_full_menu_and_exact_slot_effect(missing: str) -> None:
    required = _evaluate_connector_checkpoint({}, combat_discard=True)["errors"]
    checks = {key: True for key in required}
    assert (
        _evaluate_connector_checkpoint(checks, combat_discard=True)["status"]
        == "shipped_checkpoint_input_pass"
    )
    checks[missing] = False
    assert missing in _evaluate_connector_checkpoint(checks, combat_discard=True)["errors"]


def test_discard_scope_cannot_inherit_the_old_filtered_combat_scope() -> None:
    with pytest.raises(ValueError):
        _evaluate_connector_checkpoint({}, combat_discard=True, combat_bridge=True)
    _validate_benchmark_fixture_scope(
        {"comparison_mode": "combat_bridge_v5", "benchmark_progress": "progress"}
    )


def test_discard_panel_requires_both_new_scenarios_without_replacing_old_recipes() -> None:
    from spireshift.engine_combat_bridge import DISCARD_SCENARIOS, combat_scope

    document = panel()
    for row in document["cases"]:
        row["scenario"] = (
            "discard-automatic" if row["scenario"] == "corruption" else "discard-duplicate"
        )
    assert len(validate_combat_cases(document, scenarios=DISCARD_SCENARIOS)) == 8
    with pytest.raises(ValueError):
        validate_combat_cases(document)
    assert combat_scope({})[2:4] == ("v6", "combat_bridge_v4")
    assert combat_scope({"bridge_revision": "potion_discard_v1"})[2:4] == ("v7", "combat_bridge_v5")
    with pytest.raises(ValueError):
        combat_scope({"bridge_revision": "unknown"})
