"""A scoped rest differential must count failures and leave long batches owner-launched."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from spireshift import engine_rest_bridge as rest
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_connector import _evaluate_connector_checkpoint
from spireshift.engine_qualification import EngineQualificationConfig, _sha_file


def cases() -> list[dict[str, str]]:
    return [
        {
            "case_id": f"seed-{seed}-{kind}-{repeat}",
            "seed": f"SYNTHETIC{seed}",
            "scenario": scenario,
        }
        for repeat in (1, 2)
        for seed in (3, 6)
        for kind, scenario in (
            ("heal", "tent-heal-cancel-smith"),
            ("smith", "tent-smith-cancel-heal"),
        )
    ]


def test_repeats_do_not_become_eight_independent_seeds() -> None:
    assert rest.validate_rest_cases({"cases": cases()}) == cases()
    for bad in (cases()[:-1], [cases()[0]] * 8):
        with pytest.raises(ValueError):
            rest.validate_rest_cases({"cases": bad})


def test_first_failed_rest_case_stops_and_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = EngineQualificationConfig({"qualification": "test"}, tmp_path)
    directory = tmp_path / "configs/engine-qualification"
    directory.mkdir(parents=True)
    template: dict[str, Any] = {"fixture": "synthetic"}
    (directory / "template.json").write_text(json.dumps(template))
    config = {
        "schema_version": "engine-rest-bridges-config-v1",
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

    def failed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs["override"])
        return {"status": "rest_comparison_incomplete", "report_id": "synthetic-failure"}

    monkeypatch.setattr(rest, "compare_rest_bridge", failed)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=10_000_000_000))
    result = rest.compare_rest_bridges(q, path, node=Path("unused"))
    assert len(calls) == len(result["cases"]) == 1
    assert (result["completed_cases"], result["failed_cases"], result["not_attempted_cases"]) == (
        0,
        1,
        7,
    )
    assert result["full_run_attempts"] == result["optimizer_steps"] == 0
    assert result["training_allowed"] is False
    with pytest.raises(FileExistsError):
        rest.compare_rest_bridges(q, path, node=Path("unused"))


def test_starting_or_combat_success_cannot_pass_a_rest_comparison() -> None:
    required = [
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
    checks = dict.fromkeys(
        required
        + ["complete_public_starting_event", "same_starting_public_option_titles_and_availability"],
        True,
    )
    assert _evaluate_connector_checkpoint(checks, rest_bridge=True)["status"].endswith("incomplete")
    checks.update(
        dict.fromkeys(
            [
                "complete_public_rest_fixture",
                "rest_all_snapshots_match",
                "rest_all_actions_delivered",
                "rest_final_map_observed",
                "rest_heal_and_upgrade_observed",
            ],
            True,
        )
    )
    assert _evaluate_connector_checkpoint(checks, rest_bridge=True)["status"].endswith("pass")
    with pytest.raises(ValueError):
        _evaluate_connector_checkpoint(checks, journey=True, rest_bridge=True)


def test_rest_seen_baseline_requires_the_native_profile_and_keeps_other_tutorials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    q = EngineQualificationConfig({"archive_name": "test-build"}, tmp_path)
    profile = (
        tmp_path
        / "Library/Application Support/SpireShift/engine-profiles/test-build-checkpoint-example"
    )
    original = profile / "default/1/modded/profile1/saves/progress.save"
    original.parent.mkdir(parents=True)
    original.write_text(json.dumps({"enable_ftues": True, "ftue_completed": ["rest_site_ftue"]}))
    copy = tmp_path / "artifacts/baseline/progress.save"
    copy.parent.mkdir(parents=True)
    copy.write_bytes(original.read_bytes())
    source = {
        "qualification_config_id": q.config_id,
        "config_id": "connector",
        "profile": str(profile),
        "probe": {
            "latest_snapshot": {
                "interaction": {"kind": "unsupported", "content": {"context": {"kind": "rest"}}}
            }
        },
        "checks": dict.fromkeys(
            [
                "loaded_identity",
                "profile_path_logged",
                "shared_profile_unchanged",
                "natural_shutdown",
            ],
            True,
        ),
    }
    source["report_id"] = manifest_identifier(source)
    report = tmp_path / "artifacts/source.json"
    report.write_text(json.dumps(source))
    baseline = {
        "scope": (
            "native_generated_rest_site_ftue_seen_only_not_other_tutorial_or_fresh_profile_control"
        ),
        "source_report": "artifacts/source.json",
        "source_report_id": source["report_id"],
        "path": "artifacts/baseline/progress.save",
        "sha256": _sha_file(original),
    }
    rest.verify_rest_tutorial_baseline(q, baseline, "connector")
    copy.write_text(json.dumps({"enable_ftues": False, "ftue_completed": ["rest_site_ftue"]}))
    with pytest.raises(ValueError, match="provenance"):
        rest.verify_rest_tutorial_baseline(q, baseline, "connector")
    copy.write_bytes(original.read_bytes())
    original.write_text(
        json.dumps({"enable_ftues": True, "ftue_completed": ["rest_site_ftue", "other_ftue"]})
    )
    with pytest.raises(ValueError, match="provenance"):
        rest.verify_rest_tutorial_baseline(q, baseline, "connector")
