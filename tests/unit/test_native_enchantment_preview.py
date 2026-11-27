from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_public_pending_enchantment_and_event_owner() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use bundled Node for public preview checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-enchantment-preview-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
