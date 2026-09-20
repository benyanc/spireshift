from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from spireshift.adapters.sts2mcp import LiveSnapshot, Sts2McpStateProjector
from spireshift.core.manifest import load_patch_manifest
from spireshift.core.types import DecisionType, LegalAction
from spireshift.live_actions import (
    ActionReceipt,
    BoundAction,
    DeliveryCertainty,
    ReceiptStatus,
)
from spireshift.live_run import (
    LiveRunRecorder,
    LiveRunStatus,
    LiveRunStrategy,
    WeakLivePolicy,
    run_live_game,
    verify_live_run,
)

MANIFEST_PATH = Path("manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json")
SOURCE_FIXTURE = Path("tests/fixtures/sts2mcp-menu-source-v0.4.0.json")
NOW = "2026-09-20T00:00:00Z"


class SequenceSnapshotProvider:
    def __init__(self, *snapshots: LiveSnapshot) -> None:
        self.snapshots = list(snapshots)

    def snapshot(self) -> LiveSnapshot:
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]


class FakeExecutor:
    def __init__(
        self,
        *successors: LiveSnapshot,
        status: ReceiptStatus = ReceiptStatus.APPLIED,
    ) -> None:
        self.successors = list(successors)
        self.status = status
        self.requests: list[BoundAction] = []

    def execute(self, request: BoundAction, *, dry_run: bool) -> ActionReceipt:
        assert dry_run is False
        self.requests.append(request)
        successor = self.successors.pop(0) if self.successors else None
        applied = self.status is ReceiptStatus.APPLIED
        return ActionReceipt(
            request=request,
            status=self.status,
            reason="successor_observed" if applied else "fake_stop",
            message="fake receipt",
            delivery_certainty=(
                DeliveryCertainty.APPLIED if applied else DeliveryCertainty.NOT_APPLIED
            ),
            predecessor_state_hash=request.state_hash,
            successor_snapshot=None if successor is None else successor.as_dict(),
            bridge_response={"status": "ok"} if applied else {"status": "error"},
            started_at=NOW,
            completed_at=NOW,
        )


class StaleThenAppliedExecutor:
    def __init__(self, successor: LiveSnapshot) -> None:
        self.successor = successor
        self.requests: list[BoundAction] = []

    def execute(self, request: BoundAction, *, dry_run: bool) -> ActionReceipt:
        assert dry_run is False
        self.requests.append(request)
        stale = len(self.requests) == 1
        return ActionReceipt(
            request=request,
            status=ReceiptStatus.STALE if stale else ReceiptStatus.APPLIED,
            reason="stale_snapshot" if stale else "successor_observed",
            message="fake receipt",
            delivery_certainty=(
                DeliveryCertainty.NOT_APPLIED if stale else DeliveryCertainty.APPLIED
            ),
            predecessor_state_hash=request.state_hash,
            successor_snapshot=None if stale else self.successor.as_dict(),
            bridge_response=None if stale else {"status": "ok"},
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
    digit: str,
    *,
    terminal: bool = False,
    victory: bool | None = False,
    coverage: str = "ready",
) -> LiveSnapshot:
    base = _base_snapshot()
    public_state: dict[str, object] = {
        "state_type": state_type,
        "fixture_marker": digit,
        "terminal": terminal,
        "victory": victory,
    }
    if state_type == "menu":
        public_state["menu_screen"] = "main"
    state_hash = hashlib.sha256(
        json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision_type = DecisionType.TERMINAL if terminal else DecisionType.COMBAT
    return replace(
        base,
        observation=replace(
            base.observation,
            decision_type=decision_type,
            public_state=public_state,
            state_hash=state_hash,
        ),
        legal_actions=actions,
        action_coverage_status=coverage,
        action_coverage_issues=("fixture unsupported",) if coverage == "unsupported" else (),
    )


def test_live_loop_reaches_terminal_and_records_every_action(tmp_path: Path) -> None:
    menu_action = LegalAction("menu", "menu_select", {"option": "singleplayer"})
    combat_action = LegalAction("end", "end_turn", {})
    menu = _snapshot("menu", (menu_action,), "1")
    combat = _snapshot("monster", (combat_action,), "2")
    terminal = _snapshot("game_over", (), "3", terminal=True, victory=False)
    provider = SequenceSnapshotProvider(menu, combat, terminal)
    executor = FakeExecutor(combat, terminal)
    path = tmp_path / "run.jsonl"

    with LiveRunRecorder(path) as recorder:
        result = run_live_game(
            snapshot_provider=provider,
            executor=executor,
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=7),
            max_actions=10,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            run_id="11111111-2222-4333-8444-555555555555",
            now=lambda: NOW,
        )

    assert result.status is LiveRunStatus.TERMINAL
    assert result.actions == 2
    assert result.terminal is True
    assert result.victory is False
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [record["record_type"] for record in records] == [
        "header",
        "step",
        "step",
        "summary",
    ]
    assert [record["selected_action"]["kind"] for record in records[1:3]] == [
        "menu_select",
        "end_turn",
    ]
    assert len({request.request_id for request in executor.requests}) == 2
    assert verify_live_run(path).valid is True

    records[1]["request"]["state_hash"] = "f" * 64
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_text("\n".join(json.dumps(record) for record in records) + "\n")
    verification = verify_live_run(tampered)
    assert verification.valid is False
    assert "step 0: request is not bound to its snapshot" in verification.errors


