"""Versioned, reversible scaling after the unchanged native public-token encoder.

Keep direct action signals and the critic input unchanged. No fields, entity
relations, actions or duplicated facts are removed by this experiment.
"""

from __future__ import annotations

from typing import Any

NONE = "none"
QUARTER = "native-actor-hash-quarter-v1"


def normalization_spec(kind: str) -> dict[str, Any] | None:
    if kind == NONE:
        return None
    if kind != QUARTER:
        raise ValueError("Unknown native actor input normalization")
    return {
        "id": QUARTER,
        "hashed_actor_scale": 0.25,
        "position": "after_original_hash_and_clip",
        "direct_actor_features": "unchanged",
        "critic_features": "unchanged",
    }


def normalization_from_mapping(value: object) -> str:
    if value is None:
        return NONE
    if value != normalization_spec(QUARTER):
        raise ValueError("Native normalization identity or scale differs")
    return QUARTER


def normalize_actor_rows(
    rows: tuple[dict[int, float], ...], direct_columns: int, kind: str
) -> tuple[dict[int, float], ...]:
    normalization_spec(kind)
    if kind == NONE:
        return rows
    return tuple(
        {i: amount if i < direct_columns else amount * 0.25 for i, amount in row.items()}
        for row in rows
    )
