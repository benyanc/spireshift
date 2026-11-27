"""One bounded, restartable teaching/fresh-game comparison on experimental copies."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import load_engine_qualification_config
from spireshift.engine_run import _run_inputs
from spireshift.native_teaching_execute import execute
from spireshift.native_teaching_inputs import load


def run(root: Path, recipe: Path, max_units: int | None = None) -> dict[str, Any]:
    if max_units is not None and max_units < 1:
        raise ValueError("A work-unit cap must be positive")
    started = time.monotonic()
    context = load(root, recipe)
    source = context["source"]
    q = load_engine_qualification_config(root / source["qualification"])
    inputs = _run_inputs(q, root / source["native_inputs"]["path"])
    if (
        q.config_id != source["qualification_id"]
        or manifest_identifier(inputs["recipe"]) != source["native_inputs"]["id"]
        or inputs["objective"] != context["score"].evaluation_objective.as_dict()
    ):
        raise ValueError("Preserve the qualified A8 environment and terminal full-run objective")
    return execute(
        root,
        context,
        (q, inputs),
        max_units=max_units,
        launch_deadline=started + context["config"]["session_limits"]["wall_seconds"] - 15,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--max-units", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    try:
        result = run(root, root / args.recipe, args.max_units)
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TimeoutError) as error:
        print(json.dumps({"status": "stopped_preserving_teaching_evidence", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