def test_live_loop_stops_without_acting_on_unsupported_state(tmp_path: Path) -> None:
    unsupported = _snapshot("overlay", (), "4", coverage="unsupported")
    executor = FakeExecutor()

    with LiveRunRecorder(tmp_path / "unsupported.jsonl") as recorder:
        path = recorder.path
        result = run_live_game(
            snapshot_provider=SequenceSnapshotProvider(unsupported),
            executor=executor,
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=10,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            now=lambda: NOW,
        )

    assert result.status is LiveRunStatus.UNSUPPORTED
    assert result.actions == 0
    assert executor.requests == []
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert [record["record_type"] for record in records] == [
        "header",
        "unsupported_decision",
        "summary",
    ]
    assert records[1]["source"] == "adapter"
    verification = verify_live_run(path)
    assert verification.valid
    assert verification.unsupported_decisions == 1

    without_accounting = tmp_path / "unsupported-without-accounting.jsonl"
    without_accounting.write_text(
        "\n".join(
            json.dumps(record)
            for record in records
            if record["record_type"] != "unsupported_decision"
        )
        + "\n"
    )
    broken = verify_live_run(without_accounting)
    assert not broken.valid
    assert "unsupported summary requires exactly one unsupported_decision record" in broken.errors


def test_policy_gap_is_recorded_as_an_explicit_unsupported_decision(tmp_path: Path) -> None:
    settings = LegalAction("settings", "menu_select", {"option": "settings"})
    quit_game = LegalAction("quit", "menu_select", {"option": "quit"})
    menu = _snapshot("menu", (settings, quit_game), "f")
    menu_state = {
        "state_type": "menu",
        "menu_screen": "main",
        "options": ["settings", "quit"],
        "terminal": False,
        "victory": False,
    }
    menu = replace(menu, observation=replace(menu.observation, public_state=menu_state))
    path = tmp_path / "policy-gap.jsonl"

    with LiveRunRecorder(path) as recorder:
        result = run_live_game(
            snapshot_provider=SequenceSnapshotProvider(menu),
            executor=FakeExecutor(),
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=10,
            readiness_timeout_seconds=0.01,
            poll_interval_seconds=0.01,
            monotonic=iter((0.0, 1.0)).__next__,
            sleep=lambda _: None,
            now=lambda: NOW,
        )

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert result.status is LiveRunStatus.UNSUPPORTED
    assert records[-2]["record_type"] == "unsupported_decision"
    assert records[-2]["source"] == "policy"
    assert "No safe automated action" in records[-2]["reason"]
    assert verify_live_run(path).valid


def test_non_applied_receipt_stops_without_retry(tmp_path: Path) -> None:
    action = LegalAction("end", "end_turn", {})
    combat = _snapshot("monster", (action,), "5")
    executor = FakeExecutor(status=ReceiptStatus.REJECTED)

    with LiveRunRecorder(tmp_path / "rejected.jsonl") as recorder:
        result = run_live_game(
            snapshot_provider=SequenceSnapshotProvider(combat),
            executor=executor,
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=10,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            now=lambda: NOW,
        )

    assert result.status is LiveRunStatus.STOPPED
    assert result.reason == "action_rejected:fake_stop"
    assert len(executor.requests) == 1


