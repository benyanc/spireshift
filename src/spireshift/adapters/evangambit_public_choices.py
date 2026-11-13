"""Separately identified adapter for the owner-built public-menu repair."""

from __future__ import annotations

import hashlib
import importlib
import json
import platform
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol, cast

from spireshift.adapters.evangambit import (
    EvanGambitBackendError,
    EvanGambitEnvironment,
    EvanGambitLayout,
    EvanGambitRunBackend,
    EvanGambitRuntimeEvidence,
    adapter_source_sha256,
    load_evangambit_backend,
)
from spireshift.core.manifest import PatchManifest, load_patch_manifest, manifest_identifier
from spireshift.core.types import LegalAction, Observation
from spireshift.public_run_choices import (
    SCHEMA_ID,
    PublicChoiceView,
    bind_public_choice_actions,
    decode_public_choices,
    read_complete_state_list,
)

ADAPTER_ID = "spireshift-evangambit-public-choices-adapter"
ADAPTER_VERSION = "evangambit-public-choices-v2"


def public_adapter_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    return manifest_identifier(
        {
            "adapter_version": ADAPTER_VERSION,
            "sources": {
                name: adapter_source_sha256(root / name)
                for name in (
                    "adapters/evangambit.py",
                    "adapters/evangambit_public_choices.py",
                    "public_run_choices.py",
                )
            },
        }
    )[7:]


def public_choice_manifest(source: PatchManifest) -> PatchManifest:
    """Derive a new pending identity; the owner-built source manifest remains intact."""
    if source.admission_status != "pending_conformance":
        raise ValueError("Public-choice integration requires its pending native candidate")
    if (
        source.adapter.component_id != "spireshift-evangambit-environment-adapter"
        or source.adapter.digest.algorithm != "sha256"
        or source.adapter.digest.value != adapter_source_sha256()
    ):
        raise ValueError("The preserved base adapter identity differs")
    body = source.body_dict()
    digest = public_adapter_digest()
    body["adapter"] = {
        "component_id": ADAPTER_ID,
        "version": "2",
        "revision": digest,
        "source": "https://github.com/benyanc/spireshift/blob/main/src/spireshift/adapters/evangambit_public_choices.py",
        "digest": {"algorithm": "sha256", "value": digest},
    }
    return PatchManifest.from_mapping({**body, "manifest_id": manifest_identifier(body)})


def choice_view(observation: Observation) -> PublicChoiceView:
    state = observation.public_state
    phase = state.get("phase")
    values = state.get("public_choice_lists")
    if (
        not isinstance(phase, str)
        or not isinstance(values, dict)
        or set(values) != {"schema_id", "combat", "bundle", "profile"}
        or values["schema_id"] != SCHEMA_ID
        or any(not isinstance(values[k], list) for k in ("combat", "bundle", "profile"))
    ):
        raise ValueError("Missing or incompatible complete public-choice readout")
    return decode_public_choices(phase, values["combat"], values["bundle"], values["profile"])


class PublicChoiceBackend(EvanGambitRunBackend, Protocol):
    def public_choice_lists(self) -> Mapping[int, tuple[int, ...]]: ...

    def clone(self, *, resample_hidden: bool, seed: int | None) -> PublicChoiceBackend: ...


class PublicChoiceEnvironment(EvanGambitEnvironment):
    def __init__(
        self,
        backend_factory: Callable[[], PublicChoiceBackend],
        manifest: PatchManifest,
        layout: EvanGambitLayout,
        *,
        allow_pending: bool = False,
        backend: PublicChoiceBackend | None = None,
    ) -> None:
        if (
            manifest.adapter.component_id != ADAPTER_ID
            or manifest.adapter.version != "2"
            or manifest.adapter.digest.algorithm != "sha256"
            or manifest.adapter.digest.value != public_adapter_digest()
        ):
            raise EvanGambitBackendError("Public-choice adapter identity differs")
        super().__init__(
            backend_factory, manifest, layout, allow_pending=allow_pending, backend=backend
        )
        self._choice_factory = backend_factory

    def _update(self, raw: object, info: Mapping[str, object], *, terminal: bool) -> Observation:
        original = super()._update(raw, info, terminal=terminal)
        phase = self._layout.phase_names.get(cast(int, info["phase"]), f"phase-{info['phase']}")
        lists = cast(PublicChoiceBackend, self._backend).public_choice_lists()
        if set(lists) != {22, 23, 24}:
            raise ValueError("Public-choice readout must include all three public lists")
        decode_public_choices(phase, lists[22], lists[23], lists[24])
        state = {
            **original.public_state,
            "adapter_version": ADAPTER_VERSION,
            "phase": phase,
            "public_choice_lists": {
                "schema_id": SCHEMA_ID,
                "combat": list(lists[22]),
                "bundle": list(lists[23]),
                "profile": list(lists[24]),
            },
        }
        self._observation = replace(
            original,
            public_state=state,
            state_hash=hashlib.sha256(
                json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        )
        return self._observation

    def _targeted_card_actions(self, phase: int) -> frozenset[int]:
        if (
            self._observation is not None
            and choice_view(self._observation).combat_selection is not None
        ):
            # A card menu replaces combat's action space. Hand target decorations
            # are unrelated locators, not additional legal selection decisions.
            return frozenset()
        return super()._targeted_card_actions(phase)

    def legal_actions(self) -> tuple[LegalAction, ...]:
        actions = tuple(super().legal_actions())
        assert self._observation is not None
        view = choice_view(self._observation)
        if view.combat_selection is not None or view.bundle_selection is not None:
            bind_public_choice_actions(
                view, actions, bundle_offer=self._observation.public_state.get("bundle_offer", [])
            )
        return actions

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> PublicChoiceEnvironment:
        if self._observation is None:
            raise RuntimeError("Call reset() before clone()")
        backend = cast(PublicChoiceBackend, self._backend).clone(
            resample_hidden=resample_hidden, seed=seed
        )
        try:
            raw, info = backend.current()
            cloned = PublicChoiceEnvironment(
                self._choice_factory,
                self._manifest,
                self._layout,
                allow_pending=self._allow_pending,
                backend=backend,
            )
            cloned._update(raw, info, terminal=bool(self._observation.public_state.get("terminal")))
            return cloned
        except Exception:
            backend.close()
            raise


class _BackendWithChoices:
    def __init__(self, delegate: EvanGambitRunBackend, getter: Callable[..., int]) -> None:
        self.delegate, self.getter = delegate, getter

    def public_choice_lists(self) -> Mapping[int, tuple[int, ...]]:
        # The handle locates the live run. Only the three public exports are read;
        # no privileged debug, pile or RNG entry point is used here.
        handle = cast(Any, self.delegate)._environment._run_handle
        if type(handle) is not int:
            raise ValueError("Public choices require a reset run handle")
        return {i: read_complete_state_list(self.getter, handle, i) for i in (22, 23, 24)}

    def reset(self, *, seed: int) -> tuple[object, Mapping[str, object]]:
        return self.delegate.reset(seed=seed)

    def current(self) -> tuple[object, Mapping[str, object]]:
        return self.delegate.current()

    def action_masks(self) -> object:
        return self.delegate.action_masks()

    def step(
        self, action: int, target: int = -1
    ) -> tuple[object, float, bool, bool, Mapping[str, object]]:
        return self.delegate.step(action, target)

    def clone(self, *, resample_hidden: bool, seed: int | None) -> _BackendWithChoices:
        return _BackendWithChoices(
            self.delegate.clone(resample_hidden=resample_hidden, seed=seed), self.getter
        )

    def map_graph(self) -> Mapping[str, object]:
        return self.delegate.map_graph()

    def close(self) -> None:
        self.delegate.close()


@dataclass(frozen=True, slots=True)
class LoadedPublicChoiceBackend:
    factory: Callable[[], PublicChoiceEnvironment]
    evidence: EvanGambitRuntimeEvidence


def load_public_choice_backend(
    upstream_root: Path,
    manifest_path: Path,
    *,
    allow_pending: bool = False,
    max_episode_steps: int = 4096,
) -> LoadedPublicChoiceBackend:
    manifest = load_patch_manifest(manifest_path)
    if manifest.admission_status != "admitted" and not allow_pending:
        raise EvanGambitBackendError(
            "Public-choice ruleset is pending conformance; training remains disabled"
        )
    if (
        manifest.adapter.component_id != ADAPTER_ID
        or manifest.adapter.digest.value != public_adapter_digest()
    ):
        raise EvanGambitBackendError("Public-choice adapter content identity differs")
    # Delegate the preserved FFI/layout checks using its exact original adapter identity.
    # This temporary metadata is never admitted or written over the source candidate.
    body = manifest.body_dict()
    legacy_digest = adapter_source_sha256()
    body["adapter"] = {
        "component_id": "spireshift-evangambit-environment-adapter",
        "version": "1",
        "revision": legacy_digest,
        "source": "https://github.com/benyanc/spireshift/blob/main/src/spireshift/adapters/evangambit.py",
        "digest": {"algorithm": "sha256", "value": legacy_digest},
    }
    # Native bytes must match even for a pending candidate.
    root = upstream_root.resolve()
    library = root / "out/Sts2Emulator.dylib"
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    if not any(
        a.kind == "compiled-simulator-library"
        and a.platform == "macos"
        and a.architecture == platform.machine().casefold()
        and a.digest.algorithm == "sha256"
        and a.digest.value == digest
        and a.size_bytes == library.stat().st_size
        for a in manifest.mechanics
    ):
        raise EvanGambitBackendError(
            "Public-choice native library differs from the frozen candidate"
        )
    with TemporaryDirectory(prefix="spireshift-public-ffi-") as temporary:
        path = Path(temporary) / "legacy-ffi-view.json"
        path.write_text(json.dumps({**body, "manifest_id": manifest_identifier(body)}))
        loaded = load_evangambit_backend(
            root,
            path,
            allow_pending=True,
            max_episode_steps=max_episode_steps,
            max_floors=64,
        )
    native = importlib.import_module("sts2_gym.native")
    getter = native._lib.Sts2Run_GetStateList

    def factory() -> PublicChoiceEnvironment:
        original = loaded.factory()

        def backend_factory() -> PublicChoiceBackend:
            return _BackendWithChoices(loaded.factory()._backend, getter)

        return PublicChoiceEnvironment(
            backend_factory,
            manifest,
            original._layout,
            allow_pending=allow_pending,
            backend=_BackendWithChoices(original._backend, getter),
        )

    return LoadedPublicChoiceBackend(factory, loaded.evidence)
