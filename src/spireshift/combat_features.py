from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.models import _exact_keys, _integer, _mapping
from spireshift.representations import CompositionalModelInput, FeatureValueType, ScalarFeature

ENCODER_ID = "evangambit-public-card-target-v1"
LAYOUT_SCHEMA = "evangambit-public-combat-layout-v1"
SELECTION_ENCODER_ID = "evangambit-public-card-target-v2"
SELECTION_LAYOUT_SCHEMA = "evangambit-public-combat-layout-v2"
TRANSFORM_ENCODER_ID = "evangambit-public-card-target-v3"
TRANSFORM_LAYOUT_SCHEMA = "evangambit-public-combat-layout-v3"

# These numbers describe the admitted, frozen observation, not a future engine version.
# Source hashes and patch/ruleset bindings are checked by the owner data audit.
PINNED_LAYOUT = {
    "observation_size": 682,
    "hand_offset": 8,
    "hand_slots": 10,
    "card_slot_size": 4,
    "potion_offset": 48,
    "potion_slots": 6,
    "potion_slot_size": 2,
    "player_buff_offset": 60,
    "player_buff_slots": 10,
    "enemy_offset": 80,
    "enemy_slots": 6,
    "enemy_slot_size": 15,
    "enemy_buff_slots": 5,
    "secondary_intent_offset": 170,
    "selection_kind_offset": 183,
    "orb_capacity_offset": 225,
    "orb_offset": 226,
    "orb_slots": 10,
    "incoming_offset": 256,
    "incoming_slots": 5,
}
SELECTION_LAYOUT = {
    **PINNED_LAYOUT,
    "selection_count_offset": 184,
    "selection_offset": 185,
    "selection_slots": 10,
    "upgrade_selection_kind": 15,
}
TRANSFORM_LAYOUT = {**SELECTION_LAYOUT, "transform_hand_selection_kind": 20}


