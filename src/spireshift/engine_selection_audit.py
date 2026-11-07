"""Exact streaming replay of local subset UI plus the unchanged native episode audit."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience_stream import audit_worker_streaming, records
from spireshift.engine_qualification import _sha_file
from spireshift.engine_selection_worker import PROTOCOL


def audit_selection_worker(
    workspace: Path, paths: list[Path], *, deadline: float
) -> dict[str, Any]:
    # The JS verifier shares the pure UI reducer with the worker, but independently
    # replays private native responses and the ordered, separately recorded UI log.
    import subprocess

    root = Path(__file__).resolve().parents[2]
    source = workspace / "source-at-launch"
    helpers = json.loads((source / "helpers.json").read_text())
    for name, sha in helpers.items():
        if _sha_file(source / name) != sha:
            raise ValueError("Selection worker launch helpers changed")
    node = (
        json.loads((workspace / "selection-verifier.json").read_text())["node"]
        if (workspace / "selection-verifier.json").exists()
        else None
    )
    if node is None:
        raise ValueError("Bind the local Node verifier before auditing selection UI")
    script = root / "scripts/verify-selection-cursor-v1.mjs"
    p = subprocess.run(
        [node, str(script), str(workspace)],
        capture_output=True,
        text=True,
        timeout=max(1, deadline - time.monotonic()),
        check=True,
    )
    ui = json.loads(p.stdout)
    result = audit_worker_streaming(workspace, paths, deadline=deadline)
    hashes = {
        **result["source_sha256"],
        "selection-verifier.json": _sha_file(workspace / "selection-verifier.json"),
    }
    journal = workspace / "selection-cursor.jsonl.gz"
    if journal.exists():
        hashes[journal.name] = _sha_file(journal)
    # records() also checks a complete gzip tail; never trim an interrupted journal.
    if journal.exists() and sum(1 for _ in records(journal, deadline)) != ui["ui_commands"]:
        raise ValueError("Selection UI journal count changed during verification")
    body = {
        **result,
        "source_sha256": hashes,
        "selection_protocol": PROTOCOL,
        "selection_ui_audit": ui,
        "local_prefix_steps_are_native_effects": False,
    }
    body.pop("report_id", None)
    return {**body, "report_id": manifest_identifier(body)}
