from __future__ import annotations

import copy
import gzip
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score
from test_native_inventory_credit import public

from spireshift.full_run_ppo_math import Adam
from spireshift.native_context_cache import cached_model
from spireshift.native_inventory_input_audit import native_counter_example
from spireshift.native_inventory_input_probes import cards, changes, probe
from spireshift.native_structured_model import extend
from spireshift.native_structured_vocabulary import facts


def fixture() -> dict[str, Any]:
    p = public()
    p["candidates"] = [
        {"verb": "skip", "subject": None, "arguments": []},
        {"verb": "select", "subject": None, "arguments": []},
    ]
    p["context"]["interaction"]["content"]["context"]["player"]["hand"] = [
        {"definition_id": "CARD_A", "entity_id": {"public_slot": 1}, "cost": "1"}
    ]
    p["candidates"][1]["subject"] = {
        "properties": copy.deepcopy(
            p["context"]["interaction"]["content"]["context"]["player"]["hand"][0]
        )
    }
    return p


def test_same_coarse_counts_preserve_all_ten_meaningful_actor_distinctions() -> None:
    p = fixture()
    parent = cached_model(model())
    names = tuple(sorted({n for values in facts(p) for n in values}))
    models = {
        a: extend(parent, Adam.zero(parent.parameter_count), names, a)[0]
        for a in ("unchanged", "hashed", "named")
    }
    original = copy.deepcopy(p)
    rows = [probe(kind, before, after, models, score()) for kind, before, after in changes(p)]
    assert len(rows) == 10 and len({r["kind"] for r in rows}) == 10
    assert all(r["all_actual_actor_inputs_distinct"] and r["coarse_inputs_identical"] for r in rows)
    assert p == original


def test_paired_cost_and_upgrade_probes_keep_totals_and_definitions_fixed() -> None:
    for kind, before, after in changes(fixture()):
        if kind not in {"deck_cost_ownership", "deck_upgrade_ownership"}:
            continue
        field = "cost" if kind == "deck_cost_ownership" else "is_upgraded"
        assert [c["definition_id"] for c in cards(before)] == [
            c["definition_id"] for c in cards(after)
        ]
        assert sorted(c[field] for c in cards(before)) == sorted(c[field] for c in cards(after))
        assert cards(before) != cards(after)


def test_a_disconnected_actor_is_detected_even_when_the_inventory_probe_is_richer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = cached_model(model())
    kind, before, after = next(changes(fixture()))
    monkeypatch.setattr(
        "spireshift.native_inventory_input_probes.encode", lambda *args: (({0: 1.0},), (1.0,))
    )
    with pytest.raises(ValueError, match="Actual actor input lost"):
        probe(kind, before, after, {"constant": parent}, score())


@pytest.mark.parametrize("private", ["rng_state", "seed"])
def test_no_private_field_or_handle_can_hide_in_a_distinction_probe(private: str) -> None:
    parent = cached_model(model())
    kind, before, after = next(changes(fixture()))
    after["context"][private] = "PRIVATE"
    with pytest.raises(ValueError, match="Private"):
        probe(kind, before, after, {"original": parent}, score())


def test_native_debug_scan_returns_only_already_public_id_and_counter(tmp_path: Path) -> None:
    path = tmp_path / "native.jsonl.gz"
    with gzip.open(path, "wt") as handle:
        handle.write(
            json.dumps(
                {
                    "response": {
                        "decision": "combat_play",
                        "rng_state": "PRIVATE",
                        "player": {
                            "native_ref": "PRIVATE",
                            "relics": [
                                {"id": "SWORD_OF_STONE", "counter": 0, "native_ref": "PRIVATE"}
                            ],
                        },
                    }
                }
            )
            + "\n"
        )
    assert native_counter_example(path, time.monotonic() + 3) == {
        "definition_id": "SWORD_OF_STONE",
        "counter": 0,
    }
    with pytest.raises(TimeoutError):
        native_counter_example(path, time.monotonic() - 1)


def test_native_relic_projection_contract_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node not installed")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", "scripts/engine-relic-surface-v1.test.mjs"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
