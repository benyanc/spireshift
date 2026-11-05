"""Audit sealed curriculum evidence and the interrupted Test Subject turn."""

from __future__ import annotations

import copy
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_recovery import ERROR
from spireshift.native_win4_game import policy, verify_episode, write
from spireshift.native_win4_inputs import RECIPE, frozen_checks, load
from spireshift.native_win4_plan import steps
from spireshift.native_win_bank import lesson, matching_confirmation, select

PREPARATION = "artifacts/native-win-curriculum/revival-preparation-v1"
PROTECTION = f"{PREPARATION}/protected-v4-result.json"
AUDIT = "artifacts/native-win-curriculum/revival-audit-v1"
COMPLETED_CASES = 38
REUSABLE_SEALS = 210


def continuation_plan(parent: dict[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(parent["plan"])
    case = plan["fit"][COMPLETED_CASES]
    if case["key"] != "fit-039" or case["boss"] != "TEST_SUBJECT_BOSS":
        raise ValueError("Unexpected failed curriculum slot")
    case["key"] = "fit-039-replacement-1"
    case["seed_pool"] = [f"SP1RESH1FTW5F039P{i:02d}" for i in range(1, 9)]
    return dict(plan)


def failed_prefix(
    context: dict[str, Any], folder: Path, target: Path, deadline: float
) -> dict[str, Any]:
    root = context["qualification"].root
    start = identified(folder.parent / "fit-039-start/start.json")
    chooser = policy(context, start, "reference")
    converter = JsonLines(
        root,
        [context["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        target / "converter.log",
    )
    shared = iter(records(folder / "shared-public.jsonl.gz"))
    observations = records(folder / "worker/public-observations.jsonl.gz")
    receipts = iter(records(folder / "worker/public-receipts.jsonl.gz"))
    domains = iter(records(folder / "worker/answer-plan-deliveries.jsonl.gz"))
    count = 0
    failed = None
    try:
        for raw in observations:
            frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
            if not same(next(shared), {"kind": "policy_input", "frame": frame}):
                raise ValueError("Failed public observation does not reconstruct")
            choice = chooser.choose(frame)
            receipt = next(receipts)
            if (
                receipt["snapshot_id"] != frame["observation"]["snapshot_id"]
                or receipt["action"]["bound_action_id"] != choice["bound_action_id"]
            ):
                raise ValueError("Failed-prefix action binding changed")
            if receipt["delivery"] == "unknown":
                if (
                    failed is not None
                    or receipt["action"]["verb"] != "end_turn"
                    or receipt["reason_code"] != "managed_transport_unknown"
                    or receipt["successor_snapshot_id"] is not None
                ):
                    raise ValueError("Unexpected interrupted action receipt")
                failed = receipt
                continue
            row = next(shared)
            domain = next(domains)
            if (
                failed is not None
                or receipt["delivery"] != "delivered"
                or row["kind"] != "policy_choice"
                or not same(choice, row["choice"])
                or domain["delivery_domain"] != "native"
                or row["receipt"]["delivery_domain"] != "native"
                or domain["before_snapshot_id"] != receipt["snapshot_id"]
                or domain["action_id"] != choice["bound_action_id"]
                or domain["successor_snapshot_id"] != receipt["successor_snapshot_id"]
                or receipt["successor_snapshot_id"] != row["receipt"]["successor_snapshot_id"]
            ):
                raise ValueError("An acknowledged prefix action did not reconstruct")
            chooser.acknowledge(row["receipt"])
            converter.commit(choice, row["receipt"], deadline)
            count += 1
        if (
            count != 26
            or failed is None
            or chooser.pending is None
            or any(next(stream, None) is not None for stream in [shared, receipts, domains])
        ):
            raise ValueError("The diagnostic prefix or unknown final delivery changed")
        converter.close()
    finally:
        converter.stop()

    last = None
    for record in records(folder / "worker/private-transcript.jsonl.gz"):
        last = record
    if (
        last is None
        or last["request"].get("action") != "end_turn"
        or last["response"]["type"] != "error"
        or "TimeoutException" not in last["response"]["message"]
    ):
        raise ValueError("Missing actual native End Turn failure")
    diagnostics = json.loads((folder / "worker/diagnostics.json").read_text())
    lines = [row["line"] for row in diagnostics]
    cause = "Method not found: 'Void Godot.CanvasItem.SetSelfModulate(Godot.Color)'"
    if not all(
        any(term in line for line in lines)
        for term in [
            cause,
            "turn loop died",
            "TestSubject.AfterPowerApplied",
            "NemesisPower.AfterSideTurnEnd",
        ]
    ):
        raise ValueError("Missing native combat-loop fault evidence")
    stop = json.loads((folder / "worker/native-process-stop.json").read_text())
    process = subprocess.run(
        ["ps", "-p", str(stop["process_id"]), "-o", "command="],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if "Sts2Headless" in process.stdout or (folder / "done.json").exists():
        raise ValueError("The interrupted case cannot be sealed or still running")
    return {
        "case": start["scenario"],
        "status": "historical_end_turn_delivery_unknown",
        "acknowledged_diagnostic_deliveries": count,
        "unknown_end_turns": 1,
        "cause": cause,
        "native_error": last["response"]["message"],
        "native_process_terminated": True,
        "native_exit_code": stop["exit"]["code"],
        "marker_preserved": True,
        "labels_allowed": False,
    }


def audit(root: Path, out: Path) -> dict[str, Any]:
    deadline = time.monotonic() + 265
    context = load(root, root / RECIPE)
    before = frozen_checks(context)
    check_sources(root, json.loads((root / PROTECTION).read_text()))
    out.mkdir(parents=True, exist_ok=False)
    store = ChunkJournal(root, context["config"])
    imports: dict[str, dict[str, Any]] = {}

    def retain(key: str) -> dict[str, Any]:
        folder = store.workspace / "chunks" / key
        request = json.loads((folder / "active.json").read_text())["request"]
        receipt = store.completed(key, request)
        if receipt is None:
            raise ValueError("A retained case has an unsealed unit")
        imports[key] = {"request_id": receipt["request_id"], "receipt_id": receipt["report_id"]}
        return dict(receipt["result"])

    for key, expected in context["imports"].items():
        retain(key)
        path = store.workspace / "chunks" / key / "import.json"
        link = identified(path)
        if {k: v for k, v in link.items() if k != "report_id"} != {
            "original_receipt": expected,
            "new_game_or_action": False,
        }:
            raise ValueError("The inherited import no longer binds its original seal")

    episodes = []
    lessons = []
    for case in context["config"]["plan"]["fit"][31:COMPLETED_CASES]:
        key = case["key"]
        start = retain(f"{key}-start")
        variants = ["reference", *context["config"]["plan"]["teacher_variants"]]
        results = [retain(f"{key}-{variant}") for variant in variants]
        chosen = select(results[0], results[1:])
        if chosen is not None:
            confirmation = retain(f"{key}-confirm")
            if not matching_confirmation(root, chosen, confirmation):
                raise ValueError("Teacher confirmation differs")
            label = lesson(case, start, results[0], chosen, confirmation)
            labels = steps(root, label)
            lessons.append(
                {
                    "case": key,
                    "boss": case["boss"],
                    "strict_goal_rescue": label["strict_goal_rescue"],
                    "meaningful_choices": len(labels),
                    "lesson_id": label["lesson_id"],
                }
            )
            results.append(confirmation)
        for index, result in enumerate(results):
            folder = root / result["directory"]
            proof = out / f"{key}-{index}"
            proof.mkdir()
            diagnostics = json.loads((folder / "worker/diagnostics.json").read_text())
            if any(ERROR.search(row["line"]) for row in diagnostics):
                raise ValueError("A retained episode has a fatal diagnostic")
            deliveries = verify_episode(context, start, result["variant"], folder, proof, deadline)
            if (
                result["status"] != "complete"
                or deliveries != result["actual_deliveries_independently_verified"]
            ):
                raise ValueError("A completed episode failed saved verification")
            episodes.append(
                {"unit": folder.name, "deliveries": deliveries, "report_id": result["report_id"]}
            )

    failed = store.workspace / "chunks/fit-039-reference"
    diagnostic = out / "failed-prefix"
    diagnostic.mkdir()
    failure = failed_prefix(context, failed, diagnostic, deadline)
    if len(imports) != REUSABLE_SEALS or len(episodes) != 30 or len(lessons) != 2:
        raise ValueError("Unexpected retained curriculum totals")
    check_sources(root, json.loads((root / PROTECTION).read_text()))
    after = frozen_checks(context)
    return write(
        out / "report.json",
        {
            "schema_version": "native-curriculum-revival-audit-v1",
            "status": "sealed_cases_verified_failed_turn_excluded",
            "parent_config_id": context["config_id"],
            "completed_cases": COMPLETED_CASES,
            "imports": imports,
            "new_complete_episodes": episodes,
            "new_complete_deliveries": sum(ep["deliveries"] for ep in episodes),
            "new_confirmed_lessons": lessons,
            "historical_failures": [*context["historical_failures"], failure],
            "checks_before": before,
            "checks_after": after,
            "sources": {
                **context["sources"],
                PROTECTION: _sha_file(root / PROTECTION),
                "src/spireshift/native_win5_recovery.py": _sha_file(
                    root / "src/spireshift/native_win5_recovery.py"
                ),
            },
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in out.rglob("*")
                if path.is_file()
            },
            "new_games": 0,
            "optimizer_updates": 0,
        },
    )


if __name__ == "__main__":
    import sys

    root = Path.cwd()
    report = audit(root, root / (sys.argv[1] if len(sys.argv) > 1 else AUDIT))
    print(
        json.dumps(
            {
                key: report[key]
                for key in [
                    "status",
                    "report_id",
                    "completed_cases",
                    "new_complete_deliveries",
                    "new_confirmed_lessons",
                ]
            }
        )
    )
