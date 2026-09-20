from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift.core.manifest import PatchManifest
from spireshift.live_fixture_audit import REQUIRED_STATE_TYPES, audit_live_fixture_corpus
from spireshift.live_run import LiveRunStatus, verify_live_run

LIVE_COVERAGE_SPEC_SCHEMA_VERSION = "live-action-coverage-spec-v1"
LIVE_COVERAGE_REPORT_SCHEMA_VERSION = "live-action-coverage-v1"


@dataclass(frozen=True, slots=True)
class CoverageCheck:
    check_id: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "check_id": self.check_id,
            "status": "pass" if self.passed else "fail",
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class RunCoverage:
    record_sha256: str
    records: int
    steps: int
    status: str
    reason: str
    terminal: bool
    victory: bool | None
    ruleset_manifest_ids: tuple[str, ...]
    characters: tuple[str, ...]
    ascensions: tuple[int, ...]
    selected_modes: tuple[str, ...]
    floors: tuple[int, ...]
    state_types: tuple[str, ...]
    decision_types: tuple[str, ...]
    advertised_action_kinds: tuple[str, ...]
    selected_action_kinds: tuple[str, ...]
    unsupported_decisions: int
    verification_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "record_sha256": self.record_sha256,
            "records": self.records,
            "steps": self.steps,
            "status": self.status,
            "reason": self.reason,
            "terminal": self.terminal,
            "victory": self.victory,
            "ruleset_manifest_ids": list(self.ruleset_manifest_ids),
            "characters": list(self.characters),
            "ascensions": list(self.ascensions),
            "selected_modes": list(self.selected_modes),
            "floor_range": (
                None
                if not self.floors
                else {"minimum": min(self.floors), "maximum": max(self.floors)}
            ),
            "state_types": list(self.state_types),
            "decision_types": list(self.decision_types),
            "advertised_action_kinds": list(self.advertised_action_kinds),
            "selected_action_kinds": list(self.selected_action_kinds),
            "unsupported_decisions": self.unsupported_decisions,
            "verification_errors": list(self.verification_errors),
        }


@dataclass(frozen=True, slots=True)
class LiveCoverageReport:
    valid: bool
    verdict: str
    coverage_id: str
    scope: dict[str, object]
    manifest_id: str
    fixture_corpus_sha256: str
    fixture_count: int
    enumerated_state_types: tuple[str, ...]
    enumerated_decision_types: tuple[str, ...]
    enumerated_action_kinds: tuple[str, ...]
    runs: tuple[RunCoverage, ...]
    checks: tuple[CoverageCheck, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": LIVE_COVERAGE_REPORT_SCHEMA_VERSION,
            "valid": self.valid,
            "verdict": self.verdict,
            "coverage_id": self.coverage_id,
            "scope": self.scope,
            "ruleset_manifest_id": self.manifest_id,
            "fixture_evidence": {
                "corpus_sha256": self.fixture_corpus_sha256,
                "fixtures": self.fixture_count,
                "state_types": list(self.enumerated_state_types),
                "decision_types": list(self.enumerated_decision_types),
                "action_kinds": list(self.enumerated_action_kinds),
            },
            "run_evidence": {
                "runs": len(self.runs),
                "terminal_runs": sum(
                    run.status == LiveRunStatus.TERMINAL.value for run in self.runs
                ),
                "unsupported_runs": sum(
                    run.status == LiveRunStatus.UNSUPPORTED.value for run in self.runs
                ),
                "unsupported_decisions": sum(run.unsupported_decisions for run in self.runs),
                "records": sum(run.records for run in self.runs),
                "steps": sum(run.steps for run in self.runs),
                "details": [run.as_dict() for run in self.runs],
            },
            "checks": [check.as_dict() for check in self.checks],
        }


