from pathlib import Path
from typing import Any

import pytest

from spireshift.full_run_a8_evolution_budget import remaining_limits
from spireshift.full_run_ppo import frozen_json


def save_cost(root: Path, output: Path, wall: float, cpu: float) -> None:
    frozen_json(
        root / "stage-attempt-1.json",
        {
            "experiment_kind": "training",
            "artifacts": {"roots": [str(output.resolve())]},
            "usage": {"wall_seconds": wall, "cpu_seconds": cpu},
        },
        "report_id",
    )


def limits() -> dict[str, Any]:
    return {
        "wall_seconds": 3600,
        "cpu_seconds": 12000,
        "storage_bytes": 4_000_000_000,
        "memory_bytes": 12_000_000_000,
    }


def test_explicit_resume_subtracts_prior_launch_cost_and_does_not_reset_budget(
    tmp_path: Path,
) -> None:
    output = tmp_path / "result"
    save_cost(tmp_path, output, 1200.2, 7000.5)
    (tmp_path / "stage-attempt-1-metrics.json").write_text("not a launch report")
    remaining = remaining_limits(limits(), output, tmp_path, "stage")
    assert remaining["wall_seconds"] == 2399
    assert remaining["cpu_seconds"] == 4999
    assert remaining["storage_bytes"] == limits()["storage_bytes"]


def test_exhausted_budget_stops_before_another_launch(tmp_path: Path) -> None:
    save_cost(tmp_path, tmp_path / "result", 3600.1, 100)
    with pytest.raises(ValueError, match="total budget is exhausted"):
        remaining_limits(limits(), tmp_path / "result", tmp_path, "stage")


def test_another_experiments_cost_cannot_supply_free_budget(tmp_path: Path) -> None:
    save_cost(tmp_path, tmp_path / "another-result", 10, 20)
    with pytest.raises(ValueError, match="different scope"):
        remaining_limits(limits(), tmp_path / "result", tmp_path, "stage")
