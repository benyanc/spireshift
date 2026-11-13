from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_native_action_context import score
from test_native_linear_value import data

from spireshift.engine_qualification import _sha_file
from spireshift.native_linear_value import INNER_FOLDS, REGULARIZATION, SALT
from spireshift.native_linear_value_curves import curve_rows
from spireshift.native_linear_value_study import (
    COHORTS,
    PARENT_ID,
    compare_fold,
    load_config,
    run,
    summarize,
)


def fixture(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    values = data()
    mask = np.asarray([i % 4 != 0 for i in values.owners])
    path = root / "cache"
    path.mkdir()
    np.savez_compressed(
        path / "encoded.npz",
        inputs=values.inputs,
        targets=values.targets,
        potential=values.base,
        owners=np.asarray(values.owners),
        fitting_mask=mask,
        ridge_base=np.zeros(len(mask)),
        constant=np.full(len(mask), 0.4),
    )
    unit = {
        "cohort": "test-cohort",
        "fold": 0,
        "encoded": "cache",
        "encoding_report_id": "sha256:test",
        "fitting_games": sorted(set(np.asarray(values.owners)[mask].tolist())),
        "held_games": sorted(set(np.asarray(values.owners)[~mask].tolist())),
    }
    cfg = {
        "workspace": "artifacts/linear-test",
        "stage": "short_control",
        "regularization": list(REGULARIZATION),
        "inner_folds": INNER_FOLDS,
        "inner_salt": SALT,
        "resource_limits": {"wall_seconds": 240},
    }
    return cfg, unit


def test_cached_fold_reconstructs_predictions_and_ignores_fitted_outer_offset(
    tmp_path: Path,
) -> None:
    cfg, unit = fixture(tmp_path)
    directory = tmp_path / "fit"
    directory.mkdir()
    result = compare_fold(tmp_path, unit, directory, cfg, time.monotonic() + 30)
    with (
        np.load(tmp_path / "cache/encoded.npz") as cached,
        np.load(directory / "held-predictions.npz") as saved,
    ):
        for arm in ("coarse_linear", "rich_linear"):
            with np.load(directory / (arm + ".npz")) as model:
                z = (
                    np.clip((cached["inputs"] - model["mean"]) / model["scale"], -4, 4)
                    - model["center"]
                )
                predictions = cached["potential"] + (
                    model["intercept"][0] + z @ model["coefficients"]
                )
                assert np.array_equal(predictions[~cached["fitting_mask"]], saved[arm])
    assert len(curve_rows([result])) == 2 * 3 * 9
    assert summarize([result])["unique_held_games"] == 8
    assert summarize([result])["independent_training_players"] == 1
    with pytest.raises(ValueError, match="counted twice"):
        summarize([result, result])
    # A poisoned previous ridge can change its comparator score, not fitted coefficients.
    with np.load(tmp_path / "cache/encoded.npz") as source:
        arrays = {k: source[k] for k in source.files}
    arrays["ridge_base"] = np.full(len(arrays["targets"]), 12345.0)
    np.savez_compressed(tmp_path / "cache/encoded.npz", **arrays)
    other = tmp_path / "other"
    other.mkdir()
    changed = compare_fold(tmp_path, unit, other, cfg, time.monotonic() + 30)
    assert changed["selected"] == result["selected"]
    assert changed["inner"] == result["inner"]


def test_restart_reuses_sealed_fits_and_detects_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_linear_value_study as study

    cfg, unit = fixture(tmp_path)
    second = {**unit, "cohort": "another-cohort"}
    source = tmp_path / "cache/encoded.npz"
    protected = {"cache/encoded.npz": _sha_file(source)}
    monkeypatch.setattr(
        study, "prepare", lambda *a: (cfg, [unit, second], score(), protected.copy())
    )
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(cfg))
    assert run(tmp_path, recipe, preflight=True)["linear_solves"] == 0
    assert not (tmp_path / cfg["workspace"]).exists()
    first = run(tmp_path, recipe, maximum_units=1)
    assert first["status"] == "clean_pause" and first["completed_folds"] == 1
    original = study.compare_fold

    def refuse_first(*args: Any) -> dict[str, Any]:
        if args[1]["cohort"] == unit["cohort"]:
            pytest.fail("Do not refit sealed work")
        return original(*args)

    monkeypatch.setattr(study, "compare_fold", refuse_first)
    final = run(tmp_path, recipe)
    assert final["status"] == "native_linear_value_complete"
    assert final["completed_folds"] == 2 and final["actor_optimizer_steps"] == 0
    assert final["production_states_unchanged"]
    assert run(tmp_path, recipe) == final
    source.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        run(tmp_path, recipe)


def test_uncommitted_fit_is_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from spireshift import native_linear_value_study as study

    cfg, unit = fixture(tmp_path)
    monkeypatch.setattr(study, "prepare", lambda *a: (cfg, [unit], score(), {}))
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(cfg))
    directory = tmp_path / cfg["workspace"] / "chunks/test-cohort-fold-0-linear"
    directory.mkdir(parents=True)
    marker = directory / "keep.txt"
    marker.write_text("interrupted evidence")
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, recipe)
    assert marker.read_text() == "interrupted evidence"


@pytest.mark.parametrize("fault", ["none", "source", "entry", "grid", "folds", "scope"])
def test_recipe_freezes_grid_source_and_whole_game_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from spireshift import native_linear_value_study as study

    source, entry = tmp_path / "src/spireshift/example.py", tmp_path / "scripts/example.sh"
    source.parent.mkdir(parents=True)
    entry.parent.mkdir()
    source.write_text("source")
    entry.write_text("entry")
    monkeypatch.setattr(study, "SOURCES", (source.name,))
    monkeypatch.setattr(study, "ENTRIES", (entry.name,))
    cfg = {
        "schema_version": "native-linear-value-config-v1",
        "stage": "short_control",
        "regularization": list(REGULARIZATION),
        "inner_folds": INNER_FOLDS,
        "inner_salt": SALT,
        "cohorts": COHORTS[:1],
        "outer_folds": [0],
        "parent_comparison": {"id": PARENT_ID},
        "implementation_sha256": {source.name: _sha_file(source)},
        "entry_sha256": {entry.name: _sha_file(entry)},
        "resource_limits": {
            "wall_seconds": 240,
            "cpu_seconds": 240,
            "resident_memory_bytes": 2000000000,
            "storage_bytes": 500000000,
        },
    }
    if fault in {"source", "entry"}:
        (source if fault == "source" else entry).write_text("changed")
    elif fault == "grid":
        cfg["regularization"] = [0.001]
    elif fault == "folds":
        cfg["inner_folds"] = 2
    elif fault == "scope":
        cfg["outer_folds"] = [0, 1]
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(cfg))
    if fault == "none":
        assert load_config(tmp_path, path) == cfg
    else:
        with pytest.raises(ValueError, match="Freeze"):
            load_config(tmp_path, path)
