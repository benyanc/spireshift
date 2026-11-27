from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


def test_modal_belt_identity_permissions_and_selection_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use bundled Node for modal potion tests")
    result = subprocess.run(
        [
            node,
            "--test",
            "scripts/engine-modal-belt-v2.test.mjs",
            "scripts/engine-selection-owner-read-v7.test.mjs",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
