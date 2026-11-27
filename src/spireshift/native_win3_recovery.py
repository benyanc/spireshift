"""Saved reconstruction of clean cases; runtime-error episodes stay ineligible."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_win2_game import verify_episode, write
from spireshift.native_win2_inputs import RECIPE, frozen_checks, load
from spireshift.native_win2_recovery import import_unit as import_unit
from spireshift.native_win_bank import lesson, matching_confirmation, select

PREPARATION = "artifacts/native-win-curriculum/reattach-preparation-v1"
ERROR = re.compile(
    r"\[ERROR\]|unobserved task exception|missingmethodexception|"
    r"method not found|unhandled exception",
    re.I,
)


def continuation_plan(parent: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(parent["plan"])
    case = result["fit"][30]
    if case["key"] != "fit-031" or case["act_definition"] != "HIVE":
        raise ValueError("The continuation is specific to the failed act-two start")
    case["key"] = "fit-031-replacement-1"
    case["seed_pool"] = [f"SP1RESH1FTW3F031P{i:02d}" for i in range(1, 9)]
    return dict(result)


def audit(root: Path, first: int, last: int) -> dict[str, Any]:
    began = time.monotonic()
    ctx = load(root, root / RECIPE)
    before = frozen_checks(ctx)
    protection = json.loads((root / PREPARATION / "protected-v2-result.json").read_text())
    check_sources(root, protection)
    out = root / f"artifacts/native-win-curriculum/reattach-audit-{first:02d}-{last:02d}-v1"
    out.mkdir(parents=True, exist_ok=False)
    store = ChunkJournal(root, ctx["config"])
    imports: dict[str, Any] = {}
    actual, lessons, counts = [], [], 0
    for case in ctx["config"]["plan"]["fit"][first - 1 : last]:
        results = {}
        for unit in sorted((store.workspace / "chunks").glob(case["key"] + "-*")):
            request = json.loads((unit / "active.json").read_text())["request"]
            receipt = store.completed(unit.name, request)
            if receipt is None:
                raise ValueError("A prior case is not cleanly sealed")
            imports[unit.name] = {
                "request_id": receipt["request_id"],
                "receipt_id": receipt["report_id"],
            }
            results[unit.name.removeprefix(case["key"] + "-")] = receipt["result"]
        start = results["start"]
        for variant, result in results.items():
            if variant == "start":
                continue
            folder = root / result["directory"]
            diagnostics = json.loads((folder / "worker/diagnostics.json").read_text())
            if any(ERROR.search(row["line"]) for row in diagnostics):
                raise ValueError("An earlier sealed episode contains runtime errors")
            target = out / case["key"] / variant
            target.mkdir(parents=True)
            n = verify_episode(ctx, start, result["variant"], folder, target, began + 270)
            if (
                result["status"] != "complete"
                or n != result["actual_deliveries_independently_verified"]
            ):
                raise ValueError("Complete saved episode did not reconstruct")
            counts += n
            actual.append(result["report_id"])
        chosen = select(
            results["reference"], [results[v] for v in ctx["config"]["plan"]["teacher_variants"]]
        )
        if chosen is not None:
            if not matching_confirmation(root, chosen, results["confirm"]):
                raise ValueError("Teacher confirmation changed")
            lessons.append(lesson(case, start, results["reference"], chosen, results["confirm"]))
    failure = None
    if last == 30:
        folder = store.workspace / "chunks/fit-031-reference"
        if (folder / "done.json").exists():
            raise ValueError("The failed runtime case must remain unsealed")
        request = json.loads((folder / "active.json").read_text())["request"]
        stop = json.loads((folder / "worker/native-process-stop.json").read_text())
        alive = subprocess.run(
            ["ps", "-p", str(stop["process_id"]), "-o", "command="],
            capture_output=True,
            text=True,
            check=False,
        )
        if "Sts2Headless" in alive.stdout:
            raise ValueError("Failed worker is still running")
        start = identified(store.workspace / "chunks/fit-031-start/start.json")
        target = out / "runtime-error-case-diagnostic-only"
        target.mkdir()
        count = verify_episode(ctx, start, "reference", folder, target, began + 270)
        diagnostics = json.loads((folder / "worker/diagnostics.json").read_text())
        errors = [row for row in diagnostics if ERROR.search(row["line"])]
        if not any("GetIndex(Boolean)" in row["line"] for row in errors):
            raise ValueError("Exact missing-method evidence is absent")
        failure = {
            "key": "fit-031",
            "case": request["case"],
            "seed": start["seed"],
            "status": "historical_runtime_error",
            "acknowledged_deliveries": count,
            "native_terminal_loss_observed": True,
            "native_exit_code": stop["exit"]["code"],
            "labels_allowed": False,
            "marker_preserved": True,
            "worker_termination_verified": True,
            "runtime_error": errors[0]["line"],
        }
    check_sources(root, protection)
    after = frozen_checks(ctx)
    return write(
        out / "report.json",
        {
            "schema_version": "native-curriculum-reattach-saved-audit-v1",
            "status": "saved_cases_verified_runtime_error_excluded",
            "parent_config_id": ctx["config_id"],
            "first_case": first,
            "last_case": last,
            "completed_cases": last - first + 1,
            "imports": imports,
            "episode_ids": actual,
            "complete_gameplay_episodes": len(actual),
            "verified_deliveries": counts,
            "lessons": lessons,
            "confirmed_lessons": len(lessons),
            "strict_goal_rescues": sum(x["strict_goal_rescue"] for x in lessons),
            "historical_failures": [ctx["historical_failure"]] + ([failure] if failure else []),
            "checks_before": before,
            "checks_after": after,
            "new_games": 0,
            "optimizer_updates": 0,
            "sources": {
                **ctx["sources"],
                "src/spireshift/native_win3_recovery.py": _sha_file(
                    root / "src/spireshift/native_win3_recovery.py"
                ),
            },
            "evidence": {
                str(p.relative_to(root)): _sha_file(p) for p in out.rglob("*") if p.is_file()
            },
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=int)
    parser.add_argument("last", type=int)
    args = parser.parse_args()
    result = audit(Path.cwd(), args.first, args.last)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {
                    "imports",
                    "sources",
                    "evidence",
                    "lessons",
                    "episode_ids",
                    "historical_failures",
                }
            }
        )
    )
