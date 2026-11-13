"""Finite owner action-comparison stages cannot become training or discard failures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from spireshift import engine_journey_bridges as bridges
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import EngineQualificationConfig


def cases() -> list[dict[str, str]]:
    return [
        {
            "case_id": f"seed-{seed}-{option}-{repeat}",
            "seed": f"SYNTHETIC{seed}",
            "starting_option": title,
        }
        for repeat in (1, 2)
        for seed in (3, 6)
        for option, title in (("boots", "Winged Boots"), ("rod", "Dowsing Rod"))
    ]


def test_eight_comparisons_are_two_independent_seeds_and_four_choices() -> None:
    assert bridges.validate_journey_cases({"cases": cases()}) == cases()


@pytest.mark.parametrize(
    "gap", ["missing", "duplicate", "bad_seed", "unsupported_option", "no_repeat"]
)
def test_incomplete_or_unfrozen_cases_stop_before_native_execution(gap: str) -> None:
    rows = cases()
    if gap == "missing":
        rows.pop()
    elif gap == "duplicate":
        rows[1]["case_id"] = rows[0]["case_id"]
    elif gap == "bad_seed":
        rows[1]["seed"] = "../bad-seed"
    elif gap == "unsupported_option":
        rows[1]["starting_option"] = "unknown"
    else:
        rows[0]["starting_option"] = "Dowsing Rod"
    with pytest.raises(ValueError):
        bridges.validate_journey_cases({"cases": rows})


@pytest.mark.parametrize("phase", ["native", "shipped"])
def test_first_failed_prefix_is_counted_and_never_automatically_restarted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    qualification = EngineQualificationConfig({"test": "qualification"}, tmp_path)
    directory = tmp_path / "configs/engine-qualification"
    directory.mkdir(parents=True)
    document: dict[str, Any] = {
        "schema_version": "engine-journey-bridges-config-v1",
        "stage": "owner_first_combat_prefix_differentials_only",
        "qualification_config_id": qualification.config_id,
        "training_allowed": False,
        "max_wall_seconds": 900,
        "workspace": "artifacts/prefix-batch",
        "cases": cases(),
    }
    for role in ("native", "shipped"):
        template = directory / f"{role}.json"
        body = {
            "journey": {},
            "starting_bridge_config": "unused",
            "starting_bridge_report_id": "synthetic-startup",
        }
        template.write_text(json.dumps(body))
        document[f"{role}_template"] = str(template.relative_to(tmp_path))
        document[f"{role}_template_id"] = manifest_identifier(body)
    path = directory / "batch.json"
    path.write_text(json.dumps(document))
    monkeypatch.setattr(
        bridges, "verify_starting_bridges", lambda *_: {"batch_report_id": "synthetic-startup"}
    )
    monkeypatch.setattr(shutil, "disk_usage", lambda _: SimpleNamespace(free=5_000_000_000))
    jobs = []

    def failed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        jobs.append(args[3]["seed"])
        if phase == "native":
            return {"status": "journey_probe_incomplete", "report_id": "synthetic-failure"}
        attempt = tmp_path / "artifacts/native/attempt"
        attempt.mkdir(parents=True)
        (attempt / "private-starting-snapshot.json").write_text("{}")
        return {
            "status": "journey_public_projection_regression_pass",
            "report_id": "synthetic-native-success",
            "report_path": str(attempt / "report.json"),
            "probe": {"journey": [{"facts": "synthetic-prefix"}]},
        }

    def shipped_failed(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert args[2]["effective_native_config_id"] == manifest_identifier(
            kwargs["native_override"]
        )
        # A connection/runtime failure may leave no snapshots or delivery counters.
        return {
            "status": "first_combat_prefix_incomplete",
            "report_id": "synthetic-shipped-failure",
            "disposable_payload_removed_after_verified_success": False,
            "probe": {},
        }

    monkeypatch.setattr(bridges, "_probe_cli_document", failed)
    monkeypatch.setattr(bridges, "_probe_shipped_journey_document", shipped_failed)
    result = bridges.run_journey_bridges(qualification, path, node=Path("unused"))
    assert (result["completed_cases"], result["failed_cases"], result["not_attempted_cases"]) == (
        0,
        1,
        7,
    )
    assert len(result["cases"]) == len(jobs) == 1
    assert result["optimizer_steps"] == result["full_run_attempts"] == 0
    assert result["training_allowed"] is False
    if phase == "shipped":
        assert result["cases"][0]["public_actions_delivered"] is None
    with pytest.raises(FileExistsError):
        bridges.run_journey_bridges(qualification, path, node=Path("unused"))
    assert len(jobs) == 1


def test_owner_helper_displays_saved_results_and_refuses_partial_restart(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    helper = scripts / "compare-first-combat-v1.sh"
    shutil.copyfile(root / "scripts/compare-first-combat-v1.sh", helper)
    batch = tmp_path / (
        "artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/first-combat-bridges-v1"
    )
    batch.mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    uv = fake_bin / "uv"
    uv.write_text(
        '#!/bin/sh\ncase "$*" in\n'
        '  "run python - "*) shift 2; exec python3 "$@" ;;\n'
        '  *) printf "Unexpected job: %s\\n" "$*" >&2; exit 99 ;;\nesac\n'
    )
    uv.chmod(0o755)
    env = {**os.environ, "PATH": str(fake_bin) + os.pathsep + os.environ["PATH"]}
    saved = batch / "batch.json"
    saved.write_text(json.dumps({"status": "first_combat_comparisons_pass", "report_id": "saved"}))
    completed = subprocess.run(["bash", str(helper)], env=env, capture_output=True, text=True)
    assert completed.returncode == 0
    assert "no new checks follow" in completed.stdout and '"report_id": "saved"' in completed.stdout
    saved.unlink()
    (batch / "in-progress.json").write_text("{}")
    partial = subprocess.run(["bash", str(helper)], env=env, capture_output=True, text=True)
    assert partial.returncode == 1
    assert "no restart follows" in partial.stdout and "Unexpected job" not in partial.stderr


def test_frozen_owner_recipe_uses_current_helpers_and_a_single_bounded_stage() -> None:
    root = Path(__file__).resolve().parents[2]
    config = root / "configs/engine-qualification/sts2-v0.111.0-first-combat-bridges-v1.json"
    document = json.loads(config.read_text())
    assert len(bridges.validate_journey_cases(document)) == 8
    assert document["max_wall_seconds"] == 900 and document["training_allowed"] is False
    for role in ("native", "shipped"):
        template = json.loads((root / document[f"{role}_template"]).read_text())
        assert manifest_identifier(template) == document[f"{role}_template_id"]
    shipped = json.loads((root / document["shipped_template"]).read_text())
    from spireshift.engine_qualification import _sha_file

    for helper, checksum in shipped["helpers_sha256"].items():
        assert _sha_file(root / "scripts" / helper) == checksum
    script = (root / "scripts/compare-first-combat-v1.sh").read_text()
    assert script.count("spireshift resources run") == 1
    assert "--workers 1" in script and "--max-wall-seconds 900" in script
    assert "--max-memory-bytes 8000000000" in script
    assert "--max-storage-bytes 4000000000" in script
    assert "model train" not in script
