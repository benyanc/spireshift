"""The discovery batch collects blocked seeds and stops only for infrastructure/budget failures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from spireshift import engine_run_discovery as discovery
from spireshift.engine_qualification import EngineQualificationConfig


def setup_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, reporting_revision: str | None = None
) -> EngineQualificationConfig:
    q = EngineQualificationConfig(document={}, root=tmp_path)
    document: dict[str, Any] = {"workspace": "artifacts/discovery", "max_wall_seconds": 1000}
    if reporting_revision is not None:
        document["reporting_revision"] = reporting_revision
    recipes = [
        (
            tmp_path / f"recipe-{n}.json",
            {
                "workspace": f"artifacts/discovery/seed-{n}",
                "seed": f"synthetic-{n}",
                "natural_run_limits": {"max_wall_seconds": 180},
            },
        )
        for n in range(3)
    ]
    monkeypatch.setattr(discovery, "load_discovery_recipe", lambda *_: (document, recipes))
    monkeypatch.setattr(discovery, "verify_new_run", lambda *_args, **_kwargs: {"valid": True})
    return q


def saved_case(status: str, *, terminal: bool, issues: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "report_id": "synthetic",
        "status": status,
        "gameplay": {"terminal": terminal, "victory": False, "maximum_floor": 5},
        "games_launched": 1,
        "full_run_attempts": 1,
        "diagnostics": {"issues": issues, "recoveries": []},
    }


def issue() -> dict[str, Any]:
    return {
        "issue_id": "same-issue",
        "kind": "unsupported",
        "context": "shop",
        "field": "legal_actions",
        "reason": "missing owner",
        "occurrences": 1,
    }


def test_blocked_seeds_continue_and_all_denominators_and_issues_are_retained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = setup_batch(tmp_path, monkeypatch)
    calls = []

    def compare(_q: Any, recipe: Path, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("preflight"):
            return {"ready_for_diagnostic": True}
        calls.append(recipe)
        return saved_case("natural_shipped_run_incomplete", terminal=False, issues=[issue()])

    monkeypatch.setattr(discovery, "compare_new_run", compare)
    result = discovery.discover_runs(q, tmp_path / "recipe.json", node=tmp_path / "node")
    assert len(calls) == 3
    assert result["status"] == "discovery_complete"
    assert result["completed_cases"] == 0
    assert result["failed_cases"] == 3
    assert result["not_attempted_cases"] == 0
    assert result["games_launched"] == 3
    assert result["unique_issues"] == 1
    assert result["issues"][0]["occurrences"] == 3
    assert result["training_allowed"] is False
    assert result["bulk_learning_admitted"] is False


def test_an_infrastructure_failure_counts_the_attempt_and_stops_other_seeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q = setup_batch(tmp_path, monkeypatch)
    calls = []

    def compare(_q: Any, recipe: Path, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("preflight"):
            return {"ready_for_diagnostic": True}
        calls.append(recipe)
        raise ValueError("fixed app reset failed")

    monkeypatch.setattr(discovery, "compare_new_run", compare)
    result = discovery.discover_runs(q, tmp_path / "recipe.json", node=tmp_path / "node")
    assert len(calls) == 1
    assert result["status"] == "discovery_incomplete"
    assert result["failed_cases"] == 1
    assert result["not_attempted_cases"] == 2
    assert result["games_launched"] is None
    assert "reset failed" in result["cases"][0]["error"]


def test_recovered_endings_never_count_as_clean_games_or_clean_wins() -> None:
    case = {
        "case_id": "recovered",
        "status": "natural_shipped_run_incomplete",
        "gameplay": {"terminal": True, "victory": True},
        "diagnostics": {"recoveries": [{}], "issues": [issue()]},
    }
    result = discovery.discovery_summary([case], 2)
    assert result["observed_terminal_runs"] == 1
    assert result["recovered_cases"] == 1
    assert result["completed_cases"] == 0
    assert result["clean_victories"] == 0
    assert result["failed_cases"] == 1
    assert result["not_attempted_cases"] == 1


def test_preflight_never_runs_a_game(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    q = setup_batch(tmp_path, monkeypatch)
    calls = []

    def compare(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["preflight"] is True
        calls.append(kwargs)
        return {"ready_for_diagnostic": True}

    monkeypatch.setattr(discovery, "compare_new_run", compare)
    result = discovery.discover_runs(
        q, tmp_path / "recipe.json", node=tmp_path / "node", preflight=True
    )
    assert len(calls) == 3
    assert result["games_launched"] == 0
    assert not (tmp_path / "artifacts").exists()


def test_zero_missing_fields_does_not_hide_a_repeated_state_failure() -> None:
    cases = [
        {
            **saved_case("natural_shipped_run_pass", terminal=True, issues=[]),
            "case_id": "complete",
        },
        {
            **saved_case("natural_shipped_run_incomplete", terminal=False, issues=[]),
            "case_id": "loop",
            "verification": {"error": "Repeated natural-run public state; no further action"},
        },
    ]
    result = discovery.discovery_summary(cases, 3, include_outcomes=True)
    assert result["completed_cases"] == 1
    assert result["failed_cases"] == 1
    assert result["not_attempted_cases"] == 1
    assert result["unique_issues"] == 0
    assert result["failures_by_kind"] == {"repeated_state": 1}
    assert result["case_outcomes"][0]["outcome"] == "completed_loss"
    assert result["case_outcomes"][1]["error"].startswith("Repeated natural-run")
    assert "case_outcomes" not in discovery.discovery_summary(cases, 3)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("Unknown natural-run delivery; no retry", "action_delivery"),
        ("No fresh complete public menu before the run cap", "resource_or_decision_cap"),
        (None, "unclassified_incomplete"),
    ],
)
def test_incomplete_reasons_remain_visible_without_unsupported_fields(
    error: str | None, expected: str
) -> None:
    case = {
        **saved_case("natural_shipped_run_incomplete", terminal=False, issues=[]),
        "case_id": "failed",
        "error": error,
    }
    outcome = discovery.case_outcome(case)
    assert outcome["failure_kind"] == expected
    assert outcome["error"] == error
    assert outcome["outcome"] == "incomplete"


def test_new_progress_and_saved_summary_include_the_case_failure_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    q = setup_batch(tmp_path, monkeypatch, reporting_revision="outcomes_v2")

    def compare(*_args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("preflight"):
            return {"ready_for_diagnostic": True}
        return saved_case("natural_shipped_run_incomplete", terminal=False, issues=[])

    monkeypatch.setattr(discovery, "compare_new_run", compare)
    monkeypatch.setattr(
        discovery,
        "verify_new_run",
        lambda *_args, **_kwargs: {
            "valid": True,
            "error": "Repeated natural-run public state; no further action",
        },
    )
    result = discovery.discover_runs(q, tmp_path / "recipe.json", node=tmp_path / "node")
    assert result["status"] == "discovery_complete"
    assert result["failed_cases"] == 3
    assert result["failures_by_kind"] == {"repeated_state": 3}
    assert len(result["case_outcomes"]) == 3
    assert "reason: repeated_state: Repeated natural-run public state" in capsys.readouterr().out
