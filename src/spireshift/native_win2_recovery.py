"""Saved-only audit and explicit immutable imports from the stopped curriculum."""

from __future__ import annotations

import argparse
import copy
import gzip
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
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win_bank import lesson, matching_confirmation, select
from spireshift.native_win_game import verify_episode, write
from spireshift.native_win_inputs import RECIPE as BASE_RECIPE
from spireshift.native_win_inputs import frozen_checks, load

PREPARATION = "artifacts/native-win-curriculum/recovery-preparation-v1"


def continuation_plan(parent: dict[str, Any]) -> dict[str, Any]:
    plan = copy.deepcopy(parent["plan"])
    original = plan["fit"][6]
    if original["key"] != "fit-007" or original["entry"] != "act_start":
        raise ValueError("The recovery is specific to the recorded interrupted case")
    original["key"] = "fit-007-replacement-1"
    original["seed_pool"] = [f"SP1RESH1FTW2F007P{i:02d}" for i in range(1, 9)]
    return dict(plan)


def import_unit(
    context: dict[str, Any], key: str, request: dict[str, Any]
) -> dict[str, Any] | None:
    spec = context.get("imports", {}).get(key)
    if spec is None:
        return None
    if spec["request_id"] != manifest_identifier(request):
        raise ValueError("Recovered unit request differs; never replay it")
    root = context["qualification"].root
    old = ChunkJournal(root, context["parent_config"])
    receipt = old.completed(key, request)
    if receipt is None or receipt["report_id"] != spec["receipt_id"]:
        raise ValueError("Original sealed evidence is missing or changed")
    return dict(receipt["result"])


def audit(root: Path, out: Path) -> dict[str, Any]:
    started = time.monotonic()
    context = load(root, root / BASE_RECIPE)
    before = frozen_checks(context)
    protection = json.loads((root / PREPARATION / "protected-original-run-v1.json").read_text())
    check_sources(root, protection)
    store = ChunkJournal(root, context["config"])
    imports: dict[str, Any] = {}
    verified, count, lessons = [], 0, []
    for case in context["config"]["plan"]["fit"][:6]:
        results = {}
        for directory in sorted((store.workspace / "chunks").glob(case["key"] + "-*")):
            active = json.loads((directory / "active.json").read_text())
            request = active["request"]
            receipt = store.completed(directory.name, request)
            if receipt is None:
                raise ValueError("An earlier case is not fully sealed")
            imports[directory.name] = {
                "request_id": receipt["request_id"],
                "receipt_id": receipt["report_id"],
            }
            result = receipt["result"]
            results[directory.name.removeprefix(case["key"] + "-")] = result
        start = results["start"]
        for variant, result in results.items():
            if variant == "start":
                continue
            target = out / case["key"] / variant
            target.mkdir(parents=True)
            n = verify_episode(
                context, start, result["variant"], root / result["directory"], target, started + 270
            )
            if (
                n != result["actual_deliveries_independently_verified"]
                or result["status"] != "complete"
            ):
                raise ValueError("A completed original episode failed saved reconstruction")
            count += n
            verified.append(result["report_id"])
        chosen = select(
            results["reference"],
            [results[v] for v in context["config"]["plan"]["teacher_variants"]],
        )
        if chosen is not None:
            confirmation = results["confirm"]
            if not matching_confirmation(root, chosen, confirmation):
                raise ValueError("Original teacher confirmation differs")
            lessons.append(lesson(case, start, results["reference"], chosen, confirmation))
    failed = store.workspace / "chunks/fit-007-reference"
    active = json.loads((failed / "active.json").read_text())
    request = active["request"]
    if (failed / "done.json").exists():
        raise ValueError("Expected the preserved incomplete observation unit")
    stop = json.loads((failed / "worker/native-process-stop.json").read_text())
    process = subprocess.run(
        ["ps", "-p", str(stop["process_id"]), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if "Sts2Headless" in process.stdout:
        raise ValueError("Failed native process is still alive")
    # An explicitly transformed diagnostic prefix, never admitted as experience.
    prefix = out / "failed-prefix-diagnostic"
    (prefix / "worker").mkdir(parents=True)
    for name in ["public-observations.jsonl.gz", "public-receipts.jsonl.gz"]:
        (prefix / "worker" / name).write_bytes((failed / "worker" / name).read_bytes())
    rows = list(records(failed / "shared-public.jsonl.gz"))
    if rows[-1]["kind"] != "policy_input":
        raise ValueError("Expected a menu whose next delivery was not acknowledged")
    rows[-1] = {**rows[-1], "kind": "final_observation"}
    with gzip.open(prefix / "shared-public.jsonl.gz", "wt") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    verify = prefix / "verification"
    verify.mkdir()
    start = identified(store.workspace / "chunks/fit-007-start/start.json")
    prefix_count = verify_episode(context, start, "reference", prefix, verify, started + 270)
    failure = {
        "key": "fit-007",
        "case": request["case"],
        "status": "historical_observation_failed",
        "accepted_prefix_deliveries": prefix_count,
        "unacknowledged_next_action": True,
        "native_process_terminated": True,
        "labels_allowed": False,
        "marker_preserved": True,
        "original_seed_pool_excluded": request["case"]["seed_pool"],
    }
    check_sources(root, protection)
    after = frozen_checks(context)
    body = {
        "schema_version": "native-win-curriculum-saved-recovery-v1",
        "status": "sealed_cases_verified_interrupted_world_excluded",
        "parent_config_id": context["config_id"],
        "imports": imports,
        "completed_cases": 6,
        "completed_gameplay_episodes": len(verified),
        "verified_deliveries": count,
        "confirmed_lessons": len(lessons),
        "strict_goal_rescues": sum(x["strict_goal_rescue"] for x in lessons),
        "episode_ids": verified,
        "historical_failure": failure,
        "new_games": 0,
        "optimizer_updates": 0,
        "checks_before": before,
        "checks_after": after,
        "sources": context["sources"],
        "evidence": {str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()},
    }
    return write(out / "report.json", body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination")
    args = parser.parse_args()
    root = Path.cwd()
    out = root / args.destination
    out.mkdir(parents=True, exist_ok=False)
    result = audit(root, out)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in {"sources", "evidence", "imports", "historical_failure", "episode_ids"}
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
