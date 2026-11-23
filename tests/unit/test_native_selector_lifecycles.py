from __future__ import annotations

from typing import Any

import pytest

from spireshift.native_selector_lifecycle_checks import check_selector
from spireshift.native_systematic_selectors_v2 import COMPACT, DIRECT


def selector(*, removal: bool, prefix: tuple[int, ...] = ()) -> dict[str, Any]:
    ids = [f"physical-strike-{i}" for i in range(13)]
    cards = [{"entity_id": key, "definition_id": "STRIKE_IRONCLAD"} for key in ids]
    actions = []
    if removal:
        for key in ids:
            actions.append(
                {
                    "verb": "confirm",
                    "subject_referent_id": None,
                    "arguments": [{"role": "selected_card", "referent_id": key}],
                }
            )
        actions.append({"verb": "cancel", "subject_referent_id": None, "arguments": []})
    else:
        for i, key in enumerate(ids):
            if i not in prefix:
                actions.append({"verb": "select", "subject_referent_id": key, "arguments": []})
        actions.append(
            {
                "verb": "confirm",
                "subject_referent_id": None,
                "arguments": [{"role": "selected_card", "referent_id": ids[i]} for i in prefix],
            }
        )
    return {
        "snapshot": {
            "interaction": {
                "kind": "card_selection",
                "content": {
                    "context": {"kind": "shop"},
                    "surface": {
                        "cards": cards,
                        "min_select": 1 if removal else 0,
                        "max_select": 1 if removal else 3,
                        "cancelable": removal,
                        "selection_contract": DIRECT if removal else COMPACT,
                        "answer_plan": {"selected": list(prefix)},
                    },
                },
            },
            "bound_actions": {"actions": actions},
        },
        "reads": [
            {"kind": "run_deck", "content": {"card_count": 13, "cards": cards}},
            {
                "kind": "shop_catalog",
                "content": {
                    "cards": [],
                    "relics": [{"can_purchase": False}],
                    "potions": [],
                    "card_removal": {"can_purchase": False},
                },
            },
        ],
    }


def test_identically_named_cards_keep_every_physical_removal_choice_and_cancel() -> None:
    value = selector(removal=True)
    check_selector(value, 13, True)
    value["snapshot"]["bound_actions"]["actions"].pop(7)
    with pytest.raises(ValueError, match="physical answer"):
        check_selector(value, 13, True)


def test_ordered_prefix_retains_order_and_all_other_cards() -> None:
    value = selector(removal=False, prefix=(12, 0))
    check_selector(value, 13, False)
    confirm = value["snapshot"]["bound_actions"]["actions"][-1]
    confirm["arguments"].reverse()
    with pytest.raises(ValueError, match="physical answer"):
        check_selector(value, 13, False)


def test_mandatory_relic_choice_cannot_gain_an_invented_cancel() -> None:
    value = selector(removal=False)
    check_selector(value, 13, False)
    value["snapshot"]["bound_actions"]["actions"].append(
        {
            "verb": "cancel",
            "subject_referent_id": None,
            "arguments": [],
        }
    )
    with pytest.raises(ValueError, match="extra answer"):
        check_selector(value, 13, False)


def test_catalog_remains_read_only_while_a_child_owns_the_controls() -> None:
    value = selector(removal=True)
    value["reads"][1]["content"]["relics"][0]["can_purchase"] = True
    with pytest.raises(ValueError, match="while its selector owns input"):
        check_selector(value, 13, True)
