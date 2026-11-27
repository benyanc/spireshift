from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift.native_a8_practice_recovery import INTERRUPTED, ORIGINAL_PENDING, plan, summarize
from spireshift.native_a8_practice_session import TEMPLATES, schedule


def test_interruption_stays_in_original_denominator_and_supplement_stays_separate() -> None:
    templates = {
        "fit": [
            {
                "key": key,
                "act": 3,
                "act_definition": definition,
                "entry": "preboss" if i == 2 else "act_start",
            }
            for definition, keys in TEMPLATES.items()
            for i, key in enumerate(keys)
        ]
    }
    original = schedule(templates, control=False)
    tail = plan(original)
    assert tuple(case["key"] for case in tail[:2]) == ORIGINAL_PENDING
    assert not {s for c in original for s in c["seed_pool"]}.intersection(tail[-1]["seed_pool"])
    retained: dict[str, Any] = {
        f"{case['key']}-p{p}": {"outcome": "goal"} for case in original[:-2] for p in (2, 3)
    }
    retained[INTERRUPTED] = {"outcome": "failed"}
    new = {f"{case['key']}-p{p}": {"outcome": "goal"} for case in tail for p in (2, 3)}
    result = summarize(original, tail[-1], retained, new, None)
    assert result["original_panel"]["outcomes"] == {"goal": 63, "failed": 1}
    assert result["paired_supplement"]["outcomes"] == {"2": "goal", "3": "goal"}
    assert result["matched_candidate"]["planned_segments"] == 64
    assert result["matched_candidate"]["ready_for_separate_admission"] is True
    new[f"{tail[-1]['key']}-p3"] = {"outcome": "capped"}
    result = summarize(original, tail[-1], retained, new, None)
    assert result["original_panel"]["outcomes"] == {"goal": 63, "failed": 1}
    assert result["matched_candidate"]["ready_for_separate_admission"] is False


def test_combat_selector_belt_target_and_owner_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Run the public binding tests with the bundled Node on native hosts")
    result = subprocess.run(
        [node, "--test", "scripts/engine-combat-selector-belt-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
