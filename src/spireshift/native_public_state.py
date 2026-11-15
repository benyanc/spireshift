"""Reusable public-state facts for an experimental critic, without feature hashing.

This consumes the qualified public projection, not engine state. It preserves
named amounts with their owners, current card copies and public relationships.
It cannot supply facts absent from that projection or prove exhaustive mechanics.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from spireshift.engine_neural import validate_public_input

ENCODER = "native-owned-public-value-facts-v1"
IDENTITY = (
    "definition_id",
    "character_definition_id",
    "name",
    "title",
    "role",
    "verb",
    "kind",
    "zone",
)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _tag(value: dict[str, Any]) -> str:
    facts = {k: value[k] for k in IDENTITY if isinstance(value.get(k), (str, bool))}
    # Names remain useful for statuses/options without a native definition ID.
    if "definition_id" in facts:
        facts.pop("name", None)
    return _json(facts) if facts else ""


def _slot(value: Any) -> int | None:
    if isinstance(value, dict) and set(value) == {"public_slot"}:
        if type(value["public_slot"]) is not int or value["public_slot"] < 0:
            raise ValueError("Invalid local public relationship")
        return int(value["public_slot"])
    return None


def _declarations(value: Any, registry: dict[int, list[dict[str, Any]]]) -> None:
    if isinstance(value, dict):
        owner = value.get("properties", value)
        slot = _slot(value.get("entity_id"))
        # An operand pointer with only a role is not an entity declaration.
        if slot is not None and not any(
            v is not None and k not in {"entity_id", "role"} for k, v in owner.items()
        ):
            slot = None
        if "public_slot" in value and len(value) > 1:
            slot = _slot({"public_slot": value["public_slot"]})
        if slot is not None:
            registry.setdefault(slot, []).append(owner)
        for item in value.values():
            _declarations(item, registry)
    elif isinstance(value, list):
        for item in value:
            _declarations(item, registry)


def _without_pointers(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _without_pointers(v)
            for k, v in value.items()
            if k != "public_slot"
            and not k.endswith(("entity_id", "entity_ids", "referent_id", "referent_ids"))
        }
    if isinstance(value, list):
        return [_without_pointers(v) for v in value]
    return value


def public_state_facts(public: dict[str, Any]) -> dict[str, float]:
    """All supplied public fields, as general and owner-conditioned measurements.

    No action is selected here. The complete menu is a multiset, so permuting its
    display order cannot change this state value. Only explicitly unordered piles,
    the deck inventory and lookup collections are pooled; other list order stays.
    Local slot numbers are resolved to visible content and never become features.
    """
    validate_public_input(public)

    def boundary(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) & {
                "rng_state",
                "random_state",
                "seed_id",
                "native_seed",
                "future_rewards",
                "hidden_state",
            }:
                raise ValueError("Private state reached structured value input")
            for item in value.values():
                boundary(item)
        elif isinstance(value, list):
            for item in value:
                boundary(item)

    boundary(public)
    registry: dict[int, list[dict[str, Any]]] = {}
    _declarations(public, registry)
    for views in registry.values():
        ids = {v["definition_id"] for v in views if "definition_id" in v}
        if len(ids) > 1:
            raise ValueError("One public entity has conflicting native identities")
    output: dict[str, list[float]] = defaultdict(list)

    def emit(path: str, amount: float) -> None:
        output[path].append(amount)

    def walk(
        value: Any, path: str, owned: str, *, bag: bool = False, reference: bool = False
    ) -> None:
        paths = tuple(dict.fromkeys((path, owned)))
        slot = _slot(value)
        if slot is not None:
            if slot not in registry:
                raise ValueError("Unresolved public relationship in structured value input")
            # Resolve one edge using complete visible owner records. Nested edges
            # use identities only, so a public graph cycle cannot recurse forever.
            records = {_json(_without_pointers(v)): v for v in registry[slot]}
            if reference:
                for tag in sorted({_tag(v) for v in records.values()}):
                    for prefix in paths:
                        emit(prefix + "/reference_identity=" + tag, 1.0)
            else:
                for encoded in sorted(records):
                    walk(
                        json.loads(encoded),
                        path + "/reference",
                        owned + "/reference",
                        reference=True,
                    )
            return
        if isinstance(value, dict):
            tag = _tag(value)
            tagged = owned + ("@" + tag if tag else "")
            for prefix in paths:
                emit(prefix + "/object", 1.0)
            for key, item in sorted(value.items()):
                if key == "public_slot":
                    # A declaration, not an observable numerical game property.
                    continue
                unordered = key in {"candidates", "referents", "reads"} or (
                    key == "cards"
                    and (value.get("ordering_semantics") == "unordered_multiset" or bag)
                )
                deck = bag or value.get("kind") == "run_deck"
                walk(
                    item,
                    path + "/" + key,
                    tagged + "/" + key,
                    bag=unordered or (key == "content" and deck),
                    reference=reference,
                )
        elif isinstance(value, list):
            for prefix in paths:
                emit(prefix + "/length", math.log1p(len(value)))
            for i, item in enumerate(value):
                suffix = "/[]" if bag else f"/{i}"
                walk(item, path + suffix, owned + suffix, reference=reference)
        elif type(value) in (int, float):
            # Smooth bounded-size inputs, with presence separate from zero.
            for prefix in paths:
                emit(prefix + "/number", math.asinh(value) / 5)
                emit(prefix + "/number_present", 1.0)
        else:
            for prefix in paths:
                emit(prefix + "/literal=" + _json(value), 1.0)

    walk(public["context"], "context", "context")
    walk(public["candidates"], "menu", "menu", bag=True)
    return {k: math.asinh(math.fsum(v)) for k, v in sorted(output.items()) if math.fsum(v)}


@dataclass(frozen=True)
class PublicVocabulary:
    """A fitting-games-only dictionary: no hash aliases or held-game vocabulary fit.

    Finite capacity still omits rare/unseen facts. Coverage is reported explicitly;
    the full projected public graph is richer than this finite numerical model.
    """

    names: tuple[str, ...]

    @classmethod
    def fit(cls, games: Iterable[Iterable[Mapping[str, float]]], maximum: int) -> PublicVocabulary:
        if type(maximum) is not int or not 1 <= maximum <= 8192:
            raise ValueError("Invalid finite public vocabulary capacity")
        frequency: Counter[str] = Counter()
        for rows in games:
            present: set[str] = set()
            for row in rows:
                present.update(row)
            frequency.update(present)
        names = sorted(frequency, key=lambda k: (-frequency[k], k))[:maximum]
        return cls(tuple(sorted(names)))

    def encode(self, facts: Mapping[str, float]) -> tuple[tuple[float, ...], dict[str, int]]:
        known = sum(name in facts for name in self.names)
        return tuple(facts.get(name, 0.0) for name in self.names), {
            "present_facts": len(facts),
            "represented_facts": known,
            "unrepresented_facts": len(facts) - known,
        }
