"""Explicit separate owner stages: collect lessons, assess, then fit/evaluate copies."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.native_natural_curriculum import run as curriculum
from spireshift.native_natural_inputs import load
from spireshift.native_natural_teacher import collect


def run(root: Path, path: Path, phase: str, max_units: int | None = None) -> dict[str, Any]:
    if phase not in {"collect", "curriculum"} or max_units is not None and max_units < 1:
        raise ValueError("Choose one finite teacher or curriculum stage and a positive unit cap")
    started = time.monotonic()
    context = load(root, path)
    source = context["source"]
    q = load_engine_qualification_config(root / source["qualification"])
    inputs = _run_inputs(q, root / source["native_inputs"]["path"])
    if (
        q.config_id != source["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != source["native_inputs"]["id"]
        or inputs["objective"] != context["score"].evaluation_objective.as_dict()
    ):
        raise ValueError("Preserve the frozen actual engine and full-run ObjectiveSpec")
    return (collect if phase == "collect" else curriculum)(
        root,
        context,
        (q, inputs),
        max_units=max_units,
        launch_deadline=started + context["config"]["session_limits"]["wall_seconds"] - 15,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--phase", choices=("collect", "curriculum"), default="collect")
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        report = run(root, root / args.recipe, args.phase, args.max_units)
        print(
            json.dumps(
                {
                    k: v
                    for k, v in report.items()
                    if k not in {"sources", "fights", "final_players", "held_fights"}
                },
                indent=2,
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_natural_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
