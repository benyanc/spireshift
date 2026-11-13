from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_native_action_context import score
from test_native_public_value_study import cases

from spireshift.engine_qualification import _sha_file
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_matched_value import CURVE_STEPS, INITIALIZERS, SETTINGS
from spireshift.native_matched_value_curves import aggregate_curves, curve_rows, write_curves
from spireshift.native_matched_value_study import (
    compare_pair,
    encode_fold,
    load_config,
    run,
    summarize,
)
from spireshift.native_public_value import forward, game_weights


def config() -> dict[str, Any]:
    return {
        "workspace": "artifacts/test-matched",
        "stage": "short_control",
        "folds": 2,
        "maximum_vocabulary": 1024,
        "fit": SETTINGS,
        "curve_steps": list(CURVE_STEPS),
        "resource_limits": {"wall_seconds": 240},
    }


def one_pair(root: Path) -> dict[str, Any]:
    cohort = cases(root)
    encoded, fitted = root / "encoded", root / "fitted"
    encoded.mkdir()
    fitted.mkdir()
    result = encode_fold(root, cohort, score(), 0, config(), encoded, time.monotonic() + 10)
    with np.load(encoded / "encoded.npz", allow_pickle=False) as saved:
        mask = saved["fitting_mask"]
        assert len(set(saved["owners"][mask]) & set(saved["owners"][~mask])) == 0
    pair = compare_pair(
        encoded / "encoded.npz", fitted, config(), INITIALIZERS[0], time.monotonic() + 10
    )
    assert result["coverage"]["vocabulary_fit_uses_held_games"] is False
    return {"cohort": cohort["key"], "fold": 0, **pair}


def test_cached_fold_and_pure_error_curve_artifacts(tmp_path: Path) -> None:
    result = one_pair(tmp_path)
    assert result["fit"]["identical_initial_parameters_and_moments"]
    assert result["held"]["clipped"]["games"] == 4
    assert result["primary_step"] == 24
    arrays = np.load(tmp_path / "fitted/held-predictions.npz", allow_pickle=False)
    assert set(arrays["owners"].tolist()) == set(result["fit"]["held_games"])
    assert "rich_step_24" in arrays and "rich_step_96" in arrays
    summary = summarize([result])
    assert (
        summary["unique_held_games"] == summary["held_forecasts_including_numerical_repeats"] == 4
    )
    assert not summary["stronger_native_play_established"]
    assert summary["curve_snapshots_are_not_epoch_selection"]
    assert len(curve_rows([result])) == 16
    curves = aggregate_curves([result])
    assert [p["step"] for p in curves["rich"]] == list(CURVE_STEPS)
    files = write_curves(tmp_path, [result], False)
    assert [f.name for f in files] == ["progress-curves.csv", "progress-curves.png"]
    assert files[1].read_bytes().startswith(b"\x89PNG")


def test_numerical_repeats_are_not_counted_as_more_games(tmp_path: Path) -> None:
    first = one_pair(tmp_path)
    second = json.loads(json.dumps(first))
    second["fit"]["network_initializer"] = INITIALIZERS[1]
    summary = summarize([first, second])
    assert summary["unique_held_games"] == 4
    assert summary["held_forecasts_including_numerical_repeats"] == 8
    assert (
        summary["primary_equal_game_clipped_mse"]
        == summarize([first])["primary_equal_game_clipped_mse"]
    )


def test_saved_primary_weights_reconstruct_prediction_and_separate_loss_terms(
    tmp_path: Path,
) -> None:
    result = one_pair(tmp_path)
    with np.load(tmp_path / "encoded/encoded.npz", allow_pickle=False) as data:
        values = {k: data[k] for k in data.files}
    for arm in ("coarse_masked", "rich"):
        with np.load(tmp_path / f"fitted/{arm}-final.npz", allow_pickle=False) as saved:
            primary = {k: saved[f"primary_{k}"] for k in ("input", "bias", "output", "intercept")}
            z = np.clip((values["inputs"] - saved["mean"]) / saved["scale"], -4, 4)
            predicted = values["ridge_base"] + forward(primary, z * saved["input_mask"])
        mask = values["fitting_mask"]
        owners = values["owners"][mask].tolist()
        weights = np.asarray(game_weights(owners))
        expected_error = float(weights @ np.square(predicted[mask] - values["targets"][mask]))
        expected_penalty = SETTINGS["l2"] * sum(
            float(np.square(primary[k]).sum()) for k in ("input", "output")
        )
        point = next(p for p in result["fit"]["arms"][arm]["curve"] if p["step"] == 24)
        assert point["fitting_mse"] == pytest.approx(expected_error)
        assert point["weight_penalty"] == pytest.approx(expected_penalty)
        with np.load(tmp_path / "fitted/held-predictions.npz", allow_pickle=False) as held:
            assert np.array_equal(predicted[~mask], held[f"{arm}_step_24"])


