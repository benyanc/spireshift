"""Preserve thirty-one complete cases and the unsupported Gambling Chip boundary."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records, same
from spireshift.native_shared_transport import JsonLines
from spireshift.native_win3_game import policy, verify_episode, write
from spireshift.native_win3_inputs import RECIPE, frozen_checks, load
from spireshift.native_win3_recovery import ERROR

PREPARATION = "artifacts/native-win-curriculum/plan-preparation-v1"


def continuation_plan(parent: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(parent["plan"])
    case = result["fit"][31]
    if case["key"] != "fit-032":
        raise ValueError("Continuation is specific to the Gambling Chip boundary")
    case["key"] = "fit-032-replacement-1"
    case["seed_pool"] = [f"SP1RESH1FTW4F032P{i:02d}" for i in range(1, 9)]
    return dict(result)


def import_unit(
    context: dict[str, Any], key: str, request: dict[str, Any]
) -> dict[str, Any] | None:
    pin = context.get("imports", {}).get(key)
    if pin is None:
        return None
    if pin["request_id"] != manifest_identifier(request):
        raise ValueError("An imported unit cannot change requests or world")
    old = ChunkJournal(context["qualification"].root, context["parent_config"])
    receipt = old.completed(key, request)
    if receipt is None or receipt["report_id"] != pin["receipt_id"]:
        raise ValueError("Original sealed evidence changed")
    return dict(receipt["result"])


def failed_prefix(ctx: dict[str, Any], folder: Path, output: Path, deadline: float) -> int:
    root = ctx["qualification"].root
    start = identified(folder.parent / "fit-032-start/start.json")
    chooser = policy(ctx, start, "scaling")
    converter = JsonLines(
        root,
        [ctx["node"], str(root / "scripts/engine-shared-input-v16.mjs")],
        output / "converter.log",
    )
    observations = iter(records(folder / "worker/public-observations.jsonl.gz"))
    receipts = iter(records(folder / "worker/public-receipts.jsonl.gz"))
    frame = choice = None
    count = offered = 0
    try:
        for row in records(folder / "shared-public.jsonl.gz"):
            if row["kind"] == "policy_input":
                raw = next(observations)
                frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
                if not same(frame, row["frame"]):
                    raise ValueError("Failed prefix public input changed")
                choice = chooser.choose(frame)
                offered += 1
            elif row["kind"] == "policy_choice":
                if frame is None or choice is None or not same(choice, row["choice"]):
                    raise ValueError("Failed prefix policy did not reconstruct")
                actual = next(receipts)
                if (
                    actual["delivery"] != "delivered"
                    or actual["snapshot_id"] != frame["observation"]["snapshot_id"]
                    or actual["action"]["bound_action_id"] != choice["bound_action_id"]
                    or actual["successor_snapshot_id"] != row["receipt"]["successor_snapshot_id"]
                ):
                    raise ValueError("Failed prefix actual receipt differs")
                chooser.acknowledge(row["receipt"])
                converter.commit(choice, row["receipt"], deadline)
                choice = None
                count += 1
        if (
            count != 187
            or offered != 188
            or chooser.pending is None
            or next(observations, None)
            or next(receipts, None)
        ):
            raise ValueError("Expected 187 acknowledged actions and one unacknowledged next action")
        converter.close()
    finally:
        converter.stop()
    return count


def audit(root: Path, out: Path) -> dict[str, Any]:
    out = root / out
    began = time.monotonic()
    ctx = load(root, root / RECIPE)
    before = frozen_checks(ctx)
    protection = json.loads((root / PREPARATION / "protected-v3-result.json").read_text())
    check_sources(root, protection)
    out.mkdir(parents=True, exist_ok=False)
    store = ChunkJournal(root, ctx["config"])
    imports: dict[str, Any] = {}
    for key in ctx["imports"]:
        request = json.loads((store.workspace / "chunks" / key / "active.json").read_text())[
            "request"
        ]
        receipt = store.completed(key, request)
        if receipt is None:
            raise ValueError("A previously imported case changed")
        imports[key] = {"request_id": receipt["request_id"], "receipt_id": receipt["report_id"]}
    verified: list[dict[str, Any]] = []
    for case_index, complete in [(30, True), (31, False)]:
        case = ctx["config"]["plan"]["fit"][case_index]
        start = identified(store.workspace / "chunks" / (case["key"] + "-start") / "start.json")
        for unit in sorted((store.workspace / "chunks").glob(case["key"] + "-*")):
            if not (unit / "done.json").exists():
                if complete:
                    raise ValueError("A completed case lost a seal")
                continue
            request = json.loads((unit / "active.json").read_text())["request"]
            receipt = store.completed(unit.name, request)
            if receipt is None:
                raise ValueError("A clean saved unit changed")
            result = receipt["result"]
            if complete:
                imports[unit.name] = {
                    "request_id": receipt["request_id"],
                    "receipt_id": receipt["report_id"],
                }
            if unit.name.endswith("-start"):
                continue
            folder = root / result["directory"]
            if any(
                ERROR.search(row["line"])
                for row in json.loads((folder / "worker/diagnostics.json").read_text())
            ):
                raise ValueError("A saved clean episode has native runtime errors")
            target = out / unit.name
            target.mkdir()
            count = verify_episode(ctx, start, result["variant"], folder, target, began + 270)
            if (
                result["status"] != "complete"
                or count != result["actual_deliveries_independently_verified"]
            ):
                raise ValueError("Saved complete episode reconstruction failed")
            verified.append(
                {
                    "key": unit.name,
                    "deliveries": count,
                    "admitted_case": complete,
                    "episode_id": result["report_id"],
                }
            )
    folder = store.workspace / "chunks/fit-032-scaling"
    if (folder / "done.json").exists():
        raise ValueError("Failed case must remain unsealed")
    stop = json.loads((folder / "worker/native-process-stop.json").read_text())
    alive = subprocess.run(
        ["ps", "-p", str(stop["process_id"]), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if "Sts2Headless" in alive.stdout:
        raise ValueError("Failed native worker still running")
    target = out / "failed-prefix-diagnostic-only"
    target.mkdir()
    count = failed_prefix(ctx, folder, target, began + 270)
    last = None
    for row in records(folder / "worker/private-transcript.jsonl.gz"):
        last = row
    if last is None:
        raise ValueError("Missing failed native response")
    state = last["response"]
    if (
        state["decision"] != "card_select"
        or len(state["cards"]) != 6
        or state["min_select"] != 0
        or state["max_select"] != 999999999
        or state["prompt"] != "Choose any number of cards to replace."
    ):
        raise ValueError("Unexpected oversized selection evidence")
    if not any(r["id"] == "GAMBLING_CHIP" for r in state["player"]["relics"]):
        raise ValueError("Missing public Gambling Chip")
    raw = out / "failed-native-response.json"
    raw.write_text(json.dumps(last, indent=2) + "\n")
    failure = {
        "key": "fit-032",
        "status": "historical_large_selection_unsupported",
        "case": ctx["config"]["plan"]["fit"][31],
        "acknowledged_diagnostic_deliveries": count,
        "unacknowledged_next_action": True,
        "labels_allowed": False,
        "marker_preserved": True,
        "worker_termination_verified": True,
        "native_exit_code": stop["exit"]["code"],
        "ordered_answers": 1957,
        "adapter_bound": 512,
        "clean_siblings_labels_allowed": False,
    }
    check_sources(root, protection)
    assert len(imports) == 173
    return write(
        out / "report.json",
        {
            "schema_version": "native-curriculum-ordered-plan-audit-v1",
            "status": "complete_cases_preserved_large_selection_excluded",
            "parent_config_id": ctx["config_id"],
            "imports": imports,
            "completed_cases": 31,
            "prior_complete_episodes": 138,
            "new_complete_episodes_verified": verified,
            "historical_failures": [*ctx["historical_failures"], failure],
            "new_raw": str(raw.relative_to(root)),
            "checks_before": before,
            "checks_after": frozen_checks(ctx),
            "new_games": 0,
            "optimizer_updates": 0,
            "sources": {
                **ctx["sources"],
                "src/spireshift/native_win4_recovery.py": _sha_file(
                    root / "src/spireshift/native_win4_recovery.py"
                ),
            },
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    args = parser.parse_args()
    result = audit(Path.cwd(), Path(args.output))
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"imports", "sources", "evidence", "historical_failures"}
            }
        )
    )
