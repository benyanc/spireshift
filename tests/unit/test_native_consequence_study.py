from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score

from spireshift import native_consequence_study as module
from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_experience import atomic_json
from spireshift.full_run_ppo_math import Adam
from spireshift.native_consequence_math import HEAD_SEEDS
from spireshift.native_context_cache import cached_model
from spireshift.native_context_journal import ChunkJournal


def test_validation_units_hold_complete_worlds_and_never_mix_parent_encoders(
    tmp_path: Path,
) -> None:
    data = [
        {"source_seed_id": w, "numerical_seed": p}
        for p, worlds in ((2, [1, 2, 3, 4]), (3, [5, 6, 7]))
        for w in worlds
    ]
    main = module.fit_units(
        data, {"stage": "bounded_learning_comparison", "cv_head_seeds": list(HEAD_SEEDS)}
    )
    assert len(main) == 63 and len({v["key"] for v in main}) == 63
    assert all(v["purpose"] == "cross_validation" for v in main)
    assert {v["held_world"] for v in main if v["numerical_seed"] == 2} == {1, 2, 3, 4}
    assert {v["held_world"] for v in main if v["numerical_seed"] == 3} == {5, 6, 7}
    control = module.fit_units(
        data,
        {
            "stage": "short_control",
            "cv_head_seeds": [HEAD_SEEDS[0]],
            "deployment_head_seed": HEAD_SEEDS[0],
        },
    )
    assert len(control) == 10
    final = [v for v in control if v["purpose"] == "final_fork"]
    assert len(final) == 4 and all(v["held_world"] is None for v in final)
    assert {v["head_seed"] for v in final} == {HEAD_SEEDS[0]}
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/keys"})
    for unit in [*main, *control]:
        assert store.path(unit["key"]).name == unit["key"]


@pytest.mark.parametrize("fault", ["owner", "variant", "head_seed", "purpose"])
def test_saved_fit_receipt_cannot_swap_parent_treatment_or_targets(
    fault: str, tmp_path: Path
) -> None:
    store = ChunkJournal(tmp_path, {"workspace": "artifacts/study"})
    unit = {
        "key": "fit",
        "stage": "fit",
        "numerical_seed": 2,
        "purpose": "cross_validation",
        "arm": "consequence",
        "head_seed": 1,
        "held_world": 1,
    }
    value = {k: v for k, v in unit.items() if k != "key"}
    if fault == "owner":
        value["numerical_seed"] = 3
    elif fault == "variant":
        value["arm"] = "return_only"
    elif fault == "head_seed":
        value["head_seed"] = 999
    else:
        value["purpose"] = "final_fork"
    with store.lock():
        directory = store.begin("fit", module.request(unit))
        (directory / "state.txt").write_text("sealed")
        store.commit("fit", module.request(unit), value)
    with pytest.raises(ValueError, match="owner"):
        module.receipt(store, unit, {})


def setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], Path, list[int]]:
    m = cached_model(model())
    cfg = {
        "stage": "short_control",
        "workspace": "artifacts/control",
        "session_limits": {"wall_seconds": 240},
        "qualification": "q",
        "qualification_id": "q",
        "native_inputs": {},
        "node": "node",
        "helpers_sha256": {},
        "maximum_decisions": 4096,
        "episode_wall_seconds": 120,
        "implementation_sha256": {},
        "entry_sha256": {},
        "deployment_head_seed": HEAD_SEEDS[0],
        "information_scope": "supervised",
    }
    path = tmp_path / "cfg.json"
    atomic_json(path, cfg)
    context = {
        "teacher_config": dict(cfg),
        "report": {"checks": {"unchanged": True}},
        "players": [],
        "source_world_denominator": [{"usable": True}, {"usable": False}],
        "units": [
            {"key": f"data-{i}", "root": {"source_seed_id": i, "numerical_seed": p}}
            for i, p in ((1, 2), (2, 3))
        ],
    }
    monkeypatch.setattr(module, "load_config", lambda *_: cfg)
    monkeypatch.setattr(
        module,
        "prepare",
        lambda *_: (
            context,
            {2: m, 3: m},
            {2: Adam.zero(m.parameter_count), 3: Adam.zero(m.parameter_count)},
            score(),
            {},
        ),
    )
    monkeypatch.setattr(
        module,
        "evaluation_seeds",
        lambda *_: (
            [{"id": i, "seed": f"WORLD{i}", "numerical_seed": p} for i, p in ((1, 2), (2, 3))],
            {},
        ),
    )
    monkeypatch.setattr(module, "mathematical_controls", lambda *_: {"passed": True})
    monkeypatch.setattr(module, "fit_units", lambda *_: [])
    encoded: list[int] = []

    def encode(*args: Any) -> dict[str, Any]:
        unit, directory = args[2], args[5]
        encoded.append(unit["root"]["source_seed_id"])
        (directory / "encoded.txt").write_text("data")
        return {
            "source_seed_id": unit["root"]["source_seed_id"],
            "numerical_seed": unit["root"]["numerical_seed"],
            "plans": 1,
            "combat_decisions": 1,
        }

    monkeypatch.setattr(module, "encode_world", encode)

    def no_native(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("An offline session must not launch a native game or inspect current UI")

    for name in ("branch", "_run_inputs", "_running_games", "_shared_snapshot"):
        monkeypatch.setattr(module, name, no_native)
    return cfg, path, encoded


def test_plan_only_creates_no_workspace_and_never_launches_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, encoded = setup(tmp_path, monkeypatch)
    result = module.run(tmp_path, path, status_only=True)
    assert result["games_launched"] == result["optimizer_steps"] == 0 and not encoded
    assert not (tmp_path / cfg["workspace"]).exists()


def test_small_offline_sessions_reuse_sealed_worlds_and_never_touch_native_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, encoded = setup(tmp_path, monkeypatch)
    first = module.run(tmp_path, path, offline_only=True, max_units=1)
    assert first["status"] == "paused_between_sealed_units" and encoded == [1]
    second = module.run(tmp_path, path, offline_only=True, max_units=1)
    assert second["status"] == "offline_units_complete" and encoded == [1, 2]
    third = module.run(tmp_path, path, offline_only=True)
    assert third["new_units_this_session"] == 0 and encoded == [1, 2]
    assert third["completed_games"] == third["production_optimizer_steps"] == 0
    assert len(third["source_world_denominator"]) == 2
    assert not (tmp_path / cfg["workspace"] / "report.json").exists()


def test_changed_completed_data_is_preserved_and_stops_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, encoded = setup(tmp_path, monkeypatch)
    module.run(tmp_path, path, offline_only=True, max_units=1)
    (tmp_path / cfg["workspace"] / "chunks/data-1/encoded.txt").write_text("changed")
    with pytest.raises(ValueError, match="evidence changed"):
        module.run(tmp_path, path, offline_only=True)
    assert encoded == [1]


def test_uncommitted_unit_is_never_replayed_automatically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, encoded = setup(tmp_path, monkeypatch)
    directory = tmp_path / cfg["workspace"] / "chunks/data-1"
    directory.mkdir(parents=True)
    (directory / "active.json").write_text("interrupted")
    with pytest.raises(FileExistsError, match="uncommitted"):
        module.run(tmp_path, path, offline_only=True)
    assert not encoded and (directory / "active.json").read_text() == "interrupted"


def test_cached_final_result_is_checked_without_new_fit_or_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg, path, encoded = setup(tmp_path, monkeypatch)
    body = {
        "config_id": manifest_identifier(cfg),
        "status": "native_consequence_control_complete",
        "sources": {},
    }
    atomic_json(
        tmp_path / cfg["workspace"] / "report.json",
        {**body, "report_id": manifest_identifier(body)},
    )
    result = module.run(tmp_path, path)
    assert result["status"] == "native_consequence_control_complete" and not encoded
    assert json.loads((tmp_path / cfg["workspace"] / "report.json").read_text()) == result
