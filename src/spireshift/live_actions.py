from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol, cast
from uuid import UUID, uuid4

from spireshift.adapters.sts2mcp import (
    ActionDeliveryTimeout,
    ActionDeliveryUnknown,
    LiveSnapshot,
    LiveStateError,
)
from spireshift.core.types import LegalAction

BOUND_ACTION_SCHEMA_VERSION = "bound-action-v1"
ACTION_RECEIPT_SCHEMA_VERSION = "action-receipt-v1"
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_MANIFEST_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


class LiveActionError(RuntimeError):
    """A guarded live-action operation could not proceed safely."""


class ConcurrentWriterError(LiveActionError):
    """Another action writer owns the durable ledger lock."""


class ReceiptStatus(StrEnum):
    APPLIED = "applied"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    STALE = "stale"
    UNKNOWN_DELIVERY = "unknown_delivery"
    TIMEOUT = "timeout"
    UNSUPPORTED = "unsupported"
    DRY_RUN = "dry_run"


class DeliveryCertainty(StrEnum):
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class BoundAction:
    request_id: str
    manifest_id: str
    patch_id: str
    state_hash: str
    action_id: str

    def __post_init__(self) -> None:
        try:
            canonical_request_id = str(UUID(self.request_id))
        except ValueError as error:
            raise ValueError("request_id must be a UUID") from error
        if canonical_request_id != self.request_id:
            raise ValueError("request_id must use canonical lowercase UUID form")
        if _MANIFEST_PATTERN.fullmatch(self.manifest_id) is None:
            raise ValueError("manifest_id must be a sha256 content identity")
        if not self.patch_id:
            raise ValueError("patch_id must be non-empty")
        if _SHA256_PATTERN.fullmatch(self.state_hash) is None:
            raise ValueError("state_hash must be a lowercase sha256 digest")
        if not self.action_id:
            raise ValueError("action_id must be non-empty")

    @classmethod
    def from_mapping(cls, value: object) -> BoundAction:
        mapping = _mapping(value, "bound action")
        _require_exact_keys(
            mapping,
            {
                "schema_version",
                "request_id",
                "manifest_id",
                "patch_id",
                "state_hash",
                "action_id",
            },
            "bound action",
        )
        if mapping.get("schema_version") != BOUND_ACTION_SCHEMA_VERSION:
            raise ValueError("Unsupported bound action schema")
        return cls(
            request_id=_string(mapping, "request_id", "bound action"),
            manifest_id=_string(mapping, "manifest_id", "bound action"),
            patch_id=_string(mapping, "patch_id", "bound action"),
            state_hash=_string(mapping, "state_hash", "bound action"),
            action_id=_string(mapping, "action_id", "bound action"),
        )

    @classmethod
    def bind(
        cls,
        snapshot: object,
        action_id: str,
        *,
        request_id: str | None = None,
    ) -> BoundAction:
        document = _mapping(snapshot, "live snapshot")
        if document.get("schema_version") != "live-snapshot-v1":
            raise ValueError("Unsupported live snapshot schema")
        ruleset = _mapping(document.get("ruleset"), "live snapshot ruleset")
        observation = _mapping(document.get("observation"), "live snapshot observation")
        coverage = _mapping(document.get("action_coverage"), "live snapshot action coverage")
        if coverage.get("status") != "ready":
            raise ValueError("Cannot bind an action from incomplete action coverage")
        raw_actions = document.get("legal_actions")
        if not isinstance(raw_actions, list):
            raise ValueError("live snapshot legal_actions must be an array")
        matching = [
            item
            for item in raw_actions
            if isinstance(item, Mapping) and item.get("action_id") == action_id
        ]
        if len(matching) != 1:
            raise ValueError("action_id must identify exactly one advertised legal action")
        return cls(
            request_id=str(uuid4()) if request_id is None else request_id,
            manifest_id=_string(ruleset, "manifest_id", "live snapshot ruleset"),
            patch_id=_string(ruleset, "patch_id", "live snapshot ruleset"),
            state_hash=_string(observation, "state_hash", "live snapshot observation"),
            action_id=action_id,
        )

    def as_dict(self) -> dict[str, str]:
        return {
            "schema_version": BOUND_ACTION_SCHEMA_VERSION,
            "request_id": self.request_id,
            "manifest_id": self.manifest_id,
            "patch_id": self.patch_id,
            "state_hash": self.state_hash,
            "action_id": self.action_id,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(
            self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    request: BoundAction
    status: ReceiptStatus
    reason: str
    message: str
    delivery_certainty: DeliveryCertainty
    predecessor_state_hash: str | None
    successor_snapshot: dict[str, object] | None
    bridge_response: dict[str, object] | None
    started_at: str
    completed_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": ACTION_RECEIPT_SCHEMA_VERSION,
            "request": self.request.as_dict(),
            "status": self.status.value,
            "reason": self.reason,
            "message": self.message,
            "delivery_certainty": self.delivery_certainty.value,
            "automatic_retry_safe": False,
            "predecessor_state_hash": self.predecessor_state_hash,
            "successor_snapshot": self.successor_snapshot,
            "bridge_response": self.bridge_response,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class LiveSnapshotProvider(Protocol):
    def snapshot(self) -> LiveSnapshot: ...


class LiveActionTransport(Protocol):
    def deliver_action(self, action: LegalAction) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class _PriorRequest:
    digest: str
    receipt: dict[str, object] | None


class DurableActionLedger:
    """Append-only receipts and a fail-closed single-writer lock."""

    def __init__(self, state_directory: Path) -> None:
        self.state_directory = state_directory
        self.path = state_directory / "action-ledger.jsonl"
        self.lock_path = state_directory / "writer.lock"
        self.stop_path = state_directory / "STOP"

    @contextmanager
    def exclusive(self, owner: str) -> Iterator[None]:
        self.state_directory.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as error:
            raise ConcurrentWriterError(
                f"Live action writer lock already exists: {self.lock_path}"
            ) from error
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"pid": os.getpid(), "owner": owner, "created_at": _utc_now()}, handle)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            yield
        finally:
            with suppress(FileNotFoundError):
                self.lock_path.unlink()

    def append_prepared(self, request: BoundAction, *, created_at: str) -> None:
        self._append(
            {
                "record_type": "prepared",
                "request_digest": request.digest,
                "request": request.as_dict(),
                "created_at": created_at,
            }
        )

    def append_receipt(self, receipt: ActionReceipt) -> None:
        self._append(
            {
                "record_type": "receipt",
                "request_digest": receipt.request.digest,
                "receipt": receipt.as_dict(),
            }
        )

    def append_collision(self, receipt: ActionReceipt, *, existing_digest: str) -> None:
        self._append(
            {
                "record_type": "request_id_collision",
                "existing_request_digest": existing_digest,
                "attempted_request_digest": receipt.request.digest,
                "receipt": receipt.as_dict(),
            }
        )

    def prior_request(self, request_id: str) -> _PriorRequest | None:
        prior: _PriorRequest | None = None
        for record in self._records():
            request: dict[str, object] | None = None
            receipt: dict[str, object] | None = None
            if record.get("record_type") == "prepared":
                raw_request = record.get("request")
                request = (
                    cast(dict[str, object], raw_request) if isinstance(raw_request, dict) else None
                )
            elif record.get("record_type") == "receipt":
                raw_receipt = record.get("receipt")
                receipt = (
                    cast(dict[str, object], raw_receipt) if isinstance(raw_receipt, dict) else None
                )
                if receipt is not None:
                    raw_request = receipt.get("request")
                    request = (
                        cast(dict[str, object], raw_request)
                        if isinstance(raw_request, dict)
                        else None
                    )
            if request is None or request.get("request_id") != request_id:
                continue
            raw_digest = record.get("request_digest")
            if not isinstance(raw_digest, str) or _SHA256_PATTERN.fullmatch(raw_digest) is None:
                raise LiveActionError("Action ledger contains an invalid request digest")
            if prior is None:
                prior = _PriorRequest(raw_digest, receipt)
            elif prior.digest != raw_digest:
                raise LiveActionError("Action ledger contains conflicting request identities")
            elif receipt is not None:
                prior = _PriorRequest(raw_digest, receipt)
        return prior

    def recovery_required(self) -> bool:
        required = False
        for record in self._records():
            if record.get("record_type") == "recovery_acknowledged":
                required = False
                continue
            if record.get("record_type") != "receipt":
                continue
            raw_receipt = record.get("receipt")
            if isinstance(raw_receipt, dict) and raw_receipt.get("status") in {
                ReceiptStatus.TIMEOUT.value,
                ReceiptStatus.UNKNOWN_DELIVERY.value,
            }:
                required = True
        return required

    def emergency_stop(self) -> None:
        self.state_directory.mkdir(parents=True, exist_ok=True)
        with self.stop_path.open("w", encoding="utf-8") as handle:
            handle.write(f"created_at={_utc_now()}\n")
            handle.flush()
            os.fsync(handle.fileno())

    def acknowledge_safety(self) -> None:
        self.stop_path.unlink(missing_ok=True)
        self._append({"record_type": "recovery_acknowledged", "created_at": _utc_now()})

    def safety_status(self) -> dict[str, object]:
        return {
            "state_directory": str(self.state_directory),
            "emergency_stop": self.stop_path.exists(),
            "recovery_required": self.recovery_required(),
            "writer_lock": self.lock_path.exists(),
            "ledger": str(self.path),
        }

    def _records(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        records: list[dict[str, object]] = []
        try:
            with self.path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    value: object = json.loads(line)
                    if not isinstance(value, dict):
                        raise LiveActionError(
                            f"Action ledger line {line_number} is not a JSON object"
                        )
                    records.append(cast(dict[str, object], value))
        except (OSError, json.JSONDecodeError) as error:
            raise LiveActionError(f"Cannot safely read action ledger: {error}") from error
        return records

    def _append(self, record: dict[str, object]) -> None:
        self.state_directory.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as error:
            raise LiveActionError(f"Cannot durably append action ledger: {error}") from error


class GuardedActionExecutor:
    def __init__(
        self,
        *,
        snapshot_provider: LiveSnapshotProvider,
        action_transport: LiveActionTransport,
        ledger: DurableActionLedger,
        settle_timeout_seconds: float = 8.0,
        poll_interval_seconds: float = 0.1,
        stable_reads: int = 2,
        settle_quiet_seconds: float = 0.5,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], str] | None = None,
    ) -> None:
        if settle_timeout_seconds <= 0:
            raise ValueError("settle_timeout_seconds must be positive")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if stable_reads <= 0:
            raise ValueError("stable_reads must be positive")
        if settle_quiet_seconds < 0:
            raise ValueError("settle_quiet_seconds cannot be negative")
        self._snapshot_provider = snapshot_provider
        self._action_transport = action_transport
        self._ledger = ledger
        self._settle_timeout_seconds = settle_timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds
        self._stable_reads = stable_reads
        self._settle_quiet_seconds = settle_quiet_seconds
        self._monotonic = monotonic
        self._sleep = sleep
        self._now = _utc_now if now is None else now

    def execute(self, request: BoundAction, *, dry_run: bool) -> ActionReceipt:
        started_at = self._now()
        try:
            with self._ledger.exclusive(request.request_id):
                return self._execute_locked(request, dry_run=dry_run, started_at=started_at)
        except ConcurrentWriterError as error:
            return self._receipt(
                request,
                ReceiptStatus.REJECTED,
                "concurrent_writer",
                str(error),
                DeliveryCertainty.NOT_APPLIED,
                started_at,
            )

    def _execute_locked(
        self, request: BoundAction, *, dry_run: bool, started_at: str
    ) -> ActionReceipt:
        prior = self._ledger.prior_request(request.request_id)
        if prior is not None:
            if prior.digest != request.digest:
                receipt = self._receipt(
                    request,
                    ReceiptStatus.REJECTED,
                    "request_id_collision",
                    "request_id was already used for a different bound action",
                    DeliveryCertainty.NOT_APPLIED,
                    started_at,
                )
                self._ledger.append_collision(receipt, existing_digest=prior.digest)
            else:
                receipt = self._duplicate_receipt(request, prior, started_at)
                self._ledger.append_receipt(receipt)
            return receipt

        if self._ledger.stop_path.exists():
            return self._record_preflight(
                request,
                ReceiptStatus.REJECTED,
                "emergency_stop",
                f"Emergency stop is active at {self._ledger.stop_path}",
                started_at,
            )
        if self._ledger.recovery_required():
            return self._record_preflight(
                request,
                ReceiptStatus.REJECTED,
                "recovery_required",
                "A prior action has uncertain delivery; acknowledge recovery before continuing",
                started_at,
            )

        try:
            snapshot = self._snapshot_provider.snapshot()
        except LiveStateError as error:
            return self._record_preflight(
                request,
                ReceiptStatus.REJECTED,
                "snapshot_unavailable",
                str(error),
                started_at,
            )

        if (
            request.manifest_id != snapshot.ruleset.manifest_id
            or request.patch_id != snapshot.ruleset.patch_id
        ):
            return self._record_preflight(
                request,
                ReceiptStatus.REJECTED,
                "ruleset_mismatch",
                "Bound action does not match the live ruleset identity",
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
            )
        if request.state_hash != snapshot.observation.state_hash:
            return self._record_preflight(
                request,
                ReceiptStatus.STALE,
                "stale_snapshot",
                "Live state no longer matches the bound snapshot",
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
            )
        if snapshot.action_coverage_status != "ready":
            return self._record_preflight(
                request,
                ReceiptStatus.UNSUPPORTED,
                "incomplete_action_coverage",
                "Live action coverage is not complete for the current screen",
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
            )
        matching = [
            action for action in snapshot.legal_actions if action.action_id == request.action_id
        ]
        if len(matching) != 1:
            return self._record_preflight(
                request,
                ReceiptStatus.REJECTED,
                "illegal_action",
                "Bound action is not in the current legal-action set",
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
            )
        if dry_run:
            return self._record_preflight(
                request,
                ReceiptStatus.DRY_RUN,
                "validated_without_delivery",
                "Bound action passed every guard; no action was delivered",
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
            )

        self._ledger.append_prepared(request, created_at=self._now())
        if self._ledger.stop_path.exists():
            receipt = self._receipt(
                request,
                ReceiptStatus.REJECTED,
                "emergency_stop",
                "Emergency stop became active before delivery",
                DeliveryCertainty.NOT_APPLIED,
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
            )
            self._ledger.append_receipt(receipt)
            return receipt

        try:
            bridge_response = self._action_transport.deliver_action(matching[0])
        except ActionDeliveryTimeout as error:
            return self._record_post_delivery_failure(
                request,
                ReceiptStatus.TIMEOUT,
                "delivery_timeout",
                str(error),
                started_at,
                snapshot.observation.state_hash,
            )
        except ActionDeliveryUnknown as error:
            return self._record_post_delivery_failure(
                request,
                ReceiptStatus.UNKNOWN_DELIVERY,
                "unknown_delivery",
                str(error),
                started_at,
                snapshot.observation.state_hash,
            )

        if bridge_response.get("status") == "error":
            receipt = self._receipt(
                request,
                ReceiptStatus.REJECTED,
                "bridge_rejected",
                _bridge_message(bridge_response),
                DeliveryCertainty.NOT_APPLIED,
                started_at,
                predecessor_state_hash=snapshot.observation.state_hash,
                bridge_response=bridge_response,
            )
            self._ledger.append_receipt(receipt)
            return receipt
        if bridge_response.get("status") != "ok":
            return self._record_post_delivery_failure(
                request,
                ReceiptStatus.UNKNOWN_DELIVERY,
                "invalid_bridge_response",
                "Bridge response did not contain status=ok or status=error",
                started_at,
                snapshot.observation.state_hash,
                bridge_response=bridge_response,
            )

        return self._wait_for_successor(
            request,
            action=matching[0],
            predecessor=snapshot,
            bridge_response=bridge_response,
            started_at=started_at,
        )

    def _wait_for_successor(
        self,
        request: BoundAction,
        *,
        action: LegalAction,
        predecessor: LiveSnapshot,
        bridge_response: dict[str, object],
        started_at: str,
    ) -> ActionReceipt:
        deadline = self._monotonic() + self._settle_timeout_seconds
        settling_started = self._monotonic()
        last_hash: str | None = None
        stable_since: float | None = None
        consecutive_reads = 0
        unchanged_reads = 0
        while self._monotonic() <= deadline:
            try:
                candidate = self._snapshot_provider.snapshot()
            except LiveStateError as error:
                return self._record_post_delivery_failure(
                    request,
                    ReceiptStatus.UNKNOWN_DELIVERY,
                    "successor_read_failed",
                    str(error),
                    started_at,
                    predecessor.observation.state_hash,
                    bridge_response=bridge_response,
                )
            if (
                candidate.ruleset.manifest_id != request.manifest_id
                or candidate.ruleset.patch_id != request.patch_id
            ):
                return self._record_post_delivery_failure(
                    request,
                    ReceiptStatus.UNKNOWN_DELIVERY,
                    "successor_ruleset_changed",
                    "Ruleset identity changed after delivery",
                    started_at,
                    predecessor.observation.state_hash,
                    bridge_response=bridge_response,
                )
            candidate_hash = candidate.observation.state_hash
            observed_at = self._monotonic()
            if candidate_hash != predecessor.observation.state_hash:
                if candidate_hash == last_hash:
                    consecutive_reads += 1
                else:
                    last_hash = candidate_hash
                    consecutive_reads = 1
                    stable_since = observed_at
                if (
                    consecutive_reads >= self._stable_reads
                    and stable_since is not None
                    and observed_at - stable_since >= self._settle_quiet_seconds
                    and candidate.action_coverage_status == "ready"
                ):
                    receipt = self._receipt(
                        request,
                        ReceiptStatus.APPLIED,
                        "successor_observed",
                        "Action was accepted and a stable successor snapshot was observed",
                        DeliveryCertainty.APPLIED,
                        started_at,
                        predecessor_state_hash=predecessor.observation.state_hash,
                        successor_snapshot=candidate.as_dict(),
                        bridge_response=bridge_response,
                    )
                    self._ledger.append_receipt(receipt)
                    return receipt
            else:
                last_hash = None
                consecutive_reads = 0
                unchanged_reads += 1
                if (
                    unchanged_reads >= self._stable_reads
                    and observed_at - settling_started >= self._settle_quiet_seconds
                    and candidate.action_coverage_status == "ready"
                    and _allows_acknowledged_no_public_delta(action, predecessor, bridge_response)
                ):
                    receipt = self._receipt(
                        request,
                        ReceiptStatus.APPLIED,
                        "connector_acknowledged_no_public_delta",
                        "Connector acknowledged a selection that has no public-state delta",
                        DeliveryCertainty.APPLIED,
                        started_at,
                        predecessor_state_hash=predecessor.observation.state_hash,
                        successor_snapshot=candidate.as_dict(),
                        bridge_response=bridge_response,
                    )
                    self._ledger.append_receipt(receipt)
                    return receipt
            self._sleep(self._poll_interval_seconds)

        return self._record_post_delivery_failure(
            request,
            ReceiptStatus.TIMEOUT,
            "successor_timeout",
            "Bridge accepted the action but no stable successor snapshot was observed",
            started_at,
            predecessor.observation.state_hash,
            bridge_response=bridge_response,
        )

    def _record_preflight(
        self,
        request: BoundAction,
        status: ReceiptStatus,
        reason: str,
        message: str,
        started_at: str,
        *,
        predecessor_state_hash: str | None = None,
    ) -> ActionReceipt:
        receipt = self._receipt(
            request,
            status,
            reason,
            message,
            DeliveryCertainty.NOT_APPLIED,
            started_at,
            predecessor_state_hash=predecessor_state_hash,
        )
        self._ledger.append_receipt(receipt)
        return receipt

    def _record_post_delivery_failure(
        self,
        request: BoundAction,
        status: ReceiptStatus,
        reason: str,
        message: str,
        started_at: str,
        predecessor_state_hash: str,
        *,
        bridge_response: dict[str, object] | None = None,
    ) -> ActionReceipt:
        receipt = self._receipt(
            request,
            status,
            reason,
            message,
            DeliveryCertainty.UNKNOWN,
            started_at,
            predecessor_state_hash=predecessor_state_hash,
            bridge_response=bridge_response,
        )
        self._ledger.append_receipt(receipt)
        return receipt

    def _duplicate_receipt(
        self, request: BoundAction, prior: _PriorRequest, started_at: str
    ) -> ActionReceipt:
        if prior.receipt is None:
            return self._receipt(
                request,
                ReceiptStatus.UNKNOWN_DELIVERY,
                "incomplete_prior_delivery",
                "A durable prepared record exists without a final receipt; delivery is uncertain",
                DeliveryCertainty.UNKNOWN,
                started_at,
            )
        prior_status = prior.receipt.get("status")
        certainty_raw = prior.receipt.get("delivery_certainty")
        try:
            certainty = DeliveryCertainty(str(certainty_raw))
        except ValueError:
            certainty = DeliveryCertainty.UNKNOWN
        successor_raw = prior.receipt.get("successor_snapshot")
        successor = (
            cast(dict[str, object], successor_raw) if isinstance(successor_raw, dict) else None
        )
        return self._receipt(
            request,
            ReceiptStatus.DUPLICATE,
            "duplicate_request",
            "request_id already completed with status "
            f"{prior_status!r}; action was not redelivered",
            certainty,
            started_at,
            predecessor_state_hash=_optional_string_value(
                prior.receipt.get("predecessor_state_hash")
            ),
            successor_snapshot=successor,
        )

    def _receipt(
        self,
        request: BoundAction,
        status: ReceiptStatus,
        reason: str,
        message: str,
        certainty: DeliveryCertainty,
        started_at: str,
        *,
        predecessor_state_hash: str | None = None,
        successor_snapshot: dict[str, object] | None = None,
        bridge_response: dict[str, object] | None = None,
    ) -> ActionReceipt:
        return ActionReceipt(
            request=request,
            status=status,
            reason=reason,
            message=message,
            delivery_certainty=certainty,
            predecessor_state_hash=predecessor_state_hash,
            successor_snapshot=successor_snapshot,
            bridge_response=bridge_response,
            started_at=started_at,
            completed_at=self._now(),
        )


