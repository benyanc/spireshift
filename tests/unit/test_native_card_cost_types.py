from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_current_card_cost_types_and_exact_preservation() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use bundled Node for current card cost checks")
    result = subprocess.run(
        [
            node,
            "--test",
            "scripts/engine-card-cost-types-v1.test.mjs",
            "scripts/engine-selection-owner-read-v5.test.mjs",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
