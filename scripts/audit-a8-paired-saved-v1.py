"""Finalize the sealed A8 panel in its historical checkout, without a game entry point."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from statistics import fmean, median
from typing import Any

from spireshift import native_a8_paired_session as panel
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_paired_inputs import freeze
from spireshift.native_a8_paired_report import diagnostics, summarize
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

BEFORE = "da63b75371060d3c685e0cc9caa26108c399fce5"
AFTER = "761a7ceceaf3897d1a52dee6de7912aa742c4e08"
WORKFLOW = ".github/workflows/ci.yml"
RESOURCE = "artifacts/resources/a8-paired-finals-v1-1793985085447476000.json"
FAILED_REPORT_ID = "sha256:ddf0750874baed906f619e0939bb1a73978e8914d5c37814fce036aefcd03690"
OUTPUT = "artifacts/native-a8-paired/saved-recovery-v1/report.json"


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root, timeout=20)


def audit_cell(
    directory: Path, task: dict[str, Any], row: dict[str, Any], ctx: dict[str, Any]
) -> None:
    start = identified(directory / "start.json")
    episode = identified(directory / "report.json")
    seed = task["world"]
    model = ctx["models" if task["arm"] == "original" else "finals"][task["player"]]
    ending = episode["native_ending"]
    final_identity = ending["private_final_identity"]
    won = row["outcome"] == "win"
    if (
        any(row[k] != v for k, v in task.items())
        or row["model_id"] != model.model_id
        or episode["model_id"] != model.model_id
        or start["seed"] != episode["seed"]
        or start["seed"] != seed
        or start["scenario"]["key"] != task["key"]
        or start["scenario"]["player"] != task["player"]
        or start["scenario"]["entry"] != "natural"
        or start["scenario"]["partition"] != "a8_development_evaluation"
        or start["save_path"] is not None
        or episode["start_id"] != start["report_id"]
        or episode["report_id"] != row["episode_report_id"]
        or episode["status"] != "complete"
        or row["outcome"] not in {"win", "loss"}
        or episode["full_run_win"] is not won
        or row["native_terminal"] is not True
        or episode["native_terminal"] is not True
        or episode["optimizer_updates"] != 0
        or ending["native_ending_evidence_agrees"] is not True
        or final_identity["seed"] != seed
        or final_identity["ascension"] != 8
        or final_identity["native_game_over"] is not True
        or final_identity["native_victory_room"] is not won
        or (not won and final_identity["native_player_dead"] is not True)
    ):
        raise ValueError(f"The sealed cell has inconsistent run or ending facts: {task['key']}")

    worker = directory / "worker"
    identity = json.loads((worker / "identity.json").read_text())["runtime_identity"]
    build = ctx["native"]["build"]
    stopped = json.loads((worker / "native-process-stop.json").read_text())
    shutdown = json.loads((worker / "closed.json").read_text())
    if (
        identity["host_assembly_sha256"] != build["artifact_sha256"]
        or identity["sts2_assembly_sha256"] != build["runtime_sts2_sha256"]
        or identity["godot_stub_assembly_sha256"] != build["godot_stub_sha256"]
        or identity["host_module_mvid"] != build["artifact_mvid"]
        or identity["managed_runtime_version"] != "9.0.7"
        or shutdown != episode["shutdown"]
        or shutdown["clean_exit"] is not True
        or shutdown["runtime_errors"]
        or shutdown["episodes"] != 1
        or shutdown["exit"]["code"] != 0
        or stopped["process_id"] != identity["process_id"]
        or stopped["exit"] != shutdown["exit"]
    ):
        raise ValueError(f"The sealed cell has inconsistent native worker evidence: {task['key']}")
    identities = [
        line["response"]
        for line in records(worker / "private-transcript.jsonl.gz")
        if line["request"]["cmd"] == "run_identity"
    ]
    if (
        not identities
        or identities[-1] != final_identity
        or not any(
            item.get("active") is True
            and item.get("seed") == seed
            and item.get("ascension") == 8
            and item.get("started_with_neow") is True
            and item.get("native_game_over") is False
            for item in identities
        )
    ):
        raise ValueError(f"The start or ending is missing from the raw transcript: {task['key']}")

    trace = directory / "shared-public.jsonl.gz"
    initial_id, final, deliveries = None, None, 0
    for line in records(trace):
        if final is not None:
            raise ValueError("The terminal observation must be last")
        if line["kind"] == "policy_input" and initial_id is None:
            initial_id = manifest_identifier(line["frame"]["public_input"])
        if line["kind"] == "policy_choice" and line["receipt"]["delivery_domain"] == "native":
            deliveries += 1
        if line["kind"] == "final_observation":
            final = line["frame"]
    if (
        final is None
        or final["terminal"] is not True
        or final["ending"]["victory"] is not won
        or initial_id != row["initial_public_input_id"]
        or initial_id != episode["initial_public_input_id"]
        or deliveries != row["verified_native_deliveries"]
        or deliveries != episode["actual_deliveries_independently_verified"]
        or deliveries != episode["policy_decisions"]
        or any(row[k] != value for k, value in diagnostics(trace, won).items())
    ):
        raise ValueError(f"The public trace disagrees with its seal: {task['key']}")


def arm_progress(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    for player in (2, 3):
        for arm in ("original", "fitted"):
            own = [r for r in rows if r["player"] == player and r["arm"] == arm]
            route = Counter[str]()
            shop = Counter[str]()
            for r in own:
                route.update(r["map_destinations"])
                shop.update(r["shop_actions"])
            results.append(
                {
                    "player": player,
                    "arm": arm,
                    "games": len(own),
                    "maximum_act": max(r["maximum_act"] for r in own),
                    "act_1_boss_reached": sum(
                        any(b["act"] == 1 for b in r["bosses_reached"]) for r in own
                    ),
                    "act_1_cleared": sum(r["completed_acts"] >= 1 for r in own),
                    "mean_farthest_floor": fmean(r["maximum_floor"] for r in own),
                    "median_farthest_floor": median(r["maximum_floor"] for r in own),
                    "map_destinations": dict(route),
                    "shop_actions": dict(shop),
                    "shop_visits": sum(len(r["shop_visits"]) for r in own),
                }
            )
    return results


def recover(root: Path, checkout: Path) -> dict[str, Any]:
    if (
        checkout == root
        or not Path(panel.__file__).is_relative_to(checkout / "src")
        or git(checkout, "rev-parse", "HEAD").decode().strip() != BEFORE
        or git(checkout, "status", "--porcelain").strip()
        or git(root, "diff", "--name-only", BEFORE, AFTER).decode().splitlines() != [WORKFLOW]
        or (root / WORKFLOW).read_bytes() != git(root, "show", f"{AFTER}:{WORKFLOW}")
    ):
        raise ValueError("Use the detached execution checkout and exact recorded CI-only change")
    failure = identified(root / RESOURCE)
    if (
        failure["report_id"] != FAILED_REPORT_ID
        or failure["status"] != "failed"
        or failure["exit_code"] != 1
        or failure["cap"] is not None
        or _sha_file(root / RESOURCE) != _sha_file(checkout / RESOURCE)
    ):
        raise ValueError("The failed owner receipt does not match the saved incident")

    cfg = panel.declaration(checkout)
    ctx = panel.qualified_inputs(checkout, cfg, control=False)
    frozen = freeze(checkout, ctx)
    protection = json.loads(verified(checkout, ctx["config"]["protection"]).read_text())
    old_ci, new_ci = _sha_file(checkout / WORKFLOW), _sha_file(root / WORKFLOW)
    if old_ci != protection[WORKFLOW] or old_ci == new_ci:
        raise ValueError("The only approved difference must be the exact CI workflow bytes")
    # Confirm the live protected tree also agrees with every historical pin outside CI.
    for name, expected in protection.items():
        if name != WORKFLOW:
            verified(root, {"path": name, "sha256": expected})

    store = ChunkJournal(checkout, cfg)
    original = ChunkJournal(root, cfg)
    planned = panel.tasks(panel.WORLDS)
    keys = {task["key"] for task in planned}
    for journal in (store, original):
        if (
            json.loads((journal.workspace / "config-at-launch.json").read_text()) != cfg
            or {p.name for p in (journal.workspace / "chunks").iterdir()} != keys
        ):
            raise ValueError("Require the exact saved panel with all declared cells")
    games = {}
    seals = {}
    for task in planned:
        key = task["key"]
        saved = store.completed(key, task)
        live = original.completed(key, task)
        if saved is None or saved != live:
            raise ValueError(f"Missing or mismatched saved cell: {key}")
        row = saved["result"]
        audit_cell(store.path(key), task, row, ctx)
        games[task["world"], task["player"], task["arm"]] = row
        seals[key] = saved["report_id"]
    for world in panel.WORLDS:
        panel.same_start([row for (seed, _, _), row in games.items() if seed == world])

    if freeze(checkout, ctx) != frozen or _sha_file(root / WORKFLOW) != new_ci:
        raise ValueError("The verified inputs changed during recovery")
    rows = list(games.values())
    return write(
        root / OUTPUT,
        {
            "schema_version": "native-a8-paired-saved-recovery-v1",
            "status": "saved_paired_development_comparison_verified",
            "config_id": store.config_id,
            "environment_id": ctx["environment"]["manifest_id"],
            "fitting_evidence_id": ctx["fitting_evidence"]["report_id"],
            "objective": cfg["objective"],
            "failed_owner_attempt": {
                "path": RESOURCE,
                "sha256": _sha_file(root / RESOURCE),
                "report_id": failure["report_id"],
                "exit_code": failure["exit_code"],
                "original_final_guard_passed": False,
                "original_final_shared_profile_comparison_reconstructed": False,
            },
            "workflow_delta": {
                "path": WORKFLOW,
                "execution_commit": BEFORE,
                "ci_commit": AFTER,
                "execution_sha256": old_ci,
                "current_sha256": new_ci,
                "historical_guard_ran_on_exact_checkout": True,
            },
            "audit_source_sha256": _sha_file(Path(__file__)),
            "frozen_checks": frozen,
            "worlds": panel.WORLDS,
            "sealed_terminal_games": len(rows),
            "verified_native_deliveries": sum(row["verified_native_deliveries"] for row in rows),
            "summary": summarize(panel.WORLDS, games),
            "arm_progress": arm_progress(rows),
            "seals": seals,
            "cells": rows,
            "new_game_launches": 0,
            "optimizer_updates": 0,
            "final_test_worlds_used": False,
            "official_live_qualification_granted": False,
            "promotion_allowed": False,
            "automatic_follow_up": False,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    result = recover(Path.cwd().resolve(), args.checkout.resolve())
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "sealed_terminal_games",
                    "verified_native_deliveries",
                    "new_game_launches",
                    "optimizer_updates",
                    "report_id",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
