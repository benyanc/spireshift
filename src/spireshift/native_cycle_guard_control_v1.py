"""Short native controls for the effect-free cycle guard on frozen final copies.

Fresh declared control worlds only. Each game plays with the guard active, then
the existing raw verifier replays the guarded policy from native observations.
The guarded ``groups`` and ``samples`` then rebuild every decision exactly as PPO
would. No optimizer update happens and no source state or full Adam changes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift import native_a8_own_experience
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_cycle_guard_v1 import CONTRACT, using_cycle_guard
from spireshift.native_flow_verification_v12 import records
from spireshift.native_normalization_inputs_v2 import context, load
from spireshift.native_normalized_actor_v1 import load as load_state
from spireshift.native_normalized_actor_v1 import using_correction_scoring
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.native_win4_game import write

AREA = "artifacts/effect-free-cycles/control-v1"
STATUS = "effect_free_cycle_guard_native_controls_verified"
CASES = (
    (2, "normalized", "SP1RESH1FTA8CYG001"),
    (2, "normalized", "SP1RESH1FTA8CYG002"),
    (2, "normalized", "SP1RESH1FTA8CYG003"),
    (3, "raw", "SP1RESH1FTA8CYG004"),
)


def journal_facts(directory: Path) -> dict[str, Any]:
    withheld = families = 0
    for row in records(directory / "shared-public.jsonl.gz"):
        if row["kind"] == "policy_choice":
            choice = row["choice"]
            if choice["policy_contract"] != CONTRACT:
                raise ValueError("A control decision bypassed the guarded policy")
            withheld += choice["withheld_effect_free_actions"] > 0
            families += 1
    return {"decisions": families, "decisions_with_withheld_actions": withheld}


def run(root: Path) -> dict[str, Any]:
    cfg = load(root)
    ctx = context(root, cfg)
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / AREA
    if (out / "report.json").exists():
        result = identified(out / "report.json")
        check_sources(root, result["sources"])
        return result
    if out.exists() or _running_games():
        raise ValueError("Preserve existing checks and close STS2/other workers")
    out.mkdir(parents=True)
    rows = []
    deadline = time.monotonic() + 280
    with using_correction_scoring(), using_cycle_guard():
        for i, (p, method, seed) in enumerate(CASES, 1):
            path = root / cfg["workspace"] / "chunks" / f"fit-p{p}-{method}-r064/shared.json"
            state, identifier = load_state(path)
            source_sha = _sha_file(path)
            task: dict[str, Any] = {
                "key": f"control-{i:04d}-p{p}-{method}",
                "seed": seed,
                "seed_id": i,
                "player": p,
                "round": 1,
                "partition": "control",
                "arm": "shared",
            }
            target = out / task["key"]
            target.mkdir()
            result = play(
                {**ctx, "config": {"plan": cfg["game_limits"]}}, task, target, state, deadline
            )
            if _sha_file(path) != source_sha or load_state(path) != (state, identifier):
                raise ValueError("A frozen final state or its full Adam changed")
            facts = journal_facts(target)
            rebuilt = None
            if result["outcome"] in {"win", "loss"}:
                decisions, _, _ = native_a8_own_experience.samples(
                    target, result, state.model, ctx["score"], "control", 1
                )
                rebuilt = len(decisions)
                if rebuilt != result["native_decisions"]:
                    raise ValueError("PPO reconstruction differs from native deliveries")
            if (
                result["policy_contract"] != CONTRACT
                or facts["decisions"] < result["native_decisions"]
            ):
                raise ValueError("The guarded contract or decision count differs")
            rows.append(
                {
                    "state_id": identifier,
                    "method": method,
                    "ppo_decisions_rebuilt": rebuilt,
                    **facts,
                    **result,
                }
            )
    if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
        raise ValueError("Frozen inputs or personal profile changed")
    return write(
        out / "report.json",
        {
            "status": STATUS,
            "policy_contract": CONTRACT,
            "games": rows,
            "optimizer_updates": 0,
            "training_labels": 0,
            "frozen_checks": before,
            "sources": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            }
            | {
                "src/spireshift/native_cycle_guard_v1.py": _sha_file(
                    root / "src/spireshift/native_cycle_guard_v1.py"
                ),
                "src/spireshift/native_cycle_guard_control_v1.py": _sha_file(Path(__file__)),
            },
        },
    )


if __name__ == "__main__":
    result = run(Path.cwd())
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}))
