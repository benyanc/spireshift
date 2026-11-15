from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.native_policy_confirmation import COMPLETE


@pytest.mark.parametrize(
    "fault", [None, "capped", "no_progress", "wrong_recipe", "no_receipt", "one_session"]
)
def test_wrapper_resumes_only_new_verified_progress_and_uses_recipe_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    entry = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/policy-confirmation-v1.py")
    )
    run = entry["run_budgeted"]
    cfg: dict[str, Any] = {
        "workspace": "artifacts/recipe-owned-workspace",
        "stage": "fresh_frozen_confirmation",
        "invocation_wall_seconds": 3600,
        "session_limits": {
            "wall_seconds": 900,
            "cpu_seconds": 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 2000000000,
        },
    }
    workspace = tmp_path / cfg["workspace"]
    calls: list[list[str]] = []

    def save(p: Path, d: dict[str, Any]) -> None:
        atomic_json(p, {**d, "report_id": manifest_identifier(d)})

    def next_resource(root: Path, name: str) -> Path:
        return root / f"artifacts/resources/{name}-{len(calls)}.json"

    def call(command: list[str], **kwargs: Any) -> int:
        calls.append(command)
        if command[-1] == "--status":
            return 0
        assert command[command.index("--kind") + 1] == "rollout"
        assert command[command.index("--artifact-root") + 1] == cfg["workspace"]
        assert command[command.index("--max-wall-seconds") + 1] == "900"
        save(
            Path(command[command.index("--report") + 1]),
            {"status": "capped" if fault == "capped" else "completed", "exit_code": 0},
        )
        if fault != "no_receipt":
            save(
                workspace / f"sessions/session-{len(calls):03d}.json",
                {
                    "config_id": "wrong" if fault == "wrong_recipe" else manifest_identifier(cfg),
                    "status": COMPLETE if len(calls) == 2 else "paused_between_committed_chunks",
                    "new_units_this_session": 0 if fault == "no_progress" else 2,
                },
            )
        return 0

    monkeypatch.setattr("subprocess.call", call)
    monkeypatch.setitem(
        run.__globals__,
        "runpy",
        type("Helpers", (), {"run_path": lambda *_: {"next_resource": next_resource}}),
    )
    monkeypatch.setitem(run.__globals__, "time", type("Clock", (), {"monotonic": lambda: 0}))
    if fault in {"no_progress", "wrong_recipe", "no_receipt"}:
        with pytest.raises(ValueError):
            run(tmp_path, cfg, ["comparison-module"])
    else:
        result = run(tmp_path, cfg, ["comparison-module"], one_session=fault == "one_session")
        assert result == (1 if fault == "capped" else 0)
    assert len(calls) == (3 if fault is None else 1)
    assert not any("training" in c for c in calls)
