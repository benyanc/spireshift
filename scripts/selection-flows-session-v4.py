"""Owner launch: cache exact repository checks, then run the finite compatibility batch."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_flow_inputs_v4 import load
from spireshift.native_launch_limits import load_launch


def repository_files(root: Path) -> dict[str, str]:
    raw = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return {
        n: _sha_file(root / n)
        for n in sorted({s.decode() for s in raw.split(b"\0") if s})
        if (root / n).is_file()
    }


def check_repository(root: Path) -> int:
    sources = repository_files(root)
    workspace = (
        root
        / "artifacts/validation/selection-flows-v1"
        / manifest_identifier(sources).split(":")[1]
    )
    receipt = workspace / "passed.json"
    if receipt.exists():
        saved = identified(receipt)
        resources = identified(root / saved["resources_path"])
        if (
            saved["sources"] != sources
            or resources["report_id"] != saved["resources_id"]
            or resources["status"] != "completed"
            or resources["exit_code"] != 0
        ):
            raise ValueError("Saved repository-check receipt changed")
        print(
            "Repository checks already passed for these exact files; reusing the receipt.",
            flush=True,
        )
        return 0
    workspace.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (workspace / f"resources-{attempt}.json").exists():
        attempt += 1
    resource = workspace / f"resources-{attempt}.json"
    print(
        "Checking the repository first, with a separate 10-minute allowance. No games yet.",
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
            str(resource),
            "--artifact-root",
            str(workspace),
            "--workers",
            "1",
            "--max-wall-seconds",
            "600",
            "--max-cpu-seconds",
            "1800",
            "--max-memory-bytes",
            "4000000000",
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
    resources = identified(resource)
    if (
        code
        or resources["status"] != "completed"
        or resources["exit_code"] != 0
        or repository_files(root) != sources
    ):
        raise ValueError("Repository checks did not finish cleanly; comparison has not started")
    body: dict[str, Any] = {
        "schema_version": "selection-flows-repository-check-v1",
        "sources": sources,
        "resources_path": str(resource.relative_to(root)),
        "resources_id": resources["report_id"],
    }
    atomic_json(receipt, {**body, "report_id": manifest_identifier(body)})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("launch", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    context = load(root, args.recipe.resolve())
    load_launch(root, args.launch.resolve(), args.recipe.resolve(), context["config"])
    check_repository(root)
    return subprocess.call(
        [
            "bash",
            str(root / "scripts/check-selection-flows-v4.sh"),
            str(args.recipe),
            str(args.launch),
        ],
        cwd=root,
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"status": "stopped_preserving_evidence", "error": str(error)}))
        raise SystemExit(2) from error
