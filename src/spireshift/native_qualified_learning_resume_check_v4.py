"""Restore the actual saved study and stop before the first unstarted game; no actions or fits."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_session_v1 as previous
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_qualified_learning_inputs_v2 import RECIPE as ORIGINAL
from spireshift.native_qualified_learning_inputs_v4 import PARENT, RECIPE, context, load
from spireshift.native_qualified_learning_session_v4 import Session
from spireshift.native_win4_game import write


class BeforeNewUnit(RuntimeError):
    def __init__(self, key: str, request: dict[str, Any]):
        self.key, self.request = key, request


class Preview(Session):
    def unit(
        self, key: str, request: dict[str, Any], reserve: float, action: Any
    ) -> dict[str, Any]:
        if key not in self.proof["inherited_units"]:
            raise BeforeNewUnit(key, request)
        return super().unit(key, request, reserve, action)


def check(root: Path) -> dict[str, Any]:
    cfg = load(root)
    output = root / cfg["resume_check_workspace"]
    final = output / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        if result["config_id"] != manifest_identifier(cfg):
            raise ValueError("The saved resume check has a different effective study declaration")
        return result
    original = json.loads((root / ORIGINAL).read_text())
    parent = json.loads((root / PARENT).read_text())
    with (
        ChunkJournal(root, original).lock(),
        ChunkJournal(root, parent).lock(),
        patch.multiple(
            previous,
            load=load,
            context=context,
        ),
    ):
        session = Preview(root, cfg, False, time.monotonic() + 150)
        try:
            session.run()
        except BeforeNewUnit as boundary:
            first = boundary
        else:
            raise ValueError("The resume check must stop before any new game or fit")
        restored = {
            str(p): [r for r in session.training if r["player"] == p][-1]["state_id"]
            for p in (2, 3)
        }
        if (
            first.key != "train-0573-p3-learner"
            or len(session.training) != 71
            or session.seals != session.proof["inherited_units"]
            or sum(r["work"]["optimizer_updates"] for r in session.training) != 3813
            or first.request["behavior_state_id"] != restored["3"]
            or session.game_counts["train-p3"]["failed"] != 2
            or (root / cfg["workspace"] / "chunks").exists()
        ):
            raise ValueError(
                "The actual resumed prefix, exact Adam lineage or first new cell changed"
            )
        session.unchanged()
        output.mkdir(parents=True, exist_ok=True)
        return write(
            final,
            {
                "schema_version": "native-qualified-learning-resume-check-v4",
                "status": "restored_exact_prefix_stopped_before_first_unstarted_game",
                "config_id": manifest_identifier(cfg),
                "first_unstarted_game": first.key,
                "request": first.request,
                "current_states": restored,
                "restored_games": 1146,
                "restored_fits": 71,
                "restored_optimizer_updates": 3813,
                "preserved_failed_cells": 2,
                "games_launched": 0,
                "optimizer_updates": 0,
                "frozen_checks": session.before,
                "sources": {
                    RECIPE: _sha_file(root / RECIPE),
                    **{
                        cfg[key]["path"]: cfg[key]["sha256"]
                        for key in ("source_assessment", "verifier_controls")
                    },
                },
            },
        )


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in check(Path.cwd()).items() if k != "sources"}))
