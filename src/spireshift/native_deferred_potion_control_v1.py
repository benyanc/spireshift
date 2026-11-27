"""Qualify real deferred discard/use effects and the existing queue boundaries."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from spireshift import native_lifecycle_worker, native_potion_queue_control_v1
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_deferred_potions_v1 import AREA, with_adapter
from spireshift.native_flow_verification_v12 import records
from spireshift.native_lifecycle_contract import check_chain
from spireshift.native_lifecycle_worker import LifecycleWorker
from spireshift.native_normalization_inputs_v1 import context, load
from spireshift.native_potion_queue_v1 import with_adapter as previous_adapter
from spireshift.native_selector_lifecycle_trace import Trace, label, potion
from spireshift.native_selector_lifecycle_worker import OwnerWorker
from spireshift.native_win4_game import write

SCRIPT = "engine-deferred-potion-control-v1.mjs"
STATUS = "deferred_potion_and_existing_queue_handoffs_verified"


def verify_buffer(identity: dict[str, Any], kinds: list[str]) -> dict[str, Any]:
    proof = identity["deferred_potions"]
    rows = proof["buffer"]
    if (
        proof["combat_state"] != "NotPlayPhase"
        or [r["kind"] for r in rows] != kinds
        or any(r["action_id"] is not None or r["state"] != "None" for r in rows)
        or any(not r["tracked_discard"] for r in rows if r["kind"] == "DiscardPotionGameAction")
    ):
        raise ValueError("Require exact native pre-ID buffered action objects in submission order")
    return {
        "native_buffered_kinds": kinds,
        "native_ids_assigned_yet": False,
        "native_state": "None",
        "tracked_discards": sum(r["tracked_discard"] for r in rows),
    }


def run(root: Path, attempt: int = 1) -> dict[str, Any]:
    cfg = load(root)
    ctx = with_adapter(root, context(root, cfg))
    before = frozen(root, ctx)
    profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
    out = root / AREA / f"qualification-{attempt}"
    final = out / "report.json"
    if final.exists():
        result = identified(final)
        check_sources(root, result["sources"])
        return result
    if out.exists() or _running_games():
        raise ValueError("Preserve existing controls and close STS2/other native workers")
    out.mkdir(parents=True)
    (root / AREA / "legacy").mkdir(exist_ok=True)
    deadline = time.monotonic() + 250
    with patch.multiple(
        native_potion_queue_control_v1,
        SCRIPT=SCRIPT,
        AREA=f"{AREA}/legacy",
        with_adapter=lambda r, c: with_adapter(r, previous_adapter(r, c)),
    ):
        legacy = native_potion_queue_control_v1.run(root, attempt)
    results = []
    for i, key in enumerate(("opening-discard-and-use", "opening-two-discards"), 1):
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
                        "seed": f"SP1RESH1FTA8DP{attempt}C{i:03}",
                        "combat": True,
                        "opening": True,
                    },
                )
            )
            if trace.frame["source_family"] != "native_generated_card_choice":
                raise ValueError("Require a genuine native opening generated selector")
            owner = trace.frame["public_input"]["context"]["interaction"]["kind"]
            trace.take(potion("discard", "SPEED_POTION"))
            first = verify_buffer(worker.request("inspect_buffer"), ["DiscardPotionGameAction"])
            rejected = worker.request("reject_duplicate")
            verify_buffer(worker.request("inspect_buffer"), ["DiscardPotionGameAction"])
            if any(
                c["label"] == "Discard Speed Potion"
                for c in trace.frame["public_input"]["candidates"]
            ):
                raise ValueError("A buffered discard was offered twice")
            trace.take(potion("use" if i == 1 else "discard", "BLOOD_POTION"))
            second = verify_buffer(
                worker.request("inspect_buffer"),
                [
                    "DiscardPotionGameAction",
                    "UsePotionAction" if i == 1 else "DiscardPotionGameAction",
                ],
            )
            if trace.frame["public_input"]["context"]["interaction"]["kind"] != owner:
                raise ValueError("A buffered potion displaced the required opening child owner")
            chosen = next(
                c["label"]
                for c in trace.frame["public_input"]["candidates"]
                if c["verb"] == "select"
            )
            trace.take(label(chosen))
            player = trace.frame["public_input"]["context"]["persistent"]["player"]
            after = worker.request("inspect_buffer")
            if (
                player["potions"]
                or after["deferred_potions"]["buffer"]
                or after["pending_potion_discards"]
                or trace.frame["source_family"] != "combat_turn"
            ):
                raise ValueError(
                    "Buffered potion actions did not drain at the native play-phase handoff"
                )
            # Prepared controls start at 50/80 HP; Blood Potion natively heals 20%.
            if player["hp"] != (66 if i == 1 else 50):
                raise ValueError("Deferred potion effects were missing or repeated")
            chain = check_chain(
                trace.captures, trace.choices, records(target / "worker/public-receipts.jsonl.gz")
            )
            closed = worker.close()
            if not closed["clean_exit"] or closed["runtime_errors"]:
                raise ValueError("The opening potion control did not reset cleanly")
            results.append(
                {
                    "case": key,
                    "first": first,
                    "second": second,
                    "rejected": rejected,
                    "after_hp": player["hp"],
                    "clean_reset": True,
                    **chain,
                }
            )
        finally:
            trace.stop()
            worker.stop()
    if frozen(root, ctx) != before or _shared_snapshot(Path.home() / SHARED_PROFILE) != profile:
        raise ValueError("The game/build/full source Adam or personal profile changed")
    sources = {str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()}
    legacy_path = root / AREA / "legacy" / f"control-{attempt}" / "report.json"
    sources[str(legacy_path.relative_to(root))] = _sha_file(legacy_path)
    for name in (f"scripts/{SCRIPT}", "src/spireshift/native_deferred_potion_control_v1.py"):
        sources[name] = _sha_file(root / name)
    return write(
        final,
        {
            "status": STATUS,
            "legacy_controls_id": legacy["report_id"],
            "legacy_cases": legacy["cases"],
            "opening_cases": results,
            "adapter_sha256": ctx["lifecycle_adapter"]["sha256"],
            "frozen_checks": before,
            "optimizer_updates": 0,
            "official_live_qualification_granted": False,
            "sources": sources,
        },
    )


if __name__ == "__main__":
    import sys

    result = run(Path.cwd(), int(sys.argv[1]) if len(sys.argv) > 1 else 1)
    print(json.dumps({k: v for k, v in result.items() if k != "sources"}))
