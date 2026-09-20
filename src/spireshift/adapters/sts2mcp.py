from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from spireshift.core.manifest import (
    PatchManifest,
    RulesetIdentity,
    verify_installation_identity,
)
from spireshift.core.types import DecisionType, LegalAction, Observation

LIVE_SNAPSHOT_SCHEMA_VERSION = "live-snapshot-v1"
STS2MCP_PROTOCOL = "sts2mcp-http-v1"
DEFAULT_STS2MCP_URL = "http://127.0.0.1:15526"

_BRIDGE_VERSION_PATTERN = re.compile(r"^Hello from STS2 MCP v(?P<version>[^\s]+)$")
_PUBLIC_TOP_LEVEL_FIELDS = {
    "battle",
    "blocked_options",
    "bundle_select",
    "card_reward",
    "card_select",
    "characters",
    "completed_count",
    "crystal_sphere",
    "current_profile_id",
    "epochs",
    "event",
    "fake_merchant",
    "fast_mp",
    "friends",
    "game_over",
    "hand_select",
    "loading",
    "lobby",
    "locked_count",
    "map",
    "menu_screen",
    "message",
    "no_friends",
    "no_slot_count",
    "obtained_unrevealed_count",
    "options",
    "overlay",
    "player",
    "relic_select",
    "rest_site",
    "revealed_count",
    "rewards",
    "room_type",
    "run",
    "shop",
    "state_type",
    "total_slots",
    "treasure",
}
_REJECTED_SOURCE_KEYS = {
    "draw_order",
    "draw_pile_order",
    "future",
    "future_reward",
    "hidden",
    "next_reward",
    "random_seed",
    "rng",
    "rng_state",
}
_COMBAT_STATES = {"monster", "elite", "boss"}


class LiveStateError(RuntimeError):
    """Base error for safe live-state capture failures."""


class LiveTransportError(LiveStateError):
    """The pinned bridge could not be read safely."""


class InformationBoundaryError(LiveStateError):
    """The source payload cannot be admitted to the public observation."""


class BridgeVersionError(LiveStateError):
    """The running bridge version differs from the ruleset manifest."""


class Sts2McpReadTransport(Protocol):
    def bridge_version(self) -> str: ...

    def read_singleplayer_state(self) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class ActionProjection:
    actions: tuple[LegalAction, ...]
    status: str
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiveSnapshot:
    ruleset: RulesetIdentity
    observation: Observation
    legal_actions: tuple[LegalAction, ...]
    bridge_version: str
    action_coverage_status: str
    action_coverage_issues: tuple[str, ...]
    omitted_source_paths: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": LIVE_SNAPSHOT_SCHEMA_VERSION,
            "ruleset": self.ruleset.as_dict(),
            "observation": self.observation.as_dict(),
            "legal_actions": [action.as_dict() for action in self.legal_actions],
            "bridge": {
                "component_id": "sts2mcp",
                "version": self.bridge_version,
                "protocol": STS2MCP_PROTOCOL,
                "read_only": True,
            },
            "action_coverage": {
                "status": self.action_coverage_status,
                "issues": list(self.action_coverage_issues),
            },
            "projection": {"omitted_source_paths": list(self.omitted_source_paths)},
        }


