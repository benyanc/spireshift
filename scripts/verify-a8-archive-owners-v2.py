"""Audit the new replay bindings on saved source and native receipts."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from spireshift import native_a8_archive_batch as pilot
from spireshift import native_a8_archive_matching_v2 as owners
from spireshift import native_a8_replay_probe as replay
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.native_a8_mix_session import admit, unchanged
from spireshift.native_a8_replay_source import Intent, Journal
from spireshift.native_a8_rescue_game import bridge, receipt
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_shop_control_verification import verify_host

PILOT = "artifacts/native-a8-archive-batch/pilot-v1-verified-start"
CANCEL = "artifacts/native-shop-readiness/short-controls-v2/removal-cancel-804"
CANCEL_RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-shop-short-v2.json"
ORDERED = "artifacts/native-win-curriculum/plan-control-v4/ordered"


def audit_prefixes(
    root: Path,
    ctx: dict[str, Any],
    output: Path,
    deadline: float,
) -> tuple[dict[str, Any], Journal]:
    published = identified(root / "docs/evidence/native-a8-archive-pilot-v1.json")
    store = ChunkJournal(root, json.loads((root / PILOT / "config-at-launch.json").read_text()))
    locale = ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): value
        for kind in ("potion", "relic", "card")
        for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    result = {}
    decline = None
    for case in store.recipe["cases"]:
        key = case["run_id"]
        if key == "6739ccb495f9b471":
            decline = owners.read(verified(root, case["source"]))
            continue
        if published["worlds"][key]["status"] not in {pilot.WIN, "diverged"}:
            continue
        seal = store.completed(key, case)
        if seal is None or seal["report_id"] != published["seals"][key]:
            raise ValueError("Require the sealed pilot observations")
        (trace,) = (root / p for p in seal["sources"] if p.endswith("/" + replay.TRACE))
        out = trace.parent
        report = identified(out / "report.json")
        final = identified(out / "last-frame.json")
        final_id = final.pop("report_id")
        old, _ = pilot.screen(root, case)
        assert old is not None
        delivered = replay.verify(
            ctx,
            out,
            replace(old, reward_names=names),
            len(old.intents),
            deadline,
            final,
            log=output / f"{key}.log",
        )
        replay.equal("saved deliveries", report["verified_native_deliveries"], delivered)
        new = replace(owners.read(verified(root, case["source"])), reward_names=names)
        cursor = count = 0
        with owners.installed():
            for row in records(trace):
                index, cursor, domain = replay.next_choice(
                    row["frame"], new, cursor, len(new.intents)
                )
                replay.equal(
                    "saved public action and delivery domain",
                    (row["choice"]["action_index"], row["receipt"]["delivery_domain"]),
                    (index, domain),
                )
                count += 1
            index, cursor, domain = replay.next_choice(final, new, cursor, len(new.intents))
        replay.equal("reconstructed prefix length", delivered, count)
        choice = None if index is None else final["public_input"]["candidates"][index]
        if report["genuine_native_victory"]:
            replay.equal("completed demonstration", (None, len(new.intents)), (index, cursor))
            replay.victory(final, new, report["native_ending"])
        elif choice is None or not report["clean_shutdown"] or report["stop"]["delivery_uncertain"]:
            raise ValueError("Require a new exact binding on a clean saved stop")
        result[key] = {
            "prefix_deliveries_reconstructed": count,
            "sealed_report_id": seal["report_id"],
            "last_frame_id": final_id,
            "native_victory": report["genuine_native_victory"],
            "purchase_successors_checked": sum(
                i.kind == "shop_effect" for i in new.intents[:cursor]
            ),
            "next_unsent_action": choice["label"] if choice else None,
            "next_unsent_domain": domain if choice else None,
            "selected_public_slots": replay.arguments(choice, "selected_card") if choice else [],
        }
    assert decline is not None
    return result, decline


def audit_cancel(
    root: Path,
    ctx: dict[str, Any],
    output: Path,
    deadline: float,
    journal: Journal,
) -> dict[str, Any]:
    index = next(i for i, row in enumerate(journal.intents) if row.kind == "shop_removal_cancel")
    parent, cancel, successor, following = journal.intents[index - 1 : index + 3]
    replay.equal(
        "cancel chronology",
        ("removal_owner", "shop_effect", "buy"),
        (parent.kind, successor.kind, following.kind),
    )
    out = root / CANCEL
    case = json.loads((out / "complete.json").read_text())["case"]
    directory = out / "native"
    cfg = json.loads((root / CANCEL_RECIPE).read_text())
    replay.equal("cancel control workspace", str(out.parent.relative_to(root)), cfg["workspace"])
    count = verify_host(
        root, {"config": {**cfg, "node": ctx["node"]}}, case, "native", directory, output, deadline
    )
    trace = list(records(directory / "shared-public.jsonl.gz"))
    start = trace[0]["frame"]["public_input"]["context"]
    child = trace[4]["frame"]["public_input"]["context"]["interaction"]["content"]["surface"]
    gold = start["persistent"]["player"]["gold"]
    price = owners.public_read(start, "shop_catalog")["card_removal"]["price"]
    facts = {"gold": gold, "deck": owners.public_deck(start), "removal": price}
    # Compare the lifecycle on the separate saved native fixture. The archive
    # world has its own offer, cards, price and seed.
    location = {k: start["persistent"]["run"][k] for k in ("act", "floor")}
    offer = {
        "options": [
            {
                "option_id": c["definition_id"],
                "up": int(c["is_upgraded"]),
                "presented": True,
                "selectable": True,
            }
            for c in child["cards"]
        ]
    }
    control = replace(
        journal,
        intents=(
            Intent(
                "removal_owner", {**location, "cost_current": price, "archive_shop_before": facts}
            ),
            Intent("shop_removal_cancel", {**location, "archive_shop_before": facts}, offer),
            Intent("shop_effect", {**location, "archive_shop_after": facts}),
        ),
    )
    cursor = 0
    with owners.installed():
        for observed, delivered in zip(trace[:6:2], trace[1:6:2], strict=True):
            action, cursor, domain = replay.next_choice(observed["frame"], control, cursor, 3)
            replay.equal(
                "saved removal binding",
                (delivered["choice"]["action_index"], "native"),
                (action, domain),
            )
        replay.equal(
            "removal successor",
            (None, 3, "native"),
            replay.next_choice(trace[-1]["frame"], control, cursor, 3),
        )
    return {
        "archive_open_record": parent.record["s"],
        "archive_empty_pick_record": cancel.record["s"],
        "next_purchase_record": following.record["s"],
        "saved_native_deliveries": count,
        "native_gold_deck_and_removal_stock_verified": True,
        "saved_native_report_id": identified(directory / "report.json")["report_id"],
    }


def audit_factors(root: Path, ctx: dict[str, Any], output: Path, deadline: float) -> dict[str, Any]:
    folder = root / ORDERED
    report = identified(folder / "report.json")
    proof = identified(folder / "answer-proof.json")
    worker = folder / "worker"
    checked = subprocess.run(
        [ctx["node"], str(root / "scripts/engine-ordered-plan-verify-v1.mjs"), str(worker)],
        check=True,
        capture_output=True,
        text=True,
        timeout=25,
    )
    raw_domains = json.loads(checked.stdout)
    replay.equal("raw ordered commit proof", report["raw"], raw_domains)
    raw = iter(records(worker / "public-observations.jsonl.gz"))
    predecessor = next(raw)
    replay.equal(
        "diagnostic setup owner", "event_option", predecessor["snapshot"]["interaction"]["kind"]
    )
    current = next(raw)
    converter = bridge(ctx, output / "ordered.log")
    try:
        initial = converter.project(current["snapshot"], current["reads"], None, deadline)
        context = initial["public_input"]["context"]
        owner = context["interaction"]["content"]["context"]
        hand = owner["player"]["hand"]
        names = [card["definition_id"] for card in hand]
        replay.equal("one-definition fixture", 1, len(set(names)))
        selected = report["ordered_native_indices"]
        location = {k: context["persistent"]["run"][k] for k in ("act", "floor")}
        facts = {
            "before": names,
            "after": names,
            "discarded": [names[i] for i in selected],
            "enemies": [(e["definition_id"], e["hp"], e["max_hp"]) for e in owner["enemies"]],
        }
        record = {**location, "archive_opening": facts}
        intents = (
            Intent("opening_discard_owner", record),
            Intent(
                "pick",
                {
                    **record,
                    "n_picked": len(selected),
                    "cards": [
                        {"c": i, "id": names[i], "up": int(hand[i]["is_upgraded"])}
                        for i in selected
                    ],
                },
                hand=tuple(enumerate(names)),
            ),
            Intent("opening_discard_effect", record),
        )
        control = Journal("CONTROL", {}, 0, "", "", {}, frozenset(), intents)
        cursor = 0
        frame = initial
        with owners.installed():
            for saved in proof["factors"]:
                index, cursor, domain = replay.next_choice(frame, control, cursor, 3)
                choice = saved["choice"]
                current = next(raw)
                replay.equal("ordered selector action", choice["action_index"], index)
                replay.equal("ordered frame reconstruction", True, same(saved["frame"], frame))
                replay.equal(
                    "ordered successor binding",
                    saved["receipt"],
                    receipt(frame, choice, domain, current["snapshot"]["snapshot_id"]),
                )
                converter.commit(choice, saved["receipt"], deadline)
                frame = converter.project(current["snapshot"], current["reads"], None, deadline)
            replay.equal(
                "ordered replacement successor",
                (None, 3, "native"),
                replay.next_choice(frame, control, cursor, 3),
            )
        replay.equal("all saved observations", None, next(raw, None))
        converter.close()
    finally:
        converter.stop()
    return {
        "saved_report_id": report["report_id"],
        "post_discard_hand_and_pile_verified": True,
        **raw_domains,
    }


def main() -> None:
    for name in THREADS:
        os.environ[name] = "1"
    root = Path.cwd()
    base = admit(root)
    before = frozen(root, base.ctx)
    deadline = time.monotonic() + 150
    with TemporaryDirectory(prefix="spireshift-a8-owner-audit-") as tmp:
        output = Path(tmp)
        prefixes, decline = audit_prefixes(root, base.ctx, output, deadline)
        cancel = audit_cancel(root, base.ctx, output, deadline, decline)
        ordered = audit_factors(root, base.ctx, output, deadline)
    unchanged(base, before, deadline)
    report = {
        "schema_version": "native-a8-archive-owner-saved-audit-v2",
        "environment_id": base.ctx["environment_id"],
        "prefixes": prefixes,
        "removal_cancellation": cancel,
        "ordered_opening": ordered,
        "frozen_checks": before,
        "fresh_native_runs": 0,
        "optimizer_updates": 0,
        "training_admission_granted": False,
    }
    print(json.dumps({**report, "report_id": manifest_identifier(report)}))


if __name__ == "__main__":
    main()
