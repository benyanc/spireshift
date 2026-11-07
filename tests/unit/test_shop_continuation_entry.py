from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.native_shop_continuation import COMPLETE


@pytest.mark.parametrize(
    "fault",
    [None, "capped", "no_receipt", "wrong_recipe", "no_progress", "one_session", "budget_spent"],
)
def test_continuation_wrapper_requires_new_clean_receipts_and_preserves_recipe_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    run = runpy.run_path(
        str(Path(__file__).resolve().parents[2] / "scripts/shop-continuation-v1.py")
    )["run_budgeted"]
    cfg: dict[str, Any] = {
        "workspace": "artifacts/from-recipe",
        "stage": "bounded_shop_continuation",
        "invocation_wall_seconds": 14400,
        "session_limits": {
            "wall_seconds": 900,
            "cpu_seconds": 1800,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 8000000000,
        },
    }
    workspace = tmp_path / cfg["workspace"]
    calls: list[list[str]] = []

    def save(p: Path, d: dict[str, Any]) -> None:
        atomic_json(p, {**d, "report_id": manifest_identifier(d)})

    def call(cmd: list[str], **kwargs: Any) -> int:
        calls.append(cmd)
        if cmd[-1] == "--status":
            return 0
        assert cmd[cmd.index("--artifact-root") + 1] == cfg["workspace"]
        assert cmd[cmd.index("--kind") + 1] == "training"
        save(
            Path(cmd[cmd.index("--report") + 1]),
            {"status": "capped" if fault == "capped" else "completed", "exit_code": 0},
        )
        if fault != "no_receipt":
            save(
                workspace / f"sessions/session-{len(calls):03d}.json",
                {
                    "config_id": "wrong" if fault == "wrong_recipe" else manifest_identifier(cfg),
                    "status": COMPLETE if len(calls) == 2 else "paused_between_committed_chunks",
                    "new_units_this_session": 0 if fault == "no_progress" else 3,
                },
            )
        return 0

    monkeypatch.setattr("subprocess.call", call)
    monkeypatch.setitem(
        run.__globals__,
        "runpy",
        type(
            "Helper",
            (),
            {
                "run_path": lambda *_: {
                    "next_resource": lambda root, name: (
                        root / f"artifacts/resources/{name}-{len(calls)}.json"
                    )
                }
            },
        ),
    )
    clock = iter([0, 14400]) if fault == "budget_spent" else None
    monkeypatch.setitem(
        run.__globals__,
        "time",
        type("Clock", (), {"monotonic": lambda: next(clock) if clock else 0}),
    )
    if fault in {"no_receipt", "wrong_recipe", "no_progress"}:
        with pytest.raises(ValueError):
            run(tmp_path, cfg, ["continuation-module"])
    else:
        assert run(tmp_path, cfg, ["continuation-module"], one_session=fault == "one_session") == (
            1 if fault == "capped" else 0
        )
    assert len(calls) == (3 if fault is None else 0 if fault == "budget_spent" else 1)
