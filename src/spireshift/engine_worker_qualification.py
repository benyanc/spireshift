"""Finite natural-run and parallel/reset control. No optimizer or automatic next stage."""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_native import (
    _private_path,
    _require_native_launch_support,
    _running_games,
    _shared_snapshot,
)
from spireshift.engine_qualification import (
    EngineQualificationConfig,
    _inventory,
    _sha_file,
    verify_game_archive,
)
from spireshift.engine_run import _run_inputs
from spireshift.engine_worker import (
    ISOLATION_ID,
    LIVENESS_POLICY,
    WORKER_SCRIPT,
    EngineWorker,
    worker_helpers,
)
from spireshift.full_run_experience import atomic_json

WORKER_IMPLEMENTATION = ("engine_worker.py", "engine_worker_qualification.py", "engine_run.py")


def worker_implementation(root: Path) -> dict[str, str]:
    return {name: _sha_file(root / "src/spireshift" / name) for name in WORKER_IMPLEMENTATION}


def worker_script(document: dict[str, Any]) -> str:
    script = document.get("worker_script", WORKER_SCRIPT)
    if script not in {WORKER_SCRIPT, "engine-native-worker-v7.mjs", "engine-native-worker-v8.mjs"}:
        raise ValueError("Unqualified production worker entry point")
    return str(script)


def load_worker_config(path: Path, q: EngineQualificationConfig) -> dict[str, Any]:
    d = json.loads(path.read_text())
    if (
        d.get("schema_version") != "actual-engine-worker-qualification-config-v1"
        or d.get("qualification_config_id") != q.config_id
        or d.get("isolation_id") != ISOLATION_ID
        or d.get("training_allowed") is not False
        or d.get("helpers_sha256") != worker_helpers(q.root, worker_script(d))
        or d.get("python_sha256") != worker_implementation(q.root)
        or d.get("serial_seeds") != [f"SP1RESH1FTA8D1AG{i:03}" for i in range(1, 9)]
        or d.get("parallel_seeds") != d["serial_seeds"][:2]
        or d.get("repeats") != 2
        or d.get("maximum_decisions") != 4096
        or d.get("episode_wall_seconds") != 45
        or d.get("liveness_policy") != LIVENESS_POLICY
    ):
        raise ValueError("Worker qualification must bind its finite A8 panel and current helpers")
    recipe = json.loads((q.root / d["base_run_recipe"]).read_text())
    if manifest_identifier(recipe) != d["base_run_recipe_id"]:
        raise ValueError("Worker qualification base input identity changed")
    _private_path(q.root, d["workspace"])
    return dict(d)


def immutable_checks(q: EngineQualificationConfig, inputs: dict[str, Any]) -> dict[str, bool]:
    return {
        "candidate_unchanged": _inventory(inputs["candidate"]) == inputs["candidate_before"],
        "runtime_unchanged": _inventory(inputs["runtime"]) == inputs["runtime_before"],
        "sdk_unchanged": _inventory(Path(inputs["projection"]["node_modules"]))
        == inputs["sdk_before"],
        "frozen_archive_unchanged": verify_game_archive(q, inputs["archive"])["valid"],
    }


def _episode_digest(case: dict[str, Any]) -> str:
    # Candidate ordering can differ by transport binding. Compare the semantic
    # input menu as a set, and the chosen public candidate, never bound_action_id.
    trace = []
    for row in case["decisions"]:
        public = row["public_input"]
        trace.append(
            {
                "context": public["context"],
                "candidates": sorted(public["candidates"], key=manifest_identifier),
                "chosen": public["candidates"][row["choice"]["action_index"]],
            }
        )
    return manifest_identifier(
        {"trace": trace, "terminal": case["terminal_public_key"], "victory": case["victory"]}
    )


