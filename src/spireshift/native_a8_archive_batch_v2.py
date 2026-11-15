"""Run a separately pinned batch with the archive owner-matching rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from spireshift import native_a8_archive_batch as batch
from spireshift.native_a8_archive_matching_v2 import MATCHER, installed, screen
from spireshift.native_compatibility_contract import local
from spireshift.native_compatibility_inputs import check_sources

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-archive-owner-replay-v2.json"
SCHEMA = "native-a8-archive-batch-v2"
REQUIRED = {
    "src/spireshift/native_a8_archive_batch.py",
    "src/spireshift/native_a8_archive_batch_v2.py",
    "src/spireshift/native_a8_archive_matching_v2.py",
    *(f"src/spireshift/{name}" for name in batch.REPLAY_FILES),
}


def load(root: Path, recipe: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads(recipe.read_text())
    if (
        cfg["schema_version"] != SCHEMA
        or cfg.get("matcher_contract") != MATCHER
        or REQUIRED - cfg["replay_implementation"].keys()
    ):
        raise ValueError("Require the separately pinned owner-matching implementation")
    batch.validate_plan({**cfg, "schema_version": batch.SCHEMA})
    check_sources(root, cfg["replay_implementation"])
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", nargs="?", default=RECIPE)
    parser.add_argument("--run", action="store_true", help="Replay the declared fresh sources")
    args = parser.parse_args()
    root = Path.cwd()
    try:
        recipe = local(root, args.recipe)
        cfg = load(root, recipe)
        screened = {case["run_id"]: screen(root, case) for case in cfg["cases"]}
        if args.run:
            with installed():
                result = batch.execute(root, recipe, cfg, screened)
            check_sources(root, cfg["replay_implementation"])
        else:
            result = {
                "status": "archive_sources_screened",
                "sources": {key: row for key, (_, row) in screened.items()},
                "optimizer_updates": 0,
            }
    except batch.FAILURES as exc:
        result = {
            "status": "stopped_preserving_evidence",
            "error": str(exc),
            "optimizer_updates": 0,
            "training_admission_granted": False,
        }
    print(json.dumps(result))
    return 2 if result["status"] == "stopped_preserving_evidence" else 0


if __name__ == "__main__":
    raise SystemExit(main())
