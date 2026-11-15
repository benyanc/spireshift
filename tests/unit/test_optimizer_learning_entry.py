from __future__ import annotations

import json
import runpy
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json


def entry() -> dict[str, Any]:
    return runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/optimizer-learning-v1.py")
    )


def save(path: Path, body: dict[str, Any]) -> None:
    atomic_json(path, {**body, "report_id": manifest_identifier(body)})


@pytest.mark.parametrize(
    "fault", [None, "capped_zero_exit", "failed_check", "changed_files", "changed_receipt"]
)
def test_full_check_receipt_requires_success_and_exact_repository_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    check = entry()["ensure_checked"]
    fingerprint = {"a.py": "original"}
    fingerprints = iter(
        [fingerprint, {"a.py": "changed"} if fault == "changed_files" else fingerprint, fingerprint]
    )
    monkeypatch.setitem(check.__globals__, "repository_files", lambda *_: next(fingerprints))
    calls = []

    def call(command: list[str], **kwargs: Any) -> int:
        calls.append(command)
        assert command[-1] == "check"
        save(
            Path(command[command.index("--report") + 1]),
            {
                "status": "capped" if fault == "capped_zero_exit" else "completed",
                "exit_code": 1 if fault == "failed_check" else 0,
            },
        )
        return 1 if fault == "failed_check" else 0

    monkeypatch.setattr("subprocess.call", call)
    if fault in {"capped_zero_exit", "failed_check", "changed_files"}:
        with pytest.raises(ValueError, match="Full repository check"):
            check(tmp_path)
        assert not list(tmp_path.glob("artifacts/validation/**/passed.json"))
    else:
        check(tmp_path)
        if fault == "changed_receipt":
            resource = tmp_path / "artifacts/resources/native-optimizer-repository-check-v1-1.json"
            changed = {"status": "capped", "exit_code": 0}
            resource.write_text(json.dumps({**changed, "report_id": manifest_identifier(changed)}))
            with pytest.raises(ValueError, match="Saved repository check changed"):
                check(tmp_path)
        else:
            check(tmp_path)
    assert len(calls) == 1  # A receipt never substitutes for an unsuccessful complete check.


@pytest.mark.parametrize(
    "fault",
    [None, "one_session", "capped_zero_exit", "no_progress", "no_receipt", "wrong_recipe"],
)
def test_only_clean_new_receipts_continue_the_same_finite_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    run = entry()["run_budgeted"]
    cfg: dict[str, Any] = {
        "workspace": "artifacts/recipe-owned-workspace",
        "invocation_wall_seconds": 10800,
        "session_limits": {
            "wall_seconds": 900,
            "cpu_seconds": 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 6000000000,
        },
    }
    workspace = tmp_path / cfg["workspace"]
    # Existing progress cannot stand in for the new invocation's receipt.
    save(
        workspace / "sessions/session-001.json",
        {"status": "paused_between_committed_chunks", "new_units_this_session": 3},
    )
    calls: list[list[str]] = []
    monkeypatch.setitem(run.__globals__, "time", type("Clock", (), {"monotonic": lambda: 0}))

    def call(command: list[str], **kwargs: Any) -> int:
        calls.append(command)
        assert command[command.index("--artifact-root") + 1] == cfg["workspace"]
        assert command[command.index("--max-wall-seconds") + 1] == "900"
        assert command[-3:] == ["native-module", "--wall-seconds", "900"]
        save(
            Path(command[command.index("--report") + 1]),
            {"status": "capped" if fault == "capped_zero_exit" else "completed", "exit_code": 0},
        )
        if fault != "no_receipt":
            save(
                workspace / f"sessions/session-{len(calls) + 1:03d}.json",
                {
                    "status": "native_optimizer_learning_curve_complete"
                    if len(calls) == 2
                    else "paused_between_committed_chunks",
                    "config_id": "other" if fault == "wrong_recipe" else manifest_identifier(cfg),
                    "new_units_this_session": 0 if fault == "no_progress" else 2,
                },
            )
        return 0

    monkeypatch.setattr("subprocess.call", call)
    if fault in {"no_progress", "no_receipt", "wrong_recipe"}:
        with pytest.raises(ValueError, match="progress|recipe"):
            run(tmp_path, cfg, ["native-module"])
    else:
        code = run(tmp_path, cfg, ["native-module"], one_session=fault == "one_session")
        assert code == (1 if fault == "capped_zero_exit" else 0)
    assert len(calls) == (2 if fault is None else 1)
    if len(calls) == 2:
        assert calls[0][calls[0].index("--report") + 1] != calls[1][calls[1].index("--report") + 1]


def test_exhausted_invocation_budget_launches_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = entry()["run_budgeted"]
    times = iter([0, 10800])
    monkeypatch.setitem(
        run.__globals__, "time", type("Clock", (), {"monotonic": lambda: next(times)})
    )
    monkeypatch.setattr("subprocess.call", lambda *_a, **_k: pytest.fail("No budget left"))
    assert (
        run(
            tmp_path,
            {
                "workspace": "artifacts/unused",
                "invocation_wall_seconds": 10800,
                "session_limits": {"wall_seconds": 900},
            },
            ["native-module"],
        )
        == 0
    )
