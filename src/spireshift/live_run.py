from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4, uuid5

from spireshift.adapters.sts2mcp import LiveSnapshot
from spireshift.core.types import LegalAction
from spireshift.live_actions import (
    ActionReceipt,
    BoundAction,
    DeliveryCertainty,
    ReceiptStatus,
)

LIVE_RUN_SCHEMA_VERSION = "live-run-v1"


class LiveRunStrategy(StrEnum):
    DETERMINISTIC = "deterministic"
    LEGAL_RANDOM = "legal-random"


class LiveRunStatus(StrEnum):
    TERMINAL = "terminal"
    ACTION_LIMIT = "action_limit"
    STOPPED = "stopped"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class SnapshotProvider(Protocol):
    def snapshot(self) -> LiveSnapshot: ...


class ActionExecutor(Protocol):
    def execute(self, request: BoundAction, *, dry_run: bool) -> ActionReceipt: ...


@dataclass(frozen=True, slots=True)
class LiveRunResult:
    run_id: str
    status: LiveRunStatus
    reason: str
    actions: int
    terminal: bool
    victory: bool | None
    record_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": LIVE_RUN_SCHEMA_VERSION,
            "run_id": self.run_id,
            "status": self.status.value,
            "reason": self.reason,
            "actions": self.actions,
            "terminal": self.terminal,
            "victory": self.victory,
            "record_path": str(self.record_path),
        }


@dataclass(frozen=True, slots=True)
class LiveRunVerification:
    valid: bool
    records: int
    steps: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "live-run-verification-v1",
            "valid": self.valid,
            "records": self.records,
            "steps": self.steps,
            "errors": list(self.errors),
        }