def run_worker_qualification(
    q: EngineQualificationConfig, path: Path, *, node: Path
) -> dict[str, Any]:
    _require_native_launch_support()
    if _running_games() or not node.is_file():
        raise ValueError("Close the game and select the local Node runtime")
    d = load_worker_config(path, q)
    inputs = _run_inputs(q, q.root / d["base_run_recipe"])
    output = _private_path(q.root, d["workspace"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "config.json", d)
    launched_source = output / "python-at-launch"
    launched_source.mkdir()
    for name in WORKER_IMPLEMENTATION:
        (launched_source / name).write_bytes((q.root / "src/spireshift" / name).read_bytes())
    shared = Path.home() / "Library/Application Support/SlayTheSpire2"
    shared_before = _shared_snapshot(shared)
    cases: list[dict[str, Any]] = []
    workers: list[dict[str, Any]] = []
    started = time.monotonic()
    serial_wall: float | None = None
    parallel_wall: float | None = None

    def batch(name: str, seeds: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        records: list[dict[str, Any]] = []
        worker = EngineWorker(
            q, inputs, output / name, node, d["helpers_sha256"], script=worker_script(d)
        )
        try:
            for index, seed in enumerate(seeds):
                case = worker.episode(
                    seed,
                    maximum_decisions=d["maximum_decisions"],
                    wall_seconds=d["episode_wall_seconds"],
                    cpu_seconds=inputs["objective"]["whole_run_budget"],
                )
                case["public_trace_id"] = (
                    _episode_digest(case) if case["status"] == "terminal" else None
                )
                atomic_json(worker.workspace / f"episode-{index:03}.json", case)
                records.append(case)
                if case["status"] != "terminal":
                    return records, {
                        "worker": name,
                        "clean_exit": False,
                        "error": case.get("error"),
                    }
            closed = worker.close()
            return records, {"worker": name, **worker.identity, **closed}
        except (ValueError, TimeoutError, OSError, subprocess.TimeoutExpired) as exc:
            return records, {"worker": name, "clean_exit": False, "error": str(exc)}
        finally:
            worker.stop()

    error: str | None = None
    try:
        serial_started = time.monotonic()
        serial, state = batch("serial", d["serial_seeds"])
        cases.extend(serial)
        workers.append(state)
        serial_wall = time.monotonic() - serial_started
        if len(serial) != 8 or not state["clean_exit"]:
            raise ValueError("Serial worker panel failed; parallel stage was not started")
        parallel_started = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(batch, f"parallel-{i}", [seed] * d["repeats"])
                for i, seed in enumerate(d["parallel_seeds"])
            ]
            for future in futures:
                records, state = future.result()
                cases.extend(records)
                workers.append(state)
        parallel_wall = time.monotonic() - parallel_started
        if len(cases) != 12 or any(not w["clean_exit"] for w in workers):
            raise ValueError("Parallel worker panel failed")
        by_seed: dict[str, set[str | None]] = {}
        for case in cases:
            by_seed.setdefault(case["seed"], set()).add(case["public_trace_id"])
        if any(len(ids) != 1 or None in ids for ids in by_seed.values()):
            raise ValueError("Serial/parallel/reset semantic traces differ")
        if len({w["runtime_identity"]["process_id"] for w in workers}) != 3:
            raise ValueError("Workers shared a native process")
        # Exercise the exact sandbox on a sentinel: own profile is writable; a sibling
        # profile is neither readable nor writable. No account/frozen files are touched.
        sandbox = output / "serial/profile-isolation.sb"
        own = output / "serial/private-profile/isolation-sentinel"
        other = output / "parallel-0/private-profile/isolation-sentinel"
        other.write_text("sibling sentinel")
        for command, expected in (
            (["/usr/bin/touch", str(own)], 0),
            (["/usr/bin/touch", str(other)], 1),
            (["/bin/cat", str(other)], 1),
        ):
            check = subprocess.run(
                ["/usr/bin/sandbox-exec", "-f", str(sandbox), *command],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if (check.returncode == 0) != (expected == 0):
                raise ValueError("Worker sandbox isolation sentinel failed")
    except (ValueError, TimeoutError, OSError) as exc:
        error = str(exc)
    checks = immutable_checks(q, inputs)
    checks["account_profile_unchanged"] = _shared_snapshot(shared) == shared_before
    if not all(checks.values()):
        error = "Shared or frozen inputs changed"
    body = {
        "schema_version": "actual-engine-worker-qualification-v1",
        "config_id": manifest_identifier(d),
        "qualification_config_id": q.config_id,
        "input_config_id": inputs["recipe"]["input_config_id"],
        "build_report_id": inputs["inputs"]["build_report_id"],
        "objective": inputs["objective"],
        "isolation_id": ISOLATION_ID,
        "liveness_policy": d["liveness_policy"],
        "python_sha256": d["python_sha256"],
        "status": "worker_isolation_pass" if error is None else "worker_isolation_incomplete",
        "error": error,
        "planned_games": 12,
        "completed_games": sum(c["status"] == "terminal" for c in cases),
        "failed_games": sum(c["status"] != "terminal" for c in cases),
        "not_attempted_games": 12 - len(cases),
        "victories": sum(c["victory"] for c in cases),
        "decisions": sum(len(c["decisions"]) for c in cases),
        "workers": workers,
        "cases": [
            {
                k: v
                for k, v in c.items()
                if k not in {"decisions", "private_start_identity", "private_final_identity"}
            }
            for c in cases
        ],
        "checks": checks,
        "serial_wall_seconds": serial_wall,
        "parallel_wall_seconds": parallel_wall,
        "wall_seconds": time.monotonic() - started,
        "game_apps_created": 0,
        "training_allowed": False,
        "optimizer_steps": 0,
        "claim_scope": "finite_natural_A8_serial_parallel_process_profile_reset_control_only",
    }
    result = {**body, "report_id": manifest_identifier(body)}
    atomic_json(output / "summary.json", result)
    return result
