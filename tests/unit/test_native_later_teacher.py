from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from test_native_combat_teacher import root as original_root

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_combat_teacher import tasks
from spireshift.native_combat_teacher_data import INFORMATION, lesson
from spireshift.native_later_teacher import load, run
from spireshift.native_later_teacher_roots import (
    QUOTAS_BY_PLAYER,
    SELECTION,
    eligibility,
    first_positions,
)


def public() -> dict[str, Any]:
    p: dict[str, Any] = original_root()["public_input"]
    p["context"]["persistent"]["run"]["floor"] = 6
    p["context"]["interaction"]["content"]["context"].update(
        encounter_type="normal",
        round=2,
        turn_owner="player",
        is_play_phase=True,
        enemies=[{"intends_attack": True, "intents": [{"total_damage": 12}]}],
    )
    first, second = p["candidates"]
    first["verb"], second["verb"] = "play", "use"
    end = copy.deepcopy(first)
    end.update(verb="end_turn", label="End turn")
    p["candidates"].append(end)
    return p


def test_later_visible_attack_selects_choices_without_asserting_exact_damage() -> None:
    value = eligibility(public())
    assert value is not None and value["public_round"] == 2
    assert value["displayed_attack_excess"] == 12
    assert value["play_or_use_candidates"] == 2
    assert not value["selection_uses_final_outcomes"]
    assert not value["attack_excess_is_exact_hp_loss_prediction"]


@pytest.mark.parametrize("fault", ["turn1", "floor", "blocked", "unknown", "one_play", "rest"])
def test_sampling_filters_are_explicit_and_do_not_guess_missing_mechanics(fault: str) -> None:
    p = public()
    c = p["context"]["interaction"]["content"]["context"]
    if fault == "turn1":
        c["round"] = 1
    elif fault == "floor":
        p["context"]["persistent"]["run"]["floor"] = 4
    elif fault == "blocked":
        c["player"]["block"] = 12
    elif fault == "unknown":
        c["enemies"][0]["intents"] = [{"description": "Attack"}]
    elif fault == "one_play":
        p["candidates"][1]["verb"] = "activate"
    else:
        p["context"]["interaction"]["kind"] = "rest_site"
    assert eligibility(p) is None


def test_selection_is_first_in_fixed_order_bounded_and_invariant_to_outcomes() -> None:
    p = public()
    rows: list[dict[str, Any]] = [
        {"public_input": copy.deepcopy(p), "choice": {"action_index": a}} for a in (0, 1, 2)
    ]
    assert first_positions(rows)["normal"][0] == 0
    before = first_positions(rows)
    for row in rows:
        row.update(final_return=1, victory=True, hidden_rng=999)
        row["choice"]["action_index"] = 2
    assert first_positions(rows) == before
    skip = copy.deepcopy(p)
    skip["context"]["interaction"]["kind"] = "card_selection"
    prefix = [{"public_input": skip}] * 512
    assert first_positions([*prefix, {"public_input": p}])["normal"][0] == 512
    assert not first_positions([*prefix, {"public_input": skip}, {"public_input": p}])
    assert not first_positions(prefix)


