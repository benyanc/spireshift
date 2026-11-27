"""Exercise actual inherited restoration and stop before the first new game."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_normalization_inputs_v2 import load
from spireshift.native_normalization_session_v2 import RESTORE, Session, bindings
from spireshift.native_win4_game import write


class NextUnit(RuntimeError):
    pass


class Restore(Session):
    next_unit: dict[str, Any]

    def unit(
        self, key: str, request: dict[str, Any], reserve: float, action: Any
    ) -> dict[str, Any]:
        if key not in self.proof["inherited_units"]:
            self.next_unit = {"key": key, "request": request}
            raise NextUnit("Reached the first unstarted unit without beginning it")
        return super().unit(key, request, reserve, action)


def run(root: Path) -> dict[str, Any]:
    cfg = load(root)
    target = root / RESTORE
    if target.exists():
        result = identified(target)
        check_sources(root, result["sources"])
        return result
    with bindings():
        session = Restore(root, cfg, False, time.monotonic() + 270)
        session.store.workspace = target.parent
        with session.store.lock():
            try:
                session.run()
            except NextUnit:
                pass
            else:
                raise ValueError("Restore unexpectedly completed or launched new work")
            session.unchanged()
    next_ = session.next_unit
    expected = {
        **session.proof["failed_request"]["task"],
        "key": "train-0994-p2-normalized",
        "seed": "SP1RESH1FTA8N1T0994",
        "seed_id": 994,
    }
    if (
        next_["key"] != expected["key"]
        or next_["request"]
        != {
            "task": expected,
            "behavior_state_id": session.proof["failed_request"]["behavior_state_id"],
        }
        or len(session.seals) != 4234
        or sum(r["work"]["optimizer_updates"] for r in session.training) != 15252
        or session.evaluation
        or len(session.training) != 249
    ):
        raise ValueError("The complete restored prefix or its first unstarted behavior differs")
    latest = {
        m: {
            str(p): next(
                r["state_id"]
                for r in reversed(session.training)
                if r["player"] == p and r["method"] == m
            )
            for p in (2, 3)
        }
        for m in ("raw", "normalized")
    }
    if latest != session.proof["last_full_states"]:
        raise ValueError("A full restored final state/Adam differs")
    from spireshift.engine_qualification import _sha_file

    sources = {"src/spireshift/native_normalization_restore_v2.py": _sha_file(Path(__file__))}
    return write(
        target,
        {
            "status": "normalization_prefix_restored_before_first_unstarted_game",
            "config_id": manifest_identifier(cfg),
            "source_assessment_id": session.proof["report_id"],
            "first_unstarted_game": next_["key"],
            "first_unstarted_request": next_["request"],
            "inherited_units_restored": len(session.seals),
            "optimizer_updates_restored": 15252,
            "full_states_restored": latest,
            "frozen_checks": session.before,
            "games_launched": 0,
            "optimizer_updates": 0,
            "sources": sources,
        },
    )


if __name__ == "__main__":
    r = run(Path.cwd())
    print(json.dumps({k: v for k, v in r.items() if k != "sources"}))
