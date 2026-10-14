"""Saved-only public choice/delivery audit for a cleanly closed native worker."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.engine_run import _verify_saved_observation


def audit_worker_experience(workspace: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    def records(name: str) -> list[dict[str, Any]]:
        with gzip.open(workspace / name, "rt") as stream:
            return [json.loads(line) for line in stream]

    closed = json.loads((workspace / "closed.json").read_text())
    if closed.get("clean_exit") is not True or (workspace / "active.json").exists():
        raise ValueError("Native experience worker did not finish cleanly")
    raw = records("private-transcript.jsonl.gz")
    observations = records("public-observations.jsonl.gz")
    receipts = records("public-receipts.jsonl.gz")
    allowed = {
        "runtime_identity",
        "run_identity",
        "process_metrics",
        "start_run",
        "reset_run",
        "get_map",
        "observe",
        "action",
        "quit",
    }
    starts = [r["request"] for r in raw if r["request"]["cmd"] in {"start_run", "reset_run"}]
    if (
        len(starts) != len(cases)
        or closed["episodes"] != len(cases)
        or any(row["request"]["cmd"] not in allowed for row in raw)
    ):
        raise ValueError("Native experience contains an unbound start or fixture mutation")
    decisions = 0
    for episode, (case, start) in enumerate(zip(cases, starts, strict=True), 1):
        if (
            case["status"] != "terminal"
            or case["privileged_fixture"]
            or case["recovered"]
            or start.get("seed") != case["seed"]
            or start.get("ascension") != 8
            or start.get("character") != "Ironclad"
            or start.get("content_policy") != "native_benchmark_full_v1"
        ):
            raise ValueError("Native experience seed, scope or ending differs")
        rows = [r for r in observations if r["episode"] == episode]
        actions = [r for r in receipts if r["episode"] == episode]
        if len(rows) != len(case["decisions"]) + 1 or len(actions) != len(case["decisions"]):
            raise ValueError("Native experience observation/delivery denominator differs")
        runtime = rows[0]["snapshot"]["session"]["runtime_instance_id"]
        for row in rows:
            _verify_saved_observation(row, runtime)
        for index, (decision, delivery, current, successor) in enumerate(
            zip(case["decisions"], actions, rows[:-1], rows[1:], strict=True)
        ):
            action_index = decision["choice"]["action_index"]
            if (
                type(action_index) is not int
                or action_index < 0
                or action_index >= len(current["snapshot"]["bound_actions"]["actions"])
            ):
                raise ValueError("Native experience action is outside its complete current menu")
            action = current["snapshot"]["bound_actions"]["actions"][action_index]
            if (
                current["index"] != index
                or delivery["index"] != index
                or current["model_input"] != decision["public_input"]
                or current["public_key"] != decision["public_key"]
                or delivery["snapshot_id"] != current["snapshot"]["snapshot_id"]
                or delivery["action"] != action
                or delivery["delivery"] != "delivered"
                or delivery["successor_snapshot_id"] != successor["snapshot"]["snapshot_id"]
            ):
                raise ValueError(
                    "Neural input/choice does not match its saved public delivery chain"
                )
            decisions += 1
        end = case["private_final_identity"]
        if (
            not rows[-1]["facts"]["terminal"]
            or rows[-1]["facts"]["victory"] != case["victory"]
            or case["native_ending_evidence_agrees"] is not True
            or not any(r["request"]["cmd"] == "run_identity" and r["response"] == end for r in raw)
        ):
            raise ValueError("Native experience ending evidence does not reconstruct")
    body = {
        "schema_version": "actual-engine-saved-experience-audit-v1",
        "valid": True,
        "games": len(cases),
        "decisions": decisions,
        "games_replayed": 0,
        "source_sha256": {
            name: _sha_file(workspace / name)
            for name in (
                "private-transcript.jsonl.gz",
                "public-observations.jsonl.gz",
                "public-receipts.jsonl.gz",
                "closed.json",
            )
        },
        "claim_scope": "saved_public_menu_input_choice_delivery_and_native_ending_chain",
    }
    return {**body, "report_id": manifest_identifier(body)}
