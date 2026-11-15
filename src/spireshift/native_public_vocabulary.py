"""Bounded public dictionary with balanced source/field coverage.

The first control's global frequency/lexical cut used all 1,024 coordinates on
interaction fields. Keep that experiment immutable; this is a new treatment.
Selection uses fitting inputs only, never returns or held games.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from spireshift.native_public_state import PublicVocabulary as OriginalVocabulary

ENCODER = "native-owned-public-value-balanced-facts-v2"


def source_group(name: str) -> str:
    if name.startswith("menu"):
        return "menu"
    for part, group in (
        ("persistent", "persistent"),
        ("reads", "inventory"),
        ("interaction", "interaction"),
        ("referents", "entities"),
    ):
        if name.startswith("context/" + part):
            return group
    return "other"


def field_group(name: str) -> str:
    # Split before literal text: formatted descriptions can themselves contain '/'.
    path = name.split("/literal=", 1)[0]
    if path.endswith(("/number", "/number_present", "/object", "/length")):
        path = path.rsplit("/", 1)[0]
    return path.rsplit("/", 1)[-1].split("@", 1)[0]


@dataclass(frozen=True)
class PublicVocabulary(OriginalVocabulary):
    @classmethod
    def fit(cls, games: Iterable[Iterable[Mapping[str, float]]], maximum: int) -> PublicVocabulary:
        if type(maximum) is not int or not 1 <= maximum <= 8192:
            raise ValueError("Invalid finite public vocabulary capacity")
        frequency: Counter[str] = Counter()
        states: Counter[str] = Counter()
        first: dict[str, float] = {}
        varying: set[str] = set()
        total = 0
        for rows in games:
            seen: set[str] = set()
            for row in rows:
                total += 1
                seen.update(row)
                states.update(row.keys())
                for key, value in row.items():
                    if key not in first:
                        first[key] = value
                    elif first[key] != value:
                        varying.add(key)
            frequency.update(seen)
        # Constant columns carry no discrimination in this fitting population.
        # Absence counts as variation, including a zero-valued numeric feature.
        eligible = [k for k in frequency if states[k] < total or k in varying]
        buckets: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for name in sorted(eligible, key=lambda k: (-frequency[k], k)):
            buckets[source_group(name)][field_group(name)].append(name)
        ordered: dict[str, list[str]] = {}
        for source, fields in buckets.items():
            # Round-robin fields as well as sources; a large pile/reference subtree
            # cannot crowd out all identities, statuses, costs or menu requirements.
            pending = {field: iter(names) for field, names in fields.items()}
            names = []
            while pending:
                for field in sorted(tuple(pending)):
                    entry = next(pending[field], None)
                    if entry is None:
                        del pending[field]
                    else:
                        names.append(entry)
            ordered[source] = names
        pending = {source: iter(names) for source, names in ordered.items()}
        chosen: list[str] = []
        while pending and len(chosen) < maximum:
            for source in sorted(tuple(pending)):
                entry = next(pending[source], None)
                if entry is None:
                    del pending[source]
                else:
                    chosen.append(entry)
                    if len(chosen) == maximum:
                        break
        return cls(tuple(sorted(chosen)))

    def encode(self, facts: Mapping[str, float]) -> tuple[tuple[float, ...], dict[str, int]]:
        values, counts = super().encode(facts)
        present = Counter(source_group(name) for name in facts)
        represented = Counter(source_group(name) for name in self.names if name in facts)
        for source in ("persistent", "inventory", "interaction", "entities", "menu", "other"):
            counts[source + "_present_facts"] = present[source]
            counts[source + "_represented_facts"] = represented[source]
        return values, counts
