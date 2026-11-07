from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_native_action_context import score
from test_native_rest_exploration import rest

from spireshift.engine_experience import save_native_episode
from spireshift.native_public_value_study import (
    SETTINGS,
    compare_fold,
    dataset,
    observations,
    summarize,
)


def cases(root: Path) -> dict[str, Any]:
    paths = []
    for i in range(8):
        p = rest()
        p["context"]["persistent"]["player"]["relics"] = [{"definition_id": f"RELIC_{i}"}]
        source = root / f"case-{i}.json"
        save_native_episode(
            source,
            {
                "status": "terminal",
                "native_ending_evidence_agrees": True,
                "privileged_fixture": False,
                "recovered": False,
                "victory": False,
                "completed_acts": 0,
                "maximum_floor": i + 2,
                "cpu_seconds": 0.01,
                "decisions": [{"public_input": p, "choice": {"action_index": 0}}],
            },
            {"partition": "train", "panel_purpose": "training", "seed_id": i},
        )
        paths.append(source.name)
    return {"key": "synthetic-cohort", "round": 57, "numerical_seed": 2, "paths": paths}


def test_held_games_never_fit_the_vocabulary_or_coarse_reference(tmp_path: Path) -> None:
    cohort = cases(tmp_path)
    x, coarse, phi, y, owners, runs, vocabulary, coverage = dataset(
        tmp_path, cohort, score(), 0, 2, 1024, time.monotonic() + 10
    )
    assert len(runs) == 8 and len(x) == len(coarse) == len(phi) == len(y) == len(owners) == 8
    assert not (set(coverage["fitting_games"]) & set(coverage["held_games"]))
    for seed in coverage["held_games"]:
        assert not any(f'"RELIC_{seed}"' in name for name in vocabulary.names)
    directory = tmp_path / "result"
    directory.mkdir()
    result = compare_fold(
        tmp_path,
        cohort,
        score(),
        0,
        {"folds": 2, "maximum_vocabulary": 1024, "fit": SETTINGS},
        directory,
        time.monotonic() + 10,
    )
    assert set(result["ridge"]["fitting_runs"]) == set(coverage["fitting_games"])
    assert (
        result["held"]["games"] == 4
        and result["actor_optimizer_steps"] == result["native_games"] == 0
    )
    saved = np.load(directory / "held-predictions.npz", allow_pickle=False)
    assert set(saved["owners"].tolist()) == set(coverage["held_games"])
    summary = summarize([result])
    assert summary["held_game_predictions"] == 4 and not summary["automatic_training_follows"]
    assert not summary["stronger_native_play_established"]


@pytest.mark.parametrize("fault", ["partition", "partial", "recovered", "privileged", "trace"])
def test_study_refuses_non_train_partial_or_changed_evidence(tmp_path: Path, fault: str) -> None:
    cohort = cases(tmp_path)
    path = tmp_path / cohort["paths"][0]
    header = json.loads(path.read_text())
    if fault == "partition":
        header["binding"]["partition"] = "test"
    elif fault == "partial":
        header["episode"]["status"] = "failed"
    elif fault in {"recovered", "privileged"}:
        header["episode"]["recovered" if fault == "recovered" else "privileged_fixture"] = True
    else:
        path.with_suffix(".jsonl.gz").write_bytes(b"changed")
    if fault != "trace":
        from spireshift.core.manifest import manifest_identifier

        body = {k: v for k, v in header.items() if k not in {"case_id", "trace_file_sha256"}}
        header["case_id"] = manifest_identifier(body)
        path.write_text(json.dumps(header))
    with pytest.raises(ValueError):
        list(observations(tmp_path, cohort["paths"][0], score()))


def test_unselected_actions_are_inputs_but_selected_action_is_not(tmp_path: Path) -> None:
    cohort = cases(tmp_path)
    result = list(observations(tmp_path, cohort["paths"][0], score()))
    public = result[0][2]
    assert {c["label"] for c in public["candidates"]} == {"Rest", "Smith", "Leave rest site"}
    before = copy.deepcopy(public)
    assert "choice" not in public and public == before
