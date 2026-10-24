from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from spireshift.native_layout_inputs_v2 import canonical_seed, load
from spireshift.native_live_checkpoint_v5 import run


@pytest.mark.parametrize(
    "seed", ["SP1RESH1FTSCOPECTRL003", "OIABC123", " ABC ", "abc", "A-B", "", None]
)
def test_ambiguous_game_seed_rejected_before_a_comparison(seed: object) -> None:
    with pytest.raises(ValueError, match="canonical"):
        canonical_seed(seed)


def test_already_canonical_seed_preserved_exactly() -> None:
    assert canonical_seed("SP1RESH1FTLAY0UT101") == "SP1RESH1FTLAY0UT101"


def test_invalid_layout_plan_stops_before_side_effects(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(ValueError, match="finite"):
        load(tmp_path, path)
    assert list(tmp_path.iterdir()) == [path]


def test_offline_layout_cannot_be_used_to_launch_games(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot launch"):
        run(tmp_path, {"config": {"stage": "saved_only_checks"}})
    assert not list(tmp_path.iterdir())


def test_targeted_layout_seed_ownership_and_protocol_contracts() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Run explicitly with the pinned bundled Node on native hosts")
    result = subprocess.run(
        [
            node,
            "--test",
            "scripts/engine-input-layout-v1.test.mjs",
            "scripts/engine-input-layout-v2.test.mjs",
            "scripts/engine-input-layout-v3.test.mjs",
            "scripts/engine-input-layout-v4.test.mjs",
            "scripts/engine-relic-surface-v3.test.mjs",
            "scripts/engine-combat-surface-v5.test.mjs",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_current_layout_refuses_offline_game_execution(tmp_path: Path) -> None:
    from spireshift.native_live_checkpoint_v8 import run as current_run

    with pytest.raises(ValueError, match="cannot launch"):
        current_run(tmp_path, {"config": {"stage": "saved_only_checks"}})
    assert not list(tmp_path.iterdir())


def test_current_layout_validates_plan_before_side_effects(tmp_path: Path) -> None:
    from spireshift.native_layout_inputs_v5 import load as current_load

    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(ValueError, match="finite"):
        current_load(tmp_path, path)
    assert list(tmp_path.iterdir()) == [path]
