"""One explicit owner command qualifies reloads, then runs the declared A8 study."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireshift.engine_native import _private_path, _running_games
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_qualified_learning_inputs_v2 import MODULE
from spireshift.native_qualified_learning_inputs_v2 import RECIPE as LEARNER

RECIPE = "configs/native-learning/sts2-v0.111.0-a8-qualified-model-only-launch-v1.json"
Runner = Callable[..., Any]


def run_phases(root: Path, control_sealed: bool, runner: Runner = subprocess.run) -> int:
    prefix = ["uv", "run", "--no-sync", "python", "-B", "-m", MODULE]
    first = runner([*prefix, "saved" if control_sealed else "short"], cwd=root, check=False)
    if first.returncode:
        return int(first.returncode)
    return int(runner([*prefix, "run"], cwd=root, check=False).returncode)


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    root = Path.cwd()
    try:
        cfg = json.loads((root / RECIPE).read_text())
        if (
            cfg["schema_version"] != "native-a8-qualified-learning-owner-launch-v1"
            or verified(root, cfg["learner_recipe"]) != root / LEARNER
            or cfg["phases"] != ["verify_or_finish_short_control", "run_fixed_study"]
        ):
            raise ValueError("The declared owner launch phases changed")
        check_sources(root, cfg["implementation"])
        learner = json.loads((root / LEARNER).read_text())
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        report = _private_path(root, learner["control_workspace"]) / "report.json"
        print(
            "Verify the short control, then train two copies on 2,048 fresh A8 games "
            "and compare 128 games.",
            flush=True,
        )
        return run_phases(root, report.exists())
    except (ValueError, OSError, KeyError) as exc:
        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(exc),
                    "original_optimizer_updates": 0,
                    "automatic_follow_up": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
