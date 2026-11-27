"""Owner entry point: verified repository checks, then one bounded resumable session."""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file, load_engine_qualification_config
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_resume import load_resume


def repository_files(root: Path) -> dict[str, str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    names = sorted({n.decode() for n in raw.split(b"\0") if n})
    return {n: _sha_file(root / n) for n in names if (root / n).is_file()}


def checked_session(root: Path, cfg: dict[str, Any], command: list[str]) -> int:
    workspace = root / cfg["workspace"]
    sources = repository_files(root)
    validation = (
        root / "artifacts/validation/context-chunks-v2" / manifest_identifier(sources).split(":")[1]
    )
    receipt = validation / "passed.json"
    if receipt.exists():
        saved = identified(receipt)
        resources = identified(root / saved["resources_path"])
        if (
            saved["sources"] != sources
            or saved["resources_id"] != resources["report_id"]
            or resources["status"] != "completed"
            or resources["exit_code"] != 0
        ):
            raise ValueError("Saved full-check receipt changed")
        print(
            "Repository checks already passed for these exact files; reusing the receipt.",
            flush=True,
        )
    else:
        files = validation / "files.json"
        if files.exists():
            if identified(files)["sources"] != sources:
                raise ValueError("Preserve changed verification inputs")
        else:
            body: dict[str, Any] = {"sources": sources}
            atomic_json(files, {**body, "report_id": manifest_identifier(body)})
        check_attempt = 1
        while (validation / f"resources-{check_attempt}.json").exists():
            check_attempt += 1
        resource_path = validation / f"resources-{check_attempt}.json"
        print(
            "Running the required complete repository checks first "
            "(about 5–6 minutes, 10-minute cap).",
            flush=True,
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
                str(resource_path),
                "--artifact-root",
                str(validation),
                "--workers",
                "1",
                "--max-wall-seconds",
                "600",
                "--max-cpu-seconds",
                "1800",
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
        if code:
            return code
        resources = identified(resource_path)
        if (
            resources["status"] != "completed"
            or resources["exit_code"] != 0
            or repository_files(root) != sources
        ):
            raise ValueError(
                "Full checks did not finish cleanly against unchanged repository files"
            )
        body = {
            "schema_version": "native-context-repository-check-v2",
            "sources": sources,
            "resources_id": resources["report_id"],
            "resources_path": str(resource_path.relative_to(root)),
            "command": ["uv", "run", "--no-sync", "spireshift", "check"],
        }
        atomic_json(receipt, {**body, "report_id": manifest_identifier(body)})
    limits = cfg["session_limits"]
    name = workspace.name
    attempt = 1
    while (root / f"artifacts/resources/{name}-session-{attempt}.json").exists():
        attempt += 1
    print(
        "Continuing the fresh matched pair: at most 15 minutes this launch, two workers.",
        flush=True,
    )
    print(
        "288 new games in total; completed chunks and full model/Adam state are reused.", flush=True
    )
    print(
        "Eight games per collection chunk; the training batch remains 32. No app copies.",
        flush=True,
    )
    print("Close any running game. Run this same command again after a clean pause.", flush=True)
    return subprocess.call(
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
            f"artifacts/resources/{name}-session-{attempt}.json",
            "--artifact-root",
            cfg["workspace"],
            "--workers",
            "2",
            "--max-wall-seconds",
            str(limits["wall_seconds"]),
            "--max-cpu-seconds",
            str(limits["cpu_seconds"]),
            "--max-storage-bytes",
            str(limits["storage_bytes"]),
            "--max-memory-bytes",
            str(limits["resident_memory_bytes"]),
            "--",
            *command,
        ],
        cwd=root,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    qualification = "configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
    recipe = "configs/native-controls/action-context-chunks-comparison-v2.json"
    node = os.environ.get(
        "SPIRESHIFT_NODE",
        "/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node",
    )
    q = load_engine_qualification_config(root / qualification)
    cfg, _, _ = load_resume(q, root / recipe)
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        "-m",
        "spireshift.native_context_resume",
        qualification,
        recipe,
        "--node",
        node,
    ]
    if args.status or (root / cfg["workspace"] / "report.json").exists():
        return subprocess.call([*command, "--status"], cwd=root)
    lock = root / "artifacts/validation/context-chunks-v2-launch.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(
                "Another invocation owns the checks/comparison; leave it running"
            ) from exc
        return checked_session(root, cfg, command)


if __name__ == "__main__":
    raise SystemExit(main())
