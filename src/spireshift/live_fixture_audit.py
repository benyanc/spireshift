from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from spireshift.adapters.sts2mcp import LiveStateError, Sts2McpStateProjector
from spireshift.core.manifest import PatchManifest

LIVE_FIXTURE_CORPUS_SCHEMA_VERSION = "live-fixture-corpus-v1"
LIVE_FIXTURE_AUDIT_SCHEMA_VERSION = "live-fixture-audit-v1"

# These are every actionable single-player state emitted by pinned STS2MCP v0.4.0.
# `unknown` and `overlay` are explicit unsupported states rather than decision screens.
REQUIRED_STATE_TYPES = frozenset(
    {
        "menu",
        "monster",
        "elite",
        "boss",
        "hand_select",
        "map",
        "rewards",
        "card_reward",
        "event",
        "rest_site",
        "shop",
        "fake_merchant",
        "treasure",
        "card_select",
        "bundle_select",
        "relic_select",
        "crystal_sphere",
        "game_over",
    }
)
REQUIRED_DECISION_FAMILIES = frozenset(
    {
        "combat",
        "rewards",
        "map",
        "shop",
        "event",
        "rest_site",
        "relic_choice",
        "terminal",
    }
)


@dataclass(frozen=True, slots=True)
class FixtureAuditResult:
    fixture_id: str
    state_type: str
    decision_family: str
    valid: bool
    action_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "state_type": self.state_type,
            "decision_family": self.decision_family,
            "valid": self.valid,
            "action_count": self.action_count,
            "errors": list(self.errors),
        }


@dataclass(frozen=True, slots=True)
class LiveFixtureAuditReport:
    valid: bool
    corpus_path: Path
    manifest_id: str
    bridge_version: str
    covered_state_types: tuple[str, ...]
    covered_decision_families: tuple[str, ...]
    results: tuple[FixtureAuditResult, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": LIVE_FIXTURE_AUDIT_SCHEMA_VERSION,
            "valid": self.valid,
            "corpus_path": str(self.corpus_path),
            "manifest_id": self.manifest_id,
            "bridge_version": self.bridge_version,
            "summary": {
                "fixtures": len(self.results),
                "passed": sum(result.valid for result in self.results),
                "failed": sum(not result.valid for result in self.results),
            },
            "covered_state_types": list(self.covered_state_types),
            "covered_decision_families": list(self.covered_decision_families),
            "results": [result.as_dict() for result in self.results],
            "errors": list(self.errors),
        }


