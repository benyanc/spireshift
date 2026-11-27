"""Qualify shop and reward child handoffs on the frozen A8 native worker."""

from __future__ import annotations

import argparse
import fcntl
import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _private_path, _running_games, _shared_snapshot
from spireshift.engine_qualification import _sha_file
from spireshift.engine_worker import worker_helpers
from spireshift.native_a8_boss_checks import SHARED_PROFILE
from spireshift.native_a8_feedback_session import inputs
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_contract import verified
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_flow_inputs_v12 import canonical_seed
from spireshift.native_lifecycle_suite import load_plan as parent_plan
from spireshift.native_lifecycle_worker import build_adapter
from spireshift.native_selector_lifecycle_cases import reward_case, shop_case
from spireshift.native_selector_lifecycle_worker import SCRIPT
from spireshift.native_systematic_selectors_v2 import CONVERTER
from spireshift.native_win4_game import write
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

MODULE = "spireshift.native_selector_lifecycle_suite"
RECIPE = "configs/native-compatibility/sts2-v0.111.0-a8-selector-lifecycles-v1.json"
SCHEMA = "native-a8-selector-lifecycles-v1"
LIMITS = {
    "wall_seconds": 240,
    "cpu_seconds": 600,
    "storage_bytes": 1_000_000_000,
    "resident_memory_bytes": 4_000_000_000,
}


def cases() -> list[dict[str, Any]]:
    return [
        {
            "key": "removal-cancel-confirm",
            "kind": "removal",
            "count": 13,
            "indices": [12],
            "discard_first": False,
        },
        {"key": "reward-card-take", "kind": "reward_take", "discard_first": False},
        {
            "key": "shop-direct",
            "kind": "kifuda",
            "count": 3,
            "indices": [2, 0],
            "discard_first": True,
        },
        {
            "key": "shop-ordered",
            "kind": "kifuda",
            "count": 13,
            "indices": [12, 0],
            "discard_first": False,
        },
        {
            "key": "shop-ordered-empty",
            "kind": "kifuda",
            "count": 13,
            "indices": [],
            "discard_first": True,
        },
        {"key": "reward-card-skip", "kind": "reward_skip", "discard_first": True},
    ]


def implementation(root: Path) -> dict[str, str]:
    paths = {
        "scripts/check-selector-lifecycles-v1.sh",
        *(
            f"src/spireshift/native_selector_lifecycle_{name}.py"
            for name in ("checks", "trace", "worker", "cases", "suite")
        ),
    }
    for script in (SCRIPT, CONVERTER):
        paths.update(f"scripts/{name}" for name in worker_helpers(root, script))
    return {name: _sha_file(root / name) for name in sorted(paths)}


def load(root: Path) -> dict[str, Any]:
    cfg: dict[str, Any] = json.loads((root / RECIPE).read_text())
    expected = [{**case, "seed": f"SP1RESH1FTA8SLC{i:03}"} for i, case in enumerate(cases(), 1)]
    if (
        cfg["schema_version"] != SCHEMA
        or cfg["cases"] != expected
        or cfg["limits"] != LIMITS
        or cfg["implementation"] != implementation(root)
        or any(canonical_seed(case["seed"]) != case["seed"] for case in cfg["cases"])
    ):
        raise ValueError("The declared selector lifecycle suite differs from its execution inputs")
    return cfg


