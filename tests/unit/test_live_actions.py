from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import cast

from spireshift.adapters.sts2mcp import (
    ActionDeliveryTimeout,
    ActionDeliveryUnknown,
    LiveSnapshot,
    Sts2McpStateProjector,
)
from spireshift.core.manifest import load_patch_manifest
from spireshift.core.types import LegalAction
from spireshift.live_actions import (
    BoundAction,
    DeliveryCertainty,
    DurableActionLedger,
    GuardedActionExecutor,
    ReceiptStatus,
)

MANIFEST_PATH = Path("manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json")
SOURCE_FIXTURE = Path("tests/fixtures/sts2mcp-menu-source-v0.4.0.json")


class FakeSnapshotProvider:
    def __init__(self, *snapshots: LiveSnapshot) -> None:
        self.snapshots = list(snapshots)
        self.reads = 0

    def snapshot(self) -> LiveSnapshot:
        self.reads += 1
        if len(self.snapshots) > 1:
            return self.snapshots.pop(0)
        return self.snapshots[0]


class FakeActionTransport:
    def __init__(
        self,
        response: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response: dict[str, object] = (
            {"status": "ok", "message": "accepted"} if response is None else response
        )
        self.error = error
        self.calls: list[LegalAction] = []

    def deliver_action(self, action: LegalAction) -> dict[str, object]:
        self.calls.append(action)
        if self.error is not None:
            raise self.error
        return copy.deepcopy(self.response)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds


def _source(message: str) -> dict[str, object]:
    value = json.loads(SOURCE_FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    value["message"] = message
    return cast(dict[str, object], value)


def _snapshot(message: str = "before") -> LiveSnapshot:
    projector = Sts2McpStateProjector(load_patch_manifest(MANIFEST_PATH))
    return projector.project(_source(message), bridge_version="0.4.0")


def _request(
    snapshot: LiveSnapshot,
    *,
    request_id: str = "11111111-2222-4333-8444-555555555555",
    action_id: str | None = None,
    state_hash: str | None = None,
    manifest_id: str | None = None,
) -> BoundAction:
    return BoundAction(
        request_id=request_id,
        manifest_id=manifest_id or snapshot.ruleset.manifest_id,
        patch_id=snapshot.ruleset.patch_id,
        state_hash=state_hash or snapshot.observation.state_hash,
        action_id=action_id or snapshot.legal_actions[0].action_id,
    )


def _executor(
    tmp_path: Path,
    provider: FakeSnapshotProvider,
    transport: FakeActionTransport,
    *,
    clock: FakeClock | None = None,
) -> GuardedActionExecutor:
    fake_clock = FakeClock() if clock is None else clock
    return GuardedActionExecutor(
        snapshot_provider=provider,
        action_transport=transport,
        ledger=DurableActionLedger(tmp_path),
        settle_timeout_seconds=0.25,
        settle_quiet_seconds=0.1,
        poll_interval_seconds=0.1,
        monotonic=fake_clock.monotonic,
        sleep=fake_clock.sleep,
        now=lambda: "2026-09-20T00:00:00Z",
    )


def test_bound_action_binds_only_an_advertised_ready_action() -> None:
    snapshot_document = json.loads(Path("tests/fixtures/live-snapshot-v1.json").read_text())
    action_id = snapshot_document["legal_actions"][0]["action_id"]

    request = BoundAction.bind(
        snapshot_document,
        action_id,
        request_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
    )

    assert request == BoundAction.from_mapping(request.as_dict())
    assert request.action_id == action_id


def test_applied_action_has_stable_successor_and_is_not_redelivered(tmp_path: Path) -> None:
    before = _snapshot("before")
    after = _snapshot("after")
    provider = FakeSnapshotProvider(before, after, after)
    transport = FakeActionTransport()
    executor = _executor(tmp_path, provider, transport)
    request = _request(before)

    receipt = executor.execute(request, dry_run=False)
    duplicate = executor.execute(request, dry_run=False)

    assert receipt.status is ReceiptStatus.APPLIED
    assert receipt.delivery_certainty is DeliveryCertainty.APPLIED
    assert receipt.successor_snapshot == after.as_dict()
    assert duplicate.status is ReceiptStatus.DUPLICATE
    assert duplicate.delivery_certainty is DeliveryCertainty.APPLIED
    assert len(transport.calls) == 1
    records = [
        json.loads(line) for line in (tmp_path / "action-ledger.jsonl").read_text().splitlines()
    ]
    assert [record["record_type"] for record in records] == [
        "prepared",
        "receipt",
        "receipt",
    ]


def test_acknowledged_character_selection_can_have_no_public_delta(tmp_path: Path) -> None:
    current = _snapshot()
    provider = FakeSnapshotProvider(current)
    transport = FakeActionTransport(
        {"status": "ok", "message": "Selected The Ironclad. Use 'confirm' to embark."}
    )
    executor = _executor(tmp_path, provider, transport)

    receipt = executor.execute(_request(current), dry_run=False)

    assert receipt.status is ReceiptStatus.APPLIED
    assert receipt.reason == "connector_acknowledged_no_public_delta"
    assert receipt.successor_snapshot == current.as_dict()
    assert len(transport.calls) == 1


def test_acknowledged_dialogue_advance_can_have_no_public_delta(tmp_path: Path) -> None:
    current = replace(
        _snapshot(),
        observation=replace(
            _snapshot().observation,
            public_state={
                "state_type": "event",
                "event": {"in_dialogue": True},
                "terminal": False,
                "victory": False,
            },
        ),
        legal_actions=(LegalAction("advance", "advance_dialogue", {}),),
    )
    provider = FakeSnapshotProvider(current)
    transport = FakeActionTransport({"status": "ok", "message": "Advancing dialogue"})
    executor = _executor(tmp_path, provider, transport)

    receipt = executor.execute(_request(current), dry_run=False)

    assert receipt.status is ReceiptStatus.APPLIED
    assert receipt.reason == "connector_acknowledged_no_public_delta"
    assert len(transport.calls) == 1


def test_executor_waits_past_a_transient_partial_successor(tmp_path: Path) -> None:
    before = _snapshot("before")
    transient = replace(
        _snapshot("transitioning"),
        action_coverage_status="partial",
        action_coverage_issues=("outside player phase",),
    )
    ready = _snapshot("ready")
    provider = FakeSnapshotProvider(before, transient, ready, ready)
    executor = _executor(tmp_path, provider, FakeActionTransport())

    receipt = executor.execute(_request(before), dry_run=False)

    assert receipt.status is ReceiptStatus.APPLIED
    assert receipt.successor_snapshot == ready.as_dict()


def test_stale_action_is_never_delivered(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport()
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)

    receipt = executor.execute(_request(current, state_hash="f" * 64), dry_run=False)

    assert receipt.status is ReceiptStatus.STALE
    assert receipt.delivery_certainty is DeliveryCertainty.NOT_APPLIED
    assert transport.calls == []


def test_illegal_action_and_ruleset_mismatch_are_rejected(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport()
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)

    illegal = executor.execute(
        _request(
            current, action_id="not-advertised", request_id="11111111-2222-4333-8444-555555555555"
        ),
        dry_run=False,
    )
    mismatched = executor.execute(
        _request(
            current,
            request_id="21111111-2222-4333-8444-555555555555",
            manifest_id="sha256:" + "f" * 64,
        ),
        dry_run=False,
    )

    assert illegal.status is ReceiptStatus.REJECTED
    assert illegal.reason == "illegal_action"
    assert mismatched.status is ReceiptStatus.REJECTED
    assert mismatched.reason == "ruleset_mismatch"
    assert transport.calls == []


def test_incomplete_action_coverage_is_unsupported(tmp_path: Path) -> None:
    ready = _snapshot()
    partial = replace(
        ready,
        action_coverage_status="partial",
        action_coverage_issues=("fixture gap",),
    )
    transport = FakeActionTransport()
    executor = _executor(tmp_path, FakeSnapshotProvider(partial), transport)

    receipt = executor.execute(_request(ready), dry_run=False)

    assert receipt.status is ReceiptStatus.UNSUPPORTED
    assert receipt.reason == "incomplete_action_coverage"
    assert transport.calls == []


def test_dry_run_is_durable_and_does_not_deliver(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport()
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)
    request = _request(current)

    receipt = executor.execute(request, dry_run=True)
    duplicate = executor.execute(request, dry_run=False)

    assert receipt.status is ReceiptStatus.DRY_RUN
    assert duplicate.status is ReceiptStatus.DUPLICATE
    assert duplicate.delivery_certainty is DeliveryCertainty.NOT_APPLIED
    assert transport.calls == []


def test_bridge_rejection_is_known_not_applied(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport({"status": "error", "error": "disabled"})
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)

    receipt = executor.execute(_request(current), dry_run=False)

    assert receipt.status is ReceiptStatus.REJECTED
    assert receipt.reason == "bridge_rejected"
    assert receipt.delivery_certainty is DeliveryCertainty.NOT_APPLIED
    assert len(transport.calls) == 1


def test_unknown_delivery_latches_recovery_and_blocks_new_requests(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport(error=ActionDeliveryUnknown("connection reset"))
    ledger = DurableActionLedger(tmp_path)
    executor = GuardedActionExecutor(
        snapshot_provider=FakeSnapshotProvider(current),
        action_transport=transport,
        ledger=ledger,
        now=lambda: "2026-09-20T00:00:00Z",
    )

    uncertain = executor.execute(_request(current), dry_run=False)
    blocked = executor.execute(
        _request(current, request_id="21111111-2222-4333-8444-555555555555"),
        dry_run=False,
    )

    assert uncertain.status is ReceiptStatus.UNKNOWN_DELIVERY
    assert uncertain.delivery_certainty is DeliveryCertainty.UNKNOWN
    assert blocked.status is ReceiptStatus.REJECTED
    assert blocked.reason == "recovery_required"
    assert ledger.safety_status()["recovery_required"] is True
    assert len(transport.calls) == 1


def test_delivery_timeout_is_uncertain_and_never_retried(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport(error=ActionDeliveryTimeout("timed out"))
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)
    request = _request(current)

    timed_out = executor.execute(request, dry_run=False)
    duplicate = executor.execute(request, dry_run=False)

    assert timed_out.status is ReceiptStatus.TIMEOUT
    assert timed_out.delivery_certainty is DeliveryCertainty.UNKNOWN
    assert duplicate.status is ReceiptStatus.DUPLICATE
    assert duplicate.delivery_certainty is DeliveryCertainty.UNKNOWN
    assert len(transport.calls) == 1


def test_successor_timeout_is_uncertain(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport()
    clock = FakeClock()
    executor = _executor(
        tmp_path,
        FakeSnapshotProvider(current),
        transport,
        clock=clock,
    )

    receipt = executor.execute(_request(current), dry_run=False)

    assert receipt.status is ReceiptStatus.TIMEOUT
    assert receipt.reason == "successor_timeout"
    assert receipt.delivery_certainty is DeliveryCertainty.UNKNOWN
    assert len(transport.calls) == 1


def test_emergency_stop_and_concurrent_writer_fail_closed(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport()
    ledger = DurableActionLedger(tmp_path)
    ledger.emergency_stop()
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)

    stopped = executor.execute(_request(current), dry_run=False)
    ledger.acknowledge_safety()
    lock = tmp_path / "writer.lock"
    lock.write_text("occupied")
    concurrent = executor.execute(
        _request(current, request_id="21111111-2222-4333-8444-555555555555"),
        dry_run=False,
    )

    assert stopped.status is ReceiptStatus.REJECTED
    assert stopped.reason == "emergency_stop"
    assert concurrent.status is ReceiptStatus.REJECTED
    assert concurrent.reason == "concurrent_writer"
    assert transport.calls == []


def test_request_id_collision_does_not_corrupt_original_receipt(tmp_path: Path) -> None:
    current = _snapshot()
    transport = FakeActionTransport()
    executor = _executor(tmp_path, FakeSnapshotProvider(current), transport)
    original = _request(current)
    collision = replace(original, action_id=current.legal_actions[1].action_id)

    first = executor.execute(original, dry_run=True)
    rejected = executor.execute(collision, dry_run=True)
    replay = executor.execute(original, dry_run=False)

    assert first.status is ReceiptStatus.DRY_RUN
    assert rejected.status is ReceiptStatus.REJECTED
    assert rejected.reason == "request_id_collision"
    assert replay.status is ReceiptStatus.DUPLICATE
    assert transport.calls == []