class LiveRunRecorder:
    """Crash-tolerant append-only record for one live run attempt."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("x", encoding="utf-8")

    def append(self, record_type: str, payload: dict[str, object]) -> None:
        value = {"record_type": record_type, **payload}
        self._handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")))
        self._handle.write("\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> LiveRunRecorder:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class WeakLivePolicy:
    """A deliberately weak policy for validating the live automation path."""

    def __init__(self, strategy: LiveRunStrategy, *, seed: int) -> None:
        self.strategy = strategy
        self.seed = seed
        self._random = random.Random(seed)
        self._character_selected = False

    @property
    def policy_id(self) -> str:
        return f"weak-live-{self.strategy.value}-v1"

    def choose_action(self, snapshot: LiveSnapshot) -> LegalAction:
        actions = snapshot.legal_actions
        if not actions:
            raise ValueError("Weak live policy cannot act without legal actions")

        state = snapshot.observation.public_state
        state_type = state.get("state_type")
        if state_type == "menu":
            return self._choose_menu_action(state, actions)

        safe_progress = self._safe_progress_action(str(state_type), actions)
        if safe_progress is not None:
            return safe_progress
        if self.strategy is LiveRunStrategy.LEGAL_RANDOM:
            return self._random.choice(actions)
        return actions[0]

    def _choose_menu_action(
        self, state: dict[str, object], actions: Sequence[LegalAction]
    ) -> LegalAction:
        screen = state.get("menu_screen")
        if screen == "character_select":
            if not self._character_selected:
                raw_characters = state.get("characters")
                characters = raw_characters if isinstance(raw_characters, list) else []
                character_ids = {
                    item.get("id")
                    for item in characters
                    if isinstance(item, dict)
                    and isinstance(item.get("id"), str)
                    and item.get("locked") is not True
                }
                for action in actions:
                    if action.payload.get("option") in character_ids:
                        self._character_selected = True
                        return action
            confirmation = _menu_option(actions, ("confirm", "embark"))
            if confirmation is not None:
                return confirmation

        preferred_by_screen = {
            "main": ("singleplayer",),
            "singleplayer": ("standard",),
            "profile_select": ("profile_1", "profile 1"),
            "tutorial_prompt": ("no",),
            "timeline": ("back",),
        }
        preferred = preferred_by_screen.get(str(screen), ())
        selected = _menu_option(actions, preferred)
        if selected is not None:
            return selected
        if preferred:
            raise ValueError(f"No safe automated action is available on menu screen {screen!r}")
        fallback = _menu_option(
            actions,
            ("continue", "confirm", "embark", "proceed", "ok", "yes", "no", "back"),
        )
        if fallback is not None:
            return fallback
        raise ValueError(f"Unaudited menu screen {screen!r} has no safe fallback action")

    def _safe_progress_action(
        self, state_type: str, actions: Sequence[LegalAction]
    ) -> LegalAction | None:
        kinds = {action.kind: action for action in actions}
        if state_type == "hand_select":
            return kinds.get("combat_confirm_selection")
        if state_type == "card_select":
            return kinds.get("confirm_selection") or kinds.get("cancel_selection")
        if state_type == "bundle_select":
            return kinds.get("confirm_bundle_selection") or kinds.get("cancel_bundle_selection")
        if state_type == "crystal_sphere":
            return kinds.get("crystal_sphere_proceed")
        return None


def run_live_game(
    *,
    snapshot_provider: SnapshotProvider,
    executor: ActionExecutor,
    recorder: LiveRunRecorder,
    policy: WeakLivePolicy,
    max_actions: int,
    readiness_timeout_seconds: float,
    poll_interval_seconds: float,
    max_stale_replans: int = 3,
    run_id: str | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], str] | None = None,
) -> LiveRunResult:
    if max_actions <= 0:
        raise ValueError("max_actions must be positive")
    if readiness_timeout_seconds <= 0:
        raise ValueError("readiness_timeout_seconds must be positive")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")
    if max_stale_replans < 0:
        raise ValueError("max_stale_replans cannot be negative")
    clock_now = _utc_now if now is None else now
    canonical_run_id = str(uuid4()) if run_id is None else str(UUID(run_id))
    started_at = clock_now()
    actions_taken = 0
    last_snapshot: LiveSnapshot | None = None
    consecutive_stale_replans = 0

    try:
        last_snapshot = snapshot_provider.snapshot()
        recorder.append(
            "header",
            {
                "schema_version": LIVE_RUN_SCHEMA_VERSION,
                "run_id": canonical_run_id,
                "started_at": started_at,
                "policy_id": policy.policy_id,
                "strategy": policy.strategy.value,
                "seed": policy.seed,
                "max_actions": max_actions,
                "max_stale_replans": max_stale_replans,
                "ruleset": last_snapshot.ruleset.as_dict(),
                "initial_snapshot": last_snapshot.as_dict(),
            },
        )

        while actions_taken < max_actions:
            snapshot = _wait_until_ready(
                last_snapshot,
                snapshot_provider=snapshot_provider,
                timeout_seconds=readiness_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                monotonic=monotonic,
                sleep=sleep,
            )
            last_snapshot = snapshot
            terminal = bool(snapshot.observation.public_state.get("terminal"))
            if terminal:
                return _finish(
                    recorder,
                    canonical_run_id,
                    LiveRunStatus.TERMINAL,
                    "terminal_state_observed",
                    actions_taken,
                    snapshot,
                    started_at,
                    clock_now(),
                )
            if snapshot.action_coverage_status == "unsupported":
                return _finish(
                    recorder,
                    canonical_run_id,
                    LiveRunStatus.UNSUPPORTED,
                    "; ".join(snapshot.action_coverage_issues) or "unsupported_state",
                    actions_taken,
                    snapshot,
                    started_at,
                    clock_now(),
                )
            if snapshot.action_coverage_status != "ready":
                return _finish(
                    recorder,
                    canonical_run_id,
                    LiveRunStatus.STOPPED,
                    "readiness_timeout",
                    actions_taken,
                    snapshot,
                    started_at,
                    clock_now(),
                )

            snapshot, action = _wait_for_policy_action(
                snapshot,
                snapshot_provider=snapshot_provider,
                policy=policy,
                timeout_seconds=readiness_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                monotonic=monotonic,
                sleep=sleep,
            )
            last_snapshot = snapshot
            request_id = str(
                uuid5(
                    UUID(canonical_run_id),
                    f"{actions_taken}:{snapshot.observation.state_hash}:{action.action_id}",
                )
            )
            request = BoundAction.bind(snapshot.as_dict(), action.action_id, request_id=request_id)
            action_started = monotonic()
            receipt = executor.execute(request, dry_run=False)
            latency_ms = round((monotonic() - action_started) * 1000, 3)
            recorder.append(
                "step",
                {
                    "decision_index": actions_taken,
                    "observed_at": clock_now(),
                    "snapshot": snapshot.as_dict(),
                    "legal_actions": [candidate.as_dict() for candidate in snapshot.legal_actions],
                    "selected_action": action.as_dict(),
                    "request": request.as_dict(),
                    "receipt": receipt.as_dict(),
                    "latency_ms": latency_ms,
                    "stale_replan_index": consecutive_stale_replans,
                },
            )
            actions_taken += 1
            if (
                receipt.status is ReceiptStatus.STALE
                and receipt.reason == "stale_snapshot"
                and receipt.delivery_certainty is DeliveryCertainty.NOT_APPLIED
                and consecutive_stale_replans < max_stale_replans
            ):
                consecutive_stale_replans += 1
                last_snapshot = snapshot_provider.snapshot()
                continue
            if receipt.status is not ReceiptStatus.APPLIED:
                return _finish(
                    recorder,
                    canonical_run_id,
                    LiveRunStatus.STOPPED,
                    f"action_{receipt.status.value}:{receipt.reason}",
                    actions_taken,
                    snapshot,
                    started_at,
                    clock_now(),
                )
            consecutive_stale_replans = 0
            last_snapshot = snapshot_provider.snapshot()

        return _finish(
            recorder,
            canonical_run_id,
            LiveRunStatus.ACTION_LIMIT,
            "maximum_action_count_reached",
            actions_taken,
            last_snapshot,
            started_at,
            clock_now(),
        )
    except Exception as error:
        recorder.append(
            "failure",
            {
                "run_id": canonical_run_id,
                "actions": actions_taken,
                "error_type": type(error).__name__,
                "error": str(error),
                "observed_at": clock_now(),
                "last_snapshot": None if last_snapshot is None else last_snapshot.as_dict(),
            },
        )
        return _finish(
            recorder,
            canonical_run_id,
            LiveRunStatus.ERROR,
            f"{type(error).__name__}:{error}",
            actions_taken,
            last_snapshot,
            started_at,
            clock_now(),
        )


def verify_live_run(path: Path) -> LiveRunVerification:
    errors: list[str] = []
    records: list[dict[str, object]] = []
    try:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            value = json.loads(line)
            if not isinstance(value, dict):
                errors.append(f"line {line_number}: record must be an object")
                continue
            records.append(value)
    except (OSError, json.JSONDecodeError) as error:
        return LiveRunVerification(False, len(records), 0, (str(error),))

    if not records:
        return LiveRunVerification(False, 0, 0, ("run record is empty",))
    if records[0].get("record_type") != "header":
        errors.append("first record must be a header")
    if records[-1].get("record_type") != "summary":
        errors.append("last record must be a summary")
    header_run_id = records[0].get("run_id")
    steps = [record for record in records if record.get("record_type") == "step"]
    request_ids: set[object] = set()
    for index, step in enumerate(steps):
        label = f"step {index}"
        if step.get("decision_index") != index:
            errors.append(f"{label}: decision_index is not contiguous")
        snapshot = _record_mapping(step.get("snapshot"), label, "snapshot", errors)
        observation = _record_mapping(snapshot.get("observation"), label, "observation", errors)
        state_hash = observation.get("state_hash")
        public_state = observation.get("public_state")
        if isinstance(public_state, dict) and isinstance(state_hash, str):
            encoded = json.dumps(
                public_state, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            if hashlib.sha256(encoded).hexdigest() != state_hash:
                errors.append(f"{label}: snapshot state hash does not match public state")
        request = _record_mapping(step.get("request"), label, "request", errors)
        action = _record_mapping(step.get("selected_action"), label, "selected_action", errors)
        if request.get("state_hash") != state_hash:
            errors.append(f"{label}: request is not bound to its snapshot")
        if request.get("action_id") != action.get("action_id"):
            errors.append(f"{label}: request and selected action IDs differ")
        legal_actions = step.get("legal_actions")
        if not isinstance(legal_actions, list) or action not in legal_actions:
            errors.append(f"{label}: selected action is absent from legal actions")
        request_id = request.get("request_id")
        if request_id in request_ids:
            errors.append(f"{label}: request_id is not unique")
        request_ids.add(request_id)
        receipt = _record_mapping(step.get("receipt"), label, "receipt", errors)
        if receipt.get("request") != request:
            errors.append(f"{label}: receipt does not contain the exact request")
        if receipt.get("status") == ReceiptStatus.APPLIED.value:
            if receipt.get("delivery_certainty") != DeliveryCertainty.APPLIED.value:
                errors.append(f"{label}: applied receipt lacks applied certainty")
            if not isinstance(receipt.get("successor_snapshot"), dict):
                errors.append(f"{label}: applied receipt lacks a successor snapshot")

    summary = records[-1]
    if summary.get("run_id") != header_run_id:
        errors.append("summary run_id differs from header")
    if summary.get("actions") != len(steps):
        errors.append("summary action count differs from recorded steps")
    return LiveRunVerification(not errors, len(records), len(steps), tuple(errors))


def _wait_until_ready(
    snapshot: LiveSnapshot,
    *,
    snapshot_provider: SnapshotProvider,
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> LiveSnapshot:
    if snapshot.action_coverage_status in {"ready", "unsupported"} or bool(
        snapshot.observation.public_state.get("terminal")
    ):
        return snapshot
    deadline = monotonic() + timeout_seconds
    current = snapshot
    while monotonic() <= deadline:
        sleep(poll_interval_seconds)
        current = snapshot_provider.snapshot()
        if current.action_coverage_status in {"ready", "unsupported"} or bool(
            current.observation.public_state.get("terminal")
        ):
            return current
    return current


def _wait_for_policy_action(
    snapshot: LiveSnapshot,
    *,
    snapshot_provider: SnapshotProvider,
    policy: WeakLivePolicy,
    timeout_seconds: float,
    poll_interval_seconds: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> tuple[LiveSnapshot, LegalAction]:
    deadline = monotonic() + timeout_seconds
    current = snapshot
    first_error: ValueError | None = None
    while True:
        if current.action_coverage_status == "ready" and not bool(
            current.observation.public_state.get("terminal")
        ):
            try:
                return current, policy.choose_action(current)
            except ValueError as error:
                if first_error is None:
                    first_error = error
        if monotonic() > deadline:
            if first_error is not None:
                raise first_error
            raise ValueError("No policy action became available before the readiness timeout")
        sleep(poll_interval_seconds)
        current = snapshot_provider.snapshot()


def _finish(
    recorder: LiveRunRecorder,
    run_id: str,
    status: LiveRunStatus,
    reason: str,
    actions: int,
    snapshot: LiveSnapshot | None,
    started_at: str,
    completed_at: str,
) -> LiveRunResult:
    terminal = bool(
        snapshot is not None and snapshot.observation.public_state.get("terminal") is True
    )
    raw_victory = snapshot.observation.public_state.get("victory") if snapshot is not None else None
    victory = raw_victory if isinstance(raw_victory, bool) else None
    recorder.append(
        "summary",
        {
            "schema_version": LIVE_RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "status": status.value,
            "reason": reason,
            "actions": actions,
            "terminal": terminal,
            "victory": victory,
            "started_at": started_at,
            "completed_at": completed_at,
            "final_snapshot": None if snapshot is None else snapshot.as_dict(),
        },
    )
    return LiveRunResult(
        run_id=run_id,
        status=status,
        reason=reason,
        actions=actions,
        terminal=terminal,
        victory=victory,
        record_path=recorder.path,
    )


def _menu_option(actions: Sequence[LegalAction], preferred: Sequence[str]) -> LegalAction | None:
    normalized = tuple(value.casefold().replace(" ", "_") for value in preferred)
    for wanted in normalized:
        for action in actions:
            option = action.payload.get("option")
            if isinstance(option, str) and option.casefold().replace(" ", "_") == wanted:
                return action
    return None


def _record_mapping(
    value: object,
    label: str,
    field: str,
    errors: list[str],
) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    errors.append(f"{label}: {field} must be an object")
    return {}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