def test_restart_reuses_encoded_arrays_and_completed_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from spireshift import native_matched_value_study as study

    cohort = cases(tmp_path)
    cfg = config()
    monkeypatch.setattr(study, "prepare", lambda root, path: (cfg, [cohort], score(), {}))
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(cfg))
    preflight = run(tmp_path, path, preflight=True)
    assert preflight["numerical_fits"] == 0
    assert not (tmp_path / cfg["workspace"]).exists()
    first = run(tmp_path, path, maximum_units=2)
    assert first["status"] == "clean_pause" and first["completed_fits"] == 1
    encoded = ChunkJournal(tmp_path, cfg).path(cohort["key"] + "-fold-0-encode") / "encoded.npz"
    before = encoded.read_bytes()
    encode_original = study.encode_fold

    def refuse_same_encoding(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if args[3] == 0:
            raise AssertionError("Already sealed fold must not be encoded again")
        return encode_original(*args, **kwargs)

    monkeypatch.setattr(study, "encode_fold", refuse_same_encoding)
    second = run(tmp_path, path, maximum_units=2)
    assert second["completed_fits"] == 3 and encoded.read_bytes() == before
    final = run(tmp_path, path)
    assert final["status"] == "native_matched_value_complete"
    assert final["completed_fits"] == 6 and final["summary"]["unique_held_games"] == 8
    assert final["actor_optimizer_steps"] == 0 and final["production_states_unchanged"]
    monkeypatch.setattr(study, "compare_pair", lambda *a, **k: pytest.fail("No repeated fit"))
    assert run(tmp_path, path) == final
    encoded.write_bytes(b"changed saved cache")
    with pytest.raises(ValueError, match="changed"):
        run(tmp_path, path)


def test_uncommitted_pair_is_preserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from spireshift import native_matched_value_study as study

    cohort = cases(tmp_path)
    cfg = config()
    monkeypatch.setattr(study, "prepare", lambda root, path: (cfg, [cohort], score(), {}))
    path = tmp_path / "recipe.json"
    path.write_text(json.dumps(cfg))
    run(tmp_path, path, maximum_units=1)
    store = ChunkJournal(tmp_path, cfg)
    interrupted = store.path(cohort["key"] + f"-fold-0-init-{INITIALIZERS[0]}")
    interrupted.mkdir()
    marker = interrupted / "owned-evidence.txt"
    marker.write_text("keep this")
    with pytest.raises(FileExistsError, match="uncommitted"):
        run(tmp_path, path)
    assert marker.read_text() == "keep this"


@pytest.mark.parametrize("fault", ["none", "source", "entry", "step", "initializers", "scope"])
def test_recipe_rejects_changed_source_schedule_and_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    from spireshift import native_matched_value_study as study

    source = tmp_path / "src/spireshift/example.py"
    entry = tmp_path / "scripts/example.sh"
    source.parent.mkdir(parents=True)
    entry.parent.mkdir()
    source.write_text("frozen implementation")
    entry.write_text("frozen entry")
    monkeypatch.setattr(study, "SOURCES", (source.name,))
    monkeypatch.setattr(study, "ENTRIES", (entry.name,))
    cfg = {
        **config(),
        "schema_version": "native-matched-input-value-config-v1",
        "primary_step": 24,
        "network_initializers": list(INITIALIZERS),
        "games_per_cohort": 8,
        "cohorts": ["seed-2-standard-round-057-fit"],
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
        (source if fault == "source" else entry).write_text("changed bytes")
    elif fault == "step":
        cfg["primary_step"] = 96
    elif fault == "initializers":
        cfg["network_initializers"] = [9]
    elif fault == "scope":
        cfg["games_per_cohort"] = 32
    recipe = tmp_path / "recipe.json"
    recipe.write_text(json.dumps(cfg))
    if fault == "none":
        assert load_config(tmp_path, recipe) == cfg
    else:
        with pytest.raises(ValueError, match="Freeze"):
            load_config(tmp_path, recipe)
