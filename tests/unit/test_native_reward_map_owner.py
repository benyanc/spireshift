from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_map_reward_owner_uses_identity_and_preserves_new_modal_rewards(
    tmp_path: Path,
) -> None:
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        pytest.skip("The native contract check needs the .NET SDK")
    source = Path(__file__).resolve().parents[2] / "backend-patches/reward-map-owner-v1"
    for name in ["RewardMapPresentationOwner.cs", "OwnerContractCheck.cs", "ContractCheck.csproj"]:
        shutil.copyfile(source / name, tmp_path / name)
    result = subprocess.run(
        [dotnet, "run", "--project", str(tmp_path / "ContractCheck.csproj"), "--nologo"],
        cwd=tmp_path,
        env={**os.environ, "DOTNET_ROLL_FORWARD": "Major"},
        capture_output=True,
        text=True,
        timeout=45,
        check=True,
    )
    assert "8 controls pass; no game, optimizer or reward effects" in result.stdout
