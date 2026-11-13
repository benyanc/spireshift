"""Only the finite tactical diagnostic; saved units resume, no next experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path


def repository_snapshot(root: Path) -> str:
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
    ).split(b"\0")
    digest = hashlib.sha256()
    for name in sorted(set(n for n in names if n)):
        path = root / name.decode()
        if not path.is_file():
            continue
        digest.update(name + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def ensure_repository_checks(root: Path) -> int:
    from spireshift.core.manifest import manifest_identifier
    from spireshift.engine_learning import identified
    from spireshift.full_run_experience import atomic_json

    fingerprint = repository_snapshot(root)
    workspace = root / "artifacts/native-tactical/owner-check-v1"
    receipt = workspace / f"passed-{fingerprint}.json"
    if receipt.exists():
        saved = identified(receipt)
        report = identified(root / saved["resource_path"])
        if (
            saved["repository_snapshot"] != fingerprint
            or report["report_id"] != saved["resource_report_id"]
            or report["status"] != "completed"
            or report["exit_code"] != 0
        ):
            raise ValueError("Preserve and inspect the changed repository-check receipt")
        print(
            "Full repository checks already passed for these exact files; reusing receipt.",
            flush=True,
        )
        return 0
    print(
        "Finishing full repository checks before any diagnostic work (15-minute cap). "
        "A failed or capped check stops here; no native fixture or fitting follows.",
        flush=True,
    )
    index = 1
    template = "artifacts/resources/native-tactical-owner-check-v1-{}.json"
    while (root / template.format(index)).exists():
        index += 1
    resource_path = template.format(index)
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
            resource_path,
            "--artifact-root",
            str(workspace.relative_to(root)),
            "--workers",
            "1",
            "--max-wall-seconds",
            "900",
            "--max-cpu-seconds",
            "1800",
            "--max-memory-bytes",
            "2000000000",
            "--max-storage-bytes",
            "1000000000",
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
    report = identified(root / resource_path)
    if report["status"] != "completed" or report["exit_code"] != 0:
        raise ValueError("Only a complete passing repository check can start diagnostics")
    if repository_snapshot(root) != fingerprint:
        raise ValueError("Repository files changed during checks; no fixture or fitting follows")
    body = {
        "schema_version": "native-tactical-repository-check-receipt-v1",
        "repository_snapshot": fingerprint,
        "resource_path": resource_path,
        "resource_report_id": report["report_id"],
    }
    atomic_json(receipt, {**body, "report_id": manifest_identifier(body)})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    root = Path(__file__).resolve().parents[1]
    stage = "control" if args.control else "comparison"
    recipe = f"configs/native-tactical/sts2-v0.111.0-a8-{stage}-v1.json"
    cfg = json.loads((root / recipe).read_text())
    if (root / cfg["workspace"] / "report.json").exists():
        print(
            "Already complete. Verifying and displaying the saved result; "
            "no fixtures, fitting or next experiment follow.",
            flush=True,
        )
        return subprocess.call(
            ["uv", "run", "--no-sync", "python", "-m", "spireshift.native_tactical_study", recipe],
            cwd=root,
        )
    if not args.control:
        code = ensure_repository_checks(root)
        if code:
            return code
    print(
        "Checking simple A8 combat choices using native outcomes. "
        "These are diagnostic fixtures, not full games or a new full-run reward. "
        "Original players and their complete Adam states stay read-only. "
        "One isolated native process at a time; no app copies. Close STS2. "
        "Sealed cases resume; uncertain cases stop. No next experiment follows.",
        flush=True,
    )
    while True:
        index = 1
        template = f"artifacts/resources/native-tactical-{stage}-v1-{{}}.json"
        while (root / template.format(index)).exists():
            index += 1
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
                template.format(index),
                "--artifact-root",
                cfg["workspace"],
                "--workers",
                "1",
                "--max-wall-seconds",
                str(cfg["session_wall_seconds"]),
                "--max-cpu-seconds",
                str(cfg["session_wall_seconds"] * 2),
                "--max-memory-bytes",
                "2000000000",
                "--max-storage-bytes",
                "1000000000",
                "--",
                "uv",
                "run",
                "--no-sync",
                "python",
                "-m",
                "spireshift.native_tactical_study",
                recipe,
            ],
            cwd=root,
        )
        if code or args.control or (root / cfg["workspace"] / "report.json").exists():
            return code
        if time.monotonic() - started + cfg["session_wall_seconds"] > 3600:
            print(
                "Clean pause. Run this same command to continue the saved finite plan.", flush=True
            )
            return 0
        print("Clean session boundary; continuing the same fixed diagnostic.", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
