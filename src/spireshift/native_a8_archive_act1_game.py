"""Deliver recorded Act 1 choices and verify the native boss reward exit."""

from __future__ import annotations

import gzip
import json
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

from spireshift import native_a8_replay_probe as replay
from spireshift.native_a8_archive_act1_source import ActOne, matching
from spireshift.native_a8_archive_delivery_audit_v6 import ordered_deliveries
from spireshift.native_a8_mix_session import MixWorker, Study
from spireshift.native_a8_rescue_game import bridge, receipt
from spireshift.native_a8_reward_exit import verify_exit
from spireshift.native_flow_live_v12 import append
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write
from spireshift.native_win_teacher import validate_student_input

CLEAR = "verified_native_act1_clear"


def verify_no_delivery(
    ctx: dict[str, Any], target: Path, frame: dict[str, Any], log: Path, deadline: float
) -> None:
    worker = target / "worker"
    for path in (
        target / replay.TRACE,
        worker / "public-receipts.jsonl.gz",
        worker / "answer-plan-deliveries.jsonl.gz",
    ):
        if path.exists() and next(records(path), None) is not None:
            raise ValueError("A zero-delivery stop contains action evidence")
    commands = [row["request"]["cmd"] for row in records(worker / "private-transcript.jsonl.gz")]
    if (
        commands.count("start_run") != 1
        or commands.count("quit") != 1
        or commands[-1] != "quit"
        or set(commands)
        - {"start_run", "quit", "get_map", "process_metrics", "run_identity", "runtime_identity"}
    ):
        raise ValueError("A zero-delivery stop must contain only a fresh start, reads and shutdown")
    (raw,) = records(worker / "public-observations.jsonl.gz")
    converter = bridge(ctx, log)
    try:
        reconstructed = converter.project(raw["snapshot"], raw["reads"], None, deadline)
        replay.equal("reconstructed no-action frame", True, same(frame, reconstructed))
        converter.close()
    finally:
        converter.stop()


def export_labels(target: Path, native_count: int) -> dict[str, int]:
    """Keep every legal option and group local steps with their native commit."""
    raw = iter(records(target / "worker/public-observations.jsonl.gz"))
    counts: Counter[str] = Counter()
    factors: list[dict[str, Any]] = []
    owner: tuple[int, str] | None = None
    with gzip.open(target / "public-answers.jsonl.gz", "xt", encoding="utf-8") as stream:
        for row in records(target / replay.TRACE):
            frame, choice, ack = row["frame"], row["choice"], row["receipt"]
            public, actions = frame["public_input"], frame["actions"]
            snapshot = next(raw)["snapshot"]
            menu = snapshot["bound_actions"]
            run = public["context"]["persistent"]["run"]
            family = public["context"]["interaction"]["kind"]
            location = (run["floor"], family)
            if (
                run["act"] != 1
                or frame["terminal"]
                or menu["status"] != "complete"
                or menu["total_count"] != len(menu["actions"])
                or len(actions) != len(public["candidates"])
                or sorted(a["raw_index"] for a in actions) != list(range(len(menu["actions"])))
                or any(
                    a["bound_action_id"] != menu["actions"][a["raw_index"]]["bound_action_id"]
                    for a in actions
                )
                or (factors and location != owner)
            ):
                raise ValueError("An Act 1 label requires the exact complete public owner and menu")
            validate_student_input(public)
            owner = location
            index = choice["action_index"]
            factors.append({"public_input": public, "action_index": index})
            verb = public["candidates"][index]["verb"]
            if ack["delivery_domain"] == "local_answer_factor" and verb == "select":
                continue
            if ack["delivery_domain"] != "native" or (
                len(factors) > 1 and verb not in {"confirm", "cancel"}
            ):
                raise ValueError("A demonstration answer requires its native completion")
            stream.write(json.dumps({"act": 1, "family": family, "factors": factors}) + "\n")
            counts[family] += 1
            factors = []
    if factors or sum(counts.values()) != native_count:
        raise ValueError("Incomplete public answers or native delivery count")
    return dict(counts)


