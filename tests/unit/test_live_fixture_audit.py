from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from spireshift.core.manifest import load_patch_manifest
from spireshift.live_fixture_audit import (
    REQUIRED_DECISION_FAMILIES,
    REQUIRED_STATE_TYPES,
    audit_live_fixture_corpus,
)

MANIFEST_PATH = Path("manifests/patches/sts2-v0.107.1-sts2mcp-55e0648.json")
CORPUS_PATH = Path("tests/fixtures/live/public-state-corpus-v1.json")


def _document() -> dict[str, Any]:
    value = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_checked_corpus_covers_every_actionable_screen_and_required_family() -> None:
    report = audit_live_fixture_corpus(CORPUS_PATH, load_patch_manifest(MANIFEST_PATH))

    assert report.valid
    assert not report.errors
    assert len(report.results) == 19
    assert all(result.valid for result in report.results)
    assert set(report.covered_state_types) == REQUIRED_STATE_TYPES
    assert set(report.covered_decision_families) >= REQUIRED_DECISION_FAMILIES


def test_action_oracle_detects_an_omitted_legal_choice(tmp_path: Path) -> None:
    document = _document()
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list)
    first = fixtures[0]
    assert isinstance(first, dict)
    expected = first["expected"]
    assert isinstance(expected, dict)
    expected["legal_actions"] = []

    report = audit_live_fixture_corpus(
        _write(tmp_path, document), load_patch_manifest(MANIFEST_PATH)
    )

    assert not report.valid
    assert report.results[0].errors[0].startswith("legal-action oracle mismatch")


def test_information_boundary_rejects_privileged_fixture_state(tmp_path: Path) -> None:
    document = _document()
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list)
    fixture = copy.deepcopy(fixtures[0])
    assert isinstance(fixture, dict)
    source = fixture["source"]
    assert isinstance(source, dict)
    source["run"] = {"rng_state": "hidden"}
    fixtures[0] = fixture

    report = audit_live_fixture_corpus(
        _write(tmp_path, document), load_patch_manifest(MANIFEST_PATH)
    )

    assert not report.valid
    assert "forbidden privileged state" in report.results[0].errors[0]


def test_missing_screen_is_a_corpus_level_failure(tmp_path: Path) -> None:
    document = _document()
    fixtures = document["fixtures"]
    assert isinstance(fixtures, list)
    document["fixtures"] = [
        fixture
        for fixture in fixtures
        if isinstance(fixture, dict) and fixture.get("state_type") != "relic_select"
    ]

    report = audit_live_fixture_corpus(
        _write(tmp_path, document), load_patch_manifest(MANIFEST_PATH)
    )

    assert not report.valid
    assert report.errors == ("missing actionable state types: ['relic_select']",)