class Sts2McpHttpTransport:
    """GET-only transport for a local STS2_MCP bridge."""

    def __init__(
        self,
        base_url: str = DEFAULT_STS2MCP_URL,
        *,
        timeout_seconds: float = 3.0,
        maximum_response_bytes: int = 8 * 1024 * 1024,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if maximum_response_bytes <= 0:
            raise ValueError("maximum_response_bytes must be positive")
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("STS2_MCP base URL must be an uncredentialed local HTTP origin")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._maximum_response_bytes = maximum_response_bytes

    def bridge_version(self) -> str:
        payload = self._read_json("/")
        if payload.get("status") != "ok":
            raise LiveTransportError("STS2_MCP health response did not report status=ok")
        message = payload.get("message")
        if not isinstance(message, str):
            raise LiveTransportError("STS2_MCP health response omitted its version message")
        match = _BRIDGE_VERSION_PATTERN.fullmatch(message)
        if match is None:
            raise LiveTransportError(f"Unrecognized STS2_MCP health message: {message!r}")
        return match.group("version")

    def read_singleplayer_state(self) -> dict[str, object]:
        return self._read_json("/api/v1/singleplayer?format=json")

    def _read_json(self, path: str) -> dict[str, object]:
        request = Request(
            f"{self._base_url}{path}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                encoded = response.read(self._maximum_response_bytes + 1)
        except HTTPError as error:
            raise LiveTransportError(f"STS2_MCP returned HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            raise LiveTransportError(f"Cannot read STS2_MCP: {error}") from error
        if len(encoded) > self._maximum_response_bytes:
            raise LiveTransportError("STS2_MCP response exceeded the configured size limit")
        try:
            value: object = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LiveTransportError("STS2_MCP returned invalid JSON") from error
        if not isinstance(value, dict):
            raise LiveTransportError("STS2_MCP response must be a JSON object")
        return cast(dict[str, object], value)


class Sts2McpStateProjector:
    """Projects a recorded pinned-bridge payload into the public contract."""

    def __init__(self, manifest: PatchManifest) -> None:
        if manifest.adapter.component_id != "sts2mcp-live-bridge":
            raise ValueError(
                "Live adapter requires a manifest for component_id=sts2mcp-live-bridge"
            )
        self.patch_id = manifest.patch.patch_id
        self.ruleset = manifest.ruleset_identity()
        self._expected_bridge_version = manifest.adapter.version

    def project(self, source: object, *, bridge_version: str) -> LiveSnapshot:
        if bridge_version != self._expected_bridge_version:
            raise BridgeVersionError(
                "STS2_MCP version mismatch: "
                f"source {bridge_version!r}, manifest requires {self._expected_bridge_version!r}"
            )
        raw = _mapping(source, "STS2_MCP state")
        unknown_fields = sorted(set(raw) - _PUBLIC_TOP_LEVEL_FIELDS)
        if unknown_fields:
            raise InformationBoundaryError(
                f"STS2_MCP state contains unaudited top-level fields: {unknown_fields}"
            )
        state_type = _required_string(raw, "state_type", "STS2_MCP state")
        omitted: list[str] = []
        public_state = cast(
            dict[str, Any],
            _project_public_json(raw, path="source", omitted=omitted),
        )
        public_state["terminal"] = state_type == "game_over"
        public_state["victory"] = _terminal_victory(raw, state_type)
        encoded = json.dumps(
            public_state,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
        observation = Observation(
            schema_version=self.ruleset.interface.observation_schema,
            patch_id=self.patch_id,
            decision_type=_decision_type(state_type),
            public_state=public_state,
            state_hash=hashlib.sha256(encoded).hexdigest(),
        )
        action_projection = _legal_actions(raw, state_type)
        return LiveSnapshot(
            ruleset=self.ruleset,
            observation=observation,
            legal_actions=action_projection.actions,
            bridge_version=bridge_version,
            action_coverage_status=action_projection.status,
            action_coverage_issues=action_projection.issues,
            omitted_source_paths=tuple(omitted),
        )


class Sts2McpLiveStateAdapter:
    """Reads live state only after the game and bridge identities are verified."""

    def __init__(
        self,
        manifest: PatchManifest,
        installation_manifest: object,
        transport: Sts2McpReadTransport,
    ) -> None:
        identity_errors = verify_installation_identity(manifest, installation_manifest)
        if identity_errors:
            raise LiveStateError("; ".join(identity_errors))
        self._expected_bridge_version = manifest.adapter.version
        self._transport = transport
        self._projector = Sts2McpStateProjector(manifest)

    def snapshot(self) -> LiveSnapshot:
        bridge_version = self._transport.bridge_version()
        if bridge_version != self._expected_bridge_version:
            raise BridgeVersionError(
                "STS2_MCP version mismatch: "
                f"running {bridge_version!r}, manifest requires {self._expected_bridge_version!r}"
            )
        return self._projector.project(
            self._transport.read_singleplayer_state(), bridge_version=bridge_version
        )


def _project_public_json(value: object, *, path: str, omitted: list[str]) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, list):
        return [
            _project_public_json(item, path=f"{path}[{index}]", omitted=omitted)
            for index, item in enumerate(value)
        ]
    if not isinstance(value, Mapping):
        raise InformationBoundaryError(f"{path} contains a non-JSON value")
    projected: dict[str, object] = {}
    for raw_key, child in value.items():
        key = str(raw_key)
        child_path = f"{path}.{key}"
        normalized = key.casefold().replace("-", "_").replace(" ", "_")
        if normalized == "is_hidden":
            if not isinstance(child, bool):
                raise InformationBoundaryError(f"{child_path} must be boolean")
            projected["is_revealed"] = not child
            omitted.append(f"{child_path}->is_revealed")
            continue
        if "seed" in set(normalized.split("_")):
            omitted.append(child_path)
            continue
        if normalized in _REJECTED_SOURCE_KEYS or set(normalized.split("_")).intersection(
            {"rng", "future"}
        ):
            raise InformationBoundaryError(f"{child_path} is forbidden privileged state")
        projected[key] = _project_public_json(child, path=child_path, omitted=omitted)
    return projected


def _legal_actions(source: dict[str, object], state_type: str) -> ActionProjection:
    actions: list[LegalAction] = []
    issues: list[str] = []
    if state_type == "menu":
        _append_menu_actions(actions, source.get("options"), issues)
    elif state_type in _COMBAT_STATES:
        _append_combat_actions(actions, source, issues)
    elif state_type == "hand_select":
        _append_index_actions(actions, source, "hand_select", "cards", "combat_select_card")
        _append_flag_action(
            actions, source, "hand_select", "can_confirm", "combat_confirm_selection"
        )
    elif state_type == "map":
        _append_index_actions(actions, source, "map", "next_options", "choose_map_node")
    elif state_type == "rewards":
        _append_index_actions(actions, source, "rewards", "items", "claim_reward")
        _append_flag_action(actions, source, "rewards", "can_proceed", "proceed")
    elif state_type == "card_reward":
        _append_index_actions(
            actions, source, "card_reward", "cards", "select_card_reward", "card_index"
        )
        _append_flag_action(actions, source, "card_reward", "can_skip", "skip_card_reward")
    elif state_type == "event":
        event = _optional_mapping(source.get("event"))
        if event.get("in_dialogue") is True:
            actions.append(_action("advance_dialogue"))
        for option in _mapping_items(event.get("options")):
            if option.get("is_locked") is not True and option.get("was_chosen") is not True:
                _append_indexed(actions, "choose_event_option", option)
    elif state_type == "rest_site":
        rest_site = _optional_mapping(source.get("rest_site"))
        for option in _mapping_items(rest_site.get("options")):
            if option.get("is_enabled") is True:
                _append_indexed(actions, "choose_rest_option", option)
        if rest_site.get("can_proceed") is True:
            actions.append(_action("proceed"))
    elif state_type in {"shop", "fake_merchant"}:
        container = _optional_mapping(source.get(state_type))
        shop = (
            _optional_mapping(container.get("shop")) if state_type == "fake_merchant" else container
        )
        for item in _mapping_items(shop.get("items")):
            if item.get("is_stocked") is True and item.get("can_afford") is True:
                _append_indexed(actions, "shop_purchase", item)
        if shop.get("can_proceed") is True:
            actions.append(_action("proceed"))
    elif state_type == "treasure":
        _append_index_actions(actions, source, "treasure", "relics", "claim_treasure_relic")
        _append_flag_action(actions, source, "treasure", "can_proceed", "proceed")
    elif state_type == "card_select":
        _append_index_actions(actions, source, "card_select", "cards", "select_card")
        _append_flag_action(actions, source, "card_select", "can_confirm", "confirm_selection")
        _append_flag_action(actions, source, "card_select", "can_cancel", "cancel_selection")
    elif state_type == "bundle_select":
        _append_index_actions(actions, source, "bundle_select", "bundles", "select_bundle")
        _append_flag_action(
            actions, source, "bundle_select", "can_confirm", "confirm_bundle_selection"
        )
        _append_flag_action(
            actions, source, "bundle_select", "can_cancel", "cancel_bundle_selection"
        )
    elif state_type == "relic_select":
        _append_index_actions(actions, source, "relic_select", "relics", "select_relic")
        _append_flag_action(actions, source, "relic_select", "can_skip", "skip_relic_selection")
    elif state_type == "crystal_sphere":
        sphere = _optional_mapping(source.get("crystal_sphere"))
        if sphere.get("can_use_big_tool") is True:
            actions.append(_action("crystal_sphere_set_tool", {"tool": "big"}))
        if sphere.get("can_use_small_tool") is True:
            actions.append(_action("crystal_sphere_set_tool", {"tool": "small"}))
        for cell in _mapping_items(sphere.get("clickable_cells")):
            x = cell.get("x")
            y = cell.get("y")
            if isinstance(x, int) and isinstance(y, int):
                actions.append(_action("crystal_sphere_click_cell", {"x": x, "y": y}))
        if sphere.get("can_proceed") is True:
            actions.append(_action("crystal_sphere_proceed"))
    elif state_type == "game_over":
        game_over = _optional_mapping(source.get("game_over"))
        _append_menu_actions(actions, game_over.get("options"), issues)
    elif state_type in {"unknown", "overlay"}:
        issues.append(f"unsupported state_type: {state_type}")
        return ActionProjection(tuple(actions), "unsupported", tuple(issues))
    else:
        issues.append(f"unaudited state_type: {state_type}")
        return ActionProjection(tuple(actions), "unsupported", tuple(issues))

    action_ids = [action.action_id for action in actions]
    if len(action_ids) != len(set(action_ids)):
        raise LiveStateError("Projected legal actions contain duplicate IDs")
    if issues:
        return ActionProjection(tuple(actions), "partial", tuple(issues))
    if not actions and state_type != "game_over":
        return ActionProjection((), "settling", ("no legal action is currently available",))
    return ActionProjection(tuple(actions), "ready", ())


def _append_combat_actions(
    actions: list[LegalAction], source: dict[str, object], issues: list[str]
) -> None:
    battle = _optional_mapping(source.get("battle"))
    if battle.get("is_play_phase") is not True:
        issues.append("combat is outside the player play phase")
        return
    player = _optional_mapping(source.get("player"))
    enemies = _mapping_items(battle.get("enemies"))
    enemy_ids = [
        entity_id
        for enemy in enemies
        if isinstance((entity_id := enemy.get("entity_id")), str) and entity_id
    ]
    for card in _mapping_items(player.get("hand")):
        if card.get("can_play") is not True:
            continue
        index = card.get("index")
        if not isinstance(index, int):
            continue
        targets = _targets(card.get("target_type"), enemy_ids)
        if targets is None:
            issues.append(f"unsupported card target_type: {card.get('target_type')!r}")
            continue
        for target in targets:
            payload: dict[str, object] = {"card_index": index}
            if target is not None:
                payload["target"] = target
            actions.append(_action("play_card", payload))
    for potion in _mapping_items(player.get("potions")):
        if potion.get("can_use_in_combat") is True:
            slot = potion.get("slot")
            if not isinstance(slot, int):
                continue
            targets = _targets(potion.get("target_type"), enemy_ids)
            if targets is None:
                issues.append(f"unsupported potion target_type: {potion.get('target_type')!r}")
            else:
                for target in targets:
                    payload = {"slot": slot}
                    if target is not None:
                        payload["target"] = target
                    actions.append(_action("use_potion", payload))
        slot = potion.get("slot")
        if isinstance(slot, int):
            actions.append(_action("discard_potion", {"slot": slot}))
    actions.append(_action("end_turn"))


def _targets(target_type: object, enemy_ids: list[str]) -> list[str | None] | None:
    if not isinstance(target_type, str):
        return None
    normalized = target_type.casefold().replace("_", "")
    if normalized in {"none", "self", "allenemies", "all"}:
        return [None]
    if normalized in {"anyenemy", "enemy", "singleenemy"}:
        return list(enemy_ids)
    return None


def _append_menu_actions(actions: list[LegalAction], value: object, issues: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        issues.append("menu options are not an array")
        return
    for item in value:
        option: object
        if isinstance(item, str):
            option = item
            enabled = True
        elif isinstance(item, dict):
            option = item.get("name")
            enabled = item.get("enabled") is not False
        else:
            issues.append("menu option has an unsupported shape")
            continue
        if isinstance(option, str) and option and enabled:
            actions.append(_action("menu_select", {"option": option}))


def _append_index_actions(
    actions: list[LegalAction],
    source: dict[str, object],
    container_key: str,
    items_key: str,
    kind: str,
    parameter: str = "index",
) -> None:
    container = _optional_mapping(source.get(container_key))
    for item in _mapping_items(container.get(items_key)):
        _append_indexed(actions, kind, item, parameter)


def _append_indexed(
    actions: list[LegalAction],
    kind: str,
    item: dict[str, object],
    parameter: str = "index",
) -> None:
    index = item.get("index")
    if isinstance(index, int):
        actions.append(_action(kind, {parameter: index}))


def _append_flag_action(
    actions: list[LegalAction],
    source: dict[str, object],
    container_key: str,
    flag: str,
    kind: str,
) -> None:
    if _optional_mapping(source.get(container_key)).get(flag) is True:
        actions.append(_action(kind))


def _action(kind: str, payload: dict[str, object] | None = None) -> LegalAction:
    parameters = {} if payload is None else payload
    encoded = json.dumps(parameters, sort_keys=True, separators=(",", ":")).encode()
    suffix = hashlib.sha256(encoded).hexdigest()[:16]
    return LegalAction(action_id=f"{kind}:{suffix}", kind=kind, payload=parameters)


def _terminal_victory(source: dict[str, object], state_type: str) -> bool | None:
    if state_type != "game_over":
        return False
    game_over = _optional_mapping(source.get("game_over"))
    victory = game_over.get("victory")
    return victory if isinstance(victory, bool) else None


def _decision_type(state_type: str) -> DecisionType:
    if state_type == "menu":
        return DecisionType.MENU
    if state_type == "map":
        return DecisionType.PATH
    if state_type in _COMBAT_STATES:
        return DecisionType.COMBAT
    if state_type == "hand_select":
        return DecisionType.COMBAT_SELECTION
    if state_type in {"rewards", "card_reward"}:
        return DecisionType.REWARD
    if state_type == "event":
        return DecisionType.EVENT
    if state_type == "rest_site":
        return DecisionType.REST_SITE
    if state_type in {"shop", "fake_merchant"}:
        return DecisionType.SHOP
    if state_type == "treasure":
        return DecisionType.TREASURE
    if state_type in {"card_select", "bundle_select"}:
        return DecisionType.CARD_SELECTION
    if state_type == "relic_select":
        return DecisionType.RELIC_SELECTION
    if state_type == "crystal_sphere":
        return DecisionType.MINI_GAME
    if state_type == "game_over":
        return DecisionType.TERMINAL
    return DecisionType.UNKNOWN


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LiveStateError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _optional_mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _mapping_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)]


def _required_string(value: dict[str, object], key: str, label: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise LiveStateError(f"{label}.{key} must be a non-empty string")
    return result
