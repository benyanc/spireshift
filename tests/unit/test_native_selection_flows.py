from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.native_flow_inputs import load
from spireshift.native_launch_limits import load_launch


def test_targeted_reward_pack_shop_contracts() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Use the bundled Node for local game-contract checks")
    result = subprocess.run(
        [node, "--test", "scripts/engine-selection-flows-v1.test.mjs"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def make_plan(root: Path) -> tuple[Path, dict[str, object]]:
    config: dict[str, object] = {
        "stage": "bounded_live_checkpoint_canary",
        "cases": [{}, {}, {}, {}],
        "maximum_case_wall_seconds": 360,
    }
    recipe = root / "experiment.json"
    recipe.write_text(json.dumps(config))
    return recipe, config


def make_launch(root: Path, recipe: Path, wall: int) -> Path:
    path = root / f"launch-{wall}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "native-comparison-launch-v1",
                "recipe": {
                    "path": recipe.name,
                    "sha256": hashlib.sha256(recipe.read_bytes()).hexdigest(),
                },
                "wall_seconds": wall,
                "cpu_seconds": max(wall, 3600),
                "resident_memory_bytes": 4000000000,
                "storage_bytes": 1000000000,
            }
        )
    )
    return path


def test_whole_batch_budget_keeps_experiment_and_saved_unit_identity(tmp_path: Path) -> None:
    recipe, config = make_plan(tmp_path)
    experiment_id = manifest_identifier(config)
    first = load_launch(tmp_path, make_launch(tmp_path, recipe, 1800), recipe, config)
    extended = load_launch(tmp_path, make_launch(tmp_path, recipe, 2400), recipe, config)
    assert first.wall_seconds == 1800 and extended.wall_seconds == 2400
    assert manifest_identifier(config) == experiment_id
    assert json.loads(recipe.read_text()) == config


@pytest.mark.parametrize("wall", [900, 1440, False, 7201])
def test_insufficient_or_invalid_budget_stops_before_work(tmp_path: Path, wall: int) -> None:
    recipe, config = make_plan(tmp_path)
    with pytest.raises(ValueError, match="whole planned batch"):
        load_launch(tmp_path, make_launch(tmp_path, recipe, wall), recipe, config)
    assert not (tmp_path / "active.json").exists()


def test_launch_cannot_switch_experiments(tmp_path: Path) -> None:
    recipe, config = make_plan(tmp_path)
    launch = make_launch(tmp_path, recipe, 1800)
    recipe.write_text("{}")
    with pytest.raises(ValueError, match="exact finite experiment"):
        load_launch(tmp_path, launch, recipe, config)


def test_invalid_flow_recipe_has_no_game_side_effects(tmp_path: Path) -> None:
    recipe = tmp_path / "bad.json"
    recipe.write_text("{}")
    with pytest.raises(ValueError, match="finite"):
        load(tmp_path, recipe)
    assert list(tmp_path.iterdir()) == [recipe]


def owner_launcher() -> object:
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts/selection-flows-session-v1.py"
    spec = importlib.util.spec_from_file_location("selection_flows_owner", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status", ["capped", "failed"])
def test_owner_gate_rejects_incomplete_checks_even_with_zero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    from typing import Any, cast

    module = cast(Any, owner_launcher())
    monkeypatch.setattr(module, "repository_files", lambda _: {"source.py": "fixed"})

    def run(args: list[str], cwd: Path) -> int:
        resource = Path(args[args.index("--report") + 1])
        body = {"status": status, "exit_code": 0}
        resource.write_text(json.dumps({**body, "report_id": manifest_identifier(body)}))
        return 0

    monkeypatch.setattr(module.subprocess, "call", run)
    with pytest.raises(ValueError, match="did not finish cleanly"):
        module.check_repository(tmp_path)
    assert not list(tmp_path.rglob("passed.json"))


def test_owner_gate_reuses_only_successful_exact_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import Any, cast

    module = cast(Any, owner_launcher())
    sources = {"source.py": "fixed"}
    monkeypatch.setattr(module, "repository_files", lambda _: dict(sources))
    calls = []

    def run(args: list[str], cwd: Path) -> int:
        calls.append(args)
        resource = Path(args[args.index("--report") + 1])
        body = {"status": "completed", "exit_code": 0}
        resource.write_text(json.dumps({**body, "report_id": manifest_identifier(body)}))
        return 0

    monkeypatch.setattr(module.subprocess, "call", run)
    assert module.check_repository(tmp_path) == 0
    assert module.check_repository(tmp_path) == 0
    assert len(calls) == 1
    sources["source.py"] = "changed"
    assert module.check_repository(tmp_path) == 0
    assert len(calls) == 2
