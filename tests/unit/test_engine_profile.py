from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_connector import _evaluate_connector_checkpoint
from spireshift.engine_profile import (
    CHECKS,
    validate_profile_description_report,
    verify_benchmark_progress,
)
from spireshift.engine_profile_bridge import validate_profile_cases
from spireshift.engine_qualification_cli import add_engine_parser


def profile() -> dict[str, Any]:
    return {
        "schema_version": 24,
        "unique_id": "spireshift-benchmark-full-v1",
        "enable_ftues": True,
        "ftue_completed": [],
        "character_stats": [
            {
                "id": "CHARACTER.IRONCLAD",
                "max_ascension": 8,
                "preferred_ascension": 8,
                "total_losses": 100,
                "total_wins": 0,
            }
        ],
        "epochs": [{"id": "example_epoch", "state": 5}],
        "discovered_acts": ["ACT.EXAMPLE"],
        "encounter_stats": [{"encounter_id": "ENCOUNTER.EXAMPLE"}],
    }


def policy(raw: bytes) -> dict[str, Any]:
    return {
        "progress_sha256": hashlib.sha256(raw).hexdigest(),
        "progress_schema": 24,
        "native_prior_run_count": 100,
        "native_epoch_count": 1,
        "native_revealed_epoch_state": 5,
        "native_act_count": 1,
        "native_encounter_count": 1,
    }


@pytest.mark.parametrize("change", ["digest", "tutorial", "A8", "epoch", "act", "runs"])
def test_benchmark_progress_rejects_changed_or_semantically_invalid_inputs(
    tmp_path: Path, change: str
) -> None:
    document = profile()
    original = json.dumps(document).encode()
    expected = policy(original)
    if change == "digest":
        document["unique_id"] = "other"
    elif change == "tutorial":
        document["ftue_completed"] = ["rest_site_ftue"]
    elif change == "A8":
        document["character_stats"][0]["max_ascension"] = 0
    elif change == "epoch":
        document["epochs"][0]["state"] = 2
    elif change == "act":
        document["discovered_acts"] = []
    else:
        document["character_stats"][0]["total_losses"] = 0
    raw = json.dumps(document).encode()
    if change != "digest":
        expected["progress_sha256"] = hashlib.sha256(raw).hexdigest()
    path = tmp_path / "progress.save"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        verify_benchmark_progress(path, expected)


def report() -> dict[str, Any]:
    return {
        "schema_version": "native-profile-description-check-v1",
        "seed": "SEED",
        "wrapper_sha256": "wrapper",
        "game_sha256": "game",
        "managed_runtime_version": "9.0.7",
        "privileged_fixture": True,
        "training_allowed": False,
        "shipped_game_compared": False,
        "full_run_attempts": 0,
        "optimizer_steps": 0,
        "native_fixture_starts": 1,
        "global_test_mode_retained": True,
        "profile_json_sha256": "progress",
        "checks": dict.fromkeys(CHECKS, True),
        "errors": [],
        "excluded": [{"kind": "potion", "reason": "native_pool_IsMock"}],
        "rows": [
            {"kind": kind, "id": kind, "description": "native formatted text"}
            for kind in ("potion", "relic", "card", "upgraded_card")
        ],
        "successful_descriptions": 4,
        "planned_potions": 2,
        "planned_relics": 1,
        "planned_cards": 1,
        "planned_upgraded_cards": 1,
        "original_normal_act_selection": {"acts": ["ACT.A"], "rng": {"counter": 3}},
        "managed_act_selection": {"acts": ["ACT.A"], "rng": {"counter": 3}},
    }


@pytest.mark.parametrize(
    "change", ["missing_row", "error", "mock_reason", "rng", "private_scope", "failed_gate"]
)
def test_native_oracle_retains_failed_missing_and_excluded_models(change: str) -> None:
    document = report()
    build = {"artifact_sha256": "wrapper", "runtime_sts2_sha256": "game"}
    expected = {"progress_sha256": "progress"}
    validate_profile_description_report(document, build, "SEED", expected)
    if change == "missing_row":
        document["rows"].pop()
    elif change == "error":
        document["errors"] = [{"id": "unsupported"}]
    elif change == "mock_reason":
        document["excluded"][0]["reason"] = "guessed_class_name"
    elif change == "rng":
        document["managed_act_selection"]["rng"]["counter"] = 2
    elif change == "private_scope":
        document["training_allowed"] = True
    else:
        document["checks"]["all_acts_discovered"] = False
    with pytest.raises(ValueError):
        validate_profile_description_report(document, build, "SEED", expected)


def test_profile_panel_requires_four_seeds_each_twice() -> None:
    cases = [
        {"case_id": f"seed-{seed}-repeat-{repeat}", "seed": f"SEED{seed}"}
        for seed in range(4)
        for repeat in (1, 2)
    ]
    assert len(validate_profile_cases({"cases": cases})) == 8
    cases[0]["seed"] = "SEED1"
    with pytest.raises(ValueError):
        validate_profile_cases({"cases": cases})


def test_profile_bridge_requires_progress_binding_and_exact_public_text() -> None:
    required = _evaluate_connector_checkpoint({}, profile_text=True)["errors"]
    checks = dict.fromkeys(required, True)
    assert (
        _evaluate_connector_checkpoint(checks, profile_text=True)["status"]
        == "shipped_checkpoint_input_pass"
    )
    for key in (
        "benchmark_profile_bound_before_launch",
        "same_public_profile_descriptions",
        "native_current_act_preserved",
    ):
        assert _evaluate_connector_checkpoint({**checks, key: False}, profile_text=True)[
            "errors"
        ] == [key]


def test_profile_commands_require_explicit_recipe_and_node() -> None:
    parser = argparse.ArgumentParser()
    add_engine_parser(parser.add_subparsers(dest="command", required=True))
    for name in (
        "compare-profile-bridge",
        "compare-profile-bridges",
        "preflight-profile-bridges",
        "verify-profile-bridges",
    ):
        assert (
            parser.parse_args(
                ["engine", name, "qualification.json", "recipe.json", "--node", "/node"]
            ).engine_command
            == name
        )
