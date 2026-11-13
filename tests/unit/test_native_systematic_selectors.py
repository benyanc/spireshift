from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_systematic_selector_formats() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to check the shared selector contract")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", str(root / "scripts/engine-systematic-selectors-v1.test.mjs")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
