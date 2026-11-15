"""Remaining whole-stage caps, including previous explicit launches."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from spireshift.full_run_a8_admission import identified_document
from spireshift.full_run_ppo import bounded_number


def remaining_limits(
    limits: dict[str, Any], output: Path, resources: Path, prefix: str
) -> dict[str, int]:
    spent = {"wall_seconds": 0.0, "cpu_seconds": 0.0}
    seen: set[str] = set()
    for path in resources.glob(f"{prefix}-attempt-*.json"):
        if path.name.endswith("-metrics.json"):
            continue
        report = identified_document(path)
        if (
            report["report_id"] in seen
            or report["experiment_kind"] != "training"
            or report["artifacts"]["roots"] != [str(output.resolve())]
        ):
            raise ValueError("Prior evolution launch cost has a duplicate or different scope")
        seen.add(report["report_id"])
        for key in spent:
            spent[key] += bounded_number(report["usage"][key], key, 0, 1e13)
    remaining = {key: math.floor(limits[key] - spent[key]) for key in spent}
    if any(value <= 0 for value in remaining.values()):
        raise ValueError("This stage's total budget is exhausted; partial results are preserved")
    return {
        **remaining,
        "storage_bytes": int(limits["storage_bytes"]),
        "memory_bytes": int(limits["memory_bytes"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("prefix")
    args = parser.parse_args()
    try:
        config = identified_document(args.config, "config_id")
        remaining = remaining_limits(
            config["resource_limits"], args.output, args.resources, args.prefix
        )
        print(
            " ".join(
                str(remaining[k])
                for k in ("wall_seconds", "cpu_seconds", "storage_bytes", "memory_bytes")
            )
        )
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot launch evolution: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
