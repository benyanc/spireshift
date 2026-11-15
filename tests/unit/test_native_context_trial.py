from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path
from typing import Any

import pytest
from test_native_action_context import model, score, settings

import spireshift.native_context_trial as trial
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_experience import save_native_episode
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.native_action_context import CROSSED, ORIGINAL
from spireshift.native_conditional_control import TASK
from spireshift.native_context_game import predict, verified_samples
from spireshift.native_learning_control import public_input


def case(seed: str, chooser: Any) -> dict[str, Any]:
    p = public_input(TASK, seed.endswith("2"))
    return {
        "status": "terminal",
        "seed": seed,
        "privileged_fixture": False,
        "recovered": False,
        "native_ending_evidence_agrees": True,
        "victory": False,
        "completed_acts": 0,
        "maximum_floor": 2 if seed.endswith("2") else 7,
        "cpu_seconds": 0.01,
        "decisions": [{"public_input": p, "choice": chooser(p)}],
    }


@pytest.mark.parametrize(
    "fault", ["greedy", "probability", "model", "recovered", "fixture", "partial", "input"]
)
def test_changed_or_unfit_experience_cannot_supply_context_targets(fault: str) -> None:
    m, spec = model(), score()
    c = case("TRAIN1", lambda p: predict(m, spec, p, random.Random(1), 0.8))
    assert len(verified_samples(c, m, spec, 0.1, 0.8)) == 1
    if fault == "greedy":
        c["decisions"][0]["choice"]["behavior"] = "greedy"
    elif fault == "probability":
        c["decisions"][0]["choice"]["log_probability"] += 0.01
    elif fault == "model":
        c["decisions"][0]["choice"]["model_id"] = model(ORIGINAL).model_id
    elif fault == "recovered":
        c["recovered"] = True
    elif fault == "fixture":
        c["privileged_fixture"] = True
    elif fault == "partial":
        c["status"] = "failed"
    else:
        c["decisions"][0]["public_input"]["candidates"].reverse()
    with pytest.raises(ValueError):
        verified_samples(c, m, spec, 0.1, 0.8)


def test_streamed_credit_uses_other_whole_games_and_keeps_behavior_exact(tmp_path: Path) -> None:
    m, spec, paths = model(), score(), []
    credit = {
        "baseline": "public_residual_ridge",
        "regularization": 0.001,
        "folds": 4,
        "fold_salt": "native-whole-run-value-crossfit-v1",
    }
    for i in (1, 2):
        c = case(f"TRAIN{i}", lambda p, seed=i: predict(m, spec, p, random.Random(seed), 0.8))
        path = tmp_path / f"case-{i}.json"
        save_native_episode(
            path,
            c,
            {
                "partition": "train",
                "panel_purpose": "training",
                "model_id": m.model_id,
                "seed_id": i,
            },
        )
        paths.append(path)
    samples, report = trial.prepare(paths, m, spec, settings(), credit, 1)
    assert len(samples) == 2 and report["no_self_outcome_fitting"]
    assert report["oracle_labels"] == 0 and not report["hand_written_HP_rewards"]
    assert report["clean_complete_training_games"] == 2
    # Different end results do not alter the behavior probabilities reconstructed earlier.
    for path, sample in zip(paths, samples, strict=True):
        import gzip

        with gzip.open(path.with_suffix(".jsonl.gz"), "rt") as stream:
            choice = json.loads(next(stream))["choice"]
        assert sample.old_log_probability == choice["log_probability"]
    header = json.loads(paths[0].read_text())
    header["binding"]["partition"] = "development"
    paths[0].write_text(json.dumps(header))
    with pytest.raises(ValueError, match="Evaluation or stale"):
        trial.prepare(paths, m, spec, settings(), credit, 1)


