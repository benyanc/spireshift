from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_connector import (
    _evaluate_connector_checkpoint,
    _validate_benchmark_fixture_scope,
)
from spireshift.engine_progression import (
    CHECKS,
    validate_native_progression,
    validate_progression_save,
)
from spireshift.engine_qualification_cli import add_engine_parser


def native_evidence() -> dict[str, Any]:
    states = []
    stages = (
        ["initial"]
        + [
            f"act_{act}_{suffix}"
            for act in (1, 2, 3)
            for suffix in (
                "boss_before_force_kill",
                "after_force_kill",
                "before_proceed",
                "after_proceed",
            )
        ]
        + ["terminal"]
    )
    for stage in stages:
        terminal = stage == "terminal"
        act = 3 if terminal else 1 if stage == "initial" else int(stage[4])
        if stage.endswith("after_proceed"):
            act = min(act + 1, 3)
        victory_room = stage in {"act_3_after_proceed", "terminal"}
        state: dict[str, Any] = {
            "type": "decision",
            "context": {"ascension": 8, "act": act},
            "player": {"character_id": "IRONCLAD", "hp": 0 if terminal else 80},
            "decision": "game_over" if terminal else "combat_play",
        }
        if terminal:
            state["victory"] = True
        if stage.endswith("before_proceed"):
            state["decision"] = "combat_rewards_complete"
        if stage.endswith("after_proceed"):
            state["decision"] = (
                "event_choice" if act == 3 and stage.startswith("act_3") else "map_select"
            )
            if stage == "act_3_after_proceed":
                state["event_name"] = "The Architect"
        identity = {
            "seed": "SP1RESH1FTACT001",
            "ascension": 8,
            "profile_policy": "native_benchmark_full_v1",
            "native_game_over": terminal,
            "native_player_dead": terminal,
            "native_victory_room": victory_room,
        }
        states.append(
            {
                "stage": stage,
                "state": state,
                "native": identity,
                "native_game_over": terminal,
                "native_player_dead": terminal,
                "is_victory_room": victory_room,
                "native_player_hp": 0 if terminal else 80,
            }
        )
    by_stage = {row["stage"]: row for row in states}
    return {
        "schema_version": "native-run-progression-check-v1",
        "status": "native_progression_fixture_pass",
        "seed": "SP1RESH1FTACT001",
        "error": None,
        "wrapper_sha256": "wrapper",
        "game_sha256": "game",
        "godot_stub_sha256": "godot",
        "managed_runtime_version": "9.0.7",
        "privileged_fixture": True,
        "training_allowed": False,
        "natural_victories": 0,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "native_fixture_starts": 1,
        "fixture_forced_boss_defeats": 3,
        "planned_forced_boss_defeats": 3,
        "checks": dict.fromkeys(CHECKS, True),
        "states": states,
        "checkpoints": [
            {"act": act, "state": copy.deepcopy(by_stage[f"act_{act}_before_proceed"]["state"])}
            for act in (1, 2, 3)
        ],
        "delivered": [
            {
                "action": "proceed",
                "act": act,
                "result": by_stage[f"act_{act}_after_proceed"]["state"],
            }
            for act in (1, 2, 3)
        ]
        + [{"action": "choose_option", "act": 3, "result": by_stage["terminal"]["state"]}],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "natural_win",
        "ordinary_run",
        "training",
        "forced_count",
        "binary",
        "missing_act",
        "premature_architect",
        "missing_terminal",
        "hp_only",
        "skipped_proceed",
        "checkpoint",
        "runtime",
    ],
)
def test_fixture_cannot_manufacture_a_natural_win_or_skip_an_ending(mutation: str) -> None:
    raw = native_evidence()
    build = {
        "artifact_sha256": "wrapper",
        "runtime_sts2_sha256": "game",
        "godot_stub_sha256": "godot",
    }
    validate_native_progression(raw, build, "SP1RESH1FTACT001")
    if mutation == "natural_win":
        raw["natural_victories"] = 1
    elif mutation == "ordinary_run":
        raw["full_run_attempts"] = 1
    elif mutation == "training":
        raw["training_allowed"] = True
    elif mutation == "forced_count":
        raw["fixture_forced_boss_defeats"] = 2
    elif mutation == "binary":
        raw["godot_stub_sha256"] = "other"
    elif mutation == "missing_act":
        raw["states"].pop(4)
    elif mutation == "premature_architect":
        raw["states"][-2]["native_game_over"] = True
    elif mutation == "missing_terminal":
        raw["states"][-1]["native"]["native_game_over"] = False
    elif mutation == "hp_only":
        raw["states"][-1]["state"].pop("victory")
    elif mutation == "skipped_proceed":
        raw["delivered"].pop(0)
    elif mutation == "checkpoint":
        raw["checkpoints"][0]["state"]["context"]["act"] = 2
    else:
        raw["managed_runtime_version"] = "10.0.0"
    with pytest.raises(ValueError):
        validate_native_progression(raw, build, "SP1RESH1FTACT001")


