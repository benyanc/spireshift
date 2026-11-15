"""Exact saved public card-removal effect witness; never a game runner or learner."""

from __future__ import annotations

from typing import Any


def removed_cards(
    before: list[dict[str, Any]], after: list[dict[str, Any]], chosen: list[str]
) -> dict[str, Any]:
    """Require exactly the requested physical copies gone and the others unchanged."""
    left = {c["entity_id"]: c for c in before}
    right = {c["entity_id"]: c for c in after}
    if (
        len(left) != len(before)
        or len(right) != len(after)
        or not chosen
        or len(set(chosen)) != len(chosen)
        or set(left) - set(right) != set(chosen)
        or set(right) - set(left)
        or any(left[k] != v for k, v in right.items())
    ):
        raise ValueError("Card removal changed different copies or additional visible deck facts")
    return {
        "deck_before": len(before),
        "deck_after": len(after),
        "removed_names": [left[k]["name"] for k in chosen],
        "exact_chosen_copies_removed": True,
        "other_cards_unchanged": True,
    }
