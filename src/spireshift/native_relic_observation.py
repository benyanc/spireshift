"""Independent ordered native/public counter verification and a diagnostic legacy view."""

from __future__ import annotations

import copy
import math
from itertools import zip_longest
from pathlib import Path
from typing import Any

from spireshift.engine_experience_stream import records
from spireshift.native_structured_vocabulary import validate

CONTRACT = "public_owned_combat_relic_counters_v1"


def legacy_view(public: dict[str, Any]) -> dict[str, Any]:
    """Diagnostic trace comparison only; production learners receive the complete input."""
    validate(public)
    result = copy.deepcopy(public)
    if public["context"]["interaction"]["kind"] != "combat_turn":
        return result

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if "player_entity_id" in value and "hand" in value and "energy" in value:
                value.pop("relics", None)
            if value.get("inventoryObservation") == CONTRACT:
                value.pop("inventoryObservation")
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(result)
    return result


def verify(workspace: Path, deadline: float) -> dict[str, Any]:
    """Counter values are checked against the corresponding native response, not a set.

    At most one record from each journal is retained. All native state remains in
    DEBUG storage. Only ID/counter and counts enter this verification result.
    """
    native = (
        r["response"]
        for r in records(workspace / "private-transcript.jsonl.gz", deadline)
        if r.get("response", {}).get("decision") is not None
    )
    public = records(workspace / "public-observations.jsonl.gz", deadline)
    observations = combats = numeric = zero = null = 0
    definitions: set[str] = set()
    for raw, observed in zip_longest(native, public):
        if raw is None or observed is None:
            raise ValueError("Native/public observation streams differ in length")
        observations += 1
        p = observed["model_input"]
        validate(p)
        is_combat = p["context"]["interaction"]["kind"] == "combat_turn"
        if is_combat != (raw["decision"] == "combat_play"):
            raise ValueError("Native/public combat observations are out of order")
        if not is_combat:
            continue
        expected = []
        for r in raw["player"]["relics"]:
            amount = r["counter"]
            if (
                not isinstance(r["id"], str)
                or not r["id"]
                or not (amount is None or type(amount) in (int, float) and math.isfinite(amount))
            ):
                raise ValueError("Invalid native public relic counter")
            expected.append({"id": r["id"], "counter": amount})
            definitions.add(r["id"])
            numeric += amount is not None
            zero += amount == 0 and amount is not None
            null += amount is None
        actual = p["context"]["interaction"]["content"]["context"]["player"].get("relics")
        if actual != expected:
            raise ValueError("Owned relic identity/counter was lost, reordered, stale or changed")
        combats += 1
    if combats == 0:
        raise ValueError("No combat exercised the repaired observation")
    return {
        "contract": CONTRACT,
        "observations_verified": observations,
        "combat_observations_verified": combats,
        "numeric_counter_observations": numeric,
        "zero_counter_observations": zero,
        "unavailable_counter_observations": null,
        "owned_relic_definitions": sorted(definitions),
        "ordered_counter_equality": True,
        "maximum_records_retained_per_stream": 1,
        "private_fields_exposed": False,
    }
