"""Reaudit prior official seals and qualify the separately built merchant adapter."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_mixed_handoff_cases_v1 as cases_v1
from spireshift import native_mixed_handoff_session_v1 as session_v1
from spireshift import native_mixed_handoff_session_v5 as session_v5
from spireshift.engine_learning import identified
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_verification_v12 import records
from spireshift.native_mixed_handoff_checks_v2 import rest_menu
from spireshift.native_mixed_handoff_checks_v3 import control_label
from spireshift.native_mixed_handoff_inputs_v6 import MODULE, SCHEMA, context, load
from spireshift.native_mixed_handoff_worker_v2 import MixedWorker
from spireshift.native_selector_paired_contract import PairedPolicy, audit
from spireshift.native_selector_paired_session import evidence
from spireshift.native_win4_game import write


def prior_pairs(ctx: dict[str, Any], cfg: dict[str, Any], area: Path, deadline: float) -> None:
    if (area / "report.json").exists():
        report = identified(area / "report.json")
        if report["status"] != "five_historical_pairs_reverified":
            raise ValueError("Preserve incomplete historical assessment")
        check_sources(ctx["qualification"].root, report["sources"])
        return
    root = ctx["qualification"].root
    source = verified(root, cfg["parent_result"]).parent
    parent = identified(source / Path(cfg["parent_result"]["path"]).name)
    area.mkdir()
    rows = []
    for row in parent["pairs"]:
        if row["status"] != "verified":
            continue
        key = row["case"]["key"]
        saved = identified(source / "pairs" / key / "report.json")
        check_sources(root, saved["sources"])
        if (
            row != saved
            or not all(row["official"]["checks"].values())
            or not row["official"]["working_app"]["restored"]
        ):
            raise ValueError("Historical paired seal or clean reset changed")
        native = source / "native" / key
        policy = PairedPolicy(
            list(records(native / "frames.jsonl.gz")),
            [item["choice"]["action_index"] for item in records(native / "choices.jsonl.gz")],
        )
        target = area / key
        shutil.copytree(source / "pairs" / key / "official", target)
        policy.frames = [
            item["frame"]
            for item in records(target / "live-public.jsonl.gz")
            if item["kind"] in {"policy_input", "diagnostic_successor"}
        ]
        proof = audit(ctx, target, policy, deadline)
        if proof != saved["paired"]:
            raise ValueError("Historical raw public inputs or actual receipts differ")
        rows.append({"key": key, "report_id": saved["report_id"], **proof})
    if len(rows) != 5:
        raise ValueError("Require all five prior passing official pairs")
    write(
        area / "report.json",
        {
            "status": "five_historical_pairs_reverified",
            "pairs": rows,
            "original_planned_pairs": 12,
            "historical_verified_pairs": 5,
            "historical_blocked_pairs": 1,
            "original_unattempted_pairs": 6,
            "sources": evidence(root, area),
            "gameplay_replayed": False,
            "optimizer_updates": 0,
        },
    )


def native_cases(
    ctx: dict[str, Any], cfg: dict[str, Any], area: Path, deadline: float
) -> dict[str, Any]:
    prior_pairs(ctx, cfg, area.parent / "historical-assessment-v1", deadline)
    return session_v5.native_cases(ctx, cfg, area, deadline)


def main() -> int:
    with (
        patch.object(session_v5, "SCHEMA", SCHEMA),
        patch.multiple(
            session_v1,
            MODULE=MODULE,
            SCHEMA=SCHEMA,
            load=load,
            context=context,
            native_cases=native_cases,
        ),
        patch.multiple(
            cases_v1,
            MixedWorker=MixedWorker,
            shop=session_v5.shop,
            enter_next_room=session_v5.enter_next_room,
            rest_menu=rest_menu,
            label=control_label,
        ),
    ):
        return session_v1.main()


if __name__ == "__main__":
    raise SystemExit(main())
