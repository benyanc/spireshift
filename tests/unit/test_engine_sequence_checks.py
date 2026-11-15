from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.engine_sequence_checks import (
    PublicRandomChooser,
    _write_trace,
    audit_sequence_trace,
    summarize_sequences,
    walk_sequence,
)


def public() -> dict[str, Any]:
    return {
        "context": {"interaction": {"kind": "combat_turn"}},
        "candidates": [{"verb": v, "label": v} for v in ("play", "skip", "end_turn")],
    }


def test_uniform_public_sampling_keeps_skip_and_is_reproducible_under_menu_reordering() -> None:
    a, b = PublicRandomChooser("one"), PublicRandomChooser("one")
    first = public()
    second = copy.deepcopy(first)
    second["candidates"].reverse()
    selected = []
    for _ in range(300):
        left = first["candidates"][a.choose(first)]
        right = second["candidates"][b.choose(second)]
        assert left == right
        selected.append(left["verb"])
    assert set(selected) == {"play", "skip", "end_turn"}


def test_chooser_rejects_hidden_inputs_and_does_not_use_the_environment_seed() -> None:
    with pytest.raises(ValueError, match="Private field"):
        PublicRandomChooser("one").choose({**public(), "seed": "SECRET"})
    with pytest.raises(ValueError, match="nonempty"):
        PublicRandomChooser("one").choose({"candidates": []})


def write_prefix(path: Path, *, final: bool = True) -> dict[str, Any]:
    digest = hashlib.sha256()
    with gzip.open(path, "xt", encoding="utf-8") as stream:
        _write_trace(stream, digest, public(), 1)
        if final:
            _write_trace(stream, digest, public(), None)
    return {"semantic_trace_id": "sha256:" + digest.hexdigest()}


def test_saved_prefix_is_audited_without_any_game(tmp_path: Path) -> None:
    path = tmp_path / "public.gz"
    expected = write_prefix(path)
    result = audit_sequence_trace(path, 256)
    assert result["semantic_trace_id"] == expected["semantic_trace_id"]
    assert result["decisions"] == 1
    assert result["verbs"] == {"skip": 1}
    assert result["families"] == {"combat_turn": 2}


@pytest.mark.parametrize("defect", ["partial", "unadvertised", "private", "extra", "over_cap"])
def test_invalid_saved_prefixes_cannot_be_promoted(tmp_path: Path, defect: str) -> None:
    path = tmp_path / "public.gz"
    write_prefix(path, final=defect != "partial")
    rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    if defect == "unadvertised":
        rows[0]["chosen"] = {"verb": "invented"}
    if defect == "private":
        rows[0]["context"]["rng"] = "SECRET"
    if defect == "extra":
        rows += rows
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")
    with pytest.raises(ValueError):
        audit_sequence_trace(path, 0 if defect == "over_cap" else 256)


def row(
    case: str, seed: str, action: str, trace: str = "same", status: str = "bounded_prefix_complete"
) -> dict[str, Any]:
    return {
        "spec": {"case_id": case, "seed": seed, "action_seed": action},
        "status": status,
        "semantic_trace_id": trace,
        "decisions": 5,
        "families": {"combat_turn": 5},
        "report_id": case,
    }


def panel() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [row("one", "s1", "a1"), row("repeat", "s1", "a1"), row("two", "s2", "a2")]
    cfg = {
        "cases": [r["spec"] for r in rows],
        "minimum_total_decisions": 10,
        "required_families": ["combat_turn"],
    }
    return cfg, rows


def test_complete_prefixes_are_not_reported_as_full_game_victories_or_readiness() -> None:
    cfg, rows = panel()
    result = summarize_sequences(cfg, rows)
    assert result["status"] == "legal_sequence_panel_pass"
    assert result["terminal_games_observed"] == 0
    assert result["independent_game_seeds"] == 2
    assert result["full_run_attempts"] == 3
    assert result["verified_bounded_prefixes"] == 3
    assert result["policy_quality_evaluated"] is False
    assert result["terminal_outcomes_readiness_eligible"] is False
    assert result["training_allowed"] is False


@pytest.mark.parametrize("defect", ["different_repeat", "failed", "missing", "low_coverage"])
def test_failures_missing_cases_and_repeat_drift_stay_in_the_denominator(defect: str) -> None:
    cfg, rows = panel()
    if defect == "different_repeat":
        rows[1]["semantic_trace_id"] = "different"
    elif defect == "failed":
        rows[0]["status"] = "failed"
    elif defect == "missing":
        rows.pop()
    else:
        cfg["minimum_total_decisions"] = 1000
    result = summarize_sequences(cfg, rows)
    assert result["status"] == "legal_sequence_panel_incomplete"
    assert result["planned_cases"] == 3


def observation(index: int, terminal: bool = False) -> dict[str, Any]:
    kind = "game_over" if terminal else "combat_turn"
    actions = (
        []
        if terminal
        else [{"bound_action_id": f"action-{v}", "interaction_id": "i"} for v in range(3)]
    )
    return {
        "snapshot": {
            "snapshot_id": str(index),
            "session": {"runtime_instance_id": "worker"},
            "interaction": {"kind": kind, "interaction_id": "i"},
            "persistent": {"content": {"run": {"ascension": 8}}},
            "completeness": {"status": "complete"},
            "information_policy": {"includes_hidden_information": False},
            "bound_actions": {
                "status": "complete",
                "total_count": len(actions),
                "materialized_count": len(actions),
                "actions": actions,
            },
            "status": "observed" if terminal else "interactive",
        },
        "model_input": {
            "context": {"interaction": {"kind": kind}},
            "candidates": [] if terminal else public()["candidates"],
        },
        "facts": {"floor": 3, "act": 1, "terminal": terminal, "victory": False},
        "public_key": str(index),
    }


def test_walker_uses_current_snapshot_and_stops_at_declared_prefix_bound(tmp_path: Path) -> None:
    class Worker:
        index = 0

        def request(self, command: str, **kwargs: Any) -> dict[str, Any]:
            if command == "mount":
                return observation(0)
            assert command == "step"
            assert kwargs["snapshot_id"] == str(self.index)
            self.index += 1
            return observation(self.index)

    cfg = {"maximum_decisions": 4, "case_wall_seconds": 30}
    path = tmp_path / "trace.gz"
    result = walk_sequence(Worker(), {"seed": "ENVIRONMENT", "action_seed": "actions"}, cfg, path)  # type: ignore[arg-type]
    assert result["status"] == "bounded_prefix_complete" and result["terminal"] is False
    assert result["decisions"] == 4
    assert audit_sequence_trace(path, 4)["semantic_trace_id"] == result["semantic_trace_id"]


def test_terminal_prefix_never_requests_an_unsupported_ending_or_another_action(
    tmp_path: Path,
) -> None:
    class Worker:
        def request(self, command: str, **kwargs: Any) -> dict[str, Any]:
            return observation(0) if command == "mount" else observation(1, terminal=True)

    result = walk_sequence(
        Worker(),  # type: ignore[arg-type]
        {"seed": "ENVIRONMENT", "action_seed": "actions"},
        {"maximum_decisions": 4, "case_wall_seconds": 30},
        tmp_path / "trace.gz",
    )
    assert result["status"] == "terminal_prefix_complete"
    assert result["terminal"] is True and result["decisions"] == 1


def test_public_trace_is_only_public_decisions() -> None:
    stream = io.StringIO()
    _write_trace(stream, hashlib.sha256(), public(), 0)
    assert "ENVIRONMENT" not in stream.getvalue()
    assert "action_seed" not in stream.getvalue()
