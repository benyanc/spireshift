"""Bounded natural-run control and dependency gates, without game execution."""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_connector import _run_natural_client, _validate_benchmark_fixture_scope
from spireshift.engine_startup import _script_closure


def scope() -> dict[str, Any]:
    return {
        "comparison_mode": "new_run_v1",
        "natural_run": True,
        "shipped_ui_revision": "natural_v3",
        "seed": "SP1RESH1FTA8D1AG001",
        "benchmark_progress": "synthetic",
        "profile_policy": "synthetic",
        "natural_run_limits": {
            "schema_version": "engine-natural-run-limits-v1",
            "max_wall_seconds": 900,
            "max_decisions": 4096,
        },
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("natural_run", False),
        ("comparison_mode", "combat_bridge_v5"),
        ("shipped_ui_revision", "natural_v2"),
        ("checkpoint_path", "imported-save"),
    ],
)
def test_extended_cap_cannot_leak_into_old_or_imported_scopes(key: str, value: Any) -> None:
    fixture = scope()
    _validate_benchmark_fixture_scope(fixture)
    fixture[key] = value
    with pytest.raises(ValueError):
        _validate_benchmark_fixture_scope(fixture)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("max_wall_seconds", 901),
        ("max_wall_seconds", True),
        ("max_wall_seconds", 30),
        ("max_decisions", 4097),
        ("max_decisions", 0),
        ("extra_cap", 1),
    ],
)
def test_a_long_run_still_has_frozen_finite_caps(key: str, value: Any) -> None:
    fixture = copy.deepcopy(scope())
    fixture["natural_run_limits"][key] = value
    with pytest.raises(ValueError):
        _validate_benchmark_fixture_scope(fixture)


def test_helper_inventory_includes_indirect_imports_and_handles_cycles(tmp_path: Path) -> None:
    (tmp_path / "a.mjs").write_text('import { x } from "./b.mjs";')
    (tmp_path / "b.mjs").write_text('import { y } from "./c.mjs";')
    (tmp_path / "c.mjs").write_text('import { z } from "./a.mjs";')
    assert _script_closure(tmp_path, {"a.mjs"}) == {"a.mjs", "b.mjs", "c.mjs"}


def test_progress_relay_does_not_print_unstructured_client_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    child = (
        'import sys;sys.stdin.read();print("private synthetic data");'
        'print("Natural A8 run: 25 actions, floor 3, act 1.")'
    )
    _run_natural_client([sys.executable, "-c", child], {}, tmp_path, 5)
    assert capsys.readouterr().out == "Natural A8 run: 25 actions, floor 3, act 1.\n"
    assert "private synthetic data" in (tmp_path / "client-stdout.log").read_text()


def test_progress_client_is_stopped_when_it_exceeds_its_cap(tmp_path: Path) -> None:
    with pytest.raises(subprocess.TimeoutExpired):
        _run_natural_client([sys.executable, "-c", "import time;time.sleep(5)"], {}, tmp_path, 1)


def test_new_discovery_limits_are_explicit_and_finite() -> None:
    fixture = scope()
    fixture["shipped_ui_revision"] = "natural_v4"
    with pytest.raises(ValueError, match="diagnostic recovery"):
        _validate_benchmark_fixture_scope(fixture)
    fixture["diagnostic_limits"] = {
        "schema_version": "engine-run-diagnostic-limits-v1",
        "mode": "discovery",
        "max_unique_issues": 64,
        "max_issue_observations": 128,
        "max_recoveries": 16,
        "unsupported_grace_ms": 3000,
    }
    _validate_benchmark_fixture_scope(fixture)
    for key, value in [
        ("max_recoveries", 100),
        ("mode", "validation"),
        ("max_unique_issues", True),
    ]:
        invalid = copy.deepcopy(fixture)
        invalid["diagnostic_limits"][key] = value
        with pytest.raises(ValueError, match="diagnostic recovery"):
            _validate_benchmark_fixture_scope(invalid)
