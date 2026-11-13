"""Shared public combat features and printed card metadata; no engine execution."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

from spireshift.combat_features import CombatInput, _flatten
from spireshift.models import _exact_keys, _integer, _mapping

ENCODER_ID = "shared-public-combat-card-properties-v1"
CARD_SOURCE = "src/Sts2Emulator/Generated/Cards.g.cs"
CARD_FIELDS = ("Cost", "BaseDamage", "BaseBlock", "UpgradeDamage", "UpgradeBlock", "UpgradeCost")
CARD_FLAGS = ("Ethereal", "Exhaust", "Unplayable", "Retain", "HasEnergyCostX", "StrikeTag")
CARD_TYPES = {"Attack", "Skill", "Power", "Status", "Curse", "Quest", "None"}
CARD_TARGETS = {
    "None",
    "Self",
    "AnyEnemy",
    "AllEnemies",
    "RandomEnemy",
    "AnyPlayer",
    "AnyAlly",
    "AllAllies",
    "TargetedNoCreature",
    "Osty",
}


def load_printed_card_catalog(root: Path, source_sha256: str) -> dict[str, dict[str, Any]]:
    path = root.resolve() / CARD_SOURCE
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Card metadata source escapes the pinned backend")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha256:
        raise ValueError("Printed card metadata source hash differs")
    catalog: dict[str, dict[str, Any]] = {}
    definitions = re.findall(r"new CardDef\(([^\n]+)\)", raw.decode())
    if not definitions:
        raise ValueError("Pinned source contains no printed card definitions")
    for line in definitions:
        values: dict[str, Any] = {}
        for name in ("Id", *CARD_FIELDS):
            matches = re.findall(rf"\b{name}:\s*(-?\d+)(?=,|$)", line)
            if len(matches) != 1:
                raise ValueError(f"Unsupported printed card property: {name}")
            values[name] = int(matches[0])
        for name, namespace in (("Type", "CardType"), ("Target", "CardTarget")):
            matches = re.findall(rf"\b{name}:\s*{namespace}\.(\w+)(?=,|$)", line)
            if len(matches) != 1:
                raise ValueError(f"Missing printed card category: {name}")
            values[name] = matches[0]
        for name in CARD_FLAGS:
            matches = re.findall(rf"\b{name}:\s*(true|false)(?=,|$)", line)
            if len(matches) > 1:
                raise ValueError(f"Duplicate printed card flag: {name}")
            values[name] = bool(matches and matches[0] == "true")
        identity = str(values.pop("Id"))
        if identity in catalog:
            raise ValueError("Duplicate printed card definition")
        catalog[identity] = values
    return validate_catalog(catalog)


def validate_catalog(value: object) -> dict[str, dict[str, Any]]:
    catalog = _mapping(value, "printed card metadata")
    if not 1 <= len(catalog) <= 2000:
        raise ValueError("Printed card catalog size is outside bounds")
    for key, raw in catalog.items():
        if not key.isdigit() or str(int(key)) != key or int(key) <= 0:
            raise ValueError("Printed card ID must be a canonical positive identifier")
        item = _mapping(raw, "printed card")
        _exact_keys(item, {*CARD_FIELDS, *CARD_FLAGS, "Type", "Target"}, "printed card")
        for name in CARD_FIELDS:
            if not -10000 <= _integer(item[name], name) <= 10000:
                raise ValueError("Printed card property is outside bounds")
        if item["Type"] not in CARD_TYPES or item["Target"] not in CARD_TARGETS:
            raise ValueError("Unknown printed card type or target")
        if any(type(item[name]) is not bool for name in CARD_FLAGS):
            raise ValueError("Printed card flag must be boolean")
    return catalog


def _printed(card: dict[str, int], catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    definition = catalog.get(str(card["card_id"]))
    if definition is None:
        raise ValueError(f"Public card {card['card_id']} is absent from the frozen catalog")
    upgraded = card["upgraded"]
    # Printed costs/damage/block are descriptors, not exact resolved effects. Modifiers,
    # multi-hit effects and special-card code are deliberately not guessed here.
    return {
        "printed_cost": definition["Cost"] + upgraded * definition["UpgradeCost"],
        "printed_damage": definition["BaseDamage"] + upgraded * definition["UpgradeDamage"],
        "printed_block": definition["BaseBlock"] + upgraded * definition["UpgradeBlock"],
        "type": definition["Type"],
        "target": definition["Target"],
        **{name: int(definition[name]) for name in CARD_FLAGS},
    }


def neural_combat_vectors(
    bound: CombatInput, catalog: dict[str, dict[str, Any]], dimension: int
) -> tuple[dict[int, float], ...]:
    """Share context across identities; a nonlinear network learns its action interactions.

    Numeric card/enemy/potion IDs stay categorical. Only bound public objects and printed
    definitions are used; action handles, state hashes, seeds and hidden vectors never enter.
    """
    if type(dimension) is not int or not 64 <= dimension <= 4096:
        raise ValueError("Neural feature dimension must be in [64, 4096]")
    shared: dict[str, float] = {}
    _flatten(bound.context, "state", shared)
    player = bound.context["player"]
    shared["state/player/hp_fraction"] = player["hp"] / player["max_hp"]
    printed_hand = [_printed(c, catalog) for c in bound.context["hand"]]
    for name in ("printed_cost", "printed_damage", "printed_block"):
        shared[f"state/hand/{name}:sum"] = (
            math.log1p(sum(max(0, c[name]) for c in printed_hand)) / 5
        )
    result = []
    for binding in bound.bindings:
        tokens = dict(shared)
        _flatten(binding, "action", tokens)
        if binding["card"] is not None:
            _flatten(_printed(binding["card"], catalog), "printed", tokens)
        features: dict[int, float] = {}
        for name, amount in sorted(tokens.items()):
            digest = hashlib.sha256(f"{ENCODER_ID}|{name}".encode()).digest()
            index = int.from_bytes(digest[:8], "big") % dimension
            sign = 1 if digest[8] & 1 else -1
            features[index] = features.get(index, 0.0) + sign * amount
        result.append({k: v for k, v in sorted(features.items()) if v})
    return tuple(result)
