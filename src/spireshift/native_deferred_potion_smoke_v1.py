"""Two fresh production games on exact frozen in-progress correction states."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_deferred_potions_v1 import AREA, with_adapter
from spireshift.native_normalization_inputs_v1 import context, load
from spireshift.native_normalized_actor_v1 import load as load_state
from spireshift.native_normalized_actor_v1 import using_correction_scoring
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.native_win4_game import write


def run(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = with_adapter(root, context(root, cfg))
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / AREA / "production-v1"
    if (out / "report.json").exists():
        result = identified(out / "report.json")
        check_sources(root, result["sources"])
        return result
    if out.exists() or _running_games():
        raise ValueError("Preserve existing checks and close STS2/other workers")
    out.mkdir(parents=True)
    rows = []
    deadline = time.monotonic() + 245
    with using_correction_scoring():
        for p, method in ((2, "normalized"), (3, "raw")):
            path = root / cfg["workspace"] / "chunks" / f"fit-p{p}-{method}-r062/shared.json"
            state, identifier = load_state(path)
            task: dict[str, Any] = {
                "key": f"normal-p{p}-{method}",
                "seed": f"SP1RESH1FTA8DP2N00{p}",
                "seed_id": p,
                "player": p,
                "round": 0,
                "partition": "control",
                "arm": "shared",
            }
            target = out / task["key"]
            target.mkdir()
            result = play(
                {**ctx, "config": {"plan": cfg["game_limits"]}}, task, target, state, deadline
            )
            if result["outcome"] not in {"win", "loss"} or load_state(path) != (state, identifier):
                raise ValueError(
                    "The new adapter failed native completion or changed a source/full Adam"
                )
            rows.append({"state_id": identifier, "method": method, **result})
    if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
        raise ValueError("Frozen inputs or personal profile changed")
    return write(
        out / "report.json",
        {
            "status": "deferred_potions_production_learner_controls_verified",
            "games": rows,
            "adapter_sha256": ctx["lifecycle_adapter"]["sha256"],
            "optimizer_updates": 0,
            "frozen_checks": before,
            "sources": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )


if __name__ == "__main__":
    result = run(Path.cwd())
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}))
