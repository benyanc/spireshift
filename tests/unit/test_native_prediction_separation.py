from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spireshift.core.manifest import manifest_identifier
from spireshift.engine_qualification import _sha_file
from spireshift.full_run_experience import atomic_json
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_prediction_separation import fit_plan, run
from spireshift.native_rank_audit import aggregate, summarize_rows


def data() -> list[dict[str, Any]]:
    return [
        {"source_seed_id": n, "numerical_seed": 2 if n in (0, 2, 4, 6) else 3}
        for n in (0, 1, 2, 4, 5, 6, 7)
    ]


def test_prediction_folds_keep_each_entire_world_and_original_parent(tmp_path: Path) -> None:
    units = fit_plan(data())
    assert len(units) == 9 and len({u["key"] for u in units}) == 9
    assert [u["held_world"] for u in units if u["numerical_seed"] == 2] == [0, 2, 4, 6, None]
    assert [u["held_world"] for u in units if u["numerical_seed"] == 3] == [1, 5, 7, None]
    assert all(ChunkJournal(tmp_path, {"workspace": "artifacts/x"}).path(u["key"]) for u in units)
    with pytest.raises(ValueError):
        fit_plan(data()[:-1])
    bad = data()
    bad[0]["source_seed_id"] = 2
    with pytest.raises(ValueError):
        fit_plan(bad)


def fake_context(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, int]]:
    import spireshift.native_prediction_separation as module

    source = root / "protected.txt"
    source.write_text("Original model and optimizer stand-in")
    cfg = {"workspace": "artifacts/outputs", "session_limits": {"wall_seconds": 240}}
    report = {
        "data_units": data(),
        "report_id": "sha256:" + "1" * 64,
        "parents": [],
        "full_run_objective": {"primary": "terminal_victory"},
        "training_spec_id": "sha256:" + "2" * 64,
    }
    tasks = [
        {"key": f"game-{n}-p2-original", "numerical_seed": 2, "variant": "original"}
        for n in range(3)
    ]
    context = {
        "config": cfg,
        "report": report,
        "tasks": tasks,
        "models": {(2, "original"): None, (3, "original"): None},
        "sources": {"protected.txt": _sha_file(source)},
    }
    monkeypatch.setattr(module, "load", lambda *_: context)
    calls = {"fits": 0, "cases": 0}

    def fit(_: Any, task: Any, directory: Path, *__: Any) -> Any:
        calls["fits"] += 1
        d = {"task": task, "curves": [{"step": 128}], "constant_baseline": {}}
        atomic_json(directory / "fit-report.json", {**d, "report_id": manifest_identifier(d)})
        return {"task": task, "report_path": str((directory / "fit-report.json").relative_to(root))}

    def case(_: Any, task: Any, *args: Any) -> Any:
        calls["cases"] += 1
        directory = args[2]
        atomic_json(directory / "numeric.json", {"current_public_inputs_only": True})
        return {
            "source_key": task["key"],
            "numerical_seed": 2,
            "source_variant": "original",
            "decisions": 2,
            "groups": {},
            "fitted_prediction_policy_logs_exactly_unchanged": True,
        }

    monkeypatch.setattr(module, "fit_unit", fit)
    monkeypatch.setattr(module, "restore", lambda *_: None)
    monkeypatch.setattr(module, "audit_case", case)
    return root / "recipe.json", calls


def test_saved_work_resumes_without_refitting_or_reprocessing_completed_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe, calls = fake_context(tmp_path, monkeypatch)
    a = run(tmp_path, recipe, max_cases=1)
    assert calls == {"fits": 9, "cases": 1} and a["ranking"]["episodes"] == 1
    b = run(tmp_path, recipe, max_cases=1)
    assert calls == {"fits": 9, "cases": 2} and b["ranking"]["episodes"] == 2
    c = run(tmp_path, recipe, max_cases=1)
    assert calls == {"fits": 9, "cases": 3} and c["ranking"]["episodes"] == 3
    assert not c["games_launched"] and not c["PPO_Adam_updates"]
    assert (tmp_path / "protected.txt").read_text() == "Original model and optimizer stand-in"
    assert not (tmp_path / "artifacts/outputs/report.json").exists()


def test_uncertain_uncommitted_saved_unit_is_preserved_not_silently_reprocessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_prediction_separation as module

    recipe, calls = fake_context(tmp_path, monkeypatch)

    def broken(*_: Any) -> Any:
        raise ValueError("Finite diagnostic failure")

    monkeypatch.setattr(module, "audit_case", broken)
    with pytest.raises(ValueError, match="Finite diagnostic"):
        run(tmp_path, recipe, max_cases=1)
    assert (tmp_path / "artifacts/outputs/chunks/rank-game-0-p2-original/active.json").exists()
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, recipe, max_cases=1)
    assert calls == {"fits": 9, "cases": 0}


