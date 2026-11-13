from __future__ import annotations

from typing import Any

import pytest

from spireshift.core.types import LegalAction
from spireshift.public_run_choices import (
    MAXIMUM_VALUES,
    bind_public_choice_actions,
    decode_public_choices,
    read_complete_state_list,
)


def selection(count: int = 15, skip: bool = True) -> list[int]:
    return [1, 13, 0, 1, int(skip), 0, count] + [
        value for identity in range(1, count + 1) for value in (identity, identity % 2, 0, 0)
    ]


def actions(phase: str, *indices: int) -> tuple[LegalAction, ...]:
    return tuple(
        LegalAction(
            f"arbitrary-handle-{i}", f"evangambit_{phase}", {"phase": phase, "action_index": i}
        )
        for i in indices
    )


def test_size_probe_preserves_every_value_and_never_queries_private_lists() -> None:
    rows = selection()
    calls = []

    def getter(handle: int, list_id: int, buffer: Any, size: int) -> int:
        assert handle == 1 and list_id == 22
        calls.append(size)
        if size:
            for i, value in enumerate(rows):
                buffer[i] = value
        return len(rows)

    assert read_complete_state_list(getter, 1, 22) == tuple(rows)
    assert calls == [0, len(rows)]
    with pytest.raises(ValueError, match="Only public-menu"):
        read_complete_state_list(getter, 1, 11)
    assert len(calls) == 2


@pytest.mark.parametrize("result", [-3, MAXIMUM_VALUES + 1])
def test_bad_size_fails_before_allocating_a_card_buffer(result: int) -> None:
    with pytest.raises(ValueError, match="size query failed"):
        read_complete_state_list(lambda *args: result, 1, 22)


def test_changing_menu_is_rejected_instead_of_returning_partial_cards() -> None:
    returns = iter([7, 8])
    with pytest.raises(ValueError, match="changed size"):
        read_complete_state_list(lambda *args: next(returns), 1, 22)


def test_overflow_menu_binds_all_choices_and_skip_without_index_quality() -> None:
    view = decode_public_choices("combat", selection(), [], [1, 8, 0])
    source = actions("combat", *range(16))
    bound = bind_public_choice_actions(view, source)
    assert [b["card"]["card_id"] for b in bound[:-1]] == list(range(1, 16))
    assert bound[-1]["kind"] == "skip_combat_selection"
    assert all("action_index" not in b for b in bound)
    reverse = bind_public_choice_actions(view, tuple(reversed(source)))
    assert reverse == tuple(reversed(bound))
    assert view.fixed_profile["source_declared_ascension_level"] == 8
    assert view.fixed_profile["live_game_conformance_verified"] is False


def test_dropping_a_choice_or_adding_an_unoffered_choice_is_refused() -> None:
    view = decode_public_choices("combat", selection(15, False), [], [1, 8, 0])
    for indices in (range(10), range(16)):
        with pytest.raises(ValueError, match="Every offered"):
            bind_public_choice_actions(view, actions("combat", *indices))


def test_generated_upgrades_and_enchantments_survive_projection() -> None:
    view = decode_public_choices("combat", [1, 7, 0, 2, 0, 1, 1, 50, 1, 2, 3], [], [1, 8, 0])
    bound = bind_public_choice_actions(view, actions("combat", 0))
    assert bound[0]["card"] == {
        "card_id": 50,
        "upgraded": True,
        "enchantment_id": 2,
        "enchantment_amount": 3,
    }
    assert view.combat_selection is not None
    assert view.combat_selection["generated_retained"] is True


@pytest.mark.parametrize(
    "rows",
    [selection()[:-1], [1, 13, 0, 1, 0, 0, 1, 0, 0, 0, 0], [2, 13, 0, 1, 0, 0, 0]],
)
def test_invalid_or_truncated_cards_never_become_successful_empty_menus(rows: list[int]) -> None:
    with pytest.raises(ValueError):
        decode_public_choices("combat", rows, [], [1, 8, 0])


def test_stale_combat_choices_and_unverified_difficulty_labels_are_refused() -> None:
    with pytest.raises(ValueError, match="closed combat"):
        decode_public_choices("map", selection(), [], [1, 8, 0])
    with pytest.raises(ValueError, match="fixed difficulty"):
        decode_public_choices("map", [], [], [1, 0, 0])
    closed = decode_public_choices("map", [], [], [1, 8, 0])
    assert closed.combat_selection is None and closed.bundle_selection is None


def test_bundle_binding_distinguishes_highlight_from_confirm_and_keeps_both_bundles() -> None:
    before = decode_public_choices("bundle_selection", [], [1, -1, 0], [1, 8, 0])
    after = decode_public_choices("bundle_selection", [], [1, 1, 1], [1, 8, 0])
    offer = [1, 2, 3, 4, 5, 6]
    choices = bind_public_choice_actions(
        before, actions("bundle_selection", 0, 1), bundle_offer=offer
    )
    assert all(not b["already_selected"] for b in choices)
    chosen = bind_public_choice_actions(
        after, actions("bundle_selection", 0, 1, 2), bundle_offer=offer
    )
    assert chosen[1]["already_selected"] is True
    assert chosen[2] == {"kind": "confirm_bundle", "selected_bundle": 1}
    assert [c["card_id"] for c in chosen[1]["cards"]] == [4, 5, 6]
    with pytest.raises(ValueError, match="legal actions disagree"):
        bind_public_choice_actions(before, actions("bundle_selection", 0, 1, 2), bundle_offer=offer)


@pytest.mark.parametrize("rows", [[], [1, -1, 1], [1, 0, 0], [1, 2, 1]])
def test_bundle_selected_state_and_confirm_button_must_agree(rows: list[int]) -> None:
    with pytest.raises(ValueError):
        decode_public_choices("bundle_selection", [], rows, [1, 8, 0])