def audit_full_run_action_coverage(
    *,
    specification_path: Path,
    fixture_corpus_path: Path,
    run_paths: tuple[Path, ...],
    manifest: PatchManifest,
) -> LiveCoverageReport:
    specification = _load_object(specification_path)
    if specification.get("schema_version") != LIVE_COVERAGE_SPEC_SCHEMA_VERSION:
        raise ValueError(f"Coverage specification must use {LIVE_COVERAGE_SPEC_SCHEMA_VERSION!r}")
    coverage_id = _required_string(specification, "coverage_id", "coverage specification")
    expected_manifest_id = _required_string(
        specification, "ruleset_manifest_id", "coverage specification"
    )
    scope = _mapping(specification.get("scope"), "coverage specification scope")
    expected_character = _required_string(scope, "character", "coverage specification scope")
    difficulty = _mapping(scope.get("difficulty"), "coverage specification difficulty")
    expected_mode = _required_string(difficulty, "mode", "coverage specification difficulty")
    expected_ascension = difficulty.get("ascension")
    if not isinstance(expected_ascension, int) or isinstance(expected_ascension, bool):
        raise ValueError("coverage specification difficulty.ascension must be an integer")
    minimum_terminal_runs = specification.get("minimum_terminal_runs")
    if not isinstance(minimum_terminal_runs, int) or minimum_terminal_runs < 1:
        raise ValueError("coverage specification minimum_terminal_runs must be positive")
    required_state_types = _string_set(specification, "required_state_types")
    required_decision_types = _string_set(specification, "required_decision_types")
    required_action_kinds = _string_set(specification, "required_action_kinds")

    fixture_audit = audit_live_fixture_corpus(fixture_corpus_path, manifest)
    fixture_document = _load_object(fixture_corpus_path)
    fixtures = fixture_document.get("fixtures")
    if not isinstance(fixtures, list):
        fixtures = []
    enumerated_action_kinds = sorted(
        {
            kind
            for fixture in fixtures
            if isinstance(fixture, dict)
            for action in _expected_actions(fixture)
            if isinstance((kind := action.get("kind")), str)
        }
    )
    enumerated_decision_types = sorted(
        {
            decision_type
            for fixture in fixtures
            if isinstance(fixture, dict)
            and isinstance((expected := fixture.get("expected")), dict)
            and isinstance((decision_type := expected.get("decision_type")), str)
        }
    )

    runs = tuple(_audit_run(path) for path in run_paths)
    all_characters = {character for run in runs for character in run.characters}
    all_ascensions = {ascension for run in runs for ascension in run.ascensions}
    all_selected_modes = {mode for run in runs for mode in run.selected_modes}
    terminal_runs = sum(run.status == LiveRunStatus.TERMINAL.value for run in runs)
    unsupported_runs = sum(run.status == LiveRunStatus.UNSUPPORTED.value for run in runs)
    unsupported_decisions = sum(run.unsupported_decisions for run in runs)
    allowed_outcomes = {LiveRunStatus.TERMINAL.value, LiveRunStatus.UNSUPPORTED.value}

    checks = (
        CoverageCheck(
            "ruleset_identity",
            expected_manifest_id == manifest.manifest_id,
            "Coverage specification and selected manifest identities match."
            if expected_manifest_id == manifest.manifest_id
            else "Coverage specification and selected manifest identities differ.",
        ),
        CoverageCheck(
            "fixture_oracles",
            fixture_audit.valid,
            f"{sum(result.valid for result in fixture_audit.results)}/"
            f"{len(fixture_audit.results)} exact fixture oracles pass.",
        ),
        CoverageCheck(
            "actionable_state_types",
            set(fixture_audit.covered_state_types) == required_state_types == REQUIRED_STATE_TYPES,
            f"{len(fixture_audit.covered_state_types)}/{len(REQUIRED_STATE_TYPES)} "
            "actionable state types are enumerated.",
        ),
        CoverageCheck(
            "decision_types",
            set(enumerated_decision_types) == required_decision_types,
            f"{len(enumerated_decision_types)}/{len(required_decision_types)} "
            "required decision types are enumerated.",
        ),
        CoverageCheck(
            "legal_action_kinds",
            set(enumerated_action_kinds) == required_action_kinds,
            f"{len(enumerated_action_kinds)}/{len(required_action_kinds)} "
            "required legal-action kinds are enumerated.",
        ),
        CoverageCheck(
            "run_record_integrity",
            bool(runs) and all(not run.verification_errors for run in runs),
            f"{sum(not run.verification_errors for run in runs)}/{len(runs)} run records verify.",
        ),
        CoverageCheck(
            "run_ruleset_identity",
            bool(runs) and all(run.ruleset_manifest_ids == (manifest.manifest_id,) for run in runs),
            "Every run and embedded snapshot uses the selected ruleset manifest.",
        ),
        CoverageCheck(
            "character_scope",
            all_characters == {expected_character},
            f"Observed characters: {sorted(all_characters)!r}; expected {expected_character!r}.",
        ),
        CoverageCheck(
            "difficulty_scope",
            all_ascensions == {expected_ascension}
            and all_selected_modes == {expected_mode.casefold()},
            f"Observed modes/ascensions: {sorted(all_selected_modes)!r}/"
            f"{sorted(all_ascensions)!r}; expected {expected_mode!r}/{expected_ascension}.",
        ),
        CoverageCheck(
            "accounted_run_outcomes",
            bool(runs) and all(run.status in allowed_outcomes for run in runs),
            "Every run ends at a terminal state or an explicit unsupported decision.",
        ),
        CoverageCheck(
            "explicit_unsupported_decisions",
            unsupported_runs == unsupported_decisions,
            f"{unsupported_decisions} unsupported decisions account for "
            f"{unsupported_runs} unsupported runs.",
        ),
        CoverageCheck(
            "terminal_run_evidence",
            terminal_runs >= minimum_terminal_runs,
            f"{terminal_runs} terminal runs observed; minimum is {minimum_terminal_runs}.",
        ),
    )
    valid = all(check.passed for check in checks)
    verdict = (
        "pass" if valid and unsupported_decisions == 0 else "conditional_pass" if valid else "fail"
    )
    return LiveCoverageReport(
        valid=valid,
        verdict=verdict,
        coverage_id=coverage_id,
        scope=cast(dict[str, object], scope),
        manifest_id=manifest.manifest_id,
        fixture_corpus_sha256=_sha256_file(fixture_corpus_path),
        fixture_count=len(fixture_audit.results),
        enumerated_state_types=fixture_audit.covered_state_types,
        enumerated_decision_types=tuple(enumerated_decision_types),
        enumerated_action_kinds=tuple(enumerated_action_kinds),
        runs=runs,
        checks=checks,
    )


