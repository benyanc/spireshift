from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("completed", [True, False])
def test_reward_runner_uses_recipe_workspace_for_cache_and_resource_tracking(
    tmp_path: Path, completed: bool
) -> None:
    """Exercise the shell helper with inert CLI stand-ins; no engine can launch."""
    repository = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    runner = scripts / "compare-reward-actions-v1.sh"
    shutil.copyfile(repository / "scripts/compare-reward-actions-v1.sh", runner)
    config = tmp_path / "configs/engine-qualification/sts2-v0.111.0-reward-bridges-v8.json"
    config.parent.mkdir(parents=True)
    workspace = "artifacts/recipe-owned-reward-panel"
    config.write_text(json.dumps({"workspace": workspace}))
    if completed:
        (tmp_path / workspace).mkdir(parents=True)
        (tmp_path / workspace / "batch.json").write_text(
            json.dumps({"status": "reward_comparisons_pass", "completed_cases": 8})
        )
        # The historical script wrote outputs and tracked storage in this other directory.
        legacy = (
            tmp_path
            / "artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/reward-bridges-v8"
        )
        legacy.mkdir(parents=True)
        (legacy / "summary.json").write_text("{}")
        resource = tmp_path / "artifacts/resources/reward-comparisons-v1.json"
        resource.parent.mkdir(parents=True)
        resource.write_text("{}")
    binary = tmp_path / "bin"
    binary.mkdir()
    uv = binary / "uv"
    uv.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "with Path('calls.jsonl').open('a') as file:\n"
        "    file.write(json.dumps(args) + '\\n')\n"
        "if args[:2] == ['run', 'python']:\n"
        "    os.execv(sys.executable, [sys.executable, *args[2:]])\n"
        "if '--output' in args:\n"
        "    output = Path(args[args.index('--output') + 1])\n"
        "    output.parent.mkdir(parents=True, exist_ok=True)\n"
        "    output.write_text('{}')\n"
    )
    uv.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "SPIRESHIFT_NODE": sys.executable,
    }
    process = subprocess.run(
        ["bash", str(runner)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert process.returncode == 0, process.stderr + process.stdout
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    if completed:
        assert "already has a saved result" in process.stdout
        assert any("verify-reward-bridges" in call for call in calls)
        assert not any("compare-reward-bridges" in call or "resources" in call for call in calls)
    else:
        resource_call = next(call for call in calls if "resources" in call)
        assert resource_call[resource_call.index("--artifact-root") + 1] == workspace
        assert resource_call[resource_call.index("--output") + 1] == workspace + "/summary.json"
        audit_call = next(call for call in calls if "verify-reward-bridges" in call)
        assert (
            audit_call[audit_call.index("--output") + 1] == workspace + "/saved-verification.json"
        )
