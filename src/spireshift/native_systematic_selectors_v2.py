"""Use and verify both representations of the same native card selector."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_feedback_host, native_a8_mix_session, native_win4_game
from spireshift.native_a8_feedback_host import FeedbackWorker
from spireshift.native_a8_own_training import State
from spireshift.native_a8_rescue_game import receipt
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_shared_transport import JsonLines

WORKER = "engine-a8-mixed-practice-worker-v2.mjs"
CONVERTER = "engine-shared-input-v17.mjs"
PROJECTION = "native_a8_shared_card_selector_v1"
MATRIX = "engine-systematic-selectors-v1.test.mjs"
SAVED = "verify-a8-selector-saved-v1.mjs"
ORDERED_PROOF = "engine-ordered-plan-verify-v1.mjs"
DIRECT = "atomic_public_card_choice_v1"
COMPACT = "factorized_ordered_card_answer_v1"


class SelectorWorker(FeedbackWorker):
    def __init__(self, ctx: dict[str, Any], target: Path, *, fixture: bool = False) -> None:
        self.fixture = fixture
        with patch.multiple(native_a8_feedback_host, SCRIPT=WORKER, PROJECTION=PROJECTION):
            super().__init__(ctx, target)

    def request(self, command: str, *, timeout: float = 20, **values: Any) -> dict[str, Any]:
        if command == "initialize":
            values["spec"] = {**values["spec"], "selector_fixture": self.fixture}
        return super().request(command, timeout=timeout, **values)


class SelectorBridge(JsonLines):
    def __init__(self, root: Path, command: list[str], log: Path) -> None:
        if len(command) != 2 or command[1] != str(root / "scripts/engine-shared-input-v16.mjs"):
            raise ValueError("Unexpected parent converter entry point")
        super().__init__(root, [command[0], str(root / "scripts" / CONVERTER)], log)


def play(
    base: native_a8_mix_session.Study,
    store: ChunkJournal,
    task: dict[str, Any],
    state: State,
    deadline: float,
) -> dict[str, Any]:
    with (
        patch.object(native_a8_mix_session, "MixWorker", SelectorWorker),
        patch.object(native_win4_game, "JsonLines", SelectorBridge),
    ):
        return native_a8_mix_session.game(base, store, task, state, deadline)


def node(ctx: dict[str, Any], *args: str, payload: dict[str, Any] | None = None) -> str:
    result = subprocess.run(
        [ctx["node"], *args],
        cwd=ctx["qualification"].root,
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        timeout=25,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout)[-2500:]
        raise ValueError(f"Selector verification failed: {detail}")
    return result.stdout


def saved_selector(ctx: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    root = ctx["qualification"].root
    paths = {name: verified(root, ref) for name, ref in evidence.items()}
    last = last_action(paths["transcript"])
    delivered = {}
    for row in records(paths["receipts"]):
        delivered = row
    state = last["response"]
    if (
        last["request"].get("action") != "buy_relic"
        or delivered.get("index") != 57
        or delivered.get("delivery") != "delivered"
        or delivered.get("action", {}).get("label") != "Buy Kifuda for 210 gold"
        or state.get("decision") != "card_select"
        or state.get("enchantment", {}).get("definition_id") != "ADROIT"
    ):
        raise ValueError("Require the original delivered Kifuda handoff")
    identity = json.loads(paths["identity"].read_text())
    report: dict[str, Any] = json.loads(
        node(
            ctx,
            f"scripts/{SAVED}",
            payload={
                "state": state,
                "observations": str(paths["observations"]),
                "shared_projection": identity["shared_projection"],
                "projection": ctx["native"]["projection"],
            },
        )
    )
    if report["saved_frames_unchanged"] != 58 or report["native_bindings_verified"] != 1:
        raise ValueError("The saved prefix or exact answer did not reconstruct")
    return report


def last_action(path: Path) -> dict[str, Any]:
    last = {}
    for row in records(path):
        if row["request"]["cmd"] == "action" and not row.get("transport"):
            last = row
    if not last:
        raise ValueError("No delivered native action in selector evidence")
    return last


def shop_control(
    ctx: dict[str, Any], target: Path, seed: str, count: int, deadline: float
) -> dict[str, Any]:
    setup = SelectorWorker(ctx, target / "fixture-preparation", fixture=True)
    try:
        prepared = setup.request("prepare_shop", seed=seed, card_count=count, timeout=25)
        setup.close()
    finally:
        setup.stop()
    native_win4_game.write(target / "fixture.json", prepared)
    root = ctx["qualification"].root
    bridge = JsonLines(root, [ctx["node"], f"scripts/{CONVERTER}"], target / "converter.log")
    try:
        worker = SelectorWorker(ctx, target / "worker", fixture=True)
        try:
            current = worker.request(
                "load_shop", seed=seed, save_json=json.dumps(prepared["save"]), timeout=25
            )
            frame = bridge.project(current["snapshot"], current["reads"], None, deadline)

            def take(matches: Callable[[dict[str, Any]], bool], domain: str = "native") -> None:
                nonlocal current, frame
                actions = current["snapshot"]["bound_actions"]["actions"]
                (index,) = [
                    i
                    for i, binding in enumerate(frame["actions"])
                    if matches(actions[binding["raw_index"]])
                ]
                choice = {"binding_id": frame["binding_id"], "action_index": index}
                current = worker.request(
                    "step",
                    snapshot_id=frame["observation"]["snapshot_id"],
                    action_index=frame["actions"][index]["raw_index"],
                )
                if current["delivery_domain"] != domain:
                    raise ValueError("A selector control crossed the wrong delivery boundary")
                successor = current["snapshot"]["snapshot_id"]
                bridge.commit(choice, receipt(frame, choice, domain, successor), deadline)
                frame = bridge.project(current["snapshot"], current["reads"], None, deadline)

            take(lambda a: a["label"] == "Open shop inventory")
            catalog = next(r["content"] for r in current["reads"] if r["kind"] == "shop_catalog")
            (offer,) = [
                r for r in catalog["relics"] if r.get("relic", {}).get("definition_id") == "KIFUDA"
            ]
            if not offer["can_purchase"]:
                raise ValueError("Expected an available native Kifuda offer")
            take(lambda a: a["label"] == f"Buy Kifuda for {offer['price']} gold")
            child = current["snapshot"]["interaction"]["content"]
            surface = child["surface"]
            compact = count == 13
            if (
                child["context"]["kind"] != "shop"
                or len(surface["cards"]) != count
                or (surface["min_select"], surface["max_select"], surface["cancelable"])
                != (0, 3, False)
                or surface["enchantment"]["definition_id"] != "ADROIT"
                or surface["enchantment"]["amount"] != 3
                or surface["selection_contract"] != (COMPACT if compact else DIRECT)
            ):
                raise ValueError("Expected the exact current shop-owned card selector")

            indices = [count - 1, 0]
            if compact:
                for index in indices:
                    cards = current["snapshot"]["interaction"]["content"]["surface"]["cards"]

                    def appends(
                        a: dict[str, Any], card_id: str = cards[index]["entity_id"]
                    ) -> bool:
                        return bool(a["verb"] == "select" and a["subject_referent_id"] == card_id)

                    take(appends, "local_answer_factor")
                take(lambda a: a["verb"] == "confirm")
            else:
                answer = [surface["cards"][i]["entity_id"] for i in indices]
                take(
                    lambda a: (
                        a["verb"] == "confirm"
                        and [x["referent_id"] for x in a["arguments"]] == answer
                    )
                )
            if frame["source_family"] != "shop_inventory":
                raise ValueError("Completed native selector did not return to its shop")
            worker.close()
        finally:
            worker.stop()
        bridge.close()
    finally:
        bridge.stop()

    folder = target / "worker"
    trace = folder / "private-transcript.jsonl.gz"
    deliveries = [r for r in records(trace) if r["request"]["cmd"] == "action"]
    actual = [r for r in deliveries if not r.get("transport")]
    if [r["request"]["action"] for r in actual] != ["open_shop", "buy_relic", "select_cards"]:
        raise ValueError("Expected exactly one native purchase and one native answer")
    chosen, before, after = (actual[2]["request"], actual[1]["response"], actual[2]["response"])
    enchanted = {
        card["native_ref"]: (card["enchantment_id"], card["enchantment_amount"])
        for card in after["player"]["deck"]
        if card.get("enchantment_id")
    }
    expected_cards = {before["cards"][i]["native_ref"] for i in indices}
    (slot,) = [
        row
        for row in after["shop_catalog"]["relics"]
        if row["native_ref"] == actual[1]["request"]["args"]["entry_ref"]
    ]
    if (
        chosen["args"] != {"selection_ref": before["selection_ref"], "indices": f"{count - 1},0"}
        or enchanted.keys() != expected_cards
        or any(e != ("ADROIT", 3) for e in enchanted.values())
        or after["player"]["gold"] != 1000 - offer["price"]
        or not any(r["id"] == "KIFUDA" for r in after["player"]["relics"])
        or slot["stocked"]
        or slot["can_purchase"]
        or slot["blocked_reason"] != "sold_out"
    ):
        raise ValueError("Native purchase, ordered answer or enchantment effect differs")
    if compact:
        proof = json.loads(node(ctx, f"scripts/{ORDERED_PROOF}", str(folder)))
        if (
            proof["local_factors"],
            proof["native_deliveries"],
            proof["ordered_answer_native_commits"],
        ) != (2, 3, 1):
            raise ValueError("Compact proof must contain two local factors and one native answer")
    return {
        "format": surface["selection_contract"],
        "cards": count,
        "price": offer["price"],
        "local_factors": len(deliveries) - len(actual),
        "native_deliveries": len(actual),
        "native_answer_deliveries": 1,
        "exact_enchanted_cards": len(enchanted),
        "native_shop_slot_sold_out": True,
        "returned_to_shop": True,
        "clean_shutdown": True,
        "privileged_fixture": True,
    }
