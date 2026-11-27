"""Launch budgets are operational receipts, separate from immutable experiment identity."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spireshift.engine_qualification import _sha_file


@dataclass(frozen=True)
class LaunchLimits:
    wall_seconds: int
    cpu_seconds: int
    memory_bytes: int = 4000000000
    storage_bytes: int = 1000000000

    def as_dict(self) -> dict[str, int]:
        return {
            "wall_seconds": self.wall_seconds,
            "cpu_seconds": self.cpu_seconds,
            "resident_memory_bytes": self.memory_bytes,
            "storage_bytes": self.storage_bytes,
        }


def load_launch(root: Path, path: Path, recipe: Path, config: dict[str, Any]) -> LaunchLimits:
    body = json.loads(path.read_text())
    if body.get("schema_version") != "native-comparison-launch-v1" or body.get("recipe") != {
        "path": str(recipe.relative_to(root)),
        "sha256": _sha_file(recipe),
    }:
        raise ValueError("Launch must name this exact finite experiment")
    wall, cpu = body.get("wall_seconds"), body.get("cpu_seconds")
    minimum = (
        config["maximum_case_wall_seconds"] + 40
        if config["stage"] == "short_control"
        else len(config["cases"]) * (config["maximum_case_wall_seconds"] + 10) + 120
    )
    if (
        type(wall) is not int
        or type(cpu) is not int
        or not minimum <= wall <= 7200
        or not wall <= cpu <= 14400
        or body.get("resident_memory_bytes") != 4000000000
        or body.get("storage_bytes") != 1000000000
    ):
        raise ValueError(
            "Allow the whole planned batch plus overhead within finite resource limits"
        )
    return LaunchLimits(wall, cpu)
