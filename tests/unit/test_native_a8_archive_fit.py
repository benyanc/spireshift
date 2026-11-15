from collections import Counter
from typing import Any

import pytest

from spireshift import native_a8_archive_fit_inputs as archive
from spireshift.native_a8_archive_fit_session import fit_batch
from spireshift.native_a8_bank_fit import Decision, Factor, world_schedule
from spireshift.native_win4_plan import PLAN


def test_each_fit_batch_weights_three_uneven_worlds_equally() -> None:
    worlds = {
        seed: tuple(Decision(seed, (Factor(({0: float(i)},), 0, str(i)),)) for i in range(size))
        for seed, size in (("a", 9), ("b", 17), ("c", 24))
    }
    schedule = world_schedule(worlds, 24, "verified-bank")
    seen: set[tuple[str, str]] = set()
    for step in range(3):
        batch = fit_batch(worlds, schedule, step)
        assert Counter(d.family for d in batch) == {"a": 8, "b": 8, "c": 8}
        seen.update((d.family, d.factors[0].input_id) for d in batch)
    assert len(seen) == 9 + 17 + 24


def ordered_menu(selected: list[int], verb: str) -> dict[str, Any]:
    return {
        "action_index": 1,
        "public_input": {
            "context": {
                "persistent": {"run": {"act": 2}},
                "interaction": {
                    "kind": "card_selection",
                    "content": {
                        "surface": {
                            "selection_contract": PLAN,
                            "answer_plan": {"selected": selected},
                            "cards": [{"entity_id": {"public_slot": 12}}],
                        },
                    },
                },
            },
            "candidates": [
                {"verb": "cancel", "subject": None},
                {"verb": verb, "subject": {"public_slot": 12}},
            ],
        },
    }


def test_archive_fits_complete_ordered_answer_with_full_menus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def encode(public: dict[str, Any], _model: Any, _score: Any) -> tuple[Any, None]:
        return tuple({0: float(i)} for i in range(len(public["candidates"]))), None

    monkeypatch.setattr(archive, "validate_student_input", lambda _: None)
    monkeypatch.setattr(archive, "encode", encode)
    row = {
        "act": 2,
        "family": "card_selection",
        "factors": [ordered_menu([], "select"), ordered_menu([0], "confirm")],
    }
    model: Any = object()
    score: Any = object()
    result = archive.encode_answer(row, model, score)
    assert [f.action for f in result.factors] == [1, 1]
    assert [len(f.rows) for f in result.factors] == [2, 2]
    with pytest.raises(ValueError, match="prefixes and commit"):
        archive.encode_answer({**row, "factors": [ordered_menu([], "select")]}, model, score)
    with pytest.raises(ValueError, match="prefixes and commit"):
        archive.encode_answer(
            {**row, "factors": [ordered_menu([], "select"), ordered_menu([], "confirm")]},
            model,
            score,
        )
