"""Optional reward exits remain usable; actual no-ops and cycles stay bounded."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from spireshift.engine_worker import LIVENESS_POLICY, EngineWorker


def episode(observations: Iterator[tuple[str, bool]]) -> dict[str, Any]:
    # Exercise the real episode loop with a synthetic public transport only.
    worker = object.__new__(EngineWorker)
    worker.last_cpu_seconds = 0.0
    worker.closed = False

    def request(command: str, **kwargs: Any) -> dict[str, Any]:
        if command == "ending":
            return {"native_ending_evidence_agrees": True}
        key, terminal = next(observations)
        return {
            "private_start_identity": {},
            "native_process_id": 123,
            "reset": False,
            "snapshot": {"snapshot_id": key},
            "facts": {"floor": 4, "act": 1, "terminal": terminal, "victory": False},
            "model_input": {
                "context": {"interaction": {"kind": key}},
                "candidates": [{"kind": "skip"}, {"kind": "claim"}, {"kind": "proceed"}],
            },
            "public_key": key,
            "default_action_index": 0,
        }

    def stop() -> None:
        worker.closed = True

    def choose(public: dict[str, Any]) -> dict[str, Any]:
        assert [a["kind"] for a in public["candidates"]] == ["skip", "claim", "proceed"]
        return {"action_index": 0}

    worker.request = request  # type: ignore[method-assign]
    worker.stop = stop  # type: ignore[method-assign]
    result = worker.episode(
        "SYNTHETIC", maximum_decisions=4096, wall_seconds=60, cpu_seconds=128, chooser=choose
    )
    assert worker.closed == (result["status"] == "failed")
    assert result["liveness_policy"] == LIVENESS_POLICY
    return result


def test_several_reward_reopen_skip_cycles_can_finish_without_forced_action() -> None:
    rows = [(key, False) for _ in range(10) for key in ("reward_claim", "card_reward_selection")]
    result = episode(iter([*rows, ("game_over", True)]))
    assert result["status"] == "terminal"
    assert len(result["decisions"]) == 20
    assert all(row["choice"]["action_index"] == 0 for row in result["decisions"])


@pytest.mark.parametrize(
    ("keys", "message", "delivered"),
    [
        (["stuck"] * 9, "Consecutive unchanged", 8),
        (["reward_claim", "card_reward_selection"] * 65, "exploration cap", 128),
    ],
)
def test_no_ops_and_endless_menu_cycles_remain_bounded(
    keys: list[str], message: str, delivered: int
) -> None:
    result = episode(iter((key, False) for key in keys))
    assert result["status"] == "failed" and message in result["error"]
    assert len(result["decisions"]) == delivered