def audit_live_fixture_corpus(
    corpus_path: Path,
    manifest: PatchManifest,
) -> LiveFixtureAuditReport:
    document = _load_object(corpus_path)
    projector = Sts2McpStateProjector(manifest)
    bridge_version = manifest.adapter.version
    global_errors: list[str] = []

    if document.get("schema_version") != LIVE_FIXTURE_CORPUS_SCHEMA_VERSION:
        global_errors.append(
            f"corpus schema_version must be {LIVE_FIXTURE_CORPUS_SCHEMA_VERSION!r}"
        )
    ruleset = _object_or_empty(document.get("ruleset"))
    if ruleset.get("manifest_id") != manifest.manifest_id:
        global_errors.append("corpus ruleset manifest_id does not match the selected manifest")
    if ruleset.get("patch_id") != manifest.patch.patch_id:
        global_errors.append("corpus patch_id does not match the selected manifest")
    if ruleset.get("bridge_version") != bridge_version:
        global_errors.append("corpus bridge_version does not match the selected manifest")
    if ruleset.get("bridge_revision") != manifest.adapter.revision:
        global_errors.append("corpus bridge_revision does not match the selected manifest")

    raw_sources = document.get("sources")
    declared_sources: set[str] = set()
    if not isinstance(raw_sources, list):
        global_errors.append("corpus sources must be an array")
    else:
        for position, raw_source in enumerate(raw_sources):
            source_declaration = _object_or_empty(raw_source)
            source_id = _nonempty_string(source_declaration.get("source_id"))
            if source_id is None:
                global_errors.append(f"source[{position}] has no source_id")
            elif source_id in declared_sources:
                global_errors.append(f"duplicate source_id: {source_id!r}")
            else:
                declared_sources.add(source_id)

    raw_fixtures = document.get("fixtures")
    if not isinstance(raw_fixtures, list):
        global_errors.append("corpus fixtures must be an array")
        raw_fixtures = []

    results: list[FixtureAuditResult] = []
    fixture_ids: set[str] = set()
    covered_states: set[str] = set()
    covered_families: set[str] = set()
    for position, raw_fixture in enumerate(raw_fixtures):
        fixture = _object_or_empty(raw_fixture)
        fixture_id = _nonempty_string(fixture.get("fixture_id")) or f"fixture[{position}]"
        state_type = _nonempty_string(fixture.get("state_type")) or "unknown"
        family = _nonempty_string(fixture.get("decision_family")) or "unknown"
        errors: list[str] = []
        source_id = _nonempty_string(fixture.get("source_id"))
        if source_id not in declared_sources:
            errors.append(f"source_id is not declared: {source_id!r}")
        if fixture_id in fixture_ids:
            errors.append("duplicate fixture_id")
        fixture_ids.add(fixture_id)
        covered_states.add(state_type)
        covered_families.add(family)

        source = fixture.get("source")
        expected = _object_or_empty(fixture.get("expected"))
        action_count = 0
        if not isinstance(source, dict):
            errors.append("source must be an object")
        else:
            source_copy = cast(dict[str, object], copy.deepcopy(source))
            try:
                first = projector.project(source_copy, bridge_version=bridge_version)
                second = projector.project(source_copy, bridge_version=bridge_version)
            except (LiveStateError, TypeError, ValueError) as error:
                errors.append(f"projection failed: {error}")
            else:
                action_count = len(first.legal_actions)
                if first.as_dict() != second.as_dict():
                    errors.append("projection is not deterministic")
                if source_copy != source:
                    errors.append("projection mutated the source fixture")
                if first.observation.public_state.get("state_type") != state_type:
                    errors.append("projected state_type differs from the fixture declaration")
                expected_decision_type = _nonempty_string(expected.get("decision_type"))
                if first.observation.decision_type.value != expected_decision_type:
                    errors.append(
                        "decision_type mismatch: expected "
                        f"{expected_decision_type!r}, got {first.observation.decision_type.value!r}"
                    )
                expected_status = _nonempty_string(expected.get("action_coverage_status"))
                if first.action_coverage_status != expected_status:
                    errors.append(
                        "action coverage mismatch: expected "
                        f"{expected_status!r}, got {first.action_coverage_status!r}"
                    )
                expected_actions = expected.get("legal_actions")
                actual_actions = [
                    {"kind": action.kind, "payload": action.payload}
                    for action in first.legal_actions
                ]
                if actual_actions != expected_actions:
                    errors.append(
                        "legal-action oracle mismatch: expected "
                        f"{_canonical(expected_actions)}, got {_canonical(actual_actions)}"
                    )
                expected_omissions = expected.get("omitted_source_paths", [])
                if list(first.omitted_source_paths) != expected_omissions:
                    errors.append(
                        "information-boundary omissions mismatch: expected "
                        f"{_canonical(expected_omissions)}, "
                        f"got {_canonical(list(first.omitted_source_paths))}"
                    )

        results.append(
            FixtureAuditResult(
                fixture_id=fixture_id,
                state_type=state_type,
                decision_family=family,
                valid=not errors,
                action_count=action_count,
                errors=tuple(errors),
            )
        )

    missing_states = sorted(REQUIRED_STATE_TYPES - covered_states)
    if missing_states:
        global_errors.append(f"missing actionable state types: {missing_states}")
    missing_families = sorted(REQUIRED_DECISION_FAMILIES - covered_families)
    if missing_families:
        global_errors.append(f"missing required decision families: {missing_families}")

    valid = not global_errors and all(result.valid for result in results)
    return LiveFixtureAuditReport(
        valid=valid,
        corpus_path=corpus_path,
        manifest_id=manifest.manifest_id,
        bridge_version=bridge_version,
        covered_state_types=tuple(sorted(covered_states)),
        covered_decision_families=tuple(sorted(covered_families)),
        results=tuple(results),
        errors=tuple(global_errors),
    )


def _load_object(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Fixture corpus {path} must contain a JSON object")
    return cast(dict[str, Any], value)


def _object_or_empty(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _nonempty_string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
