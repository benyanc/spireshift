from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_current_card_titles_and_conflict_rejection() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use the bundled Node for public card-title contract checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-card-titles-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
