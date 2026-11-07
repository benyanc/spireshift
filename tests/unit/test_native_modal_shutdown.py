from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_flow_session_v12 as session


def panel() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts/modal-panel-session-v1.py"
    spec = importlib.util.spec_from_file_location("modal_test_panel", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_report() -> dict[str, Any]:
    checks = dict.fromkeys(
        [
            "profile_path_logged",
            "Steam_disabled_observed",
            "personal_profile_unchanged",
            "working_app_unchanged",
            "frozen_archive_unchanged",
            "settings_template_unchanged",
            "natural_shutdown",
            "exact_delivery_count",
        ],
        True,
    )
    return {
        "cases": [
            {
                "native": {"shutdown": {"clean_exit": True}},
                "official": {"status": "official_prefix_blocked", "checks": checks},
            }
        ]
    }


def test_clean_reset_can_continue_an_independent_case_without_claiming_compatibility() -> None:
    report = clean_report()
    before = copy.deepcopy(report)
    assert panel().clean_delivery(report)
    assert (
        report == before and report["cases"][0]["official"]["status"] == "official_prefix_blocked"
    )


@pytest.mark.parametrize("fault", ["abnormal_exit", "missing_check", "native_stop", "missing_all"])
def test_unverified_worker_never_allows_the_next_case(fault: str) -> None:
    report = clean_report()
    if fault == "abnormal_exit":
        report["cases"][0]["official"]["checks"]["natural_shutdown"] = False
    elif fault == "missing_check":
        del report["cases"][0]["official"]["checks"]["personal_profile_unchanged"]
    elif fault == "native_stop":
        report["cases"][0]["native"]["shutdown"]["clean_exit"] = False
    else:
        report["cases"][0]["official"]["checks"] = {}
    assert not panel().clean_delivery(report)


def test_saved_verification_must_belong_to_the_exact_control() -> None:
    module = panel()
    assert module.verification_matches(
        {"report_id": "one"}, {"valid": True, "source_report_id": "one"}
    )
    assert not module.verification_matches(
        {"report_id": "one"}, {"valid": True, "source_report_id": "two"}
    )
    assert not module.verification_matches(
        {"report_id": "one"}, {"valid": False, "source_report_id": "one"}
    )


@pytest.mark.parametrize("deadline,expected", [(1000.0, 45.0), (120.0, 20.0)])
def test_client_rejection_still_waits_for_game_exit_with_separate_reserve(
    monkeypatch: pytest.MonkeyPatch,
    deadline: float,
    expected: float,
) -> None:
    waits = []

    class Client:
        def close(self) -> None:
            raise ValueError("SDK input rejected")

    class Child:
        def wait(self, *, timeout: float) -> None:
            waits.append(timeout)

    monkeypatch.setattr(session.time, "monotonic", lambda: 100.0)
    assert session.finish_client(Client(), Child(), deadline) == "SDK input rejected"  # type: ignore[arg-type]
    assert waits == [expected]


def test_gameplay_budget_preserves_shutdown_time() -> None:
    assert session.gameplay_seconds(600, 500) == 55
    assert session.gameplay_seconds(600, 580) == 1


def test_expired_case_does_not_create_an_official_profile_or_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session.time, "monotonic", lambda: 100.0)
    context = {"qualification": None, "connector": None, "native": None}
    with pytest.raises(TimeoutError, match="no game started"):
        session.official_prefix(context, {}, tmp_path / "attempt", None, 140)  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []
