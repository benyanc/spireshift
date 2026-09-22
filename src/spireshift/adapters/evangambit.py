from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import platform
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from spireshift.core.manifest import PatchManifest, RulesetIdentity, load_patch_manifest
from spireshift.core.types import DecisionType, LegalAction, Observation, Transition

EVANGAMBIT_ADAPTER_VERSION = "evangambit-environment-v1"

_PUBLIC_INFO_FIELDS = (
    "phase",
    "floor",
    "act",
    "deck_size",
    "deck",
    "relic_slots",
    "shop_slots",
    "gold",
    "player_hp",
    "player_max_hp",
    "potions",
    "relics",
    "current_node_type",
    "card_rewards",
    "card_reward_upgraded",
    "shop_cards",
    "shop_relics",
    "shop_potions",
    "shop_costs",
    "relic_reward",
    "pending_rewards",
    "neow_options",
    "offer_cards",
    "bundle_offer",
    "potion_reward_odds",
    "event_id",
    "map_choices",
    "deck_selection",
    "enemy_def_ids",
    "player_won",
    "encounter_id",
    "encounter",
)


class EvanGambitBackendError(RuntimeError):
    """The optional backend is absent, incompatible, or outside its admitted identity."""


def adapter_source_sha256(path: Path | None = None) -> str:
    """Hash source identically after Git checks it out with CRLF or LF endings."""
    source = (Path(__file__) if path is None else path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(source).hexdigest()


class EvanGambitRunBackend(Protocol):
    def reset(self, *, seed: int) -> tuple[object, Mapping[str, object]]: ...

    def current(self) -> tuple[object, Mapping[str, object]]: ...

    def action_masks(self) -> object: ...

    def step(
        self, action: int, target: int = -1
    ) -> tuple[object, float, bool, bool, Mapping[str, object]]: ...

    def clone(self, *, resample_hidden: bool, seed: int | None) -> EvanGambitRunBackend: ...

    def map_graph(self) -> Mapping[str, object]: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class EvanGambitLayout:
    phase_complete: int
    phase_map: int
    phase_names: Mapping[int, str]
    decision_types: Mapping[int, DecisionType]
    observation_size: int
    max_actions: int
    max_enemies: int
    enemy_offset: int
    enemy_slot_size: int
    max_hand: int
    hand_offset: int
    hand_slot_size: int
    targeted_card_ids: frozenset[int]
    targeted_potion_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class EvanGambitRuntimeEvidence:
    upstream_root: Path
    upstream_revision: str
    upstream_tree: str
    game_version: str
    steam_build_id: str
    native_library: Path
    native_sha256: str
    native_size_bytes: int
    platform: str
    architecture: str

    def as_dict(self) -> dict[str, object]:
        return {
            "upstream_revision": self.upstream_revision,
            "upstream_tree": self.upstream_tree,
            "game_version": self.game_version,
            "steam_build_id": self.steam_build_id,
            "native_library": {
                "filename": self.native_library.name,
                "sha256": self.native_sha256,
                "size_bytes": self.native_size_bytes,
                "platform": self.platform,
                "architecture": self.architecture,
            },
        }


@dataclass(frozen=True, slots=True)
class LoadedEvanGambitBackend:
    factory: Callable[[], EvanGambitEnvironment]
    evidence: EvanGambitRuntimeEvidence


class EvanGambitEnvironment:
    """Public-state projection over the pinned EvanGambit full-run environment."""

    def __init__(
        self,
        backend_factory: Callable[[], EvanGambitRunBackend],
        manifest: PatchManifest,
        layout: EvanGambitLayout,
        *,
        allow_pending: bool = False,
        backend: EvanGambitRunBackend | None = None,
    ) -> None:
        if manifest.admission_status != "admitted" and not allow_pending:
            raise EvanGambitBackendError(
                "EvanGambit ruleset is not admitted; run backend conformance and admission first"
            )
        if manifest.interface.observation_schema != "observation-v1":
            raise EvanGambitBackendError("Manifest does not use observation-v1")
        if manifest.interface.action_schema != "action-v1":
            raise EvanGambitBackendError("Manifest does not use action-v1")
        if manifest.interface.information_policy_id != "public-state-v1":
            raise EvanGambitBackendError("Manifest does not use public-state-v1")
        self.patch_id = manifest.patch.patch_id
        self.ruleset: RulesetIdentity = manifest.ruleset_identity()
        self._manifest = manifest
        self._backend_factory = backend_factory
        self._backend = backend if backend is not None else backend_factory()
        self._layout = layout
        self._allow_pending = allow_pending
        self._observation: Observation | None = None
        self._raw_observation: tuple[int, ...] = ()
        self._info: Mapping[str, object] = {}

    def reset(self, seed: int) -> Observation:
        raw, info = self._backend.reset(seed=seed)
        return self._update(raw, info, terminal=False)

    def legal_actions(self) -> Sequence[LegalAction]:
        if self._observation is None:
            raise RuntimeError("Call reset() before legal_actions()")
        if bool(self._observation.public_state.get("terminal")):
            return ()
        mask = _boolean_vector(self._backend.action_masks(), self._layout.max_actions)
        phase = _required_int(self._info, "phase")
        targets = self._living_enemy_indices()
        targeted = self._targeted_card_actions(phase)
        actions: list[LegalAction] = []
        for action_index, enabled in enumerate(mask):
            if not enabled:
                continue
            if action_index in targeted and targets:
                for target_index in targets:
                    actions.append(self._action(phase, action_index, target_index))
            else:
                actions.append(self._action(phase, action_index, -1))
        return tuple(actions)

    def step(self, action: LegalAction) -> Transition:
        if self._observation is None:
            raise RuntimeError("Call reset() before step()")
        legal = {candidate.action_id: candidate for candidate in self.legal_actions()}
        expected = legal.get(action.action_id)
        if expected is None or expected != action:
            raise ValueError(f"Action is not legal in the current public state: {action.action_id}")
        action_index = _required_int(action.payload, "action_index")
        target_index = int(action.payload.get("target_index", -1))
        raw, backend_reward, terminal, truncated, info = self._backend.step(
            action_index, target_index
        )
        if truncated and not terminal:
            raise EvanGambitBackendError(
                "Backend truncated a non-terminal run; increase its episode limit"
            )
        victory = bool(info.get("player_won", False)) if terminal else False
        reward = 1.0 if terminal and victory else 0.0
        if not math.isfinite(float(backend_reward)):
            raise EvanGambitBackendError("Backend emitted a non-finite private reward")
        previous = self._observation
        next_observation = self._update(raw, info, terminal=terminal)
        return Transition(
            observation=previous,
            action=action,
            next_observation=next_observation,
            reward=reward,
            terminal=terminal,
            victory=victory,
        )

    def clone(self, *, resample_hidden: bool, seed: int | None = None) -> EvanGambitEnvironment:
        if self._observation is None:
            raise RuntimeError("Call reset() before clone()")
        backend = self._backend.clone(resample_hidden=resample_hidden, seed=seed)
        raw, info = backend.current()
        cloned = EvanGambitEnvironment(
            self._backend_factory,
            self._manifest,
            self._layout,
            allow_pending=self._allow_pending,
            backend=backend,
        )
        cloned._update(
            raw,
            info,
            terminal=bool(self._observation.public_state.get("terminal")),
        )
        return cloned

    def close(self) -> None:
        self._backend.close()

    def _update(self, raw: object, info: Mapping[str, object], *, terminal: bool) -> Observation:
        raw_vector = _integer_vector(raw, self._layout.observation_size)
        self._raw_observation = raw_vector
        self._info = info
        phase = _required_int(info, "phase")
        public_state: dict[str, Any] = {
            "backend": "evangambit-sts2-nativeaot",
            "adapter_version": EVANGAMBIT_ADAPTER_VERSION,
            "terminal": terminal or phase == self._layout.phase_complete,
            "victory": bool(info.get("player_won", False)),
            "phase": self._layout.phase_names.get(phase, f"phase-{phase}"),
            "phase_id": phase,
            "observation_vector": list(raw_vector),
        }
        for field in _PUBLIC_INFO_FIELDS:
            if field in info:
                public_state[field] = _json_value(info[field], f"info.{field}")
        if phase == self._layout.phase_map:
            public_state["map"] = _project_map(self._backend.map_graph())
        state_hash = hashlib.sha256(
            json.dumps(public_state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        observation = Observation(
            schema_version="observation-v1",
            patch_id=self.patch_id,
            decision_type=(
                DecisionType.TERMINAL
                if public_state["terminal"]
                else self._layout.decision_types.get(phase, DecisionType.UNKNOWN)
            ),
            public_state=public_state,
            state_hash=state_hash,
        )
        self._observation = observation
        return observation

    def _action(self, phase: int, action_index: int, target_index: int) -> LegalAction:
        phase_name = self._layout.phase_names.get(phase, f"phase-{phase}")
        suffix = f":target:{target_index}" if target_index >= 0 else ""
        payload: dict[str, Any] = {
            "action_index": action_index,
            "phase": phase_name,
        }
        if target_index >= 0:
            payload["target_index"] = target_index
        return LegalAction(
            action_id=f"evangambit:{phase_name}:{action_index}{suffix}",
            kind=f"evangambit_{phase_name}",
            payload=payload,
        )

    def _targeted_card_actions(self, phase: int) -> frozenset[int]:
        if self._layout.decision_types.get(phase) is not DecisionType.COMBAT:
            return frozenset()
        targeted: set[int] = set()
        hand_count = 0
        for action_index in range(self._layout.max_hand):
            offset = self._layout.hand_offset + action_index * self._layout.hand_slot_size
            if offset >= len(self._raw_observation):
                break
            card_id = self._raw_observation[offset]
            if card_id == 0:
                break
            hand_count += 1
            if card_id in self._layout.targeted_card_ids:
                targeted.add(action_index)
        potions = self._info.get("potions", ())
        if isinstance(potions, Sequence) and not isinstance(potions, (str, bytes, bytearray)):
            for slot, potion_id in enumerate(potions):
                if int(potion_id) in self._layout.targeted_potion_ids:
                    targeted.add(hand_count + 1 + slot)
        return frozenset(targeted)

    def _living_enemy_indices(self) -> tuple[int, ...]:
        living: list[int] = []
        for enemy_index in range(self._layout.max_enemies):
            offset = self._layout.enemy_offset + enemy_index * self._layout.enemy_slot_size
            if offset >= len(self._raw_observation):
                break
            if self._raw_observation[offset] > 0:
                living.append(enemy_index)
        return tuple(living)


def load_evangambit_backend(
    upstream_root: Path,
    manifest_path: Path,
    *,
    allow_pending: bool = False,
    max_episode_steps: int = 4096,
    max_floors: int = 64,
) -> LoadedEvanGambitBackend:
    root = upstream_root.expanduser().resolve()
    manifest = load_patch_manifest(manifest_path)
    revision = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    dirty = _git(root, "status", "--porcelain", "--untracked-files=all")
    if dirty:
        raise EvanGambitBackendError("Upstream checkout has tracked local modifications")
    expected_revision = manifest.engine.revision
    if revision != expected_revision:
        raise EvanGambitBackendError(
            f"Upstream revision mismatch: checkout={revision}, engine={manifest.engine.revision}"
        )
    if manifest.adapter.component_id == "evangambit-sts2-python-ffi":
        if manifest.adapter.revision != expected_revision:
            raise EvanGambitBackendError("Pending upstream adapter revision differs from engine")
    elif manifest.adapter.component_id == "spireshift-evangambit-environment-adapter":
        adapter_path = Path(__file__)
        if manifest.adapter.digest.algorithm != "sha256" or (
            adapter_source_sha256(adapter_path) != manifest.adapter.digest.value
        ):
            raise EvanGambitBackendError("SpireShift adapter source digest differs from manifest")
    else:
        raise EvanGambitBackendError(
            f"Unsupported adapter component: {manifest.adapter.component_id}"
        )
    version = _load_json_object(root / "data/game_version.json")
    game_version = str(version.get("release", ""))
    steam_build_id = str(version.get("steam_buildid", ""))
    if game_version != manifest.patch.game_version:
        raise EvanGambitBackendError(
            f"Upstream game version {game_version!r} differs from manifest "
            f"{manifest.patch.game_version!r}"
        )
    if steam_build_id != manifest.patch.steam_build_id:
        raise EvanGambitBackendError(
            f"Upstream Steam build {steam_build_id!r} differs from manifest "
            f"{manifest.patch.steam_build_id!r}"
        )

    source_root = root / "src"
    if not source_root.is_dir():
        raise EvanGambitBackendError(f"Missing EvanGambit Python source: {source_root}")
    _prepend_import_path(source_root)
    try:
        run_env = importlib.import_module("sts2_gym.run_env")
        native = importlib.import_module("sts2_gym.native")
        names = importlib.import_module("sts2_gym.names")
    except (ImportError, OSError, RuntimeError, SyntaxError) as error:
        raise EvanGambitBackendError(f"Cannot load pinned EvanGambit backend: {error}") from error
    _verify_import_root(run_env, root)

    native_library = _native_library_path(root)
    if not native_library.is_file():
        raise EvanGambitBackendError(
            f"Missing native library {native_library}; build the pinned upstream checkout first"
        )
    loaded_native_library = Path(str(native._lib._name)).resolve()
    if loaded_native_library != native_library:
        raise EvanGambitBackendError(
            "Imported native library differs from the library selected for admission: "
            f"loaded={loaded_native_library}, selected={native_library}"
        )
    native_bytes = native_library.read_bytes()
    native_sha256 = hashlib.sha256(native_bytes).hexdigest()
    if manifest.admission_status == "admitted":
        compiled_artifacts = tuple(
            mechanic
            for mechanic in manifest.mechanics
            if mechanic.kind == "compiled-simulator-library"
            and mechanic.platform == _platform_name()
            and mechanic.architecture == platform.machine().casefold()
        )
        if not compiled_artifacts:
            raise EvanGambitBackendError(
                "Admitted manifest has no compiled simulator fingerprint for this host"
            )
        if not any(
            artifact.digest.algorithm == "sha256"
            and artifact.digest.value == native_sha256
            and artifact.size_bytes == len(native_bytes)
            for artifact in compiled_artifacts
        ):
            raise EvanGambitBackendError(
                "Native simulator library hash or size differs from admitted manifest"
            )
    card_definitions = cast(Mapping[int, Any], names.cards())
    targeted_card_ids = frozenset(
        int(card_id) for card_id, card in card_definitions.items() if bool(card.targets_an_enemy())
    )
    layout = EvanGambitLayout(
        phase_complete=int(run_env.PHASE_COMPLETE),
        phase_map=int(run_env.PHASE_MAP),
        phase_names={
            int(run_env.PHASE_COMBAT): "combat",
            int(run_env.PHASE_CARD_REWARD): "card_reward",
            int(run_env.PHASE_MAP): "map",
            int(run_env.PHASE_REST): "rest_site",
            int(run_env.PHASE_SHOP): "shop",
            int(run_env.PHASE_RELIC_REWARD): "relic_reward",
            int(run_env.PHASE_COMPLETE): "complete",
            int(run_env.PHASE_EVENT): "event",
            int(run_env.PHASE_ANCIENT): "ancient",
            int(run_env.PHASE_TRANSFORM_SELECT): "card_selection",
            int(run_env.PHASE_TREASURE): "treasure",
            int(run_env.PHASE_CRYSTAL_SPHERE): "crystal_sphere",
            int(run_env.PHASE_BUNDLE_SELECT): "bundle_selection",
        },
        decision_types={
            int(run_env.PHASE_COMBAT): DecisionType.COMBAT,
            int(run_env.PHASE_CARD_REWARD): DecisionType.REWARD,
            int(run_env.PHASE_MAP): DecisionType.PATH,
            int(run_env.PHASE_REST): DecisionType.REST_SITE,
            int(run_env.PHASE_SHOP): DecisionType.SHOP,
            int(run_env.PHASE_RELIC_REWARD): DecisionType.RELIC_SELECTION,
            int(run_env.PHASE_COMPLETE): DecisionType.TERMINAL,
            int(run_env.PHASE_EVENT): DecisionType.EVENT,
            int(run_env.PHASE_ANCIENT): DecisionType.EVENT,
            int(run_env.PHASE_TRANSFORM_SELECT): DecisionType.CARD_SELECTION,
            int(run_env.PHASE_TREASURE): DecisionType.TREASURE,
            int(run_env.PHASE_CRYSTAL_SPHERE): DecisionType.MINI_GAME,
            int(run_env.PHASE_BUNDLE_SELECT): DecisionType.CARD_SELECTION,
        },
        observation_size=int(native.RUN_OBS_SIZE),
        max_actions=int(native.RUN_MAX_ACTIONS),
        max_enemies=int(native.MAX_ENEMIES),
        enemy_offset=int(native.OBS_ENEMY_OFFSET),
        enemy_slot_size=int(native.OBS_ENEMY_SLOT_SIZE),
        max_hand=int(native.OBS_MAX_HAND),
        hand_offset=int(native.OBS_HAND_OFFSET),
        hand_slot_size=int(native.OBS_CARD_SLOT_SIZE),
        targeted_card_ids=targeted_card_ids,
        # The pinned engine currently implements one explicitly aimed potion. Keep this
        # list at the adapter boundary until upstream exports potion target metadata.
        targeted_potion_ids=frozenset({47}),
    )
    env_class = cast(Callable[..., object], run_env.Sts2RunEnv)

    def backend_factory() -> EvanGambitRunBackend:
        raw_environment = env_class(
            max_episode_steps=max_episode_steps,
            max_floors=max_floors,
        )
        return _GymRunBackend(raw_environment)

    def environment_factory() -> EvanGambitEnvironment:
        return EvanGambitEnvironment(
            backend_factory,
            manifest,
            layout,
            allow_pending=allow_pending,
        )

    evidence = EvanGambitRuntimeEvidence(
        upstream_root=root,
        upstream_revision=revision,
        upstream_tree=tree,
        game_version=game_version,
        steam_build_id=steam_build_id,
        native_library=native_library,
        native_sha256=native_sha256,
        native_size_bytes=len(native_bytes),
        platform=_platform_name(),
        architecture=platform.machine().casefold(),
    )
    return LoadedEvanGambitBackend(environment_factory, evidence)


class _GymRunBackend:
    def __init__(self, environment: object) -> None:
        self._environment = cast(Any, environment)

    def reset(self, *, seed: int) -> tuple[object, Mapping[str, object]]:
        raw, info = self._environment.reset(seed=seed)
        return raw, cast(Mapping[str, object], info)

    def current(self) -> tuple[object, Mapping[str, object]]:
        return self._environment._obs(), cast(Mapping[str, object], self._environment._info())

    def action_masks(self) -> object:
        return self._environment.action_masks()

    def step(
        self, action: int, target: int = -1
    ) -> tuple[object, float, bool, bool, Mapping[str, object]]:
        raw, reward, terminal, truncated, info = self._environment.step(action, target)
        return raw, float(reward), bool(terminal), bool(truncated), cast(Mapping[str, object], info)

    def clone(self, *, resample_hidden: bool, seed: int | None) -> _GymRunBackend:
        return _GymRunBackend(self._environment.clone(resample_hidden=resample_hidden, seed=seed))

    def map_graph(self) -> Mapping[str, object]:
        return cast(Mapping[str, object], self._environment.map_graph())

    def close(self) -> None:
        self._environment.close()


def _integer_vector(value: object, expected_size: int) -> tuple[int, ...]:
    try:
        result = tuple(int(item) for item in cast(Any, value))
    except (TypeError, ValueError) as error:
        raise EvanGambitBackendError("Backend observation is not an integer vector") from error
    if len(result) != expected_size:
        raise EvanGambitBackendError(
            f"Backend observation size changed: expected {expected_size}, got {len(result)}"
        )
    return result


def _boolean_vector(value: object, expected_size: int) -> tuple[bool, ...]:
    try:
        result = tuple(bool(item) for item in cast(Any, value))
    except TypeError as error:
        raise EvanGambitBackendError("Backend action mask is not iterable") from error
    if len(result) != expected_size:
        raise EvanGambitBackendError(
            f"Backend action-mask size changed: expected {expected_size}, got {len(result)}"
        )
    return result


def _json_value(value: object, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    item_method = getattr(value, "item", None)
    if callable(item_method):
        return _json_value(item_method(), path)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise EvanGambitBackendError(f"Non-string mapping key at {path}: {key!r}")
            result[key] = _json_value(child, f"{path}.{key}")
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(child, f"{path}[]") for child in value]
    raise EvanGambitBackendError(f"Non-public or unserializable backend value at {path}")


def _project_map(value: Mapping[str, object]) -> dict[str, object]:
    nodes_value = value.get("nodes", {})
    if not isinstance(nodes_value, Mapping):
        raise EvanGambitBackendError("Backend map nodes are malformed")
    nodes = [
        {"x": int(coordinate[0]), "y": int(coordinate[1]), "node_type": int(node_type)}
        for coordinate, node_type in nodes_value.items()
        if isinstance(coordinate, tuple) and len(coordinate) == 2
    ]
    edges_value = value.get("edges", ())
    edges = [
        {
            "from": {"x": int(edge[0][0]), "y": int(edge[0][1])},
            "to": {"x": int(edge[1][0]), "y": int(edge[1][1])},
        }
        for edge in cast(Sequence[tuple[tuple[int, int], tuple[int, int]]], edges_value)
    ]
    current = value.get("current")
    current_value = (
        {"x": int(current[0]), "y": int(current[1])}
        if isinstance(current, tuple) and len(current) == 2
        else None
    )
    return {
        "nodes": sorted(nodes, key=lambda node: (node["y"], node["x"])),
        "edges": edges,
        "boss_encounter": str(value.get("boss_encounter", "unknown")),
        "current": current_value,
    }


def _required_int(value: Mapping[str, object], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise EvanGambitBackendError(f"Backend field {key!r} must be an integer")
    return raw


def _git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise EvanGambitBackendError(f"Cannot inspect upstream checkout {root}: {error}") from error
    return result.stdout.strip()


def _load_json_object(path: Path) -> dict[str, object]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvanGambitBackendError(f"Cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise EvanGambitBackendError(f"Expected a JSON object in {path}")
    return cast(dict[str, object], value)


def _prepend_import_path(source_root: Path) -> None:
    path = str(source_root)
    if path not in sys.path:
        sys.path.insert(0, path)


def _verify_import_root(module: object, root: Path) -> None:
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or root not in Path(module_file).resolve().parents:
        raise EvanGambitBackendError(
            "A different sts2_gym installation is already imported; start a fresh process"
        )


def _native_library_path(root: Path) -> Path:
    names = {
        "darwin": "Sts2Emulator.dylib",
        "linux": "Sts2Emulator.so",
        "win32": "Sts2Emulator.dll",
    }
    name = names.get(sys.platform)
    if name is None:
        raise EvanGambitBackendError(f"Unsupported platform: {sys.platform}")
    configured = os.environ.get("STS2_LIB_PATH")
    directory = Path(configured).expanduser().resolve() if configured else root / "out"
    return (directory / name).resolve()


def _platform_name() -> str:
    return {"darwin": "macos", "linux": "linux", "win32": "windows"}.get(sys.platform, sys.platform)
