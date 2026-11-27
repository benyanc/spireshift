from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json


@pytest.mark.parametrize("fault", [None, "capped_zero_exit", "changed_files", "failed_check"])
def test_owner_entry_only_launches_session_after_exact_file_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    namespace = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/context-session-v2.py")
    )
    function = namespace["checked_session"]
    calls: list[list[str]] = []
    fingerprints = iter(
        [
            {"a.py": "before"},
            {"a.py": "changed" if fault == "changed_files" else "before"},
            {"a.py": "before"},
        ]
    )
    monkeypatch.setitem(function.__globals__, "repository_files", lambda *_: next(fingerprints))

    def call(command: list[str], **kwargs: Any) -> int:
        calls.append(command)
        if command[-1] == "check":
            report = Path(command[command.index("--report") + 1])
            body = {
                "status": "capped" if fault == "capped_zero_exit" else "completed",
                "exit_code": 1 if fault == "failed_check" else 0,
            }
            atomic_json(report, {**body, "report_id": manifest_identifier(body)})
            return 1 if fault == "failed_check" else 0
        report = tmp_path / command[command.index("--report") + 1]
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("saved bounded session")
        return 0

    monkeypatch.setattr("subprocess.call", call)
    cfg = {
        "workspace": "artifacts/recipe-owned-place",
        "session_limits": {
            "wall_seconds": 900,
            "cpu_seconds": 1800,
            "storage_bytes": 4000000000,
            "resident_memory_bytes": 4000000000,
        },
    }
    if fault in {"changed_files", "capped_zero_exit"}:
        with pytest.raises(ValueError, match="Full checks"):
            function(tmp_path, cfg, ["context-module"])
    elif fault == "failed_check":
        assert function(tmp_path, cfg, ["context-module"]) == 1
    else:
        assert function(tmp_path, cfg, ["context-module"]) == 0
        assert function(tmp_path, cfg, ["context-module"]) == 0
        assert len(calls) == 3 and sum(c[-1] == "check" for c in calls) == 1
        assert calls[1][calls[1].index("--artifact-root") + 1] == cfg["workspace"]
        assert calls[1][calls[1].index("--max-wall-seconds") + 1] == "900"
        assert calls[1][calls[1].index("--report") + 1].endswith("session-1.json")
        assert calls[2][calls[2].index("--report") + 1].endswith("session-2.json")
    if fault:
        assert len(calls) == 1  # Failure/cap/change never reaches native collection.
