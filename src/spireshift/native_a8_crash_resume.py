"""Resume only the untouched tail of the ordinary-lethal panel on the exact Node binary."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import time
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games
from spireshift.native_a8_ordinary_session import ARMS, load, require_short, saved_check
from spireshift.native_a8_rescue_inputs import RECIPE as RESCUE_RECIPE
from spireshift.native_a8_rescue_inputs import SESSION_LIMITS
from spireshift.native_a8_rescue_session import NO_UPDATES
from spireshift.native_a8_reward_exit_recovery import chunk_evidence_id, previous_attempt
from spireshift.native_a8_reward_exit_session import require_control, run
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS, execution_runtime
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RECIPE = "configs/native-curriculum/sts2-v0.111.0-a8-act1-ordinary-lethal-crash-resume-v1.json"
MODULE = "spireshift.native_a8_crash_resume"


def relocated_context(
    root: Path, original: dict[str, Any], ref: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    rescue = json.loads((root / RESCUE_RECIPE).read_text())
    parent = json.loads(verified(root, rescue["parent_recipe"]).read_text())
    runtime = parent["execution_runtime"]
    node = verified(root, ref)
    if ref["sha256"] != runtime["node_executable_sha256"] or not os.access(node, os.X_OK):
        raise ValueError("The project-local Node must be executable and match the original pin")

    def check(configured_path: str) -> dict[str, Any]:
        if configured_path != parent["node"]:
            raise ValueError("Unexpected Node path in the historical runtime check")
        return execution_runtime(str(node))

    # The historical loader's bytes and manifests are pinned. Change only the
    # path used by its runtime check while loading this one private context.
    with patch("spireshift.native_a8_rescue_inputs.execution_runtime", check):
        ctx = load(root, original)
    ctx["node"] = str(node)
    return ctx, runtime


def check_crash_boundary(
    history: ChunkJournal, audit: dict[str, Any], worlds: list[dict[str, Any]]
) -> None:
    interrupted = audit["interrupted_world"]
    suffix = audit["unstarted_worlds"]
    sealed = audit["continuation_seals"]
    head = worlds[: len(sealed)]
    if (
        audit["status"] != "saved_crash_boundary_verified"
        or audit["original_continuation_config_id"] != history.config_id
        or json.loads((history.workspace / "config-at-launch.json").read_text()) != history.recipe
        or [*head, interrupted["case"], *suffix] != worlds
        or set(sealed) != {case["key"] for case in head}
        or interrupted["pair_seal_exists"] is not False
    ):
        raise ValueError("The saved crash boundary differs from the original world order")
    for case in head:
        key = case["key"]
        seal = history.completed(key, case)
        if seal is None or seal["report_id"] != sealed[key]["seal_id"]:
            raise ValueError(f"Previously sealed world changed: {key}")
    target = history.path(interrupted["case"]["key"])
    if (
        not (target / "active.json").is_file()
        or (target / "done.json").exists()
        or chunk_evidence_id(target) != interrupted["source_chunk_id"]
        or any(history.path(case["key"]).exists() for case in suffix)
    ):
        raise ValueError("Interrupted or previously unstarted worlds changed")


def execute(
    root: Path, cfg: dict[str, Any], attempt_number: int | None, deadline: float
) -> dict[str, Any]:
    check_sources(root, cfg["implementation"])
    predecessor = json.loads(verified(root, cfg["continuation_recipe"]).read_text())
    check_sources(root, predecessor["implementation"])
    audit = identified(verified(root, cfg["crash_audit"]))
    original = json.loads(verified(root, predecessor["previous_recipe"]).read_text())
    old, history = ChunkJournal(root, original), ChunkJournal(root, predecessor)
    suffix = audit["unstarted_worlds"]
    pin = audit["post_restart_refusal"]
    if (
        [case["key"] for case in suffix] != cfg["launch_worlds"]
        or cfg["node"] != {"path": pin["matching_local_copy"], "sha256": pin["expected"]}
        or cfg["workspace"] in {old.recipe["workspace"], history.recipe["workspace"]}
    ):
        raise ValueError(
            "Require the audited Node and declared untouched worlds in a new workspace"
        )
    ctx, runtime = relocated_context(root, original, cfg["node"])
    require_short(root, ctx, saved_check(root, ctx))
    ctx["reward_exit_execution_id"] = history.config_id

    with ExitStack() as locks:
        for store in (old, history):
            handle = locks.enter_context((store.workspace / "session.lock").open("rb"))
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        attempt, _, world7, remaining = previous_attempt(root, ctx, predecessor, old)
        short, recovered = require_control(
            root, ctx, predecessor, {"source": world7, "attempt": attempt["report_id"]}
        )
        check_crash_boundary(history, audit, remaining)
        if (
            short["report_id"] != audit["short_check_id"]
            or short["frozen_checks"] != audit["frozen_checks"]
        ):
            raise ValueError("The frozen checks differ from the saved crash audit")

        launch = {
            "crash_audit_id": audit["report_id"],
            "node_sha256": cfg["node"]["sha256"],
            "worlds": cfg["launch_worlds"],
            "saved_continuation_seals": audit["continuation_seals"],
            "interrupted_world": audit["interrupted_world"],
        }
        if attempt_number is None:
            return {"status": "post_crash_continuation_ready", **launch, **NO_UPDATES}
        if _running_games():
            raise ValueError("Close STS2 and wait for any other native worker")

        runner = {
            **predecessor,
            "workspace": cfg["workspace"],
            "crash_resume": cfg,
            "implementation": {
                **predecessor["implementation"],
                **cfg["implementation"],
                cfg["node"]["path"]: cfg["node"]["sha256"],
            },
        }
        store = ChunkJournal(root, runner)
        ctx["reward_exit_execution_id"] = store.config_id
        result = run(
            root, ctx, runner, old, attempt, suffix, short, recovered, attempt_number, deadline
        )
        check_crash_boundary(history, audit, remaining)
        if execution_runtime(ctx["node"]) != runtime:
            raise ValueError("The exact numerical runtime changed during the continuation")
        counts = {}
        for arm in ARMS:
            prior = Counter(row["outcomes"][arm] for row in audit["continuation_seals"].values())
            counts[arm] = {
                key: count + prior[key]
                for key, count in result["sealed_pair_outcomes"][arm].items()
            }
        return write(
            store.workspace / f"post-crash-{attempt_number}.json",
            {
                "schema_version": "native-a8-ordinary-lethal-crash-resume-v1",
                "status": result["status"],
                "full_panel_complete": False,
                "sealed_pair_outcomes": counts,
                "continuation": result,
                **launch,
                **NO_UPDATES,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight", action="store_true")
    modes.add_argument("--attempt", type=int)
    args = parser.parse_args()
    root, started = Path.cwd(), time.monotonic()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread crash-resume launcher")
        cfg = json.loads((root / RECIPE).read_text())
        if args.preflight or args.attempt is not None:
            if args.attempt is not None and args.attempt < 1:
                raise ValueError("Use the resource-tracked crash-resume launcher")
            result = execute(root, cfg, args.attempt, started + SESSION_LIMITS["wall_seconds"] - 25)
            print(json.dumps(result))
            return (
                0
                if result["status"]
                in {
                    "post_crash_continuation_ready",
                    "ordinary_lethal_continuation_complete",
                }
                else 2
            )
        attempt = time.time_ns()
        print("Close STS2. Four untouched A8 worlds, 13–16. Zero optimizer updates.", flush=True)
        tracked = run_tracked_command(
            command=["uv", "run", "--no-sync", "python", "-m", MODULE, "--attempt", str(attempt)],
            experiment_kind=ExperimentKind.OTHER,
            report_path=_private_path(root, f"{cfg['resource_prefix']}-{attempt}.json"),
            artifact_roots=[_private_path(root, cfg["workspace"])],
            working_directory=root,
            limits=ResourceLimits(**SESSION_LIMITS),
        )
        print(json.dumps(tracked.report, indent=2))
        return 0 if tracked.exit_code == 0 and tracked.status == "completed" else 2
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(
            json.dumps({"status": "stopped_preserving_evidence", "error": str(exc), **NO_UPDATES})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