def fixture(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], Path]:
    from spireshift import native_later_teacher as teacher

    source_path, entry_path = root / "src/spireshift/test.py", root / "scripts/test.py"
    source_path.parent.mkdir(parents=True)
    entry_path.parent.mkdir()
    source_path.write_text("source")
    entry_path.write_text("entry")
    monkeypatch.setattr(teacher, "SOURCES", (source_path.name,))
    monkeypatch.setattr(teacher, "ENTRIES", (entry_path.name,))
    monkeypatch.setattr(teacher, "worker_helpers", lambda *a: {"helper": "frozen"})
    directory = root / "artifacts/roots"
    directory.mkdir(parents=True)
    references, sources = [], {}
    for i in range(8):
        p = public()
        body = {
            "public_input": p,
            "public_input_id": manifest_identifier(p),
            "prefix": [],
            "reference_action": 0,
            "native_seed": f"TRAIN{i}",
            "numerical_seed": 2 + i // 4,
            "root_selection": SELECTION,
            "selection_evidence": eligibility(p),
        }
        value = {**body, "root_id": manifest_identifier(body)}
        path = directory / f"root-{i}.json"
        atomic_json(path, value)
        references.append(
            {
                "path": str(path.relative_to(root)),
                "id": value["root_id"],
                "numerical_seed": body["numerical_seed"],
                "actions": 3,
                "prefix_decisions": 0,
            }
        )
        sources[str(path.relative_to(root))] = _sha_file(path)
    body = {
        "schema_version": "native-later-combat-teacher-roots-v2",
        "roots": references,
        "new_games": 0,
        "sources": sources,
        "selection": SELECTION,
        "selection_uses_final_outcomes": False,
        "encounter_quotas_per_initializer": QUOTAS_BY_PLAYER,
        "temperature": 0.8,
    }
    report = {**body, "report_id": manifest_identifier(body)}
    atomic_json(directory / "report.json", report)
    cfg = {
        "schema_version": "native-later-combat-teacher-config-v2",
        "stage": "short_control",
        "roots_report": {"path": "artifacts/roots/report.json", "id": report["report_id"]},
        "workspace": "artifacts/control",
        "repeats": 2,
        "temperature": 0.8,
        "information_scope": INFORMATION,
        "ordinary_PPO_eligible": False,
        "root_selection": SELECTION,
        "implementation_sha256": {source_path.name: _sha_file(source_path)},
        "entry_sha256": {entry_path.name: _sha_file(entry_path)},
        "helpers_sha256": {"helper": "frozen"},
        "session_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 480,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 1000000000,
        },
    }
    recipe = root / "recipe.json"
    recipe.write_text(json.dumps(cfg))
    return cfg, recipe


def test_plan_only_and_completed_result_reuse_never_launches_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_later_teacher as teacher

    cfg, recipe = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(teacher, "_running_games", lambda: pytest.fail("No host for saved plans"))
    result = run(tmp_path, recipe, Path("not-used"), status_only=True)
    assert result["new_games"] == 0 and result["planned_branches"] == 14
    assert not (tmp_path / cfg["workspace"]).exists()
    directory = tmp_path / cfg["workspace"]
    directory.mkdir()
    body = {
        "config_id": manifest_identifier(cfg),
        "status": "native_later_combat_teacher_complete",
        "planned_branches": 14,
        "root_selection": SELECTION,
        "sources": {},
    }
    saved = {**body, "report_id": manifest_identifier(body)}
    atomic_json(directory / "report.json", saved)
    assert run(tmp_path, recipe, Path("not-used")) == saved
    cfg["temperature"] = 0.9
    recipe.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="continuation"):
        run(tmp_path, recipe, Path("not-used"))


@pytest.mark.parametrize("fault", ["source", "grid", "selector", "PPO", "caps", "root"])
def test_changed_sources_scope_caps_and_root_conditions_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    cfg, recipe = fixture(tmp_path, monkeypatch)
    if fault == "source":
        (tmp_path / "src/spireshift/test.py").write_text("changed")
    elif fault == "grid":
        cfg["repeats"] = 32
    elif fault == "selector":
        cfg["root_selection"] = "pick_by_final_return"
    elif fault == "PPO":
        cfg["ordinary_PPO_eligible"] = True
    elif fault == "caps":
        cfg["session_limits"]["wall_seconds"] = 7200
    else:
        (tmp_path / "artifacts/roots/root-0.json").write_text("changed")
    recipe.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        load(tmp_path, recipe)


def test_unchanged_branch_plan_uncertainty_and_non_PPO_contract() -> None:
    p = public()
    root = {
        "public_input": p,
        "public_input_id": manifest_identifier(p),
        "root_id": "fixed",
        "reference_action": 0,
    }
    assert len(tasks([root], 8, False)) == 24
    cells = [
        {
            "action": a,
            "repeat": r,
            "status": "terminal",
            "root_reached": True,
            "native_audit_valid": True,
            "training_return": 0.03,
            "maximum_floor": 8,
            "victory": False,
        }
        for a in range(3)
        for r in range(8)
    ]
    result = lesson(root, cells, 8)
    assert result["comparison_complete"] and not result["ordinary_PPO_eligible"]
    assert not any(p["admitted_exploratory_preference"] for p in result["preferences"])
    assert all(a["independent_hidden_worlds"] == 1 for a in result["actions"])