def _audit_run(path: Path) -> RunCoverage:
    verification = verify_live_run(path)
    records = _read_jsonl(path)
    summary = records[-1] if records and records[-1].get("record_type") == "summary" else {}
    snapshots = list(_snapshots(records))
    public_states = [
        public_state
        for snapshot in snapshots
        if isinstance((observation := snapshot.get("observation")), dict)
        and isinstance((public_state := observation.get("public_state")), dict)
    ]
    manifest_ids = {
        manifest_id
        for snapshot in snapshots
        if isinstance((ruleset := snapshot.get("ruleset")), dict)
        and isinstance((manifest_id := ruleset.get("manifest_id")), str)
    }
    for record in records:
        if record.get("record_type") != "header":
            continue
        ruleset = record.get("ruleset")
        if isinstance(ruleset, dict) and isinstance(
            (manifest_id := ruleset.get("manifest_id")), str
        ):
            manifest_ids.add(manifest_id)
    characters = sorted(
        {
            character
            for state in public_states
            if isinstance((player := state.get("player")), dict)
            and isinstance((character := player.get("character")), str)
        }
    )
    ascensions = sorted(
        {
            ascension
            for state in public_states
            if isinstance((run := state.get("run")), dict)
            and isinstance((ascension := run.get("ascension")), int)
            and not isinstance(ascension, bool)
        }
    )
    floors = sorted(
        {
            floor
            for state in public_states
            if isinstance((run := state.get("run")), dict)
            and isinstance((floor := run.get("floor")), int)
            and not isinstance(floor, bool)
        }
    )
    state_types = sorted(
        {
            state_type
            for state in public_states
            if isinstance((state_type := state.get("state_type")), str)
        }
    )
    decision_types = sorted(
        {
            decision_type
            for snapshot in snapshots
            if isinstance((observation := snapshot.get("observation")), dict)
            and isinstance((decision_type := observation.get("decision_type")), str)
        }
    )
    advertised_action_kinds = sorted(
        {
            kind
            for snapshot in snapshots
            if isinstance((actions := snapshot.get("legal_actions")), list)
            for action in actions
            if isinstance(action, dict) and isinstance((kind := action.get("kind")), str)
        }
    )
    selected_action_kinds = sorted(
        {
            kind
            for record in records
            if record.get("record_type") == "step"
            and isinstance((action := record.get("selected_action")), dict)
            and isinstance((kind := action.get("kind")), str)
        }
    )
    known_modes = {"standard", "daily", "custom"}
    selected_modes = sorted(
        {
            normalized
            for record in records
            if record.get("record_type") == "step"
            and isinstance((action := record.get("selected_action")), dict)
            and action.get("kind") == "menu_select"
            and isinstance((payload := action.get("payload")), dict)
            and isinstance((option := payload.get("option")), str)
            and (normalized := option.casefold().replace(" ", "_")) in known_modes
        }
    )
    victory = summary.get("victory")
    return RunCoverage(
        record_sha256=_sha256_file(path),
        records=verification.records,
        steps=verification.steps,
        status=str(summary.get("status", "missing")),
        reason=str(summary.get("reason", "missing")),
        terminal=summary.get("terminal") is True,
        victory=victory if isinstance(victory, bool) else None,
        ruleset_manifest_ids=tuple(sorted(manifest_ids)),
        characters=tuple(characters),
        ascensions=tuple(ascensions),
        selected_modes=tuple(selected_modes),
        floors=tuple(floors),
        state_types=tuple(state_types),
        decision_types=tuple(decision_types),
        advertised_action_kinds=tuple(advertised_action_kinds),
        selected_action_kinds=tuple(selected_action_kinds),
        unsupported_decisions=verification.unsupported_decisions,
        verification_errors=verification.errors,
    )