def default_live_state_directory() -> Path:
    configured = os.environ.get("XDG_STATE_HOME")
    root = Path(configured).expanduser() if configured else Path.home() / ".local" / "state"
    return root / "spireshift"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _bridge_message(response: dict[str, object]) -> str:
    for key in ("error", "message"):
        value = response.get(key)
        if isinstance(value, str) and value:
            return value
    return "Bridge rejected the action without an error message"


def _allows_acknowledged_no_public_delta(
    action: LegalAction,
    predecessor: LiveSnapshot,
    bridge_response: dict[str, object],
) -> bool:
    public_state = predecessor.observation.public_state
    if (
        action.kind != "menu_select"
        or public_state.get("state_type") != "menu"
        or public_state.get("menu_screen") != "character_select"
    ):
        return False
    option = action.payload.get("option")
    if not isinstance(option, str):
        return False
    characters = public_state.get("characters")
    if not isinstance(characters, list):
        return False
    advertised_character_ids = {
        item.get("id")
        for item in characters
        if isinstance(item, dict) and item.get("locked") is not True
    }
    message = bridge_response.get("message")
    return (
        option in advertised_character_ids
        and isinstance(message, str)
        and message.startswith("Selected ")
    )


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _string(value: Mapping[str, object], key: str, label: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return result


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _require_exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
