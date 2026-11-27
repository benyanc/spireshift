from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from spireshift.native_capacity_result_v1 import episode
from spireshift.native_win4_game import write


@pytest.mark.parametrize(
    "fault", [None, "unclean", "runtime", "unverified", "foreign_seed", "updates"]
)
def test_capacity_result_requires_native_ending_delivery_and_reset(
    tmp_path: Path, fault: str | None
) -> None:
    saved: dict[str, Any] = {
        "status": "complete",
        "native_terminal": True,
        "optimizer_updates": 0,
        "shutdown": {"clean_exit": True, "runtime_errors": []},
        "actual_deliveries_independently_verified": 12,
        "native_ending": {
            "native_ending_evidence_agrees": True,
            "private_final_identity": {
                "seed": "WORLD",
                "ascension": 8,
                "native_game_over": True,
                "native_player_dead": True,
            },
        },
    }
    if fault == "unclean":
        saved["shutdown"]["clean_exit"] = False
    if fault == "runtime":
        saved["shutdown"]["runtime_errors"] = ["error"]
    if fault == "unverified":
        saved["actual_deliveries_independently_verified"] = 11
    if fault == "foreign_seed":
        saved["native_ending"]["private_final_identity"]["seed"] = "OTHER"
    if fault == "updates":
        saved["optimizer_updates"] = 1
    report = write(tmp_path / "report.json", saved)
    row = {
        "outcome": "loss",
        "episode_report_id": report["report_id"],
        "native_decisions": 12,
        "task": {"seed": "WORLD"},
    }
    if fault is None:
        episode(tmp_path, row)
    else:
        with pytest.raises(ValueError):
            episode(tmp_path, row)
