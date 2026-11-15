"""Owner-run fixed learning curve; automatically continue safe session boundaries."""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.full_run_experience import atomic_json
from spireshift.native_optimizer_trial import load_trial, plan


def repository_files(root: Path) -> dict[str, str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return {
        n: _sha_file(root / n)
        for n in sorted({x.decode() for x in raw.split(b"\0") if x})
        if (root / n).is_file()
    }


def next_resource(root: Path, name: str) -> Path:
    n = 1
    while (root / f"artifacts/resources/{name}-{n}.json").exists() or (
        root / f"artifacts/resources/{name}-{n}.json"
    ).is_symlink():
        n += 1
    return root / f"artifacts/resources/{name}-{n}.json"


def ensure_checked(root: Path) -> None:
    sources = repository_files(root)
    folder = (
        root
        / "artifacts/validation/optimizer-learning-v1"
        / manifest_identifier(sources).split(":")[1]
    )
    receipt = folder / "passed.json"
    if receipt.exists():
        r = identified(receipt)
        check = identified(root / r["resource_path"])
        if (
            r["sources"] != sources
            or r["resource_id"] != check["report_id"]
            or check["status"] != "completed"
            or check["exit_code"] != 0
        ):
            raise ValueError("Saved repository check changed")
        print("Reusing complete repository checks for these exact files.", flush=True)
        return
    body: dict[str, Any] = {"sources": sources}
    source_path = folder / "sources.json"
    if source_path.exists():
        if identified(source_path)["sources"] != sources:
            raise ValueError("Preserve changed verification inputs")
    else:
        atomic_json(source_path, {**body, "report_id": manifest_identifier(body)})
    report = next_resource(root, "native-optimizer-repository-check-v1")
    print(
        "Running complete repository checks before training; expected about one minute.", flush=True
    )
    code = subprocess.call(
        [
            "uv",
            "run",
            "--no-sync",
            "spireshift",
            "resources",
            "run",
            "--kind",
            "other",
            "--report",
            str(report),
            "--artifact-root",
            str(folder),
            "--workers",
            "1",
            "--max-wall-seconds",
            "240",
            "--max-cpu-seconds",
            "600",
            "--max-storage-bytes",
            "1000000000",
            "--max-memory-bytes",
            "4000000000",
            "--",
            "uv",
            "run",
            "--no-sync",
            "spireshift",
            "check",
        ],
        cwd=root,
    )
    check = identified(report)
    if (
        code
        or check["status"] != "completed"
        or check["exit_code"] != 0
        or repository_files(root) != sources
    ):
        raise ValueError(
            "Full repository check did not pass against unchanged files; no training follows"
        )
    body = {
        "sources": sources,
        "resource_path": str(report.relative_to(root)),
        "resource_id": check["report_id"],
    }
    atomic_json(receipt, {**body, "report_id": manifest_identifier(body)})


def run_budgeted(
    root: Path, cfg: dict[str, Any], command: list[str], *, one_session: bool = False
) -> int:
    workspace = root / cfg["workspace"]
    deadline = time.monotonic() + cfg["invocation_wall_seconds"]
    while True:
        if (workspace / "report.json").exists():
            print("Fixed learning curve complete. Verifying saved final results.", flush=True)
            return subprocess.call([*command, "--status"], cwd=root)
        remaining = int(deadline - time.monotonic()) - 20
        wall = min(cfg["session_limits"]["wall_seconds"], remaining)
        if wall < 330:
            print(
                "Invocation budget reached at a safe boundary. Re-run this same command to resume.",
                flush=True,
            )
            return 0
        report = next_resource(root, workspace.name + "-session")
        limits = cfg["session_limits"]
        previous_receipts = set((workspace / "sessions").glob("session-*.json"))
        code = subprocess.call(
            [
                "uv",
                "run",
                "--no-sync",
                "spireshift",
                "resources",
                "run",
                "--kind",
                "training",
                "--report",
                str(report),
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "2",
                "--max-wall-seconds",
                str(wall),
                "--max-cpu-seconds",
                str(limits["cpu_seconds"]),
                "--max-storage-bytes",
                str(limits["storage_bytes"]),
                "--max-memory-bytes",
                str(limits["resident_memory_bytes"]),
                "--",
                *command,
                "--wall-seconds",
                str(wall),
            ],
            cwd=root,
        )
        resources = identified(report)
        if code or resources["status"] != "completed" or resources["exit_code"] != 0:
            print(
                "Stopped after a failed/capped session. Evidence is preserved; no automatic retry.",
                flush=True,
            )
            return code or 1
        new_receipts = set((workspace / "sessions").glob("session-*.json")) - previous_receipts
        if len(new_receipts) != 1:
            raise ValueError("Completed invocation must create exactly one sealed progress receipt")
        result = identified(new_receipts.pop())
        if result["config_id"] != manifest_identifier(cfg):
            raise ValueError("Session progress belongs to a different frozen recipe")
        if result["status"] == "native_optimizer_learning_curve_complete":
            return 0
        if (
            result["status"] != "paused_between_committed_chunks"
            or result["new_units_this_session"] < 1
        ):
            raise ValueError(
                "Session made no verified progress; do not loop or replay uncertain work"
            )
        if one_session:
            print(
                "One bounded session finished. The same command resumes the fixed plan.", flush=True
            )
            return 0
        print(
            "Clean session boundary. Continuing the same finite experiment from saved units.",
            flush=True,
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--status", action="store_true")
    p.add_argument("--one-session", action="store_true")
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    qualification = "configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
    recipe = "configs/native-learning/sts2-v0.111.0-a8-optimizer-learning-curve-v1.json"
    q = load_engine_qualification_config(root / qualification)
    cfg, _, seeds = load_trial(q, root / recipe)
    node = os.environ.get(
        "SPIRESHIFT_NODE",
        "/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node",
    )
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_optimizer_trial",
        qualification,
        recipe,
        "--node",
        node,
    ]
    if a.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    lock = root / "artifacts/validation/native-optimizer-learning-v1-launch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("Another invocation owns this learning curve") from exc
        ensure_checked(root)
        games = sum(len(t.get("seeds", [])) for t in plan(cfg, seeds))
        print(
            f"Two matched A8 methods across two initializers: {games} planned game attempts.",
            flush=True,
        )
        print(
            "Standard: 32 games/batch, 3 passes. Candidate: 128 games/batch, 9 passes.", flush=True
        )
        print(
            "Each player gets 512 training games. "
            "Frozen development checks after 0/128/256/384/512.",
            flush=True,
        )
        print(
            "Expect roughly 2–3 hours; three-hour work budget, 4 GB memory, "
            "6 GB retained output. Two workers, shared frozen game; no app copies.",
            flush=True,
        )
        print(
            "Clean 15-minute sessions continue automatically. "
            "Failures stop; no new experiment or promotion follows.",
            flush=True,
        )
        print(
            "Close the Steam game. "
            "Re-running preserves completed work and resumes this fixed plan.",
            flush=True,
        )
        return run_budgeted(root, cfg, command, one_session=a.one_session)


if __name__ == "__main__":
    raise SystemExit(main())