def plan(short: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    cfg: dict[str, Any] = {
        "schema_version": "native-action-context-trial-config-v1",
        "stage": trial.STAGES[0 if short else 1],
        "modes": [ORIGINAL, CROSSED],
        "training_seeds": [0] if short else [0, 1],
        "rounds": 1 if short else 4,
        "games_per_round": 2 if short else 32,
        "evaluation_games": 2 if short else 16,
        "initializer": "common_zero_hidden_output_no_frozen_layers_v1",
        "checkpoint_selection": "final_only",
        "resource_limits": {
            "wall_seconds": 180 if short else 3600,
            "cpu_seconds": 360 if short else 7200,
            "resident_memory_bytes": 4000000000,
            "storage_bytes": 1000000000 if short else 6000000000,
        },
    }
    rows = [
        {"id": i, "seed": f"TRAIN{i}", "partition": "control" if short else "train"}
        for i in range(len(cfg["training_seeds"]) * cfg["rounds"] * cfg["games_per_round"])
    ]
    rows += [
        {
            "id": 1000 + i,
            "seed": f"EVAL{i}",
            "partition": "control_eval" if short else "development",
        }
        for i in range(len(cfg["training_seeds"]) * cfg["evaluation_games"])
    ]
    return cfg, {"seeds": rows}


@pytest.mark.parametrize("short", [True, False])
def test_plan_cannot_silently_expand_change_treatment_or_cross_seed_ownership(short: bool) -> None:
    cfg, seeds = plan(short)
    trial.validate_plan(cfg, seeds)
    for field in ("rounds", "initializer", "resource_limits", "modes", "checkpoint_selection"):
        changed = {**cfg, field: None}
        with pytest.raises(ValueError):
            trial.validate_plan(changed, seeds)
    repeated = copy.deepcopy(seeds)
    repeated["seeds"][1]["seed"] = repeated["seeds"][0]["seed"]
    with pytest.raises(ValueError):
        trial.validate_plan(cfg, repeated)


@pytest.mark.parametrize("fault", ["none", "failed_game", "retirement", "audit"])
def test_panel_streams_and_preserves_failed_games_without_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    q = EngineQualificationConfig(document={}, root=tmp_path)
    cfg, _ = plan(False)
    parent = {
        "maximum_decisions": 10,
        "episode_wall_seconds": 60,
        "helpers_sha256": {},
        "worker_script": "engine-native-worker-v9.mjs",
        "environment_manifest": {"id": score().scope.ruleset_manifest_id},
        "learning": {"ppo": settings()},
    }
    cfg["seed_manifest"] = {"id": "synthetic"}
    rows = [{"id": i, "seed": f"TRAIN{i}", "partition": "train"} for i in range(1, 5)]
    launched: list[str] = []
    audits: list[int] = []
    stopped: list[Path] = []

    class Worker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.workspace: Path = args[2]
            self.workspace.mkdir()
            self.closed = False

        def episode(self, seed: str, **kwargs: Any) -> dict[str, Any]:
            launched.append(seed)
            c = case(seed, kwargs["chooser"])
            if seed == "TRAIN1" and fault in {"failed_game", "retirement"}:
                c.update(status="failed", error="synthetic stuck state")
            return c

        def close(self) -> None:
            self.closed = True

        def stop(self) -> None:
            stopped.append(self.workspace)
            self.closed = True

        def retire(self, reason: str) -> None:
            if fault == "retirement":
                raise ValueError("Unverified shutdown")
            self.closed = True
            stopped.append(self.workspace)
            (self.workspace / "retired.json").write_text(reason)

    def audit(workspace: Path, paths: list[Path], **_: Any) -> dict[str, Any]:
        audits.append(len(paths))
        if fault == "audit":
            raise ValueError("Synthetic evidence mismatch")
        body = {"source_sha256": {}, "cases": len(paths)}
        return {**body, "report_id": manifest_identifier(body)}

    monkeypatch.setattr(trial, "EngineWorker", Worker)
    monkeypatch.setattr(trial, "audit_worker_streaming", audit)
    args: tuple[Any, ...] = (
        q,
        cfg,
        parent,
        {},
        rows,
        tmp_path / "node",
        tmp_path / "panel",
        model(),
        score(),
        0,
        "round-001",
        True,
        time.monotonic() + 20,
    )
    if fault in {"retirement", "audit"}:
        with pytest.raises(ValueError, match="unauditable"):
            trial.collect_panel(*args)
        assert list((tmp_path / "panel").glob("worker-*-failure.json"))
    else:
        paths, summary, seals = trial.collect_panel(*args)
        assert len(paths) == 4 and summary["not_attempted_games"] == 0
        assert summary["failed_games"] == int(fault == "failed_game")
        assert len(audits) == (3 if fault == "failed_game" else 2)
        assert seals and summary["decisions"] == 4
        assert len(stopped) >= 2
        assert sorted(launched) == ["TRAIN1", "TRAIN2", "TRAIN3", "TRAIN4"]
    assert launched.count("TRAIN1") == 1
    assert (tmp_path / "panel/case-1.json").is_file()
