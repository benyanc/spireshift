from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_owned_previews_generated_choices_and_shop_reads() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use bundled Node for public owner and read checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-selection-owner-read-v3.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
