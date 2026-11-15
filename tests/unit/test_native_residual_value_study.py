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
from spireshift.native_linear_value import INNER_FOLDS, REGULARIZATION, SALT, subset
from spireshift.native_linear_value_study import COHORTS
from spireshift.native_matched_value import parameter_digest
from spireshift.native_residual_value import METHOD, CorrectedValue, coarse_fit
from spireshift.native_residual_value_curves import curve_rows
from spireshift.native_residual_value_study import (
    PARENT_ID,
    PARENT_RECIPE,
    compare_fold,
    load_config,
    run,
    summarize,
    verify,
)


def fixture(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    values = data()
    mask = np.asarray([i % 4 != 0 for i in values.owners])
    baseline = coarse_fit(subset(values, mask))
    path = root / "cache"
    path.mkdir()
    np.savez_compressed(
        path / "encoded.npz",
        inputs=values.inputs,
        targets=values.targets,
        potential=values.base,
        owners=np.asarray(values.owners),
        fitting_mask=mask,
        ridge_base=values.base + values.inputs[:, :20] @ np.asarray(baseline.weights),
        ridge_weights=np.asarray(baseline.weights),
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
        "workspace": "artifacts/correction-test",
        "stage": "short_control",
        "regularization": list(REGULARIZATION),
        "inner_folds": INNER_FOLDS,
        "inner_salt": SALT,
        "resource_limits": {"wall_seconds": 240},
    }
    return cfg, unit


def test_cached_fold_preserves_weights_and_reconstructs_predictions(tmp_path: Path) -> None:
    cfg, unit = fixture(tmp_path)
    directory = tmp_path / "fit"
    directory.mkdir()
    result = compare_fold(tmp_path, unit, directory, cfg, time.monotonic() + 30)
    with (
        np.load(directory / "selected-model.npz") as arrays,
        np.load(directory / "held-predictions.npz") as saved,
        np.load(tmp_path / "cache/encoded.npz") as cache,
    ):
        model = CorrectedValue.restore({n: arrays[n] for n in arrays.files})
        mask = ~cache["fitting_mask"]
        assert np.array_equal(
            model.forecast(cache["inputs"][mask], cache["potential"][mask]), saved[METHOD]
        )
        assert np.array_equal(arrays["baseline_weights"], cache["ridge_weights"])
        assert parameter_digest(model.arrays()) == result["selected"]["parameter_digest"]
    assert len(curve_rows([result])) == 3 * (1 + 9)
    assert summarize([result])["unique_held_games"] == 8
    with pytest.raises(ValueError, match="counted twice"):
        summarize([result, result])


def test_corrupt_previous_baseline_is_refused_instead_of_training_on_it(tmp_path: Path) -> None:
    cfg, unit = fixture(tmp_path)
    path = tmp_path / "cache/encoded.npz"
    with np.load(path) as source:
        arrays = {k: source[k] for k in source.files}
    arrays["ridge_base"] += 1000
    np.savez_compressed(path, **arrays)
    directory = tmp_path / "fit"
    directory.mkdir()
    with pytest.raises(ValueError, match="forecasts differ"):
        compare_fold(tmp_path, unit, directory, cfg, time.monotonic() + 30)


def test_clean_resume_reuses_sealed_folds_and_source_corruption_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_residual_value_study as study

    cfg, unit = fixture(tmp_path)
    other = {**unit, "cohort": "another-cohort"}
    path = tmp_path / "cache/encoded.npz"
    sources = {"cache/encoded.npz": _sha_file(path)}
    monkeypatch.setattr(study, "prepare", lambda *a: (cfg, [unit, other], score(), sources.copy()))
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(cfg))
    assert run(tmp_path, recipe, preflight=True)["correction_solves"] == 0
    assert not (tmp_path / cfg["workspace"]).exists()
    first = run(tmp_path, recipe, maximum_units=1)
    assert first["status"] == "clean_pause" and first["completed_folds"] == 1
    original = study.compare_fold

    def refuse_first(*args: Any) -> dict[str, Any]:
        if args[1]["cohort"] == unit["cohort"]:
            pytest.fail("Never refit sealed work")
        return original(*args)

    monkeypatch.setattr(study, "compare_fold", refuse_first)
    final = run(tmp_path, recipe)
    assert final["status"] == "native_residual_value_complete"
    assert final["completed_folds"] == 2 and final["baseline_solves"] == 8
    assert final["production_states_unchanged"] and final["actor_optimizer_steps"] == 0
    assert run(tmp_path, recipe) == final
    certificate = verify(tmp_path, recipe)
    assert certificate["models_verified"] == 2 and certificate["new_fits"] == 0
    assert certificate["predictions_bitwise_reconstructed"]
    path.write_bytes(b"corruption")
    with pytest.raises(ValueError, match="changed"):
        run(tmp_path, recipe)


def test_interrupted_fold_is_retained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from spireshift import native_residual_value_study as study

    cfg, unit = fixture(tmp_path)
    monkeypatch.setattr(study, "prepare", lambda *a: (cfg, [unit], score(), {}))
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(cfg))
    target = tmp_path / cfg["workspace"] / "chunks/test-cohort-fold-0-correction"
    target.mkdir(parents=True)
    (target / "keep").write_text("failed evidence")
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, recipe)
    assert (target / "keep").read_text() == "failed evidence"


@pytest.mark.parametrize("fault", ["none", "source", "entry", "grid", "baseline", "off", "scope"])
def test_config_freezes_baseline_off_candidate_and_separate_grid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from spireshift import native_residual_value_study as study

    source, entry = tmp_path / "src/spireshift/test.py", tmp_path / "scripts/test.sh"
    source.parent.mkdir(parents=True)
    entry.parent.mkdir()
    source.write_text("source")
    entry.write_text("entry")
    monkeypatch.setattr(study, "SOURCES", (source.name,))
    monkeypatch.setattr(study, "ENTRIES", (entry.name,))
    cfg = {
        "schema_version": "native-residual-value-config-v1",
        "stage": "short_control",
        "regularization": list(REGULARIZATION),
        "coarse_regularization": 0.001,
        "no_correction_candidate": True,
        "correction_intercept": 0.0,
        "inner_folds": INNER_FOLDS,
        "inner_salt": SALT,
        "cohorts": COHORTS[:1],
        "outer_folds": [0],
        "parent_comparison": {"id": PARENT_ID},
        "parent_recipe": PARENT_RECIPE,
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
    elif fault == "baseline":
        cfg["coarse_regularization"] = 0.1
    elif fault == "off":
        cfg["no_correction_candidate"] = False
    elif fault == "scope":
        cfg["outer_folds"] = [0, 1]
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(cfg))
    if fault == "none":
        assert load_config(tmp_path, path) == cfg
    else:
        with pytest.raises(ValueError, match="Freeze"):
            load_config(tmp_path, path)
