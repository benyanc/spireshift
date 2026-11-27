from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.native_policy_trial_inputs import SHARED, control_sources


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "not_complete",
        "failed_game",
        "missing_game",
        "failed_math",
        "changed_state",
        "different_learning",
    ],
)
def test_main_requires_matching_complete_clean_native_and_mathematical_control(
    tmp_path: Path, fault: str
) -> None:
    state = tmp_path / "state.json"
    state.write_text("Original full state and all Adam moments")
    shared = {name: {"same": name} for name in SHARED}
    old: dict[str, Any] = {**shared, "stage": "short_control"}
    (tmp_path / "control.json").write_text(json.dumps(old))
    body = {
        "config_id": manifest_identifier(old),
        "status": "native_policy_update_control_complete",
        "games_recorded": 8,
        "failed_games": 0,
        "policy_checks": {"passed": True},
        "original_full_states_and_Adam_unchanged": True,
        "sources": {"state.json": _sha_file(state)},
    }
    if fault == "not_complete":
        body["status"] = "paused_between_sealed_units"
    if fault == "failed_game":
        body["failed_games"] = 1
    if fault == "missing_game":
        body["games_recorded"] = 7
    if fault == "failed_math":
        body["policy_checks"] = {"passed": False}
    result = {**body, "report_id": manifest_identifier(body)}
    (tmp_path / "result.json").write_text(json.dumps(result))
    cfg = {
        **shared,
        "control_recipe": {"path": "control.json"},
        "control_report": {"path": "result.json", "id": result["report_id"]},
    }
    if fault == "changed_state":
        state.write_text("Changed original optimizer")
    if fault == "different_learning":
        cfg["learning"] = {"different": "actor loss or optimizer"}
    if fault == "none":
        verified = control_sources(tmp_path, cfg)
        assert set(verified) == {"state.json", "control.json", "result.json"}
    else:
        with pytest.raises(ValueError):
            control_sources(tmp_path, cfg)
