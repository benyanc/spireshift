"""Verify duplicate gold delivery after a sealed, clean archive stop."""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_a8_archive_batch as batch
from spireshift import native_a8_archive_matching_v2 as previous
from spireshift import native_a8_archive_rewards_v3 as rewards
from spireshift import native_a8_replay_probe as replay
from spireshift.engine_learning import identified
from spireshift.native_a8_archive_batch_v3 import RECIPE
from spireshift.native_a8_mix_session import admit
from spireshift.native_a8_replay_source import Journal
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_win4_game import write

EVIDENCE = "docs/evidence/native-a8-archive-owners-v2.json"
CONTROL = "reward-gold-control-v3"


def prior(
    root: Path, output: Path, ctx: dict[str, Any]
) -> tuple[dict[str, Any], Path, Path, Journal]:
    published = identified(root / EVIDENCE)
    key = published["fresh_replay"]["source_run_id"]
    location = (root / published["native_batch_result_path"]).parent
    receipt = identified(location / "result.json")
    replay.equal("sealed owner batch", published["native_batch_report_id"], receipt["report_id"])
    cfg = json.loads((location / "config-at-launch.json").read_text())
    check_sources(root, cfg["replay_implementation"])
    (case,) = (row for row in cfg["cases"] if row["run_id"] == key)
    seal = ChunkJournal(root, cfg).completed(key, case)
    if seal is None or seal["report_id"] != published["native_case_seals"][key]:
        raise ValueError("Require the preserved clean stop")
    (trace,) = (root / path for path in seal["sources"] if path.endswith("/" + replay.TRACE))
    directory = trace.parent
    report = identified(directory / "report.json")
    frame = identified(directory / "last-frame.json")
    replay.equal(
        "prior native report", published["fresh_replay"]["native_report_id"], report["report_id"]
    )
    replay.equal(
        "prior saved frame", published["fresh_replay"]["last_frame_id"], frame.pop("report_id")
    )
    stop = report["stop"]
    if (
        not report["clean_shutdown"]
        or stop["delivery_uncertain"]
        or stop["mismatch"] != {"field": "unique recorded reward", "archive": 1, "native": 2}
    ):
        raise ValueError("Require a clean stop before either duplicate reward was sent")
    path = verified(root, case["source"])
    locale = ctx["native"]["localization"] / "localization_eng"
    names = {
        (kind, key.removesuffix(".title")): value
        for kind in ("potion", "relic", "card")
        for key, value in json.loads((locale / f"{kind}s.json").read_text()).items()
        if key.endswith(".title")
    }
    journal = replace(previous.read(path), reward_names=names)
    with previous.installed():
        count = replay.verify(
            ctx,
            directory,
            journal,
            len(journal.intents),
            time.monotonic() + 90,
            frame,
            log=output / "verify-prior.log",
        )
    replay.equal("reconstructed clean prefix", report["verified_native_deliveries"], count)
    updated = replace(rewards.read(path), reward_names=names)
    cursor = 0
    with rewards.installed():
        for row in records(trace):
            index, cursor, domain = replay.next_choice(
                row["frame"], updated, cursor, len(updated.intents)
            )
            replay.equal(
                "clean prefix action",
                (row["choice"]["action_index"], row["receipt"]["delivery_domain"]),
                (index, domain),
            )
        index, cursor, domain = replay.next_choice(frame, updated, cursor, len(updated.intents))
    if index is None or domain != "native" or updated.intents[cursor - 1].kind != "repeated_gold":
        raise ValueError("Require a reconstructed first gold binding on the saved menu")
    return case, path, directory, updated