def test_changed_prediction_source_or_completed_work_stops_before_new_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe, calls = fake_context(tmp_path, monkeypatch)
    run(tmp_path, recipe, max_cases=1)
    path = tmp_path / "artifacts/outputs/chunks/predictor-p2-w0/fit-report.json"
    path.write_text("altered")
    with pytest.raises(ValueError, match="evidence changed"):
        run(tmp_path, recipe, max_cases=1)
    assert calls == {"fits": 9, "cases": 1}


def test_invalid_case_cap_does_not_load_sources_or_launch_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import spireshift.native_prediction_separation as module

    def forbidden(*_: Any) -> Any:
        raise AssertionError("Invalid request progressed")

    monkeypatch.setattr(module, "load", forbidden)
    with pytest.raises(ValueError, match="positive"):
        run(tmp_path, tmp_path / "unused", max_cases=0)


def test_forced_and_singleton_menus_do_not_dilute_ranking_rates() -> None:
    from spireshift.native_action_rankings import compare

    row = {
        "group": "combat",
        "strategic_menu": True,
        "comparisons": {
            f"{a}_to_{b}": compare((2.0, 1.0), (1.0, 2.0))
            for a, b in (
                ("original", "return_only"),
                ("original", "consequence"),
                ("return_only", "consequence"),
            )
        },
    }
    result = summarize_rows([row, {**row, "strategic_menu": False}])
    assert result["combat"]["all_menus"] == 2 and result["combat"]["strategic_menus"] == 1
    assert result["combat"]["contrasts"]["original_to_return_only"]["greedy_changed"] == 1


def test_rank_aggregation_weights_games_equally_and_stratifies_source_paths() -> None:
    def case(origin: str, rate: float, count: int) -> Any:
        return {
            "numerical_seed": 2,
            "source_variant": origin,
            "decisions": count,
            "groups": {
                "combat": {
                    "strategic_menus": count,
                    "contrasts": {"x": {"greedy_changed": rate, "same_draw_choice_changed": None}},
                }
            },
        }

    result = aggregate(
        [case("original", 1.0, 100), case("original", 0.0, 1), case("consequence", 0.0, 20)]
    )
    own = next(c for c in result["cells"] if c["source_policy"] == "original")
    assert own["equal_game_mean"]["greedy_changed"] == 0.5
    assert own["games_with_eligible_menus"] == 2 and result["episodes"] == 3


def test_real_source_config_checks_the_immutable_implementation_contract_first(
    tmp_path: Path,
) -> None:
    from spireshift.native_separation_inputs import load

    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema_version": "unknown"}))
    with pytest.raises(ValueError, match="Freeze"):
        load(tmp_path, path)


def test_completed_cached_inspection_does_not_fit_or_reprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recipe, calls = fake_context(tmp_path, monkeypatch)
    cfg = {"workspace": "artifacts/outputs", "session_limits": {"wall_seconds": 240}}
    body = {
        "config_id": manifest_identifier(cfg),
        "sources": {"protected.txt": _sha_file(tmp_path / "protected.txt")},
        "status": "native_prediction_separation_complete",
        "games_launched": 0,
        "PPO_Adam_updates": 0,
    }
    atomic_json(
        tmp_path / "artifacts/outputs/report.json", {**body, "report_id": manifest_identifier(body)}
    )
    result = run(tmp_path, recipe)
    assert result["status"] == "native_prediction_separation_complete" and calls == {
        "fits": 0,
        "cases": 0,
    }


def test_saved_prediction_state_restores_own_optimizer_without_policy_state_conversion(
    tmp_path: Path,
) -> None:
    import time

    from test_native_action_context import model
    from test_native_consequence_math import split

    from spireshift.native_context_cache import cached_model
    from spireshift.native_outcome_predictor import fit_predictor
    from spireshift.native_prediction_separation import restore

    m = cached_model(model())
    f, h = split()
    p, optimizer, _ = fit_predictor(m, f, h, 0, time.monotonic() + 10)
    body = {
        "schema_version": "native-separated-prediction-state-v1",
        "predictor": p.as_dict(),
        "optimizer": optimizer,
    }
    path = tmp_path / "state.json"
    atomic_json(path, {**body, "state_id": manifest_identifier(body)})
    result = {"state_path": "state.json", "predictor_id": p.as_dict()["predictor_id"]}
    restored = restore(tmp_path, result, m)
    assert restored.player is m and restored.predictor == p
    changed = {**body, "optimizer": {**optimizer, "second": [-1.0] * p.parameter_count}}
    path.write_text(json.dumps({**changed, "state_id": manifest_identifier(changed)}))
    with pytest.raises(ValueError, match="optimizer state changed"):
        restore(tmp_path, result, m)
