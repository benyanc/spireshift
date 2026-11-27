"""Shop qualification must preserve scope, failed denominators and native save identity."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_engine_checkpoint import checkpoint_fixture

from spireshift import engine_connector as connector
from spireshift import engine_shop_bridge as shop
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_checkpoint import verify_checkpoint_input
from spireshift.engine_connector import _evaluate_connector_checkpoint
from spireshift.engine_native import NativeQualificationConfig
from spireshift.engine_qualification import EngineQualificationConfig


def cases() -> list[dict[str, str]]:
    return [
        {
            "case_id": f"seed-{seed}-{index}-{repeat}",
            "seed": f"SYNTHETIC{seed}",
            "scenario": scenario,
        }
        for repeat in (1, 2)
        for seed in (3, 6)
        for index, scenario in enumerate(sorted(shop.SCENARIOS))
    ]


def test_low_disk_stops_before_game_copy_or_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = connector.ConnectorQualificationConfig(
        {},
        NativeQualificationConfig({}, EngineQualificationConfig({"synthetic": True}, tmp_path)),
    )
    node = tmp_path / "synthetic-node"
    node.touch()
    monkeypatch.setattr(connector, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(connector, "_running_games", lambda: [])
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=3_499_999_999))
    monkeypatch.setattr(
        connector, "_verified_archive", lambda _: pytest.fail("Must not prepare a game copy")
    )
    with pytest.raises(ValueError, match="3.5 GB free"):
        connector._probe_connector_private(config, node=node)
    assert not (tmp_path / "artifacts").exists()


def test_repeats_are_two_independent_seeds_and_four_scenario_pairs() -> None:
    assert shop.validate_shop_cases({"cases": cases()}) == cases()
    for bad in (cases()[:-1], [cases()[0]] * 8):
        with pytest.raises(ValueError):
            shop.validate_shop_cases({"cases": bad})


@pytest.mark.parametrize("exception", [False, True])
def test_first_failure_is_counted_and_stops_the_shop_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exception: bool
) -> None:
    q = EngineQualificationConfig({"test": "qualification"}, tmp_path)
    directory = tmp_path / "configs/engine-qualification"
    directory.mkdir(parents=True)
    template = {"synthetic": "template"}
    (directory / "template.json").write_text(json.dumps(template))
    config = {
        "schema_version": "engine-shop-bridges-config-v1",
        "stage": "owner_privileged_shop_fixture_differentials_only",
        "qualification_config_id": q.config_id,
        "training_allowed": False,
        "max_wall_seconds": 900,
        "cases": cases(),
        "workspace": "artifacts/batch",
        "template": "configs/engine-qualification/template.json",
        "template_id": manifest_identifier(template),
    }
    path = directory / "batch.json"
    path.write_text(json.dumps(config))
    calls = []

    def fail(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["override"])
        if exception:
            raise OSError("Synthetic setup failure before a completed report")
        return {"status": "shop_comparison_incomplete", "report_id": "failure"}

    monkeypatch.setattr(shop, "compare_shop_bridge", fail)
    monkeypatch.setattr(shop, "validate_shop_template", lambda *_: ({}, Path("unused")))
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=10_000_000_000))
    result = shop.compare_shop_bridges(q, path, node=Path("unused"))
    assert len(calls) == 1
    assert (result["completed_cases"], result["failed_cases"], result["not_attempted_cases"]) == (
        0,
        1,
        7,
    )
    assert result["full_run_attempts"] == result["optimizer_steps"] == 0
    assert result["training_allowed"] is False
    assert result["privileged_fixture"] is True
    with pytest.raises(FileExistsError):
        shop.compare_shop_bridges(q, path, node=Path("unused"))


def test_other_mechanics_cannot_pass_shop_qualification() -> None:
    base = [
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
    ]
    shop_gates = [
        "fresh_shop_progress_absent_before_launch",
        "complete_public_shop_fixture",
        "shop_all_snapshots_match",
        "shop_all_actions_delivered",
        "shop_final_map_observed",
        "shop_purchase_removal_and_exit_effects",
        "shop_fresh_potion_tutorial_delivered",
    ]
    checks = dict.fromkeys(base + shop_gates, True)
    assert _evaluate_connector_checkpoint(checks, shop_bridge=True)["status"].endswith("pass")
    for name in shop_gates:
        incomplete = {k: value for k, value in checks.items() if k != name}
        assert _evaluate_connector_checkpoint(incomplete, shop_bridge=True)["status"].endswith(
            "incomplete"
        )
    for other in ({"journey": True}, {"rest_bridge": True}, {"fresh_rest_tutorial": True}):
        with pytest.raises(ValueError):
            _evaluate_connector_checkpoint(checks, shop_bridge=True, **other)


@pytest.mark.parametrize("wrong_policy", [False, True])
def test_privileged_shop_save_has_its_own_scope_even_with_valid_hashes(
    tmp_path: Path, wrong_policy: bool
) -> None:
    q, config, report, report_path = checkpoint_fixture(tmp_path)
    report["schema_version"] = "engine-cli-shop_bridge-projection-probe-v1"
    report["status"] = "shop_bridge_public_projection_regression_pass"
    report["checks"]["native_shop_bridge_regressions_pass"] = report["checks"].pop(
        "native_checkpoint_regressions_pass"
    )
    report["probe"]["checkpoint"]["content_policy"] = (
        "native_all_unlocked" if wrong_policy else "serialized_native_privileged_shop_fixture"
    )
    report["report_id"] = manifest_identifier(
        {k: v for k, v in report.items() if k not in {"report_id", "report_path"}}
    )
    config["checkpoint_report_id"] = report["report_id"]
    report_path.write_text(json.dumps(report))
    if wrong_policy:
        with pytest.raises(ValueError):
            verify_checkpoint_input(q, config, panel="shop_bridge")
    else:
        assert verify_checkpoint_input(q, config, panel="shop_bridge")["seed"] == "SYNTHETICSEED"
        with pytest.raises(ValueError):
            verify_checkpoint_input(q, config)