def test_progression_verdict_requires_bound_profile_source_target_and_delivery() -> None:
    checks = dict.fromkeys(
        (
            "loaded_identity",
            "endpoint_owned_by_child",
            "native_continue_offered",
            "native_checkpoint_loaded",
            "native_A8_seed_preserved",
            "profile_path_logged",
            "steam_disabled_observed",
            "shared_profile_unchanged",
            "working_game_unchanged",
            "archive_still_valid",
            "template_unchanged",
            "natural_shutdown",
            "benchmark_profile_bound_before_launch",
            "progression_source_not_terminal",
            "progression_target_observed",
            "progression_all_actions_delivered",
        ),
        True,
    )
    assert (
        _evaluate_connector_checkpoint(checks, progression=True)["status"]
        == "shipped_checkpoint_input_pass"
    )
    for key in checks:
        failed = dict(checks)
        failed.pop(key)
        assert (
            _evaluate_connector_checkpoint(failed, progression=True)["status"]
            == "shipped_checkpoint_input_incomplete"
        )
    with pytest.raises(ValueError):
        _evaluate_connector_checkpoint(checks, progression=True, new_run=True)


@pytest.mark.parametrize("mutation", ["scope", "ordinary", "missing_save", "act"])
def test_progression_import_requires_a_privileged_checkpoint(mutation: str) -> None:
    fixture: dict[str, Any] = {
        "comparison_mode": "progression_v1",
        "privileged_fixture": True,
        "act": 3,
        "benchmark_progress": "progress",
        "profile_policy": "policy",
        "checkpoint_path": "save",
    }
    _validate_benchmark_fixture_scope(fixture)
    if mutation == "scope":
        fixture["privileged_fixture"] = False
    elif mutation == "ordinary":
        fixture["natural_run"] = True
    elif mutation == "missing_save":
        fixture.pop("checkpoint_path")
    else:
        fixture["act"] = 4
    with pytest.raises(ValueError):
        _validate_benchmark_fixture_scope(fixture)


def test_progression_commands_are_separate_from_natural_runs() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command")
    add_engine_parser(commands)
    for name in (
        "check-native-progression",
        "verify-native-progression",
        "preflight-progression-bridges",
        "compare-progression-bridges",
        "verify-progression-bridges",
    ):
        args = ["engine", name, "qualification.json", "progression.json"]
        if name.endswith("bridges"):
            args += ["--node", "/node"]
        result = parser.parse_args(args)
        assert result.progression_config == Path("progression.json")


def test_cumulative_patch_does_not_replace_boss_gameplay_hooks() -> None:
    root = Path(__file__).parents[2]
    patch = (root / "patches/engine/sts2-cli-v0.111.0-native-run-v24.patch").read_text()
    assert "public void SetVisible(bool visible) => Visible = visible;" in patch
    assert 'new Harmony("spireshift.headless.audio-service.v1").Patch(getter' in patch
    assert "if (!TestMode.IsOn) return true;" in patch
    assert "Crusher.BeforeDeath" not in patch
    config = json.loads(
        (
            root / "configs/engine-qualification/sts2-v0.111.0-cli-build-native-run-v24.json"
        ).read_text()
    )
    assert (
        config["expected_repaired"]["runtime_sts2_sha256"]
        == config["expected_baseline"]["runtime_sts2_sha256"]
    )


@pytest.mark.parametrize(
    "missing", ["visited_map_coords", "pre_finished_room", "map_point_history"]
)
def test_boss_checkpoint_needs_the_native_room_and_reload_position(missing: str) -> None:
    save = {
        "ascension": 8,
        "current_act_index": 2,
        "acts": [{}, {}, {"rooms": {"boss_id": "ENCOUNTER.EXAMPLE"}}],
        "visited_map_coords": [{"col": 3, "row": 14}],
        "pre_finished_room": {
            "room_type": "boss",
            "is_pre_finished": True,
            "encounter_id": "ENCOUNTER.EXAMPLE",
        },
        "map_point_history": [
            [],
            [],
            [{"map_point_type": "boss", "rooms": [{"model_id": "ENCOUNTER.EXAMPLE"}]}],
        ],
    }
    validate_progression_save(save, 3)
    save.pop(missing)
    with pytest.raises(ValueError):
        validate_progression_save(save, 3)


@pytest.mark.parametrize("pending", ["active", "pending_bundle", "action_executor_running"])
def test_progression_ending_cannot_hide_failed_cleanup(pending: str) -> None:
    raw = native_evidence()
    raw["schema_version"] = "native-run-progression-check-v3"
    raw["checks"].update({f"act_{act}_native_boss_map_coordinate": True for act in (1, 2, 3)})
    raw["checks"]["native_cleanup_completed"] = True
    raw["cleanup_identity"] = dict.fromkeys(
        (
            "active",
            "action_executor_running",
            "pending_host_operation",
            "pending_card_selection",
            "pending_card_reward",
            "pending_reward_set",
            "pending_bundle",
        ),
        False,
    )
    build = {
        "artifact_sha256": "wrapper",
        "runtime_sts2_sha256": "game",
        "godot_stub_sha256": "godot",
    }
    validate_native_progression(raw, build, "SP1RESH1FTACT001")
    raw["cleanup_identity"][pending] = True
    with pytest.raises(ValueError):
        validate_native_progression(raw, build, "SP1RESH1FTACT001")