def _snapshots(records: list[dict[str, object]]) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []
    for record in records:
        record_type = record.get("record_type")
        candidates: list[object] = []
        if record_type == "header":
            candidates.append(record.get("initial_snapshot"))
        elif record_type == "step":
            candidates.append(record.get("snapshot"))
            receipt = record.get("receipt")
            if isinstance(receipt, dict):
                candidates.append(receipt.get("successor_snapshot"))
        elif record_type == "unsupported_decision":
            candidates.append(record.get("snapshot"))
        elif record_type == "summary":
            candidates.append(record.get("final_snapshot"))
        snapshots.extend(
            cast(dict[str, object], item) for item in candidates if isinstance(item, dict)
        )
    return snapshots


def _expected_actions(fixture: dict[str, object]) -> list[dict[str, object]]:
    expected = fixture.get("expected")
    if not isinstance(expected, dict):
        return []
    actions = expected.get("legal_actions")
    if not isinstance(actions, list):
        return []
    return [cast(dict[str, object], action) for action in actions if isinstance(action, dict)]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value: object = json.loads(line)
            if isinstance(value, dict):
                records.append(cast(dict[str, object], value))
    except (OSError, json.JSONDecodeError):
        return []
    return records


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(dict[str, Any], value)


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _required_string(mapping: dict[str, Any], key: str, label: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label}.{key} must be a non-empty string")
    return value


def _string_set(mapping: dict[str, Any], key: str) -> set[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"coverage specification {key} must be a non-empty array")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"coverage specification {key} must contain non-empty strings")
    strings = cast(list[str], value)
    if len(strings) != len(set(strings)):
        raise ValueError(f"coverage specification {key} must not contain duplicates")
    return set(strings)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
