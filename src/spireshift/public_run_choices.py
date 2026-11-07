"""Versioned public-menu sidecar. This does not rewrite the historical agent's inputs."""

from __future__ import annotations

import ctypes
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from spireshift.core.types import LegalAction

SCHEMA_ID = "public-run-choices-v1"
PUBLIC_LIST_IDS = frozenset({22, 23, 24})
MAXIMUM_VALUES = 65543


def read_complete_state_list(
    getter: Callable[..., int], handle: int, list_id: int
) -> tuple[int, ...]:
    """Query required length first; never silently return a truncated or changing menu."""
    if list_id not in PUBLIC_LIST_IDS:
        raise ValueError("Only public-menu sidecar lists may be queried")
    count = int(getter(handle, list_id, None, 0))
    if count < 0 or count > MAXIMUM_VALUES:
        raise ValueError(f"Public-menu size query failed for list {list_id}: {count}")
    buffer = (ctypes.c_int * count)()
    actual = int(getter(handle, list_id, buffer, count))
    if actual != count:
        raise ValueError("Public menu changed size or failed during readout")
    return tuple(int(item) for item in buffer)


def _integers(values: Sequence[int]) -> tuple[int, ...]:
    if any(type(v) is not int for v in values):
        raise ValueError("Public menu values must be integers")
    return tuple(values)


def _combat(values: Sequence[int]) -> dict[str, Any] | None:
    rows = _integers(values)
    if not rows:
        return None
    if len(rows) < 7 or rows[0] != 1 or not 1 <= rows[1] <= 25:
        raise ValueError("Unknown public combat-menu schema or selection kind")
    _, kind, source, amount, skip, retained, count = rows[:7]
    if source < 0 or amount < 0 or skip not in (0, 1) or retained not in (0, 1):
        raise ValueError("Invalid public selection metadata")
    if count < 0 or len(rows) != 7 + 4 * count:
        raise ValueError("Public combat menu is incomplete")
    cards = []
    for at in range(7, len(rows), 4):
        identity, upgraded, enchantment, enchant_amount = rows[at : at + 4]
        if identity <= 0 or upgraded not in (0, 1) or enchantment < 0:
            raise ValueError("Invalid offered public card")
        cards.append(
            {
                "card_id": identity,
                "upgraded": bool(upgraded),
                "enchantment_id": enchantment,
                "enchantment_amount": enchant_amount,
            }
        )
    return {
        "selection_kind_id": kind,
        "source_card_id": source,
        "remaining_amount": amount,
        "skippable": bool(skip),
        "generated_retained": bool(retained),
        "cards": cards,
    }


@dataclass(frozen=True)
class PublicChoiceView:
    phase: str
    combat_selection: dict[str, Any] | None
    bundle_selection: dict[str, Any] | None
    fixed_profile: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_id": SCHEMA_ID,
            "phase": self.phase,
            "combat_selection": self.combat_selection,
            "bundle_selection": self.bundle_selection,
            "fixed_profile": self.fixed_profile,
        }


def decode_public_choices(
    phase: str,
    combat_values: Sequence[int],
    bundle_values: Sequence[int],
    profile_values: Sequence[int],
) -> PublicChoiceView:
    profile = _integers(profile_values)
    if profile != (1, 8, 0):
        raise ValueError("Unknown public-choice capability or fixed difficulty profile")
    combat = _combat(combat_values)
    if combat is not None and phase != "combat":
        raise ValueError("A closed combat menu must not expose stale or hidden cards")
    bundle_rows = _integers(bundle_values)
    bundle = None
    if bundle_rows:
        if (
            len(bundle_rows) != 3
            or bundle_rows[0] != 1
            or bundle_rows[1] not in (-1, 0, 1)
            or bundle_rows[2] != int(bundle_rows[1] >= 0)
            or phase != "bundle_selection"
        ):
            raise ValueError("Invalid public bundle selection/confirmation state")
        bundle = {"selected_bundle": bundle_rows[1], "confirmation_enabled": bool(bundle_rows[2])}
    elif phase == "bundle_selection":
        raise ValueError("Open bundle menu is missing its selected state")
    return PublicChoiceView(
        phase,
        combat,
        bundle,
        {
            "profile_id": "evangambit-source-fixed-ascension-8-v1",
            "source_declared_ascension_level": 8,
            "selectable_difficulty": False,
            "live_game_conformance_verified": False,
        },
    )


def bind_public_choice_actions(
    view: PublicChoiceView,
    actions: tuple[LegalAction, ...],
    *,
    bundle_offer: Sequence[int] = (),
) -> tuple[dict[str, Any], ...]:
    """Bind every legal menu locator to a shown object; no action index becomes quality."""
    if view.combat_selection is None and view.bundle_selection is None:
        raise ValueError("No public choice menu is open")
    indices = []
    for action in actions:
        if (
            action.kind != f"evangambit_{view.phase}"
            or action.payload.get("phase") != view.phase
            or set(action.payload) - {"phase", "action_index", "target_index"}
            or action.payload.get("target_index", -1) != -1
            or type(action.payload.get("action_index")) is not int
        ):
            raise ValueError("Public menu action must have an unambiguous phase/index locator")
        indices.append(action.payload["action_index"])
    if len(set(indices)) != len(indices):
        raise ValueError("Duplicate public choice action locators")
    bindings = []
    if view.combat_selection is not None:
        menu = view.combat_selection
        n = len(menu["cards"])
        if set(indices) != set(range(n + int(menu["skippable"]))):
            raise ValueError("Every offered public combat action must be retained")
        for index in indices:
            binding = {"selection_kind_id": menu["selection_kind_id"]}
            if index == n:
                binding["kind"] = "skip_combat_selection"
            else:
                binding.update(kind="select_card", card=dict(menu["cards"][index]))
            bindings.append(binding)
    else:
        assert view.bundle_selection is not None
        menu = view.bundle_selection
        offer = _integers(bundle_offer)
        if len(offer) != 6 or any(v <= 0 for v in offer):
            raise ValueError("Both public bundle offers must contain three valid cards")
        expected = {0, 1, 2} if menu["confirmation_enabled"] else {0, 1}
        if set(indices) != expected:
            raise ValueError("Public bundle legal actions disagree with selected state")
        for index in indices:
            if index == 2:
                bindings.append(
                    {"kind": "confirm_bundle", "selected_bundle": menu["selected_bundle"]}
                )
            else:
                bindings.append(
                    {
                        "kind": "select_bundle",
                        "already_selected": menu["selected_bundle"] == index,
                        "cards": [
                            {"card_id": value, "upgraded": False}
                            for value in offer[index * 3 : index * 3 + 3]
                        ],
                    }
                )
    return tuple(bindings)
