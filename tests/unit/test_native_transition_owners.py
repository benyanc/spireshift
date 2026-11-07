from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_reward_potion_and_closed_merchant_contracts() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use bundled Node for public transition checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-transition-owners-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
