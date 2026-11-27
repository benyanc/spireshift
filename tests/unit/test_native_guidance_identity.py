from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from spireshift.native_flow_live_v3 import completion_status


def test_guidance_and_physical_copy_identity() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use bundled Node for guidance and identity checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-guidance-identity-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "delivered,equal,status",
    [
        (True, True, "live_checkpoint_delivery_control_pass"),
        (True, False, "live_checkpoint_inputs_blocked"),
        (False, True, "live_checkpoint_delivery_blocked"),
        (False, False, "live_checkpoint_delivery_blocked"),
    ],
)
def test_input_mismatch_cannot_be_reported_as_success(
    delivered: bool,
    equal: bool,
    status: str,
) -> None:
    assert completion_status(delivered, equal) == status
