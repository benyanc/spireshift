from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

from spireshift.adapters.evangambit import (
    EvanGambitBackendError,
    EvanGambitEnvironment,
    EvanGambitLayout,
    EvanGambitRunBackend,
    EvanGambitRuntimeEvidence,
)
from spireshift.backend_admission import (
    MANDATORY_CONFORMANCE_CHECKS,
    assess_backend_admission,
    load_backend_admission_report,
    verify_backend_admission,
)
from spireshift.conformance import run_environment_conformance
from spireshift.core.manifest import PatchManifest, freeze_patch_manifest, load_patch_manifest
from spireshift.core.types import DecisionType


class FakeEvanGambitRun:
    def __init__(self) -> None:
        self.phase = 0
        self.resample_marker = 0
        self.victory = False

    def reset(self, *, seed: int) -> tuple[object, Mapping[str, object]]:
        self.phase = 0
        self.resample_marker = 0
        self.victory = False
        return self._raw(), self._info()

    def current(self) -> tuple[object, Mapping[str, object]]:
        return self._raw(), self._info()

    def action_masks(self) -> object:
        mask = [False] * 8
        if self.phase in {0, 2}:
            mask[0] = True
        return mask

    def step(
        self, action: int, target: int = -1
    ) -> tuple[object, float, bool, bool, Mapping[str, object]]:
        if action != 0:
            return self._raw(), -1.0, False, False, self._info()
        if self.phase == 0:
            if target not in {0, 1}:
                return self._raw(), -1.0, False, False, self._info()
            self.phase = 2
            return self._raw(), -0.25, False, False, self._info()
        if self.phase == 2:
            self.phase = 6
            self.victory = True
            return self._raw(), 1.0, True, False, self._info()
        return self._raw(), -1.0, False, False, self._info()

    def clone(self, *, resample_hidden: bool, seed: int | None) -> FakeEvanGambitRun:
        copy = FakeEvanGambitRun()
        copy.phase = self.phase
        copy.victory = self.victory
        copy.resample_marker = int(seed or 1) if resample_hidden else self.resample_marker
        return copy

    def map_graph(self) -> Mapping[str, object]:
        return {
            "nodes": {(0, 0): 1, (0, 1): 6},
            "edges": (((0, 0), (0, 1)),),
            "boss_encounter": "fake-boss",
            "current": (0, 0),
        }

    def close(self) -> None:
        return None

    def _raw(self) -> list[int]:
        raw = [0] * 16
        if self.phase == 0:
            raw[0] = 42
            raw[4] = 20
            raw[6] = 15
        raw[15] = self.resample_marker
        return raw

    def _info(self) -> Mapping[str, object]:
        return {
            "phase": self.phase,
            "floor": 1,
            "act": "test",
            "deck_size": 1,
            "deck": ({"card_id": 42, "upgraded": False},),
            "relic_slots": (),
            "shop_slots": (),
            "gold": self.resample_marker,
            "player_hp": 80,
            "player_max_hp": 80,
            "potions": (),
            "relics": (),
            "player_won": self.victory,
            "encounter_id": 1,
            "encounter": "fake",
        }


def _manifest(status: str = "admitted") -> PatchManifest:
    return freeze_patch_manifest(
        {
            "schema_version": "patch-manifest-v1",
            "admission_status": status,
            "patch": {
                "patch_id": "sts2-test",
                "game_version": "v0.test",
                "game_commit": "test",
                "branch": "test",
                "release_date": None,
                "steam_build_id": "1",
            },
            "engine": {
                "component_id": "test-engine",
                "version": "1",
                "revision": "a" * 40,
                "source": "https://example.com/engine",
                "digest": {"algorithm": "git-commit-sha1", "value": "a" * 40},
            },
            "adapter": {
                "component_id": "test-adapter",
                "version": "1",
                "revision": "b" * 40,
                "source": "https://example.com/adapter",
                "digest": {"algorithm": "git-commit-sha1", "value": "b" * 40},
            },
            "mechanics": [
                {
                    "artifact_id": "test-game",
                    "kind": "authoritative-game-assembly",
                    "version": "v0.test",
                    "platform": None,
                    "architecture": None,
                    "digest": {"algorithm": "sha256", "value": "c" * 64},
                    "size_bytes": 1,
                }
            ],
            "interface": {
                "observation_schema": "observation-v1",
                "action_schema": "action-v1",
                "information_policy_id": "public-state-v1",
            },
        }
    )


def _layout() -> EvanGambitLayout:
    return EvanGambitLayout(
        phase_complete=6,
        phase_map=2,
        phase_names={0: "combat", 2: "map", 6: "complete"},
        decision_types={
            0: DecisionType.COMBAT,
            2: DecisionType.PATH,
            6: DecisionType.TERMINAL,
        },
        observation_size=16,
        max_actions=8,
        max_enemies=2,
        enemy_offset=4,
        enemy_slot_size=2,
        max_hand=3,
        hand_offset=0,
        hand_slot_size=1,
        targeted_card_ids=frozenset({42}),
        targeted_potion_ids=frozenset({47}),
    )


def _matching_installation(source: PatchManifest) -> dict[str, object]:
    installation = json.loads(Path("tests/fixtures/game-installation-v1.json").read_text())
    authoritative = next(
        mechanic for mechanic in source.mechanics if mechanic.kind == "authoritative-game-assembly"
    )
    installation["release"].update(
        {
            "version": source.patch.game_version,
            "commit": source.patch.game_commit,
            "steam_build_id": source.patch.steam_build_id,
        }
    )
    installation["assembly"].update(
        {
            "size_bytes": authoritative.size_bytes,
            "sha256": authoritative.digest.value,
        }
    )
    return cast(dict[str, object], installation)