def test_known_not_applied_stale_action_is_replanned_once(tmp_path: Path) -> None:
    first = _snapshot("monster", (LegalAction("old", "end_turn", {}),), "c")
    fresh = _snapshot("monster", (LegalAction("new", "end_turn", {}),), "d")
    terminal = _snapshot("game_over", (), "e", terminal=True, victory=False)
    provider = SequenceSnapshotProvider(first, fresh, terminal)
    executor = StaleThenAppliedExecutor(terminal)

    with LiveRunRecorder(tmp_path / "stale.jsonl") as recorder:
        result = run_live_game(
            snapshot_provider=provider,
            executor=executor,
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=5,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            now=lambda: NOW,
        )

    assert result.status is LiveRunStatus.TERMINAL
    assert result.actions == 2
    assert [request.action_id for request in executor.requests] == ["old", "new"]


def test_character_selection_is_followed_by_confirmation() -> None:
    select = LegalAction("select", "menu_select", {"option": "IRONCLAD"})
    confirm = LegalAction("confirm", "menu_select", {"option": "confirm"})
    snapshot = _snapshot("menu", (select, confirm), "6")
    state = {
        "state_type": "menu",
        "menu_screen": "character_select",
        "characters": [{"id": "IRONCLAD", "locked": False}],
        "terminal": False,
        "victory": False,
    }
    snapshot = replace(snapshot, observation=replace(snapshot.observation, public_state=state))
    policy = WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0)

    assert policy.choose_action(snapshot) == select
    assert policy.choose_action(snapshot) == confirm


def test_main_menu_without_singleplayer_fails_instead_of_guessing() -> None:
    settings = LegalAction("settings", "menu_select", {"option": "settings"})
    quit_game = LegalAction("quit", "menu_select", {"option": "quit"})
    snapshot = _snapshot("menu", (settings, quit_game), "8")
    state = {
        "state_type": "menu",
        "menu_screen": "main",
        "options": ["settings", "quit"],
        "terminal": False,
        "victory": False,
    }
    snapshot = replace(snapshot, observation=replace(snapshot.observation, public_state=state))

    with pytest.raises(ValueError, match="No safe automated action"):
        WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0).choose_action(snapshot)


def test_seeded_random_policy_is_reproducible() -> None:
    actions = tuple(LegalAction(str(index), "choice", {"index": index}) for index in range(5))
    snapshot = _snapshot("event", actions, "7")
    first = WeakLivePolicy(LiveRunStrategy.LEGAL_RANDOM, seed=123)
    second = WeakLivePolicy(LiveRunStrategy.LEGAL_RANDOM, seed=123)

    assert [first.choose_action(snapshot) for _ in range(10)] == [
        second.choose_action(snapshot) for _ in range(10)
    ]


def test_live_loop_waits_through_disabled_character_confirmation(tmp_path: Path) -> None:
    select = LegalAction("select", "menu_select", {"option": "IRONCLAD"})
    confirm = LegalAction("confirm", "menu_select", {"option": "confirm"})
    end = LegalAction("end", "end_turn", {})
    character = _snapshot("menu", (select, confirm), "9")
    character_state = {
        "state_type": "menu",
        "menu_screen": "character_select",
        "characters": [{"id": "IRONCLAD", "locked": False}],
        "terminal": False,
        "victory": False,
    }
    character = replace(
        character, observation=replace(character.observation, public_state=character_state)
    )
    disabled = replace(character, legal_actions=(select,))
    combat = _snapshot("monster", (end,), "a")
    terminal = _snapshot("game_over", (), "b", terminal=True, victory=False)
    provider = SequenceSnapshotProvider(character, disabled, disabled, combat, combat, terminal)
    executor = FakeExecutor(disabled, combat, terminal)

    with LiveRunRecorder(tmp_path / "transition.jsonl") as recorder:
        result = run_live_game(
            snapshot_provider=provider,
            executor=executor,
            recorder=recorder,
            policy=WeakLivePolicy(LiveRunStrategy.DETERMINISTIC, seed=0),
            max_actions=5,
            readiness_timeout_seconds=1.0,
            poll_interval_seconds=0.1,
            now=lambda: NOW,
        )

    assert result.status is LiveRunStatus.TERMINAL