def play(
    study: Study, archive: ActOne, target: Path, execution_id: str, deadline: float
) -> dict[str, Any]:
    ctx = study.ctx
    limits = study.cfg["game_limits"]
    locale = ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): value
        for kind in ("potion", "relic", "card")
        for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    journal = replace(archive.journal, reward_names=names)
    end = len(journal.intents)
    worker = target / "worker"
    native = MixWorker({**ctx, "execution_id": execution_id}, worker)
    converter = None
    last: dict[str, Any] | None = None
    cursor = deliveries = 0
    status = CLEAR
    stop: dict[str, Any] | None = None
    try:
        converter = bridge(ctx, target / "converter.log")
        current = native.request("mount", seed=journal.seed, timeout=25)
        identity = current["private_start_identity"]
        if (
            current["episode"] != 1
            or current["reset"] is not False
            or identity["seed"] != journal.seed
            or identity["started_with_neow"] is not True
        ):
            raise ValueError("Expected the exact fresh native Neow start")
        write(target / "native-start.json", identity)
        frame = converter.project(current["snapshot"], current["reads"], None, deadline)
        with matching():
            while cursor < end:
                combat = frame["public_input"]["context"]["interaction"]["content"].get(
                    "context", {}
                )
                if (
                    deliveries >= limits["maximum_decisions"]
                    or current["usage"]["native_cpu_seconds"] >= limits["episode_cpu_seconds"]
                    or combat.get("round", 0) > limits["maximum_rounds_per_fight"]
                    or time.monotonic() >= deadline - 25
                ):
                    status, stop = "capped", {"error": "Native choice, time or compute limit"}
                    break
                try:
                    if cursor == 0:
                        replay.start(frame, journal)
                    index, following, domain = replay.next_choice(frame, journal, cursor, end)
                except replay.Divergence as exc:
                    status, stop = "diverged", {"error": str(exc), "mismatch": exc.facts}
                    break
                if index is None:
                    raise ValueError("The recorded Act 1 exit has no bound native action")
                choice = {"action_index": index, "binding_id": frame["binding_id"]}
                current = native.request(
                    "step",
                    snapshot_id=current["snapshot"]["snapshot_id"],
                    action_index=frame["actions"][index]["raw_index"],
                    timeout=min(15, deadline - time.monotonic() - 15),
                )
                replay.equal("delivery domain", domain, current["delivery_domain"])
                accepted = receipt(frame, choice, domain, current["snapshot"]["snapshot_id"])
                converter.commit(choice, accepted, deadline)
                last = {"frame": frame, "choice": choice, "receipt": accepted, "cursor": following}
                append(target / replay.TRACE, last)
                frame = converter.project(current["snapshot"], current["reads"], None, deadline)
                deliveries += 1
                cursor = following
        if (
            status == CLEAR
            and current["usage"]["native_cpu_seconds"] > limits["episode_cpu_seconds"]
        ):
            status, stop = "capped", {"error": "Native compute limit at the successor"}
        converter.close()
        shutdown = native.close()
    finally:
        if converter is not None:
            converter.stop()
        native.stop()

    if (
        shutdown["episodes"] != 1
        or shutdown["clean_exit"] is not True
        or shutdown["runtime_errors"]
    ):
        raise ValueError("Native shutdown failed; preserve the attempt")
    write(target / "last-frame.json", frame)
    if deliveries:
        with matching():
            reconstructed = replay.verify(ctx, target, journal, end, deadline, frame)
    else:
        verify_no_delivery(ctx, target, frame, target / "verify.log", deadline)
        reconstructed = 0
    replay.equal("reconstructed transport count", deliveries, reconstructed)
    proof = labels = None
    if status == CLEAR:
        if last is None or cursor != end:
            raise ValueError("A clear requires the complete recorded Act 1")
        run = frame["public_input"]["context"]["persistent"]["run"]
        replay.equal(
            "recorded Act 2 entry",
            (2, archive.entry["floor"], archive.entry["name"]),
            (run["act"], run["floor"], run["act_definition_id"]),
        )
        proof = verify_exit(
            worker, last["frame"], last["choice"], last["receipt"], frame, deliveries
        )
        native_count, local = ordered_deliveries(
            records(worker / "private-transcript.jsonl.gz"), records(target / replay.TRACE)
        )
        replay.equal("native and local transports", deliveries, native_count + local)
        labels = export_labels(target, native_count)
    return write(
        target / "report.json",
        {
            "schema_version": "native-a8-archive-act1-replay-v1",
            "status": status,
            "seed": journal.seed,
            "opening": archive.opening,
            "act1_boss": journal.boss,
            "source_intents": end,
            "source_intents_consumed": cursor,
            "verified_deliveries": reconstructed,
            "native_act2_entry": proof,
            "public_answers_by_owner": labels,
            "stop": stop,
            "shutdown": shutdown,
            "optimizer_updates": 0,
        },
    )
