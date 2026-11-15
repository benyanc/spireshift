"""Verify the retained v6 cases and the unusable Soul Nexus successor."""

from __future__ import annotations

import argparse
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
from spireshift.native_win4_game import policy, verify_episode, write
from spireshift.native_win4_plan import steps
from spireshift.native_win6_inputs import frozen_checks, load
from spireshift.native_win_bank import coverage, lesson, matching_confirmation, select

PROTECTION = "artifacts/native-win-curriculum/nexus-preparation-v1/protected-v6-result.json"
OWNER_RESOURCE = "artifacts/resources/win-curriculum-v6-attempt-1.json"
CONVERTER = "scripts/engine-shared-input-v16.mjs"
COMPLETED_FIT = 56
COMPLETED_HELDOUT = 10
REUSABLE_SEALS = 354


def failed_prefix(
    ctx: dict[str, Any], start: dict[str, Any], folder: Path, output: Path, deadline: float
) -> dict[str, Any]:
    root = ctx["qualification"].root
    worker = folder / "worker"
    chooser = policy(ctx, start, "balanced")
    converter = JsonLines(root, [ctx["node"], str(root / CONVERTER)], output / "converter.log")
    observations = iter(records(worker / "public-observations.jsonl.gz"))
    receipts = iter(records(worker / "public-receipts.jsonl.gz"))
    domains = iter(records(worker / "answer-plan-deliveries.jsonl.gz"))
    shared = iter(records(folder / "shared-public.jsonl.gz"))
    count = 0
    last_action = None
    try:
        for raw in observations:
            frame = converter.project(raw["snapshot"], raw["reads"], None, deadline)
            if not same(next(shared), {"kind": "policy_input", "frame": frame}):
                raise ValueError("Interrupted public input does not reconstruct")
            choice = chooser.choose(frame)
            receipt = next(receipts)
            if (
                receipt["snapshot_id"] != frame["observation"]["snapshot_id"]
                or receipt["action"]["bound_action_id"] != choice["bound_action_id"]
                or receipt["delivery"] != "delivered"
                or receipt["reason_code"] is not None
                or not receipt["successor_snapshot_id"]
            ):
                raise ValueError("Interrupted worker receipt binding differs")
            row = next(shared, None)
            if row is None:
                candidate = frame["public_input"]["candidates"][choice["action_index"]]
                targets = [
                    argument["entity"]["properties"]["definition_id"]
                    for argument in candidate["arguments"]
                    if argument["role"] == "target"
                ]
                if (
                    candidate["verb"] != "play"
                    or candidate["subject"]["properties"]["definition_id"] != "BLUDGEON"
                    or targets != ["SOUL_NEXUS"]
                ):
                    raise ValueError("Unexpected final action at the Soul Nexus fault")
                last_action = receipt
                break
            domain = next(domains)
            if (
                row["kind"] != "policy_choice"
                or not same(row["choice"], choice)
                or domain["delivery_domain"] != "native"
                or row["receipt"]["delivery_domain"] != "native"
                or domain["before_snapshot_id"] != receipt["snapshot_id"]
                or domain["action_id"] != choice["bound_action_id"]
                or domain["successor_snapshot_id"] != receipt["successor_snapshot_id"]
                or row["receipt"]["successor_snapshot_id"] != receipt["successor_snapshot_id"]
            ):
                raise ValueError("Acknowledged diagnostic action did not reconstruct")
            chooser.acknowledge(row["receipt"])
            converter.commit(choice, row["receipt"], deadline)
            count += 1
        if (
            count != 134
            or last_action is None
            or chooser.pending is None
            or any(next(stream, None) is not None for stream in (observations, receipts, domains))
        ):
            raise ValueError("Unexpected interrupted prefix length or successor")
        converter.close()
    finally:
        converter.stop()

    diagnostics = [row["line"] for row in json.loads((worker / "diagnostics.json").read_text())]
    fault = next((i for i, line in enumerate(diagnostics) if "NullReferenceException" in line), -1)
    last = None
    for row in records(worker / "private-transcript.jsonl.gz"):
        last = row
    if (
        fault < 0
        or "SoulNexus.AfterDeath" not in diagnostics[fault + 1]
        or last is None
        or last["request"].get("action") != "play_card"
        or last["response"].get("decision") != "combat_play"
        or last["response"]["enemies"] != []
    ):
        raise ValueError("The raw combat death fault does not match the worker rejection")
    stop = json.loads((worker / "native-process-stop.json").read_text())
    identity = json.loads((worker / "identity.json").read_text())["runtime_identity"]
    process = subprocess.run(
        ["ps", "-p", str(stop["process_id"]), "-o", "command="],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if (
        stop["process_id"] != identity["process_id"]
        or stop["exit"]["code"] != 143
        or "Sts2Headless" in process.stdout
        or (folder / "done.json").exists()
        or not (folder / "active.json").is_file()
    ):
        raise ValueError("Interrupted worker has no verified retirement or preserved marker")
    return {
        "case": start["scenario"],
        "status": "historical_soul_nexus_runtime_fault_after_delivery",
        "seed": start["seed"],
        "variant": "balanced",
        "acknowledged_diagnostic_deliveries": count,
        "final_transport_delivered": True,
        "final_worker_successor_accepted": False,
        "native_error": diagnostics[fault],
        "native_callback": diagnostics[fault + 1].strip(),
        "native_process_terminated": True,
        "native_exit_code": stop["exit"]["code"],
        "marker_preserved": True,
        "labels_allowed": False,
    }


def audit(root: Path, output: Path) -> dict[str, Any]:
    deadline = time.monotonic() + 265
    ctx = load(root)
    before = frozen_checks(ctx)
    protected = json.loads((root / PROTECTION).read_text())
    check_sources(root, protected)
    owner = identified(root / OWNER_RESOURCE)
    store = ChunkJournal(root, ctx["config"])
    if (
        owner["status"] != "failed"
        or owner["exit_code"] != 2
        or owner["cap"] is not None
        or json.loads((store.workspace / "config-at-launch.json").read_text()) != ctx["config"]
    ):
        raise ValueError("Saved v6 owner execution differs")
    output.mkdir(parents=True, exist_ok=False)
    imports: dict[str, dict[str, Any]] = {}
    targeted = []

    def retain(key: str, request: dict[str, Any], *, diagnostic: bool = False) -> dict[str, Any]:
        receipt = store.completed(key, request)
        if receipt is None:
            raise ValueError(f"Missing saved curriculum unit {key}")
        if not diagnostic:
            imports[key] = {"request_id": receipt["request_id"], "receipt_id": receipt["report_id"]}
        inherited = ctx["imports"].get(key)
        if inherited is not None:
            link = identified(store.path(key) / "import.json")
            if link["original_receipt"] != inherited or link["new_game_or_action"] is not False:
                raise ValueError("A previous import lost its original receipt")
        return dict(receipt["result"])

    def episode_request(
        case: dict[str, Any], start: dict[str, Any], variant: str
    ) -> dict[str, Any]:
        return {
            "case": case,
            "stage": "episode",
            "start_id": start["report_id"],
            "variant": variant,
            "model_id": ctx["models"][case["player"]].model_id,
        }

    def verify_saved(start: dict[str, Any], result: dict[str, Any], key: str) -> None:
        folder = root / result["directory"]
        proof = output / key
        proof.mkdir()
        count = verify_episode(ctx, start, result["variant"], folder, proof, deadline)
        if count != result["actual_deliveries_independently_verified"]:
            raise ValueError("Saved complete trace disagrees with its sealed replay")
        targeted.append({"unit": key, "native_deliveries": count})

    def checked_episode(key: str, result: dict[str, Any]) -> None:
        folder = root / result["directory"]
        if (
            result != identified(folder / "report.json")
            or result["status"] != "complete"
            or result["shutdown"]["clean_exit"] is not True
            or result["shutdown"]["runtime_errors"]
            or result["optimizer_updates"] != 0
            or (key not in ctx["imports"] and folder != store.path(key))
        ):
            raise ValueError("A retained episode lacks its complete original verification")

    plan = ctx["config"]["plan"]
    lessons, heldout = [], []
    families: set[str] = set()
    episode_count = native_deliveries = 0
    for partition, complete in (("fit", COMPLETED_FIT), ("heldout", COMPLETED_HELDOUT)):
        for case in plan[partition][:complete]:
            key = case["key"]
            start = retain(f"{key}-start", {"case": case, "stage": "setup"})
            if start["status"] != "ready" or start["scenario"] != case:
                raise ValueError("A retained case start changed")
            rows = []
            for variant in ("reference", *plan["teacher_variants"]):
                episode_key = f"{key}-{variant}"
                value = retain(episode_key, episode_request(case, start, variant))
                checked_episode(episode_key, value)
                rows.append(value)
            best = select(rows[0], rows[1:])
            if partition == "heldout":
                heldout.append(best or rows[1])
            elif best is not None:
                confirmation = retain(
                    f"{key}-confirm",
                    {
                        "stage": "confirmation",
                        "chosen_id": best["report_id"],
                        "start_id": start["report_id"],
                    },
                )
                checked_episode(f"{key}-confirm", confirmation)
                if not matching_confirmation(root, best, confirmation):
                    raise ValueError("Saved teacher confirmation differs")
                if f"{key}-confirm" not in ctx["imports"]:
                    verify_saved(start, best, f"{key}-chosen")
                    verify_saved(start, confirmation, f"{key}-confirm")
                value = lesson(case, start, rows[0], best, confirmation)
                labels = steps(root, value)
                families.update(row["family"] for row in labels)
                lessons.append(value)
                rows.append(confirmation)
            episode_count += len(rows)
            native_deliveries += sum(r["actual_deliveries_independently_verified"] for r in rows)

    case = plan["heldout"][COMPLETED_HELDOUT]
    if case["key"] != "heldout-011":
        raise ValueError("The interrupted world is not held-out case 11")
    start = retain("heldout-011-start", {"case": case, "stage": "setup"}, diagnostic=True)
    sibling = retain(
        "heldout-011-reference", episode_request(case, start, "reference"), diagnostic=True
    )
    checked_episode("heldout-011-reference", sibling)
    verify_saved(start, sibling, "heldout-011-reference")
    failure = failed_prefix(ctx, start, store.path("heldout-011-balanced"), output, deadline)
    if not sibling["curriculum_success"]:
        raise ValueError("Historical reference sibling differs")
    if {p.name for p in (store.workspace / "chunks").iterdir()} != {
        *imports,
        "heldout-011-start",
        "heldout-011-reference",
        "heldout-011-balanced",
    }:
        raise ValueError("Unexpected saved chunk or completed receipt")
    quality = coverage(lessons, families, heldout, plan["quality"])
    if (
        len(imports) != REUSABLE_SEALS
        or episode_count != 288
        or native_deliveries != 25266
        or len(lessons) != 24
        or len(quality["goal_rescue_worlds"]) != 18
        or quality["missing_bosses"] != ["SOUL_FYSH_BOSS"]
        or quality["missing_families"]
        or quality["heldout_successes"] != 5
        or quality["passed"]
    ):
        raise ValueError("The retained case counts or pending quality gates differ")
    check_sources(root, protected)
    after = frozen_checks(ctx)
    return write(
        output / "report.json",
        {
            "schema_version": "native-curriculum-nexus-audit-v1",
            "status": "sealed_cases_verified_failed_nexus_excluded",
            "parent_config_id": ctx["config_id"],
            "owner_resource_id": owner["report_id"],
            "completed_fitting_cases": COMPLETED_FIT,
            "completed_heldout_cases": COMPLETED_HELDOUT,
            "complete_episodes": episode_count,
            "native_deliveries": native_deliveries,
            "confirmed_lessons": len(lessons),
            "quality_on_complete_cases": quality,
            "imports": imports,
            "historical_failures": [*ctx["historical_failures"], failure],
            "excluded_successful_reference_sibling": {
                "report_id": sibling["report_id"],
                "native_deliveries": sibling["actual_deliveries_independently_verified"],
                "complete_case_outcome": False,
            },
            "new_saved_reconstructions": targeted,
            "checks_before": before,
            "checks_after": after,
            "new_games": 0,
            "optimizer_updates": 0,
            "sources": {
                **ctx["sources"],
                **{
                    name: _sha_file(root / name)
                    for name in [
                        PROTECTION,
                        OWNER_RESOURCE,
                        "src/spireshift/native_win7_recovery.py",
                    ]
                },
            },
            "evidence": {
                str(path.relative_to(root)): _sha_file(path)
                for path in output.rglob("*")
                if path.is_file()
            },
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    value = audit(Path.cwd(), args.output.resolve())
    print(
        json.dumps(
            {
                k: value[k]
                for k in (
                    "status",
                    "report_id",
                    "completed_fitting_cases",
                    "completed_heldout_cases",
                    "native_deliveries",
                    "confirmed_lessons",
                )
            }
        )
    )
