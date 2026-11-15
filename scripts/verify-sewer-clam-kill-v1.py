"""Replay the sealed Sewer Clam menu and prove the three-Strike fight win."""

from __future__ import annotations

import fcntl
import json
import time
from pathlib import Path

from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_rescue_game import TRACE
from spireshift.native_a8_tactical_episode import play
from spireshift.native_a8_tactical_session import RECIPE, boundary, context, frozen, require_control
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_win4_game import write

ATTEMPT = 1794080276572507000
DIAGNOSTIC = "sha256:1883933f4bfd5bc99d643ef5b8dff74246302283273d0523f64b11b3e4a9287f"
WORKSPACE = "artifacts/native-a8-act1-boss/sewer-clam-control-v1"
CASE = {
    "key": "sewer-clam-three-strikes",
    "source_world": "diagnostic-004",
    "seed": "SP1RESH1FTA8TPD004",
    "player": 3,
    "floor": 7,
    "line": 155,
    "input_digest": "9f2b5ce16eed3c9039b244b0a344cdcc9882263d1517ba7be09c88ac785ac550",
    "enemy": "SEWER_CLAM",
    "encounter": "normal",
}


def main() -> None:
    root = Path.cwd()
    deadline = time.monotonic() + 125
    parent = json.loads((root / RECIPE).read_text())
    ctx = context(root, parent)
    short = require_control(root, ctx, diagnostic=True)
    previous = ChunkJournal(
        root,
        {
            **parent,
            "workspace": parent["diagnostic_workspace"],
            "worlds": parent["diagnostic_worlds"],
        },
    )
    world = next(w for w in parent["diagnostic_worlds"] if w["key"] == CASE["source_world"])
    with (previous.workspace / "session.lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
        report = identified(previous.workspace / f"attempt-{ATTEMPT}.json")
        launch = identified(previous.workspace / f"launch-{ATTEMPT}.json")
        resources = identified(root / f"{parent['diagnostic_resource_prefix']}-{ATTEMPT}.json")
        seal = previous.completed(world["key"], world)
        before = frozen(root, ctx)
        if (
            report["report_id"] != DIAGNOSTIC
            or report["status"] != "tactical_diagnostic_complete"
            or report["config_id"] != previous.config_id
            or report["execution_id"] != ctx["tactical_execution_id"]
            or report["launch_id"] != launch["report_id"]
            or launch["short_report_id"] != short["report_id"]
            or launch["frozen_checks"] != report["frozen_checks"]
            or report["frozen_checks"] != before
            or resources["exit_code"] != 0
            or resources["cap"] is not None
            or seal is None
            or seal["result"]["outcomes"]["boss"] != "act1_loss"
            or world["seed"] != CASE["seed"]
        ):
            raise ValueError("Sewer Clam requires the exact completed tactical diagnostic loss")
        trace = previous.path(world["key"]) / "boss" / TRACE
        trace_name = trace.relative_to(root).as_posix()
        store = ChunkJournal(
            root,
            {
                "workspace": WORKSPACE,
                "objective": parent["objective"],
                "parent_execution_id": ctx["tactical_execution_id"],
                "source_report_id": report["report_id"],
                "source_seal_id": seal["report_id"],
                "case": CASE,
                "script_sha256": _sha_file(Path(__file__)),
            },
        )
        with store.lock():
            if _running_games():
                raise ValueError("Close STS2 and wait for any other native worker")
            profile = _shared_snapshot(Path.home() / SHARED_PROFILE)
            result = play(ctx, CASE, store.begin(CASE["key"], CASE), deadline, trace=trace)
            branch = result["diagnostic"]
            if (
                result["outcome"] != "fight_win"
                or result["cap"]
                or branch["exact_prefix_choices"] != 77
                or branch["root"]["saved_action"] != "Play Bash on Sewer Clam"
                or [s["action"] for s in branch["steps"]] != ["Play Strike on Sewer Clam"] * 3
                or [s["enemy_hp"] for s in branch["steps"]] != [38, 29, 14]
                or any(s["hp"] != 16 or s["round"] != 5 for s in branch["steps"])
            ):
                raise ValueError(
                    "Sewer Clam did not finish with the exact native three-Strike line"
                )
            boundary(root, ctx, before, profile)
            proof = store.commit(
                CASE["key"], CASE, result, {trace_name: seal["sources"][trace_name]}
            )
            record = write(
                store.workspace / "report.json",
                {
                    "status": "sewer_clam_three_strike_kill_verified",
                    "config_id": store.config_id,
                    "source_seal_id": seal["report_id"],
                    "seal_id": proof["report_id"],
                    "source_report_id": report["report_id"],
                    "result_id": result["report_id"],
                    "prefix_choices": branch["exact_prefix_choices"],
                    "verified_native_deliveries": result["verified_native_deliveries"],
                    "reward_hp": result["final_hp"],
                    "frozen_checks": before,
                    "shared_profile_unchanged": True,
                    "optimizer_updates": 0,
                },
            )
    print(json.dumps(record))


if __name__ == "__main__":
    main()