def run(root: Path, cfg: dict[str, Any], output: Path, mode: str) -> dict[str, Any]:
    started = time.monotonic()
    deadline = started + cfg["limits"]["wall_seconds"] - 15
    _, ctx, runtime, *_ = inputs(root)
    previous_cfg = parent_plan(root)
    previous = identified(verified(root, cfg["parent_result"]))
    if (
        previous["config_id"] != manifest_identifier(previous_cfg)
        or previous["status"] != "verified"
        or previous["mode"] != "full"
        or not previous["native_stampede_branches_verified"]
    ):
        raise ValueError("Require the verified complete shared lifecycle suite")
    before = frozen(root, ctx)
    profile = Path.home() / SHARED_PROFILE
    shared = _shared_snapshot(profile) if not _running_games() else None
    outcomes: list[dict[str, Any]] = []
    stopped = None
    selected = cfg["cases"][:2] if mode == "short" else cfg["cases"]
    adapter = build_adapter(
        root, ctx["native"]["candidate"], output / "adapter", previous_cfg["compiler"]
    )
    if adapter["sha256"] != previous["adapter"]["sha256"]:
        raise ValueError("The cleanup adapter differs from its qualified build")
    ctx = {**ctx, "lifecycle_adapter": adapter, "execution_id": manifest_identifier(cfg)}
    for case in selected:
        directory = output / case["key"]
        directory.mkdir()
        try:
            if time.monotonic() + 30 >= deadline:
                raise TimeoutError("Insufficient time for a complete selector control")
            runner = shop_case if case["kind"] in {"removal", "kifuda"} else reward_case
            result = runner(ctx, case, directory, deadline)
            evidence = {
                str(path.relative_to(root)): _sha_file(path)
                for path in sorted(directory.rglob("*"))
                if path.is_file()
            }
            row = write(
                directory / "report.json",
                {
                    "status": "verified",
                    "case": case,
                    "optimizer_updates": 0,
                    "sources": evidence,
                    **result,
                },
            )
            outcomes.append(row)
            print(f"{case['key']} verified", flush=True)
        except (ValueError, KeyError, OSError, TimeoutError, StopIteration) as error:
            stopped = {"case": case["key"], "error": f"{type(error).__name__}: {error}"}
            write(directory / "failure.json", stopped)
            break
        check_sources(root, cfg["implementation"])
        if frozen(root, ctx) != before:
            raise ValueError("Frozen build, runtime, checkpoints or Adam changed")
    if shared is not None and _shared_snapshot(profile) != shared:
        raise ValueError("Personal save profile changed during the isolated controls")
    check_sources(root, cfg["implementation"])
    if frozen(root, ctx) != before:
        raise ValueError("Frozen inputs changed after the lifecycle controls")
    return write(
        output / "report.json",
        {
            "schema_version": SCHEMA,
            "status": "verified" if stopped is None else "blocked_preserving_evidence",
            "config_id": manifest_identifier(cfg),
            "mode": mode,
            "parent_result_id": previous["report_id"],
            "environment_id": ctx["environment_id"],
            "runtime": runtime,
            "game_assembly_sha256": ctx["qualification"].target["assembly_sha256"],
            "frozen_checks": before,
            "personal_profile_before_after_checked": shared is not None,
            "adapter": adapter,
            "cases": outcomes,
            "native_deliveries": sum(row["native_deliveries"] for row in outcomes),
            "local_answer_factors": sum(row["local_answer_factors"] for row in outcomes),
            "coverage_obligations_exercised": [
                "selector-parent-return",
                "selector-zero-order-duplicates",
                "potions-queued-all-owners",
                "shop-belt-remove-restock",
                "reward-belt-child",
            ],
            "remaining_inventory_rows": previous["remaining_inventory_rows"],
            "official_live_qualification_granted": False,
            "training_allowed": False,
            "optimizer_updates": 0,
            "wall_seconds": time.monotonic() - started,
            "stop": stopped,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("short", "full"), nargs="?", default="short")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    cfg = load(root)
    workspace = _private_path(root, cfg["workspace"])
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = args.execute or time.time_ns()
    output = workspace / f"{args.mode}-{attempt}"
    if args.mode == "full" and args.execute is None:
        tracked = run_tracked_command(
            command=[
                "uv",
                "run",
                "--no-sync",
                "python",
                "-B",
                "-m",
                MODULE,
                "full",
                "--execute",
                str(attempt),
            ],
            working_directory=root,
            experiment_kind=ExperimentKind.OTHER,
            report_path=workspace / f"resources-{attempt}.json",
            artifact_roots=[output],
            limits=ResourceLimits(**cfg["limits"]),
        )
        print(json.dumps(tracked.report))
        return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
    with (workspace / "session.lock").open("ab") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output.mkdir()
        result = run(root, cfg, output, args.mode)
    print(
        json.dumps(
            {
                "status": result["status"],
                "report": str(output / "report.json"),
                "report_id": result["report_id"],
                "cases": len(result["cases"]),
                "native_deliveries": result["native_deliveries"],
                "local_answer_factors": result["local_answer_factors"],
                "stop": result["stop"],
            }
        )
    )
    return 0 if result["status"] == "verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
