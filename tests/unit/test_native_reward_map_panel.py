from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest


def load_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "contract",
    [
        "test_saved_only_then_resume_reuses_the_first_control_and_all_immutable_files",
        "test_changed_raw_evidence_blocks_before_any_new_case",
        "test_zero_exit_with_capped_verification_cannot_grant_a_pass",
        "test_unverified_worker_blocks_later_cases",
        "test_a_matching_short_prefix_does_not_pass_the_declared_target",
        "test_unstarted_but_uncertain_case_is_never_replayed",
    ],
)
def test_new_source_panel_retains_all_completed_result_and_no_retry_guarantees(
    contract: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).resolve().parents[2]
    # Exercise the new executable with the same producer-shaped records. Keep
    # the pinned v2 implementation and its historical regressions unchanged.
    harness = load_file("reward_map_harness", root / "tests/unit/test_native_modal_coordination.py")
    current = load_file("reward_map_panel", root / "scripts/modal-panel-session-v3.py")
    monkeypatch.setattr(harness, "coordinator", lambda: current)
    write = harness.write_identified

    def write_current_resource(path: Path, body: dict[str, Any]) -> Any:
        if path.name.startswith("map-settling-control-"):
            path = path.with_name(path.name.replace("map-settling-control-", "reward-map-control-"))
        return write(path, body)

    monkeypatch.setattr(harness, "write_identified", write_current_resource)
    batch = harness.batch.__wrapped__(tmp_path, monkeypatch)
    getattr(harness, contract)(batch)
