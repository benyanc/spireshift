from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spireshift import native_qualified_learning_verification_v2 as old_verification
from spireshift import native_qualified_learning_verification_v3 as verification
from spireshift.native_qualified_learning_inputs_v1 import plan
from spireshift.native_qualified_learning_readiness_v2 import cases


def test_absent_ledger_production_shape_and_negative_receipt_cases() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for saved transport verification")
    result = subprocess.run(
        [node, "--test", "scripts/engine-card-answer-verify-v3.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_fresh_control_worlds_are_disjoint_and_never_training_labels() -> None:
    controls = cases()
    declared = plan()
    old = set().union(*(declared[k] for k in ("training", "development", "control", "reload")))
    assert len({row["seed"] for row in controls}) == 2
    assert old.isdisjoint(row["seed"] for row in controls)
    assert {row["player"] for row in controls} == {2, 3}
    assert {row["partition"] for row in controls} == {"verifier-control"}


def test_optional_ledger_binding_retains_the_entire_frame_and_policy_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = old_verification.SCRIPT
    called = []

    def check(*args: Any, **kwargs: Any) -> int:
        assert old_verification.SCRIPT == verification.SCRIPT
        called.append((args, kwargs))
        return 123

    monkeypatch.setattr(old_verification, "verify_episode", check)
    assert (
        verification.verify_episode(
            {}, {}, "own_policy", tmp_path, tmp_path, 10, model="exact-model"
        )
        == 123
    )
    assert called[0][1] == {"model": "exact-model"}
    assert script == old_verification.SCRIPT
