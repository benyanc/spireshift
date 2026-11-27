from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.native_win2_inputs import binding, validate
from spireshift.native_win2_recovery import continuation_plan, import_unit
from spireshift.native_win2_session import inspect_resume
from spireshift.native_win2_study import unit

ROOT = Path(__file__).resolve().parents[2]


def parent() -> dict[str, Any]:
    return dict(
        json.loads(
            (ROOT / "configs/native-curriculum/sts2-v0.111.0-a8-win-curriculum-v1.json").read_text()
        )
    )


def config() -> tuple[dict[str, Any], dict[str, Any]]:
    old = parent()
    new = {
        **copy.deepcopy(old),
        "schema_version": "native-win-curriculum-config-v2",
        "workspace": "artifacts/native-win-curriculum/study-v2",
        "plan": continuation_plan(old),
        "historical_incomplete_cases": 1,
        "repair_generation": 2,
        "reused_original_cases": 6,
    }
    return new, old


def test_only_interrupted_world_is_replaced_and_all_heldout_worlds_stay_owned() -> None:
    cfg, old = config()
    before = copy.deepcopy(old)
    validate(cfg, old)
    assert old == before
    assert cfg["plan"]["fit"][:6] == old["plan"]["fit"][:6]
    assert cfg["plan"]["fit"][7:] == old["plan"]["fit"][7:]
    assert cfg["plan"]["heldout"] == old["plan"]["heldout"]
    assert cfg["plan"]["quality"] == old["plan"]["quality"]
    assert cfg["plan"]["fit"][6]["key"] == "fit-007-replacement-1"
    assert set(cfg["plan"]["fit"][6]["seed_pool"]).isdisjoint(old["plan"]["fit"][6]["seed_pool"])
    assert (
        len(cfg["plan"]["fit"]) + len(cfg["plan"]["heldout"]) + cfg["historical_incomplete_cases"]
        == 69
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("main_optimizer_updates", 1),
        ("promotion_allowed", True),
        ("automatic_follow_up", True),
        ("ordinary_PPO_allowed", True),
        ("historical_incomplete_cases", 0),
        ("official_live_qualification_inherited", True),
        ("reused_original_cases", 0),
    ],
)
def test_recovery_does_not_grant_training_or_erase_original_failures(key: str, value: Any) -> None:
    cfg, old = config()
    cfg[key] = value
    with pytest.raises(ValueError):
        validate(cfg, old)


def test_stale_repair_receipt_or_seed_plan_cannot_match_binding() -> None:
    cfg, old = config()
    value = binding(cfg)
    cfg["repair_control"] = {"report": "receipt"}
    assert binding(cfg) == value
    cfg["plan"]["fit"][6]["seed_pool"] = old["plan"]["fit"][6]["seed_pool"]
    assert binding(cfg) != value
    with pytest.raises(ValueError):
        validate(cfg, old)


def test_import_requires_exact_old_seal_and_original_request(
    monkeypatch: Any, tmp_path: Path
) -> None:
    request = {"stage": "episode"}
    ctx = {
        "qualification": SimpleNamespace(root=tmp_path),
        "parent_config": {},
        "imports": {
            "fit-001-reference": {
                "request_id": manifest_identifier(request),
                "receipt_id": "expected",
            }
        },
    }
    monkeypatch.setattr(
        "spireshift.native_win2_recovery.ChunkJournal",
        lambda *_: SimpleNamespace(completed=lambda *_: {"report_id": "wrong", "result": {}}),
    )
    with pytest.raises(ValueError, match="changed"):
        import_unit(ctx, "fit-001-reference", request)
    with pytest.raises(ValueError, match="request differs"):
        import_unit(ctx, "fit-001-reference", {"stage": "different"})
    assert import_unit(ctx, "fit-007-replacement-1-reference", request) is None


def test_imported_unit_never_calls_game_operation(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "spireshift.native_win2_study.import_unit", lambda *_: {"status": "complete"}
    )
    store = SimpleNamespace(
        completed=lambda *_: None, begin=lambda *_: tmp_path, commit=lambda *_: None
    )

    def forbidden(*_: Any) -> None:
        raise AssertionError("Imported sealed evidence must not launch another game")

    out = unit(
        {"imports": {"fit-001-reference": {"receipt_id": "old"}}, "sources": {}},
        cast(Any, store),
        "fit-001-reference",
        {},
        time.monotonic() + 1,
        forbidden,
    )
    assert out == {"status": "complete"}
    assert json.loads((tmp_path / "import.json").read_text())["new_game_or_action"] is False


def test_old_interrupted_workspace_and_marker_stay_blocked(tmp_path: Path) -> None:
    cfg = {"workspace": "artifacts/native-win-curriculum/study-v1"}
    base = tmp_path / cfg["workspace"]
    chunk = base / "chunks/fit-007-reference"
    chunk.mkdir(parents=True)
    (base / "config-at-launch.json").write_text(json.dumps(cfg))
    (chunk / "active.json").write_text('{"preserve":true}\n')
    before = (chunk / "active.json").read_bytes()
    with pytest.raises(FileExistsError, match="unfinished"):
        inspect_resume({"qualification": SimpleNamespace(root=tmp_path), "config": cfg})
    assert (chunk / "active.json").read_bytes() == before
