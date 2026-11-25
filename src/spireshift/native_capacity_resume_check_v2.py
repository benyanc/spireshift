"""Restore the exact clean prefix and stop before any new game or optimizer update."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_capacity_session_v1 as original
from spireshift import native_qualified_learning_session_v1 as base
from spireshift.engine_learning import identified
from spireshift.native_capacity_inputs_v2 import context, load
from spireshift.native_capacity_session_v2 import Session, control_receipt
from spireshift.native_win4_game import write

FIRST = "train-0155-p3-expanded"
STATUS = "capacity_prefix_restored_before_first_unstarted_game"


class Boundary(RuntimeError):
    pass


class RestoreSession(Session):
    def unit(
        self, key: str, request: dict[str, Any], reserve: float, action: Any
    ) -> dict[str, Any]:
        if key not in self.proof["inherited_units"]:
            if key != FIRST:
                raise ValueError("Unexpected first unstarted capacity unit")
            self.active = key
            raise Boundary("No new game or optimizer call")
        return super().unit(key, request, reserve, action)


def run(root: Path) -> dict[str, Any]:
    cfg = load(root)
    with (
        patch.multiple(base, context=context, load=load),
        patch.object(original, "control_receipt", control_receipt),
    ):
        session = RestoreSession(root, cfg, False, time.monotonic() + 250)
        out = root / "artifacts/native-policy-capacity/resume-check-v2.json"
        if out.exists():
            result = identified(out)
            if result["config_id"] != session.store.config_id:
                raise ValueError("Preserve the restore check for its exact declaration")
            session.unchanged()
            return result
        # No journal lock or writes are required: every allowed unit must be inherited.
        try:
            session.run()
        except Boundary:
            pass
        else:
            raise ValueError("Restore control continued beyond the first unstarted game")
        if (
            set(session.seals) != set(session.proof["inherited_units"])
            or len(session.training) != 39
        ):
            raise ValueError("Restore skipped a historical game or full model/Adam fit")
        session.unchanged()
        return write(
            out,
            {
                "status": STATUS,
                "config_id": session.store.config_id,
                "source_assessment_id": session.proof["report_id"],
                "first_unstarted_game": session.active,
                "inherited_units_restored": len(session.seals),
                "optimizer_updates_restored": sum(
                    r["work"]["optimizer_updates"] for r in session.training
                ),
                "games_launched": 0,
                "optimizer_updates": 0,
                "frozen_checks": session.before,
            },
        )


if __name__ == "__main__":
    print(json.dumps(run(Path.cwd())))
