from __future__ import annotations

import copy
import gzip
import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_native_inventory_input import fixture

from spireshift.native_relic_observation import legacy_view, verify
from spireshift.native_relic_qualification import Replay


def public() -> dict[str, Any]:
    p = fixture()
    p["context"]["interaction"]["kind"] = "combat_turn"
    player = p["context"]["interaction"]["content"]["context"]["player"]
    player.update(player_entity_id={"public_slot": 0}, energy=3)
    p["candidates"][1]["arguments"] = [{"role": "target", "entity": {"properties": player}}]
    return p


def test_legacy_view_keeps_owned_inventory_and_noncombat_counters() -> None:
    p = public()
    original = copy.deepcopy(p)
    v = legacy_view(p)
    assert (
        v["context"]["persistent"]["player"]["relics"]
        == p["context"]["persistent"]["player"]["relics"]
    )
    assert "relics" not in v["context"]["interaction"]["content"]["context"]["player"]
    assert "relics" not in v["candidates"][1]["arguments"][0]["entity"]["properties"]
    assert p == original
    p["context"]["interaction"]["kind"] = "rest_site"
    assert legacy_view(p) == p


def test_diagnostic_replay_checks_every_old_fact_and_menu_without_training() -> None:
    p = public()
    replay = Replay(
        {"decisions": [{"public_input": legacy_view(p), "choice": {"action_index": 1}}]}
    )
    choice = replay(p)
    assert choice["action_index"] == 1 and choice["ordinary_PPO_eligible"] is False
    with pytest.raises(ValueError, match="legacy public trace"):
        replay(p)
    replay = Replay(
        {"decisions": [{"public_input": legacy_view(p), "choice": {"action_index": 1}}]}
    )
    p["context"]["persistent"]["player"]["hp"] = 1
    with pytest.raises(ValueError, match="legacy public trace"):
        replay(p)


def journals(root: Path, public_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]]) -> None:
    for name, rows in (("private-transcript", raw_rows), ("public-observations", public_rows)):
        with gzip.open(root / f"{name}.jsonl.gz", "wt") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")


@pytest.mark.parametrize("fault", [None, "drop", "swap", "stale", "private", "short", "zero_null"])
def test_ordered_counter_verifier_detects_missing_ownership_staleness_and_private_fields(
    tmp_path: Path,
    fault: str | None,
) -> None:
    inputs = [public(), public()]
    for p, amounts in zip(inputs, ((0, 7), (1, 8)), strict=True):
        relics = p["context"]["interaction"]["content"]["context"]["player"]["relics"]
        for r, amount in zip(relics, amounts, strict=True):
            r["counter"] = amount
    raw = [
        {
            "response": {
                "decision": "combat_play",
                "player": {
                    "relics": copy.deepcopy(
                        p["context"]["interaction"]["content"]["context"]["player"]["relics"]
                    )
                },
            }
        }
        for p in inputs
    ]
    relics = inputs[1]["context"]["interaction"]["content"]["context"]["player"]["relics"]
    if fault == "drop":
        del inputs[1]["context"]["interaction"]["content"]["context"]["player"]["relics"]
    elif fault == "swap":
        relics.reverse()
    elif fault == "stale":
        relics[0]["counter"] = 0
    elif fault == "private":
        inputs[1]["context"]["rng_state"] = "PRIVATE"
    elif fault == "zero_null":
        inputs[0]["context"]["interaction"]["content"]["context"]["player"]["relics"][0][
            "counter"
        ] = None
    public_rows = [{"model_input": p} for p in inputs]
    if fault == "short":
        public_rows.pop()
    journals(tmp_path, public_rows, raw)
    if fault:
        with pytest.raises(ValueError):
            verify(tmp_path, time.monotonic() + 3)
    else:
        result = verify(tmp_path, time.monotonic() + 3)
        assert result["combat_observations_verified"] == 2
        assert result["zero_counter_observations"] == 1
        assert result["maximum_records_retained_per_stream"] == 1
