"""Check local ordered-card factors and their one native commit separately."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_replay_probe as replay
from spireshift.native_a8_replay_source import Journal
from spireshift.native_flow_verification_v12 import records

legacy_check = batch.check_private_run
LOCAL = "local_answer_factor"
LOCAL_TRANSPORT = "local_selection_ui"
PLAN = "factorized_ordered_card_answer_v1"


def ordered_deliveries(
    transcript: Iterable[dict[str, Any]], deliveries: Iterable[dict[str, Any]]
) -> tuple[int, int]:
    actions = (row for row in transcript if row["request"]["cmd"] == "action")
    committed = local = 0
    selection_ref: str | None = None
    selected: list[int] = []
    for row, delivery in zip(actions, deliveries, strict=True):
        request = row["request"]
        domain = delivery["receipt"]["delivery_domain"]
        public = delivery["frame"]["public_input"]
        candidate = public["candidates"][delivery["choice"]["action_index"]]
        action = request["action"]
        if domain == LOCAL:
            args, response = request["args"], row["response"]
            index = args["index"]
            ref = args["selection_ref"]
            interaction = public["context"]["interaction"]
            surface = interaction["content"]["surface"]
            if (
                row.get("transport") != LOCAL_TRANSPORT
                or action != "ordered_answer_append"
                or candidate["verb"] != "select"
                or not isinstance(ref, str)
                or not ref
                or (selection_ref is not None and ref != selection_ref)
                or args["prefix"] != ",".join(map(str, selected))
                or interaction["kind"] != "card_selection"
                or surface["answer_plan"]["selected"] != selected
                or type(index) is not int
                or not 0 <= index < len(surface["cards"])
                or index in selected
                or candidate["subject"]["public_slot"]
                != surface["cards"][index]["entity_id"]["public_slot"]
                or response["decision"] != "card_select"
                or response["selection_ref"] != ref
                or response["answer_plan"] != {"contract": PLAN, "selected": [*selected, index]}
            ):
                raise ValueError(
                    "Local card factor did not preserve the ordered selector and prefix"
                )
            selection_ref = ref
            selected.append(index)
            local += 1
        else:
            if (
                domain != "native"
                or row.get("transport") is not None
                or action.startswith("ordered_answer_")
            ):
                raise ValueError("Archive native delivery has the wrong private transport")
            if selected:
                args = request["args"]
                valid = args["selection_ref"] == selection_ref and (
                    (
                        candidate["verb"] == "confirm"
                        and action == "select_cards"
                        and args["indices"] == ",".join(map(str, selected))
                    )
                    or (candidate["verb"] == "cancel" and action == "skip_select")
                )
                if not valid:
                    raise ValueError("The native card action did not commit its ordered answer")
                selection_ref = None
                selected.clear()
            committed += 1
    if selected:
        raise ValueError("Archive ordered answer lacks a native completion")
    return committed, local


def check_private_run(out: Path, journal: Journal, report: dict[str, Any], decisions: int) -> None:
    native, local = ordered_deliveries(
        records(out / "worker/private-transcript.jsonl.gz"), records(out / replay.TRACE)
    )
    replay.equal("committed native decisions", decisions, native)
    replay.equal("all verified transports", report["verified_native_deliveries"], native + local)
    # The original fresh-run and shutdown checks count every raw action row.
    legacy_check(out, journal, report, native + local)
