from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift import native_capacity_recovery_v1 as recovery
from spireshift.native_potion_queue_control_v1 import check_belt
from spireshift.native_selector_lifecycle_trace import Trace


def trace_with(offers: list[dict[str, Any]]) -> Trace:
    return cast(
        Trace,
        SimpleNamespace(
            frame={
                "public_input": {
                    "context": {
                        "persistent": {"player": {"potions": [{"definition_id": "BLOOD_POTION"}]}}
                    },
                    "candidates": offers,
                }
            }
        ),
    )


def test_queue_control_rejects_illegal_potions_and_missing_legal_discards() -> None:
    action = {"label": "Discard Blood Potion", "subject": {"role": "potion"}}
    check_belt(trace_with([]), False)
    check_belt(trace_with([action]), True)
    with pytest.raises(ValueError, match="canceled potion"):
        check_belt(trace_with([action]), False)
    with pytest.raises(ValueError, match="legal potion discard"):
        check_belt(trace_with([]), True)


def test_failed_prefix_has_no_terminal_or_training_admission(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    rows: list[dict[str, Any]] = [
        {
            "response": {
                "decision": "card_select",
                "selection_owner": {"kind": "combat"},
                "selection_combat": {"is_play_phase": False, "turn_owner": "player"},
                "context": {"act": 2},
            }
        },
        {
            "request": {"action": "discard_potion"},
            "response": {
                "type": "error",
                "message": "Godot.Callable.From missing",
                "stack_trace": "GameAction.Cancel()",
            },
        },
    ]
    monkeypatch.setattr(recovery, "records", lambda _: iter(rows))
    result = recovery.failure_facts(tmp_path)
    assert not result["training_admitted"] and not result["replayed"] and not result["clean_close"]
    rows[0]["response"]["selection_combat"]["is_play_phase"] = True
    with pytest.raises(ValueError, match="exact unfinished"):
        recovery.failure_facts(tmp_path)
