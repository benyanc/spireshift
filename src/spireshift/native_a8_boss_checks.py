"""Saved boss and potion regressions, then short native prefixes on a fresh world."""

from __future__ import annotations

import json
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_game import play
from spireshift.native_a8_boss_inputs import (
    CONTROL,
    CONTROL_ARMS,
    CONTROL_DELIVERIES,
    REGRESSION,
    freeze,
)
from spireshift.native_a8_boss_policy import intervention
from spireshift.native_a8_rescue_curriculum import first_change
from spireshift.native_a8_rescue_game import TRACE, decisions
from spireshift.native_compatibility_contract import verified
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_flow_verification_v12 import records
from spireshift.native_win4_game import write

SHARED_PROFILE = "Library/Application Support/SlayTheSpire2"
ANCHORS = {
    "collect-002": {
        107: ("Take Havoc+", "Skip", "boss_preparation"),
        503: ("Play Defend", "Play Breakthrough", "boss_turn"),
    },
    "collect-003": {635: ("Play Headbutt on Kin Follower", "Play Thunderclap+", "boss_turn")},
    "collect-004": {
        105: ("Take Second Wind+", "Take Rampage+", "boss_preparation"),
        383: (
            "Play Strike on Ceremonial Beast",
            "Play Twin Strike on Ceremonial Beast",
            "boss_turn",
        ),
    },
}


def saved_checks(root: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    store = ChunkJournal(root, ctx["config"])
    audit = ctx["prior_audit"]
    changes = []
    for key, anchors in ANCHORS.items():
        chunk = store.path(key)
        seal = identified(chunk / "done.json")
        if seal["report_id"] != audit["seals"][key]:
            raise ValueError("Saved boss menu has the wrong world seal")
        path = str((chunk / "teacher" / TRACE).relative_to(root))
        trace = verified(root, {"path": path, "sha256": seal["sources"][path]})
        count = 0
        for line, frame, delivered in decisions(trace):
            if line not in anchors or delivered is None:
                continue
            public = frame["public_input"]
            menu = public["candidates"]
            old = delivered["choice"]["action_index"]
            new, reason = intervention(public, list(range(len(menu))), old)
            old_label, new_label = menu[old]["label"], menu[new]["label"]
            if (old_label, new_label, reason) != anchors[line] or delivered["receipt"][
                "delivery_domain"
            ] != "native":
                raise ValueError("Saved boss or reward regression differs")
            changes.append(
                {
                    "world": key,
                    "line": line,
                    "survival_teacher": old_label,
                    "boss_teacher": new_label,
                    "reason": reason,
                }
            )
            count += 1
        if count != len(anchors):
            raise ValueError("Missing saved boss or reward regression")

    worker = store.path(audit["failure"]["case"]["key"]) / "fitted/worker"
    saved = deque(records(worker / "private-transcript.jsonl.gz"), maxlen=1).pop()
    shared = json.loads((worker / "identity.json").read_text())["shared_projection"]
    check = subprocess.run(
        [ctx["node"], str(root / "scripts" / REGRESSION)],
        input=json.dumps(
            {
                "projection": {
                    "shared_projection": shared,
                    "projection": ctx["native"]["projection"],
                },
                "state": saved["response"],
            }
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    belt = json.loads(check.stdout)
    if belt["repaired_strict_sdk_and_converter_pass"] is not True or belt["new_games"] != 0:
        raise ValueError("Generated card-choice belt regression did not pass")
    return {"same_menu_choice_checks": changes, "saved_potion_belt_regression": belt}


def compare_teachers(path: Path) -> dict[str, Any] | None:
    change = first_change(path / "survival" / TRACE, path / "boss" / TRACE)
    if change is None:
        return None
    return {
        "choice_ordinal_including_local_factors": change["choice_ordinal_including_local_factors"],
        "public_input_id": change["public_input_id"],
        "family": change["family"],
        "survival_action_index": change["fitted_action_index"],
        "boss_action_index": change["teacher_action_index"],
        "reason": change["reason"],
    }


def control(root: Path, ctx: dict[str, Any], deadline: float) -> dict[str, Any]:
    out = root / ctx["boss_config"]["control_workspace"]
    out.mkdir(parents=True, exist_ok=False)
    shared = Path.home() / SHARED_PROFILE
    before, profile = freeze(root, ctx), _shared_snapshot(shared)
    saved = saved_checks(root, ctx)
    episodes = {
        arm: play(ctx, CONTROL, arm, out / arm, deadline, choices=CONTROL_DELIVERIES)
        for arm in CONTROL_ARMS
    }
    if len({row["initial_public_input_id"] for row in episodes.values()}) != 1 or any(
        row["outcome"] != "capped"
        or row["cap"] != ["choices"]
        or row["native_terminal"]
        or row["verified_native_deliveries"] != CONTROL_DELIVERIES
        for row in episodes.values()
    ):
        raise ValueError("Require two exact short native prefixes on one disjoint start")
    change = compare_teachers(out)
    if freeze(root, ctx) != before or _shared_snapshot(shared) != profile or _running_games():
        raise ValueError("Frozen inputs, worker exit or shared profile differs after the control")
    return write(
        out / "report.json",
        {
            "schema_version": "native-a8-act1-boss-short-check-v1",
            "status": "act1_boss_short_check_verified",
            "config_id": ctx["boss_config_id"],
            "execution_id": ctx["execution_id"],
            "control_world": CONTROL["seed"],
            "saved": saved,
            "episodes": episodes,
            "first_different_teacher_action": change,
            "verified_deliveries": sum(
                row["verified_native_deliveries"] for row in episodes.values()
            ),
            "frozen_checks": before,
            "shared_profile_unchanged": True,
            "qualification_games": 0,
            "optimizer_updates": 0,
            "evidence": {
                str(file.relative_to(root)): _sha_file(file)
                for file in sorted(out.rglob("*"))
                if file.is_file() and not file.is_symlink()
            },
        },
    )
