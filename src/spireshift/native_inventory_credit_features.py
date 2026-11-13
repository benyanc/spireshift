"""Typed public inventory counts for diagnosis, never an actor or complete-state encoder."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_neural import validate_public_input

ENCODER = "public_deck_and_relic_inventory_credit_v1"


def _identity(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError("Require a public definition identity, never a runtime handle")
    return value


def _category(value: Any) -> str:
    if type(value) not in (str, int, float, type(None)) or (
        isinstance(value, float) and not math.isfinite(value)
    ):
        raise ValueError("Unsupported public inventory category")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def inventory(public: dict[str, Any]) -> dict[str, Any]:
    """Bag counts preserve identity/upgrade/cost ownership, independent of chosen actions.

    Deck order, entity slots, prose and offered/chosen rewards are deliberately not
    predictor inputs. Costs are the deck view's displayed categories, not inferred
    combat costs. This is a narrow diagnostic of omitted inventory information.
    """
    validate_public_input(public)
    context = public["context"]
    reads = [r["content"] for r in context.get("reads", []) if r["kind"] == "run_deck"]
    if len(reads) != 1 or type(reads[0].get("card_count")) is not int:
        raise ValueError("Require one complete public run-deck read")
    cards = reads[0].get("cards")
    if not isinstance(cards, list) or len(cards) != reads[0]["card_count"]:
        raise ValueError("Do not treat missing deck composition as an empty deck")
    values: dict[str, float] = defaultdict(float)
    deck = []
    for card in cards:
        identity = _identity(card.get("definition_id"))
        upgraded = card.get("is_upgraded")
        if type(upgraded) is not bool or "cost" not in card:
            raise ValueError("Missing public per-copy upgrade or displayed cost")
        cost = _category(card["cost"])
        # All definitions share the same schema, including cross-character cards.
        values[f"deck/id/{identity}"] += 0.2
        values[f"deck/copy/{identity}/{int(upgraded)}/{cost}"] += 0.2
        values[f"deck/type/{_category(card.get('type'))}"] += 0.2
        values[f"deck/displayed_cost/{cost}"] += 0.2
        values["deck/upgraded_total"] += 0.2 * upgraded
        deck.append((identity, upgraded, cost))

    player = context["persistent"]["player"]
    relics = player.get("relics")
    if not isinstance(relics, list):
        raise ValueError("Missing public relic inventory")
    visible = context["interaction"].get("content", {}).get("context", {}).get("player", {})
    counters = visible.get("relics")
    by_id: dict[str, list[Any]] = {}
    if counters is not None:
        if not isinstance(counters, list):
            raise ValueError("Invalid public relic counter view")
        for relic in counters:
            identity = _identity(relic.get("id", relic.get("definition_id")))
            by_id.setdefault(identity, []).append(relic.get("counter"))
        if Counter({k: len(v) for k, v in by_id.items()}) != Counter(
            r["definition_id"] for r in relics
        ):
            raise ValueError("Relic counter view differs from the public persistent inventory")
    relic_state = []
    for relic in relics:
        identity = _identity(relic.get("definition_id"))
        amount = by_id[identity].pop(0) if counters is not None else None
        if amount is not None and (type(amount) not in (int, float) or not math.isfinite(amount)):
            raise ValueError("Nonfinite or opaque public relic counter")
        values[f"relic/id/{identity}"] += 1.0
        values[f"relic/counter_known/{identity}"] += float(amount is not None)
        if amount is not None:
            values[f"relic/counter/{identity}"] += math.asinh(amount) / 5
        relic_state.append((identity, _category(amount)))
    deck_id = manifest_identifier(sorted(deck))
    relic_id = manifest_identifier(sorted(relic_state))
    return {
        "values": dict(values),
        "deck_signature": deck_id,
        "relic_signature": relic_id,
        "inventory_signature": manifest_identifier([deck_id, relic_id]),
        "deck_definitions": sorted({d[0] for d in deck}),
        "relic_definitions": sorted({r[0] for r in relic_state}),
        "relic_counters_available": counters is not None,
    }
