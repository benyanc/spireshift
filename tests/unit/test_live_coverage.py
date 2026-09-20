from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from spireshift.adapters.sts2mcp import LiveSnapshot, Sts2McpStateProjector
from spireshift.core.manifest import load_patch_manifest
from spireshift.core.types import DecisionType, LegalAction
from spireshift.live_actions import ActionReceipt, BoundAction, DeliveryCertainty, ReceiptStatus
from spireshift.live_coverage import LiveCoverageReport, audit_full_run_action_coverage
from spireshift.live_run import LiveRunRecorder, LiveRunStrategy, WeakLivePolicy, run_live_game

MANIFEST_PATH = Path("manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json")
CORPUS_PATH = Path("tests/fixtures/live/public-state-corpus-v1.json")
SPECIFICATION_PATH = Path("configs/live-coverage-v0.107.1.json")
SOURCE_FIXTURE = Path("tests/fixtures/sts2mcp-menu-source-v0.4.0.json")
NOW = "2026-09-20T00:00:00Z"


class SequenceSnapshotProvider:
    def __init__(self, *snapshots: LiveSnapshot) -> None:
        self.snapshots = list(snapshots)

    def snapshot(self) -> LiveSnapshot:
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]


class AppliedExecutor:
    def __init__(self, *successors: LiveSnapshot) -> None:
        self.successors = list(successors)

    def execute(self, request: BoundAction, *, dry_run: bool) -> ActionReceipt:
        assert dry_run is False
        return ActionReceipt(
            request=request,
            status=ReceiptStatus.APPLIED,
            reason="successor_observed",
            message="applied",
            delivery_certainty=DeliveryCertainty.APPLIED,
            predecessor_state_hash=request.state_hash,
            successor_snapshot=self.successors.pop(0).as_dict(),
            bridge_response={"status": "ok"},
            started_at=NOW,
            completed_at=NOW,
        )


def _base_snapshot() -> LiveSnapshot:
    source = json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    return Sts2McpStateProjector(load_patch_manifest(MANIFEST_PATH)).project(
        source, bridge_version="0.4.0"
    )


def _snapshot(
    state_type: str,
    actions: tuple[LegalAction, ...],
    *,
    character: str = "The Defect",
    terminal: bool = False,
    coverage: str = "ready",
) -> LiveSnapshot:
    base = _base_snapshot()
    public_state: dict[str, object] = {
        "state_type": state_type,
        "player": {"character": character, "hp": 0 if terminal else 75},
        "run": {"act": 1, "floor": 1, "ascension": 0},
        "terminal": terminal,
        "victory": False,
    }
    if state_type == "menu":
        public_state["menu_screen"] = "singleplayer"
    encoded = json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
    return replace(
        base,
        observation=replace(
            base.observation,
            decision_type=(
                DecisionType.TERMINAL
                if terminal
                else DecisionType.MENU
                if state_type == "menu"
                else DecisionType.COMBAT
            ),
            public_state=public_state,
            state_hash=hashlib.sha256(encoded).hexdigest(),
        ),
        legal_actions=actions,
        action_coverage_status=coverage,
        action_coverage_issues=("fixture unsupported",) if coverage == "unsupported" else (),
    )


def _write_terminal_run(tmp_path: Path, *, character: str = "The Defect") -> Path:
    standard = LegalAction("standard", "menu_select", {"option": "standard"})
    action = LegalAction("end", "end_turn", {})
    menu = _snapshot("menu", (standard,), character=character)
    combat = _snapshot("monster", (action,), character=character)
    terminal = _snapshot("game_over", (), character=character, terminal=True)
    path = tmp_path / f"terminal-{character.replace(' ', '-')}.jsonl"
    with LiveRunRecorder(path) as recorder:
        result = run_live_game(
            snapshot_provider=SequenceSnapshotProvider(menu, combat, terminal),
            executor=AppliedExecutor(combat, terminal),
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=5,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            now=lambda: NOW,
        )
    assert result.terminal
    return path


def _write_unsupported_run(tmp_path: Path) -> Path:
    unsupported = _snapshot("overlay", (), coverage="unsupported")
    path = tmp_path / "unsupported.jsonl"
    with LiveRunRecorder(path) as recorder:
        run_live_game(
            snapshot_provider=SequenceSnapshotProvider(unsupported),
            executor=AppliedExecutor(unsupported),
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=5,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            now=lambda: NOW,
        )
    return path


def _audit(*paths: Path) -> LiveCoverageReport:
    return audit_full_run_action_coverage(
        specification_path=SPECIFICATION_PATH,
        fixture_corpus_path=CORPUS_PATH,
        run_paths=paths,
        manifest=load_patch_manifest(MANIFEST_PATH),
    )


def test_terminal_scoped_run_and_complete_fixture_oracles_pass(tmp_path: Path) -> None:
    report = _audit(_write_terminal_run(tmp_path))

    assert report.valid
    assert report.verdict == "pass"
    assert len(report.enumerated_state_types) == 18
    assert len(report.enumerated_action_kinds) >= 20
    assert all(check.passed for check in report.checks)


def test_explicit_unsupported_run_is_accounted_as_conditional_pass(tmp_path: Path) -> None:
    report = _audit(_write_terminal_run(tmp_path), _write_unsupported_run(tmp_path))

    assert report.valid
    assert report.verdict == "conditional_pass"
    assert sum(run.unsupported_decisions for run in report.runs) == 1
    check = next(check for check in report.checks if check.check_id == "accounted_run_outcomes")
    assert check.passed


def test_run_outside_frozen_character_scope_fails(tmp_path: Path) -> None:
    report = _audit(_write_terminal_run(tmp_path, character="The Ironclad"))

    assert not report.valid
    assert report.verdict == "fail"
    check = next(check for check in report.checks if check.check_id == "character_scope")
    assert not check.passed


def test_run_with_different_header_ruleset_fails(tmp_path: Path) -> None:
    path = _write_terminal_run(tmp_path)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["ruleset"]["manifest_id"] = f"sha256:{'0' * 64}"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")

    report = _audit(path)

    assert not report.valid
    check = next(check for check in report.checks if check.check_id == "run_ruleset_identity")
    assert not check.passed