def compare(before: Path, after: Path, count: int, journal: Journal) -> list[dict[str, Any]]:
    prior_rows = records(before / replay.TRACE)
    new_rows = iter(records(after / replay.TRACE))
    for old in prior_rows:
        current = next(new_rows)
        replay.equal(
            "new start matches the saved public input",
            True,
            same(old["frame"]["public_input"], current["frame"]["public_input"]),
        )
        replay.equal(
            "new start matches the saved action",
            old["choice"]["action_index"],
            current["choice"]["action_index"],
        )
    first, second, successor = next(new_rows), next(new_rows), next(new_rows)
    actions = [first, second, successor]
    balances = [
        row["frame"]["public_input"]["context"]["persistent"]["player"]["gold"] for row in actions
    ]
    remaining = [
        sum(
            r["kind"] == "gold" and r["label"] == "15 Gold"
            for r in row["frame"]["public_input"]["context"]["interaction"]["content"]["surface"][
                "rewards"
            ]
        )
        for row in actions
    ]
    replay.equal("actual gold and occurrences", ([181, 196, 211], [2, 1, 0]), (balances, remaining))
    result = []
    for number, row in enumerate(actions[:2], count + 1):
        claim = journal.intents[row["cursor"] - 1]
        candidate = row["frame"]["public_input"]["candidates"][row["choice"]["action_index"]]
        replay.equal(
            "actual repeated gold action",
            ("repeated_gold", "Claim 15 Gold", "native"),
            (claim.kind, candidate["label"], row["receipt"]["delivery_domain"]),
        )
        result.append(
            {
                "delivery": number,
                "source_record": claim.record["s"],
                "gold_before": balances[number - count - 1],
                "gold_after": balances[number - count],
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="Confirm the repair from a clean normal start"
    )
    args = parser.parse_args()
    for name in THREADS:
        os.environ[name] = "1"
    root = Path.cwd()
    cfg = json.loads((root / RECIPE).read_text())
    check_sources(root, cfg["replay_implementation"])
    base = admit(root)
    scope = ChunkJournal(
        root, {"workspace": f"{batch.AREA}/execution", "schema_version": batch.SCHEMA}
    )
    work = ChunkJournal(root, {"workspace": f"{batch.AREA}/{CONTROL}", "recipe": cfg})
    if not args.run:
        print(json.dumps(identified(work.workspace / "result.json")))
        return
    with scope.lock(), work.lock():
        request = {"prior": EVIDENCE, "matcher": rewards.MATCHER}
        target = work.begin("audit-and-replay", request)
        case, source, old, journal = prior(root, target, base.ctx)
        with (
            rewards.installed(),
            patch.multiple(
                replay,
                AREA=str(target.relative_to(root)),
                SAMPLE=case["run_id"],
                SOURCE_SHA=case["source"]["sha256"],
                FULL_SECONDS=cfg["case_wall_seconds"],
            ),
        ):
            report = replay.probe(root, journal, source, control=False, attempt=1)
        out = target / case["run_id"] / "archive-qualification-v1"
        count = identified(old / "report.json")["verified_native_deliveries"]
        if (
            report["verified_native_deliveries"] is None
            or report["verified_native_deliveries"] < count + 3
        ):
            raise ValueError("The repaired control stopped before both verified gold claims")
        claims = compare(old, out, count, journal)
        check_sources(root, cfg["replay_implementation"])
        seal = work.commit(
            "audit-and-replay",
            request,
            {
                "matching_prefix_deliveries": count,
                "actual_gold_claims": claims,
                "report_id": report["report_id"],
            },
        )
        summary = write(
            work.workspace / "result.json",
            {
                "schema_version": "native-a8-archive-gold-control-v3",
                "source_run_id": case["run_id"],
                "prior_report_id": identified(old / "report.json")["report_id"],
                "native_report_id": report["report_id"],
                "seal_id": seal["report_id"],
                "verified_native_deliveries": report["verified_native_deliveries"],
                "matching_prefix_deliveries": count,
                "actual_gold_claims": claims,
                "genuine_native_victory": report["genuine_native_victory"],
                "clean_shutdown": report["clean_shutdown"],
                "stop": report["stop"],
                "frozen_checks": report["frozen_checks"],
                "optimizer_updates": 0,
                "training_admission_granted": False,
            },
        )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
