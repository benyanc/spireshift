from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_crystal_grid_contract() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to check the native Crystal Sphere contract")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", str(root / "scripts/engine-crystal-grid-v1.test.mjs")],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
