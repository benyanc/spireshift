from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from spireshift import native_normalization_recovery_v1 as recovery
from spireshift.native_deferred_potion_control_v1 import verify_buffer


def test_deferred_acceptance_requires_original_buffer_state_and_exact_discard_tracking() -> None:
    row: dict[str, Any] = {
        "kind": "DiscardPotionGameAction",
        "action_id": None,
        "state": "None",
        "tracked_discard": True,
    }
    identity = {"deferred_potions": {"combat_state": "NotPlayPhase", "buffer": [row]}}
    assert verify_buffer(identity, ["DiscardPotionGameAction"])["tracked_discards"] == 1
    for field, value in (("action_id", 42), ("state", "Canceled"), ("tracked_discard", False)):
        old = row[field]
        row[field] = value
        with pytest.raises(ValueError, match="exact native"):
            verify_buffer(identity, ["DiscardPotionGameAction"])
        row[field] = old
    with pytest.raises(ValueError, match="exact native"):
        verify_buffer(identity, ["UsePotionAction"])


def test_unknown_prefix_is_not_relabelled_as_a_clean_ending_or_training(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transcript = [
        {
            "request": {},
            "response": {
                "type": "decision",
                "decision": "generated_card_choice",
                "selection_combat": {"is_play_phase": False},
                "context": {"floor": 17},
            },
        },
        {
            "request": {"action": "discard_potion"},
            "response": {
                "type": "error",
                "message": "Native potion discard enqueue was not confirmed",
            },
        },
    ]
    receipts: list[dict[str, Any]] = [
        {"delivery": "delivered"},
        {"delivery": "unknown", "successor_snapshot_id": None},
    ]
    monkeypatch.setattr(
        recovery,
        "records",
        lambda p: iter(transcript if p.name.startswith("private") else receipts),
    )
    result = recovery.failure_facts(tmp_path)
    assert result["acknowledged_prefix_deliveries"] == 1
    assert not result["training_admitted"] and not result["clean_close"] and not result["replayed"]
    receipts[0]["delivery"] = "unknown"
    with pytest.raises(ValueError, match="exact unsealed"):
        recovery.failure_facts(tmp_path)
    receipts[0]["delivery"] = "delivered"
    (tmp_path / "done.json").write_text("{}")
    with pytest.raises(ValueError, match="exact unsealed"):
        recovery.failure_facts(tmp_path)
