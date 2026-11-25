"""Two fresh normal-start production learner games on frozen narrow/wide states."""

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
from spireshift.native_capacity_inputs_v1 import context, load
from spireshift.native_combat_intent_model import load as load_state
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_potion_queue_v1 import AREA, with_adapter
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.native_win4_game import write

STATUS = "potion_queue_normal_start_learner_controls_verified"


def run(root: Path, attempt: int = 2) -> dict[str, Any]:
    cfg = load(root)
    ctx = with_adapter(root, context(root, cfg))
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / AREA / f"production-controls-v{attempt}"
    if (out / "report.json").exists():
        result = identified(out / "report.json")
        check_sources(root, result["sources"])
        return result
    if out.exists() or _running_games():
        raise ValueError("Preserve existing controls; close STS2 and wait for other workers")
    out.mkdir()
    deadline = time.monotonic() + 250
    rows = []
    for p, method, r in ((2, "standard", 10), (3, "expanded", 9)):
        state, state_id = load_state(
            root / cfg["workspace"] / "chunks" / f"fit-p{p}-{method}-r{r:03d}/shared.json"
        )
        task: dict[str, Any] = {
            "key": f"normal-p{p}",
            "seed": f"SP1RESH1FTA8PQ{attempt}N00{p}",
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
        if result["outcome"] not in {"win", "loss"}:
            raise ValueError("The production queue control did not reach a genuine ending")
        after, restored_id = load_state(
            root / cfg["workspace"] / "chunks" / f"fit-p{p}-{method}-r{r:03d}/shared.json"
        )
        if restored_id != state_id or after.document() != state.document():
            raise ValueError("A frozen complete learner state/Adam changed during inference")
        rows.append(
            {"state_id": state_id, "hidden_units": state.model.actor.hidden_units, **result}
        )
    if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
        raise ValueError("Frozen inputs or personal profile changed during production controls")
    return write(
        out / "report.json",
        {
            "status": STATUS,
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