@dataclass(frozen=True, slots=True)
class CombatLayout:
    patch_id: str
    ruleset_manifest_id: str
    schema_version: str = LAYOUT_SCHEMA

    @property
    def encoder_id(self) -> str:
        if self.schema_version == LAYOUT_SCHEMA:
            return ENCODER_ID
        if self.schema_version == SELECTION_LAYOUT_SCHEMA:
            return SELECTION_ENCODER_ID
        if self.schema_version == TRANSFORM_LAYOUT_SCHEMA:
            return TRANSFORM_ENCODER_ID
        raise ValueError("Unsupported public combat layout")

    @classmethod
    def from_mapping(cls, value: object) -> CombatLayout:
        doc = _mapping(value, "public combat layout")
        if doc.get("schema_version") == LAYOUT_SCHEMA:
            pinned = PINNED_LAYOUT
        elif doc.get("schema_version") == SELECTION_LAYOUT_SCHEMA:
            pinned = SELECTION_LAYOUT
        elif doc.get("schema_version") == TRANSFORM_LAYOUT_SCHEMA:
            pinned = TRANSFORM_LAYOUT
        else:
            raise ValueError("Unsupported public combat layout")
        _exact_keys(doc, {"schema_version", "patch_id", "ruleset_manifest_id", *pinned}, "layout")
        for key, expected in pinned.items():
            if _integer(doc[key], key) != expected:
                raise ValueError(f"Frozen public combat layout differs: {key}")
        if not isinstance(doc["patch_id"], str) or not doc["patch_id"]:
            raise ValueError("Combat layout patch is missing")
        if not isinstance(doc["ruleset_manifest_id"], str) or not doc["ruleset_manifest_id"]:
            raise ValueError("Combat layout ruleset is missing")
        return cls(doc["patch_id"], doc["ruleset_manifest_id"], doc["schema_version"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "patch_id": self.patch_id,
            "ruleset_manifest_id": self.ruleset_manifest_id,
            **(
                TRANSFORM_LAYOUT
                if self.encoder_id == TRANSFORM_ENCODER_ID
                else SELECTION_LAYOUT
                if self.encoder_id == SELECTION_ENCODER_ID
                else PINNED_LAYOUT
            ),
        }


def _fields(
    features: tuple[ScalarFeature, ...],
) -> dict[tuple[tuple[str, ...], tuple[int, ...]], ScalarFeature]:
    fields = {(f.path, f.indices): f for f in features}
    if len(fields) != len(features):
        raise ValueError("Duplicate public combat scalar")
    return fields


def _number(feature: ScalarFeature | None, label: str) -> int:
    if (
        feature is None
        or feature.value_type != FeatureValueType.NUMERIC
        or feature.numeric_value is None
        or not math.isfinite(feature.numeric_value)
        or not feature.numeric_value.is_integer()
    ):
        raise ValueError(f"Public combat {label} must be an integer")
    return int(feature.numeric_value)


def _cards(vector: tuple[int, ...], offset: int, slots: int) -> tuple[dict[str, int], ...]:
    cards = []
    empty_seen = False
    for slot in range(slots):
        at = offset + slot * 4
        identity, upgraded, enchantment, amount = vector[at : at + 4]
        if identity == 0:
            if any((upgraded, enchantment, amount)):
                raise ValueError("Empty public card slot carries card properties")
            empty_seen = True
            continue
        if empty_seen or identity < 0 or upgraded not in (0, 1) or enchantment < 0:
            raise ValueError("Public card slots are not a contiguous valid hand")
        cards.append(
            {
                "card_id": identity,
                "upgraded": upgraded,
                "enchantment_id": enchantment,
                "enchantment_amount": amount,
            }
        )
    return tuple(cards)


def _buffs(vector: tuple[int, ...], offset: int, slots: int) -> list[dict[str, int]]:
    values: Counter[int] = Counter()
    for slot in range(slots):
        identity, amount = vector[offset + slot * 2 : offset + slot * 2 + 2]
        if identity < 0:
            raise ValueError("Invalid public status slot")
        # BuffId.Strength is zero in this pinned public encoding. (0, 0) is padding;
        # (0, nonzero) is a visible positive or negative Strength amount.
        if identity or amount:
            values[identity] += amount
    return [{"status_id": identity, "amount": values[identity]} for identity in sorted(values)]


@dataclass(frozen=True, slots=True)
class CombatInput:
    source_action_ids: tuple[str, ...]
    bindings: tuple[dict[str, Any], ...]
    tokens: tuple[dict[str, float], ...]
    context: dict[str, Any]
    encoder_id: str = ENCODER_ID

    def vectors(self, dimension: int) -> tuple[dict[int, float], ...]:
        if isinstance(dimension, bool) or not 64 <= dimension <= 65536:
            raise ValueError("Combat feature dimension must be in [64, 65536]")
        result = []
        for tokens in self.tokens:
            values: dict[int, float] = {}
            for token, amount in sorted(tokens.items()):
                # v3 adds a new choice without changing any v2 token or vector coordinate.
                namespace = (
                    SELECTION_ENCODER_ID
                    if self.encoder_id == TRANSFORM_ENCODER_ID
                    else self.encoder_id
                )
                digest = hashlib.sha256(f"{namespace}|{token}".encode()).digest()
                index = int.from_bytes(digest[:8], "big") % dimension
                sign = 1 if digest[8] & 1 else -1
                values[index] = values.get(index, 0.0) + sign * amount
            result.append({k: v for k, v in sorted(values.items()) if v})
        return tuple(result)

    def feature_digests(self) -> tuple[str, ...]:
        return tuple(manifest_identifier(tokens) for tokens in self.tokens)


def bind_public_combat(
    representation: CompositionalModelInput, layout: CombatLayout
) -> CombatInput | None:
    """A separate policy feature space; never mutates the old encoder or checkpoint.

    Hand action indices only locate visible objects. Target positions remain categorical
    public locators because enemy position can matter to mechanics. Operational handles,
    seed, state hashes, hidden state and numeric identifier magnitudes never enter tokens.
    """
    if representation.decision_type != "combat":
        return None
    if (
        representation.patch_id != layout.patch_id
        or representation.ruleset_manifest_id != layout.ruleset_manifest_id
    ):
        raise ValueError("Public combat input belongs to another patch or ruleset")
    fields = _fields(representation.global_features + representation.persistent_resources)
    slots = {
        indices[0]: _number(f, "observation vector")
        for (path, indices), f in fields.items()
        if path == ("observation_vector",) and len(indices) == 1
    }
    if sorted(slots) != list(range(PINNED_LAYOUT["observation_size"])):
        raise ValueError("Public combat observation vector layout differs")
    vector = tuple(slots[i] for i in range(len(slots)))
    hp, maximum, block, energy, max_energy, draw, discard, exhaust = vector[:8]
    if not 0 < hp <= maximum or any(
        v < 0 for v in (block, energy, max_energy, draw, discard, exhaust)
    ):
        raise ValueError("Invalid actionable public player resources")
    selection_kind = vector[183]
    if selection_kind and (
        layout.encoder_id not in {SELECTION_ENCODER_ID, TRANSFORM_ENCODER_ID}
        or selection_kind not in ({15, 20} if layout.encoder_id == TRANSFORM_ENCODER_ID else {15})
    ):
        raise ValueError("Open card selection is not a supported combat action space")
    for name, expected in (("player_hp", hp), ("player_max_hp", maximum)):
        if _number(fields.get(((name,), ())), name) != expected:
            raise ValueError("Public player fields differ from the combat vector")
    hand = _cards(vector, 8, 10)
    choices: tuple[dict[str, int], ...] = ()
    if layout.encoder_id in {SELECTION_ENCODER_ID, TRANSFORM_ENCODER_ID}:
        selection_count = vector[184]
        choices = _cards(vector, 185, 10)
        if selection_kind:
            if not 1 <= selection_count <= 10 or len(choices) != selection_count:
                raise ValueError("Public card selection count/cards differ or exceed visibility")
            if Counter(manifest_identifier(card) for card in choices) - Counter(
                manifest_identifier(card) for card in hand
            ):
                raise ValueError("Public selection choices are not visible cards in hand")
            if selection_kind == 15 and any(card["upgraded"] for card in choices):
                raise ValueError("Public upgrade choices are not unupgraded cards in hand")
        elif selection_count or choices:
            raise ValueError("Closed public selection carries choice count/cards")
    incoming = _cards(vector, 256, 5)
    statuses = _buffs(vector, 60, 10)
    potions = []
    for slot in range(6):
        identity, present = vector[48 + slot * 2 : 50 + slot * 2]
        if identity < 0 or present != int(identity != 0):
            raise ValueError("Invalid public potion identity/presence")
        if _number(fields.get((("potions",), (slot,))), "potion ID") != identity:
            raise ValueError("Public potion list differs from combat slots")
        potions.append(identity)
    enemies = {}
    for slot in range(6):
        at = 80 + slot * 15
        ehp, emax, eblock, intent, magnitude = vector[at : at + 5]
        if ehp <= 0:
            continue
        identity = _number(fields.get((("enemy_def_ids",), (slot,))), "enemy ID")
        if emax < ehp or eblock < 0 or intent < 0 or identity <= 0:
            raise ValueError("Invalid living public enemy")
        secondary, secondary_magnitude = vector[170 + slot * 2 : 172 + slot * 2]
        enemies[slot] = {
            "public_position": slot,
            "enemy_id": identity,
            "hp": ehp,
            "max_hp": emax,
            "block": eblock,
            "intent_type": intent,
            "intent_magnitude": magnitude,
            "secondary_intent_type": secondary,
            "secondary_intent_magnitude": secondary_magnitude,
            "statuses": _buffs(vector, at + 5, 5),
        }
    if not enemies:
        raise ValueError("Actionable combat has no living visible enemies")
    orbs = []
    for slot in range(10):
        identity, passive, evoke = vector[226 + slot * 3 : 229 + slot * 3]
        if identity < 0 or (identity == 0 and (passive or evoke)):
            raise ValueError("Invalid public orb slot")
        if identity:
            orbs.append({"type_id": identity, "passive": passive, "evoke": evoke})
    floor = _number(fields.get((("floor",), ())), "floor")
    act = fields.get((("act",), ()))
    if floor < 1 or act is None or not act.categorical_value:
        raise ValueError("Public combat run context is missing")
    context = {
        "player": {
            "hp": hp,
            "max_hp": maximum,
            "block": block,
            "energy": energy,
            "max_energy": max_energy,
            "draw": draw,
            "discard": discard,
            "exhaust": exhaust,
            "statuses": statuses,
        },
        "floor": floor,
        "act": act.categorical_value,
        "hand": sorted(hand, key=manifest_identifier),
        "incoming": list(incoming),
        "potions": sorted(p for p in potions if p),
        "enemies": sorted(enemies.values(), key=manifest_identifier),
        "orb_capacity": vector[225],
        "orbs": orbs,
    }
    if selection_kind:
        context["selection"] = {
            "kind_id": selection_kind,
            "cards": sorted(choices, key=manifest_identifier),
        }
    bindings = []
    seen = set()
    for candidate in representation.candidates:
        f = _fields(candidate.features)
        phase = f.get((("phase",), ()))
        if (
            candidate.action_kind != "evangambit_combat"
            or phase is None
            or phase.categorical_value != "combat"
            or set(f) - {(("phase",), ()), (("action_index",), ()), (("target_index",), ())}
        ):
            raise ValueError("Unsupported public combat action payload")
        index = _number(f.get((("action_index",), ())), "action index")
        target = (
            _number(f[(("target_index",), ())], "target index")
            if (("target_index",), ()) in f
            else -1
        )
        if (index, target) in seen or index < 0 or target < -1:
            raise ValueError("Duplicate or invalid public combat action binding")
        seen.add((index, target))
        if target != -1 and target not in enemies:
            raise ValueError("Public combat action targets an absent/dead enemy")
        binding: dict[str, Any]
        if selection_kind:
            if index >= len(choices):
                raise ValueError("Public card selection has an outside/skip action")
            binding = {
                "kind": "select_upgrade_card"
                if selection_kind == 15
                else "select_transform_hand_to_minion_strike",
                "card": choices[index],
                "potion_id": None,
            }
            # Historical adapter menus can attach an enemy target to a selection index.
            # The pinned ResolveCardSelection uses only that index. Preserve the source
            # handle/alignment, but do not turn this decoration into an enemy choice.
            binding["target"] = None
        elif index < len(hand):
            binding = {"kind": "play_card", "card": hand[index], "potion_id": None}
        elif index == len(hand):
            binding = {"kind": "end_turn", "card": None, "potion_id": None}
            if target != -1:
                raise ValueError("End turn cannot target an enemy")
        else:
            slot = index - len(hand) - 1
            if not 0 <= slot < 6 or potions[slot] == 0:
                raise ValueError("Public combat potion action points to an empty/outside slot")
            binding = {"kind": "use_potion", "card": None, "potion_id": potions[slot]}
        if not selection_kind:
            binding["target"] = enemies.get(target)
        bindings.append(binding)
    if selection_kind and {index for index, _ in seen} != set(range(len(choices))):
        raise ValueError("Public card selection action set omits a visible choice")
    if not selection_kind and (len(hand), -1) not in seen:
        raise ValueError("Public combat action set is missing end turn")
    tokens = tuple(_tokens(binding, context) for binding in bindings)
    return CombatInput(
        tuple(c.source_action_id for c in representation.candidates),
        tuple(bindings),
        tokens,
        context,
        layout.encoder_id,
    )


def _flatten(value: object, prefix: str, tokens: dict[str, float]) -> None:
    if isinstance(value, dict):
        for key, item in sorted(value.items()):
            _flatten(item, f"{prefix}/{key}", tokens)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            # Orbs and promised next-turn cards have meaningful public order.
            _flatten(item, f"{prefix}/{index}", tokens)
    elif value is None:
        tokens[f"{prefix}=absent"] = 1.0
    elif isinstance(value, str) or prefix.endswith(
        ("_id", "/intent_type", "/secondary_intent_type", "/upgraded", "/public_position")
    ):
        tokens[f"{prefix}={value}"] = 1.0
    elif isinstance(value, int):
        tokens[f"{prefix}:present"] = 1.0
        tokens[f"{prefix}:value"] = math.copysign(math.log1p(abs(value)) / 5, value)
    else:
        raise ValueError("Unsupported typed public combat feature")


def _tokens(binding: dict[str, Any], context: dict[str, Any]) -> dict[str, float]:
    tokens: dict[str, float] = {f"action_kind={binding['kind']}": 1.0}
    _flatten(binding, "choice", tokens)
    shared: dict[str, float] = {}
    _flatten(context, "context", shared)
    # Pair decisions depend on context; broadcast it under action/card identity, not slot.
    scope = binding["kind"]
    if binding["card"] is not None:
        card = binding["card"]
        scope += f"/card={card['card_id']}/upgrade={card['upgraded']}"
    elif binding["potion_id"] is not None:
        scope += f"/potion={binding['potion_id']}"
    for token, value in shared.items():
        tokens[f"{scope}|{token}"] = value
    return dict(sorted(tokens.items()))
