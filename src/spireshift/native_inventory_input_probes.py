"""Public inventory distinction probes, never playable fixtures or learning labels."""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.native_context_cache import CachedContextModel
from spireshift.native_structured_model import encode
from spireshift.native_structured_vocabulary import validate
from spireshift.native_value_credit import public_value_features
from spireshift.training_objective import TrainingScoreSpec


def cards(public: dict[str, Any]) -> list[dict[str, Any]]:
    reads = [r["content"] for r in public["context"]["reads"] if r["kind"] == "run_deck"]
    if len(reads) != 1 or len(reads[0]["cards"]) != reads[0]["card_count"]:
        raise ValueError("Require the complete observed owned deck")
    return list(reads[0]["cards"])


def visible_player(public: dict[str, Any]) -> dict[str, Any]:
    return dict(
        public["context"]["interaction"].get("content", {}).get("context", {}).get("player", {})
    )


def changes(public: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Alter only named public fields; keep counts, prose, slots and menus fixed.

    Some paired values are deliberately constructed to test field ownership. These
    are syntactic encoder probes, not native-reachable states or optimal actions.
    """
    deck = cards(public)
    pair = next(
        (
            (i, j)
            for i, a in enumerate(deck)
            for j, b in enumerate(deck)
            if i < j and a["definition_id"] != b["definition_id"]
        ),
        None,
    )
    if pair is not None:
        i, j = pair
        for kind, field, value in (
            ("deck_definition", "definition_id", deck[j]["definition_id"]),
            ("deck_upgrade", "is_upgraded", not deck[i]["is_upgraded"]),
            ("deck_displayed_cost", "cost", "0" if deck[i]["cost"] != "0" else "1"),
        ):
            after = copy.deepcopy(public)
            cards(after)[i][field] = value
            yield kind, public, after
        for kind, field, a, b in (
            ("deck_cost_ownership", "cost", "0", "2"),
            ("deck_upgrade_ownership", "is_upgraded", False, True),
        ):
            before, after = copy.deepcopy(public), copy.deepcopy(public)
            cards(before)[i][field], cards(before)[j][field] = a, b
            cards(after)[i][field], cards(after)[j][field] = b, a
            yield kind, before, after
    relics = public["context"]["persistent"]["player"]["relics"]
    if len(relics) > 1 and relics[0]["definition_id"] != relics[1]["definition_id"]:
        after = copy.deepcopy(public)
        # Identity alone must reach the encoder, without a changed name/description.
        after["context"]["persistent"]["player"]["relics"][0]["definition_id"] = relics[1][
            "definition_id"
        ]
        yield "relic_definition", public, after
    visible = visible_player(public).get("relics", [])
    if visible:
        after = copy.deepcopy(public)
        target = after["context"]["interaction"]["content"]["context"]["player"]["relics"][0]
        target["counter"] = 1 if visible[0].get("counter") != 1 else 2
        yield "relic_counter_value", public, after
        after = copy.deepcopy(public)
        after["context"]["interaction"]["content"]["context"]["player"]["relics"][0]["counter"] = 0
        before = copy.deepcopy(after)
        before["context"]["interaction"]["content"]["context"]["player"]["relics"][0]["counter"] = (
            None
        )
        yield "relic_counter_zero_vs_unavailable", before, after
    if len(visible) > 1 and visible[0].get("id") != visible[1].get("id"):
        before, after = copy.deepcopy(public), copy.deepcopy(public)
        for p, amounts in ((before, (2, 7)), (after, (7, 2))):
            view = p["context"]["interaction"]["content"]["context"]["player"]["relics"]
            view[0]["counter"], view[1]["counter"] = amounts
        yield "relic_counter_ownership", before, after
    hand = visible_player(public).get("hand", [])
    if hand:
        after = copy.deepcopy(public)
        # Change the current copy and every advertised subject view of that copy.
        changed = after["context"]["interaction"]["content"]["context"]["player"]["hand"][0]
        changed["cost"] = "0" if hand[0]["cost"] != "0" else "1"
        for candidate in after["candidates"]:
            subject = candidate.get("subject") or {}
            props = subject.get("properties", {})
            if props.get("entity_id") == hand[0]["entity_id"]:
                props["cost"] = changed["cost"]
        yield "current_hand_and_subject_cost", public, after


def probe(
    kind: str,
    before: dict[str, Any],
    after: dict[str, Any],
    models: dict[str, CachedContextModel],
    score: TrainingScoreSpec,
) -> dict[str, Any]:
    validate(before)
    validate(after)
    if len(before["candidates"]) != len(after["candidates"]):
        raise ValueError("Inventory distinction checks must preserve the action count")
    coarse_a, _ = public_value_features(before, score)
    coarse_b, _ = public_value_features(after, score)
    if coarse_a != coarse_b or manifest_identifier(before) == manifest_identifier(after):
        raise ValueError("Require a changed public fact with exactly matched coarse inputs")
    rows = {}
    for name, model in models.items():
        a, _ = encode(before, model, score)
        b, _ = encode(after, model, score)
        if a == b:
            raise ValueError(f"Actual actor input lost {kind}: {name}")
        reversed_rows, _ = encode({**after, "candidates": after["candidates"][::-1]}, model, score)
        if reversed_rows != b[::-1]:
            raise ValueError("Candidate permutation changed inventory ownership")
        rows[name] = {"before": manifest_identifier(a), "after": manifest_identifier(b)}
    return {
        "kind": kind,
        "before_public_id": manifest_identifier(before),
        "after_public_id": manifest_identifier(after),
        "coarse_inputs_identical": True,
        "all_actual_actor_inputs_distinct": True,
        "encoders": rows,
        "native_reachability_or_better_actions_proven": False,
    }
