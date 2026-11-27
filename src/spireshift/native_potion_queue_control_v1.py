"""Bounded public-menu/effect controls for potion actions around required choices."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift import native_lifecycle_worker
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_inputs_v1 import context, load
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_lifecycle_contract import check_chain
from spireshift.native_lifecycle_worker import LifecycleWorker
from spireshift.native_potion_queue_v1 import AREA, with_adapter
from spireshift.native_selector_lifecycle_trace import Trace, label, potion, verb
from spireshift.native_selector_lifecycle_worker import OwnerWorker
from spireshift.native_win4_game import write

SCRIPT = "engine-potion-queue-control-v2.mjs"
STATUS = "native_potion_queue_and_selector_handoffs_verified"


def card(definition: str) -> Any:
    return lambda raw, candidate: (
        raw["verb"] == "play"
        and (candidate.get("subject") or {}).get("properties", {}).get("definition_id")
        == definition
    )


def belt(trace: Trace) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        trace.frame["public_input"]["context"]["persistent"]["player"]["potions"],
    )


def check_belt(trace: Trace, allowed: bool) -> None:
    rows = belt(trace)
    offers = [
        c
        for c in trace.frame["public_input"]["candidates"]
        if (c.get("subject") or {}).get("role") == "potion"
    ]
    if not rows:
        raise ValueError("The control lost its potion belt")
    if not allowed and offers:
        raise ValueError("A canceled potion request remains in the executable menu")
    if allowed and len([c for c in offers if c["label"].startswith("Discard ")]) != len(rows):
        raise ValueError("A legal potion discard disappeared behind a required selector")


def run(root: Path, attempt: int = 1) -> dict[str, Any]:
    cfg = load(root)
    ctx = with_adapter(root, context(root, cfg))
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / AREA / f"control-{attempt}"
    report = out / "report.json"
    if report.exists():
        result = identified(report)
        check_sources(root, result["sources"])
        return result
    if out.exists():
        raise ValueError("Preserve the incomplete queue control without replay")
    if _running_games():
        raise ValueError("Close STS2 and wait for other native workers")
    out.mkdir()
    deadline = time.monotonic() + 220
    results = []
    for i, key in enumerate(("player-choice", "end-turn-choice", "noncombat"), 1):
        target = out / key
        target.mkdir()
        with patch.object(native_lifecycle_worker, "SCRIPT", SCRIPT):
            worker = LifecycleWorker(ctx, target / "worker", fixture=True)
        trace = Trace(ctx, cast(OwnerWorker, worker), target, deadline)
        try:
            trace.observe(
                worker.request(
                    "prepare",
                    case={
                        "seed": f"SP1RESH1FTA8PQ{attempt}C{i:03}",
                        "combat": key != "noncombat",
                    },
                )
            )
            check_belt(trace, True)
            rejected = None
            if key == "noncombat":
                trace.take(potion("use", "BLOOD_POTION"))
                trace.take(potion("discard", "SPEED_POTION"))
                if belt(trace):
                    raise ValueError("Noncombat native potion effects did not remove both bottles")
            else:
                trace.take(card("DEFEND_IRONCLAD"))
                trace.take(card("BLOODLETTING"))
                if key == "end-turn-choice":
                    trace.take(card("STAMPEDE"))
                    trace.take(verb("end_turn"))
                    check_belt(trace, False)
                    rejected = worker.request("guarded_probe")
                else:
                    trace.take(card("HEADBUTT"))
                    check_belt(trace, True)
                    trace.take(potion("discard", "SPEED_POTION"))
                    if any(
                        c["label"].startswith("Discard Speed Potion")
                        for c in trace.frame["public_input"]["candidates"]
                    ):
                        raise ValueError("An accepted queued discard was offered twice")
                if trace.frame["source_family"] != "card_selection":
                    raise ValueError("Required selector lost ownership to a potion")
                trace.take(label("Confirm Defend"))
                check_belt(trace, True)
                if key == "player-choice" and any(
                    row["definition_id"] == "SPEED_POTION" for row in belt(trace)
                ):
                    raise ValueError("Queued discard did not execute after its required child")
                trace.take(potion("use", "BLOOD_POTION"))
            chain = check_chain(
                trace.captures, trace.choices, records(target / "worker/public-receipts.jsonl.gz")
            )
            shutdown = worker.close()
            if not shutdown["clean_exit"] or shutdown["runtime_errors"]:
                raise ValueError("Queue control did not reset cleanly")
            results.append(
                {"case": key, **chain, "guarded_rejections": rejected, "clean_reset": True}
            )
        finally:
            trace.stop()
            worker.stop()
    if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
        raise ValueError("Frozen inputs or personal profile changed during queue controls")
    return write(
        report,
        {
            "status": STATUS,
            "cases": results,
            "adapter_sha256": ctx["lifecycle_adapter"]["sha256"],
            "frozen_checks": before,
            "original_optimizer_updates": 0,
            "optimizer_updates": 0,
            "official_live_qualification_granted": False,
            "sources": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )


if __name__ == "__main__":
    import sys

    print(json.dumps(run(Path.cwd(), int(sys.argv[1]) if len(sys.argv) > 1 else 1)))
