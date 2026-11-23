"""Record and check one declared chain through native selector owners."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from spireshift.native_a8_rescue_game import receipt
from spireshift.native_flow_verification_v12 import records
from spireshift.native_lifecycle_contract import Capture, check_chain, check_frame
from spireshift.native_mixed_rest_session import conversion
from spireshift.native_selector_lifecycle_worker import OwnerWorker
from spireshift.native_systematic_live_v1 import append

Match = Callable[[dict[str, Any], dict[str, Any]], bool]


class Trace:
    def __init__(
        self, ctx: dict[str, Any], worker: OwnerWorker, directory: Path, deadline: float
    ) -> None:
        self.worker = worker
        self.directory = directory
        self.deadline = deadline
        self.bridge = conversion(ctx, directory / "converter.log")
        self.captures: list[Capture] = []
        self.choices: list[int] = []
        self.domains: list[str] = []

    @property
    def frame(self) -> dict[str, Any]:
        return self.captures[-1][1]

    @property
    def current(self) -> dict[str, Any]:
        return self.captures[-1][0]

    def observe(self, observation: dict[str, Any]) -> None:
        frame = self.bridge.project(
            observation["snapshot"], observation["reads"], None, self.deadline
        )
        capture = (observation, frame)
        check_frame(capture)
        self.captures.append(capture)
        append(self.directory / "frames.jsonl.gz", frame)

    def take(self, matches: Match, *, domain: str = "native") -> None:
        frame, snapshot = self.frame, self.current["snapshot"]
        (index,) = (
            i
            for i, binding in enumerate(frame["actions"])
            if matches(
                snapshot["bound_actions"]["actions"][binding["raw_index"]],
                frame["public_input"]["candidates"][i],
            )
        )
        choice = {"binding_id": frame["binding_id"], "action_index": index}
        result = self.worker.request(
            "step",
            snapshot_id=frame["observation"]["snapshot_id"],
            action_index=frame["actions"][index]["raw_index"],
        )
        if result["delivery_domain"] != domain:
            raise ValueError("Selector control crossed the wrong native delivery boundary")
        ack = receipt(frame, choice, domain, result["snapshot"]["snapshot_id"])
        self.bridge.commit(choice, ack, self.deadline)
        append(self.directory / "choices.jsonl.gz", {"choice": choice, "receipt": ack})
        self.choices.append(index)
        self.domains.append(domain)
        self.observe(result)

    def finish(self) -> dict[str, Any]:
        worker = self.directory / "worker"
        result = check_chain(
            self.captures, self.choices, records(worker / "public-receipts.jsonl.gz")
        )
        local = 0
        committed = 0
        native_actions = []
        for row in records(worker / "private-transcript.jsonl.gz"):
            if row["request"]["cmd"] != "action":
                continue
            if row.get("transport") == "local_selection_ui":
                if row["request"]["action"] != "ordered_answer_append":
                    raise ValueError("Unexpected local selector operation")
                local += 1
            elif row.get("transport"):
                raise ValueError("Unknown gameplay delivery transport")
            else:
                native_actions.append(row["request"])
                committed += row["request"]["action"] == "select_cards"
        if local != self.domains.count("local_answer_factor") or len(
            native_actions
        ) != self.domains.count("native"):
            raise ValueError("Local answer factors were counted as native gameplay")
        return {
            **result,
            "native_deliveries": len(native_actions),
            "local_answer_factors": local,
            "native_card_answer_commits": committed,
        }

    def close(self) -> None:
        self.bridge.close()

    def stop(self) -> None:
        self.bridge.stop()


def label(expected: str) -> Match:
    return lambda raw, _: raw["label"] == expected


def verb(expected: str) -> Match:
    return lambda raw, _: raw["verb"] == expected


def potion(verb: str, definition: str) -> Match:
    return lambda raw, candidate: (
        raw["verb"] == ("use" if verb == "use" else "activate")
        and (candidate.get("subject") or {}).get("properties", {}).get("definition_id")
        == definition
        and (verb == "use" or raw["label"].startswith("Discard "))
    )