def _factory(
    manifest: PatchManifest | None = None,
) -> Callable[[], EvanGambitEnvironment]:
    selected = manifest or _manifest()

    def create() -> EvanGambitEnvironment:
        backend_factory: Callable[[], EvanGambitRunBackend] = FakeEvanGambitRun
        return EvanGambitEnvironment(backend_factory, selected, _layout())

    return create


def test_public_projection_exposes_explicit_target_actions_and_passes_contract() -> None:
    environment = _factory()()
    observation = environment.reset(1)

    actions = tuple(environment.legal_actions())

    assert observation.public_state["gold"] == 0
    assert [action.payload["target_index"] for action in actions] == [0, 1]
    report = run_environment_conformance(_factory(), seeds=(1, 7), max_steps=8)
    assert report.verdict == "pass"


def test_pending_backend_is_fail_closed_outside_admission() -> None:
    with pytest.raises(EvanGambitBackendError, match="not admitted"):
        _factory(_manifest("pending_conformance"))()


def test_admission_requires_complete_evidence_and_binds_native_library(
    tmp_path: Path,
) -> None:
    source = load_patch_manifest(Path("manifests/patches/sts2-v0.107.1-evangambit-37e4264.json"))
    external = json.loads(Path("docs/evidence/evangambit-v0.107.1-conformance.json").read_text())
    installation = _matching_installation(source)
    checks = [
        {"check_id": check_id, "status": "pass", "detail": "passed", "metrics": {}}
        for check_id in sorted(MANDATORY_CONFORMANCE_CHECKS)
    ]
    conformance = {
        "schema_version": "conformance-report-v1",
        "suite_version": "environment-conformance-v1",
        "verdict": "pass",
        "ruleset": source.ruleset_identity().as_dict(),
        "seeds": [1, 7],
        "summary": {"pass": len(checks), "fail": 0, "inconclusive": 0},
        "checks": checks,
    }
    native = tmp_path / "Sts2Emulator.dylib"
    native.write_bytes(b"native")
    adapter = tmp_path / "evangambit.py"
    adapter.write_text("# adapter\n", encoding="utf-8")
    runtime = EvanGambitRuntimeEvidence(
        upstream_root=tmp_path,
        upstream_revision=source.engine.revision,
        upstream_tree="d" * 40,
        game_version=source.patch.game_version,
        steam_build_id=cast(str, source.patch.steam_build_id),
        native_library=native,
        native_sha256="e" * 64,
        native_size_bytes=6,
        platform="macos",
        architecture="arm64",
    )

    assessment = assess_backend_admission(
        source,
        conformance,
        external,
        installation,
        runtime,
        adapter_source=adapter,
    )

    assert assessment.report["verdict"] == "admitted"
    assert assessment.admitted_manifest is not None
    assert assessment.admitted_manifest.admission_status == "admitted"
    assert assessment.admitted_manifest.mechanics[-1].digest.value == "e" * 64
    assert verify_backend_admission(assessment.report, assessment.admitted_manifest) == ()


def test_admission_does_not_emit_manifest_when_conformance_is_conditional(
    tmp_path: Path,
) -> None:
    source = load_patch_manifest(Path("manifests/patches/sts2-v0.107.1-evangambit-37e4264.json"))
    external = json.loads(Path("docs/evidence/evangambit-v0.107.1-conformance.json").read_text())
    installation = _matching_installation(source)
    conformance = {
        "schema_version": "conformance-report-v1",
        "verdict": "conditional_pass",
        "ruleset": source.ruleset_identity().as_dict(),
        "checks": [],
    }
    adapter = tmp_path / "evangambit.py"
    adapter.write_text("# adapter\n", encoding="utf-8")
    runtime = EvanGambitRuntimeEvidence(
        upstream_root=tmp_path,
        upstream_revision=source.engine.revision,
        upstream_tree="d" * 40,
        game_version=source.patch.game_version,
        steam_build_id=cast(str, source.patch.steam_build_id),
        native_library=tmp_path / "native",
        native_sha256="e" * 64,
        native_size_bytes=6,
        platform="macos",
        architecture="arm64",
    )

    assessment = assess_backend_admission(
        source,
        conformance,
        external,
        installation,
        runtime,
        adapter_source=adapter,
    )

    assert assessment.report["verdict"] == "rejected"
    assert assessment.admitted_manifest is None


def test_checked_admission_evidence_binds_current_adapter_and_conformance() -> None:
    report = load_backend_admission_report(
        Path("docs/evidence/evangambit-v0.107.1-spireshift-admission.json")
    )
    manifest = load_patch_manifest(
        Path("manifests/patches/sts2-v0.107.1-evangambit-37e4264-macos-arm64-admitted.json")
    )
    adapter_bytes = Path("src/spireshift/adapters/evangambit.py").read_bytes()
    conformance = json.loads(
        Path("docs/evidence/evangambit-v0.107.1-spireshift-conformance.json").read_text()
    )
    conformance_digest = hashlib.sha256(
        json.dumps(conformance, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    assert verify_backend_admission(report, manifest) == ()
    assert manifest.adapter.digest.value == hashlib.sha256(adapter_bytes).hexdigest()
    assert report["conformance_sha256"] == conformance_digest
