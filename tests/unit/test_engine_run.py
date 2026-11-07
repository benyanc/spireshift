"""Portable natural-run recipe gates, independent of private game bytes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.engine_run import HELPERS, load_run_recipe, verify_native_run


def test_natural_run_recipe_uses_its_own_seeds_and_never_admits_training(tmp_path: Path) -> None:
    path = Path("configs/engine-qualification/sts2-v0.111.0-natural-run-smoke-001-v1.json")
    document = json.loads(path.read_text())
    qualification = EngineQualificationConfig(document={"synthetic": True}, root=tmp_path)
    document["qualification_config_id"] = qualification.config_id
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(document))
    result = load_run_recipe(path, qualification)
    assert result["seed"] == "SPIRESHIFTA8DIAG001"
    assert result["training_allowed"] is False
    assert result["privileged_fixture"] is False
    assert manifest_identifier(result) != qualification.config_id


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ascension", 0),
        ("character", "Silent"),
        ("content_policy", "native_all_unlocked"),
        ("training_allowed", True),
        ("privileged_fixture", True),
        ("seed", "some-development-seed"),
        ("max_wall_seconds", 900),
        ("max_wall_seconds", True),
        ("max_decisions", 5000),
        ("max_repeated_states", 100),
        ("helpers_sha256", {}),
    ],
)
def test_invalid_scope_cap_or_dependency_inventory_is_refused(
    tmp_path: Path, key: str, value: Any
) -> None:
    source = Path("configs/engine-qualification/sts2-v0.111.0-natural-run-smoke-001-v1.json")
    qualification = EngineQualificationConfig(document={}, root=tmp_path)
    document = copy.deepcopy(json.loads(source.read_text()))
    document["qualification_config_id"] = qualification.config_id
    document[key] = value
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="short, fixed-A8"):
        load_run_recipe(path, qualification)


def test_new_seed_contract_requires_the_games_canonical_characters(tmp_path: Path) -> None:
    source = Path("configs/engine-qualification/sts2-v0.111.0-natural-run-smoke-001-v8.json")
    q = EngineQualificationConfig(document={}, root=tmp_path)
    document = json.loads(source.read_text())
    document["qualification_config_id"] = q.config_id
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(document))
    assert load_run_recipe(path, q)["seed"] == "SP1RESH1FTA8D1AG001"
    document["seed"] = "SPIRESHIFTA8DIAG001"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="fixed-A8"):
        load_run_recipe(path, q)


@pytest.fixture
def sealed_diagnostic(tmp_path: Path) -> tuple[EngineQualificationConfig, Path]:
    """Synthetic action chain: exercise auditing without game bytes or engine execution."""
    import hashlib

    q = EngineQualificationConfig(document={}, root=tmp_path)
    directory = tmp_path / "artifacts/synthetic"
    sources = directory / "source-at-launch"
    sources.mkdir(parents=True)
    recipe = json.loads(
        Path("configs/engine-qualification/sts2-v0.111.0-natural-run-smoke-001-v8.json").read_text()
    )
    recipe["qualification_config_id"] = q.config_id
    recipe["helpers_sha256"] = {}
    for name in HELPERS:
        (sources / name).write_text("// synthetic saved source\n")
        recipe["helpers_sha256"][name] = hashlib.sha256((sources / name).read_bytes()).hexdigest()
    (sources / "recipe.json").write_text(json.dumps(recipe))
    action = {"bound_action_id": "action", "interaction_id": "interaction", "verb": "activate"}
    first = {
        "snapshot_id": "first",
        "status": "interactive",
        "persistent": {"content": {"run": {"ascension": 8, "floor": 1}}},
        "interaction": {"kind": "event_option", "interaction_id": "interaction"},
        "information_policy": {"includes_hidden_information": False},
        "completeness": {"status": "complete"},
        "session": {"runtime_instance_id": "worker"},
        "bound_actions": {
            "status": "complete",
            "materialized_count": 1,
            "total_count": 1,
            "actions": [action],
        },
    }
    last = copy.deepcopy(first)
    last.update(snapshot_id="last", status="observed")
    last["interaction"] = {"kind": "game_over", "content": {"surface": {"victory": False}}}
    last["bound_actions"] = {
        "status": "complete",
        "materialized_count": 0,
        "total_count": 0,
        "actions": [],
    }
    receipt = {"delivery": "delivered", "action": action, "successor": last}
    rows = [
        {"stage": "observation", "index": 0, "snapshot": first, "reads": []},
        {"stage": "action", "index": 0, "snapshot": first, "action": action},
        {"stage": "receipt", "index": 0, "snapshot": first, "receipt": receipt},
        {"stage": "observation", "index": 1, "snapshot": last, "reads": []},
    ]
    start = {
        "seed": recipe["seed"],
        "ascension": 8,
        "started_with_neow": True,
        "native_game_over": False,
        "native_player_dead": False,
    }
    end = {
        **start,
        "native_game_over": True,
        "native_player_dead": True,
        "native_victory_room": False,
    }
    transcript = [
        {
            "request": {
                "cmd": "start_run",
                "character": "Ironclad",
                "ascension": 8,
                "seed": recipe["seed"],
                "content_policy": recipe["content_policy"],
            }
        },
        {"request": {"cmd": "run_identity"}, "response": start},
        {"request": {"cmd": "action"}},
        {"request": {"cmd": "run_identity"}, "response": end},
    ]
    probe = {
        "full_run_attempts": 1,
        "private_start_identity": start,
        "private_final_identity": end,
        "native_ending_evidence_agrees": True,
        "runtime_errors": [],
        "run": {
            "decisions": 1,
            "maximum_floor": 1,
            "decision_families": {"event_option": 1, "game_over": 1},
            "victory": False,
            "terminal": True,
            "agent_cpu_seconds": 0.1,
        },
    }
    (directory / "run-probe.json").write_text(json.dumps(probe))
    (directory / "diagnostics.json").write_text("{}")
    for name, data in (("public-run.jsonl", rows), ("private-transcript.jsonl", transcript)):
        (directory / name).write_text("\n".join(json.dumps(row) for row in data) + "\n")
    report = {
        "schema_version": "engine-native-run-report-v1",
        "seed": recipe["seed"],
        "qualification_config_id": q.config_id,
        "config_id": manifest_identifier(recipe),
        "status": "candidate_terminal",
        "benchmark_denominator": 1,
        "probe": probe,
        "checks": {"synthetic_isolation": True},
        "process": {"returncode": 0, "timed_out": False},
        "training_allowed": False,
        "privileged_fixture": False,
        "terminal_semantics_qualified": False,
        "optimizer_steps": 0,
        "game_apps_created": 0,
        "objective": {"whole_run_budget": 128},
        "files": {},
    }
    path = directory / "summary.json"
    path.write_text(json.dumps(report))
    _reseal(path)
    return q, path


def _reseal(path: Path) -> None:
    import hashlib

    report = json.loads(path.read_text())
    report["probe"] = json.loads((path.parent / "run-probe.json").read_text())
    report["files"] = {
        name: hashlib.sha256((path.parent / name).read_bytes()).hexdigest()
        for name in (
            "run-probe.json",
            "private-transcript.jsonl",
            "public-run.jsonl",
            "diagnostics.json",
        )
    }
    report.pop("report_id", None)
    report["report_id"] = manifest_identifier(report)
    path.write_text(json.dumps(report))


def test_saved_chain_audit_reconstructs_without_any_game(sealed_diagnostic: Any) -> None:
    q, path = sealed_diagnostic
    result = verify_native_run(q, path)
    assert result["delivered_decisions"] == 1
    assert result["games_replayed"] == 0
    assert result["training_allowed"] is False


@pytest.mark.parametrize(
    "corruption",
    [
        "unadvertised",
        "unknown_delivery",
        "private_input",
        "truncated_menu",
        "stale_read",
        "fabricated_ending",
    ],
)
def test_resealed_bad_evidence_still_fails_saved_audit(
    sealed_diagnostic: Any, corruption: str
) -> None:
    q, path = sealed_diagnostic
    journal = path.parent / "public-run.jsonl"
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    if corruption == "unadvertised":
        rows[1]["action"]["bound_action_id"] = "invented"
    elif corruption == "unknown_delivery":
        rows[2]["receipt"]["delivery"] = "unknown"
    elif corruption == "private_input":
        rows[0]["snapshot"]["persistent"]["content"]["rng"] = 1
    elif corruption == "truncated_menu":
        rows[0]["snapshot"]["bound_actions"]["total_count"] = 2
    elif corruption == "stale_read":
        rows[0]["reads"] = [{"expected_snapshot_id": "old", "observed_snapshot_id": "old"}]
    else:
        probe_path = path.parent / "run-probe.json"
        probe = json.loads(probe_path.read_text())
        probe["private_final_identity"]["native_player_dead"] = False
        probe["private_final_identity"]["native_game_over"] = False
        probe_path.write_text(json.dumps(probe))
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    _reseal(path)
    with pytest.raises(ValueError):
        verify_native_run(q, path)
