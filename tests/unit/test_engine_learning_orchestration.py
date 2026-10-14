"""Exercise the entire finite pilot with a tiny synthetic worker, without a game."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_engine_neural import public, settings

import spireshift.engine_learning as learning
from spireshift.engine_qualification import EngineQualificationConfig
from spireshift.training_objective import load_training_score_spec


def test_progress_best_game_is_one_real_game_and_prioritizes_a_full_win() -> None:
    cases = [
        {
            "status": "terminal",
            "victory": victory,
            "completed_acts": acts,
            "maximum_floor": floor,
            "decisions": [],
            "cpu_seconds": 0.1,
        }
        for victory, acts, floor in ((False, 1, 90), (True, 3, 52), (False, 2, 70))
    ]
    summary = learning.summarize(cases, 3)
    assert summary["best_victory"] is True
    assert (summary["best_floor"], summary["best_completed_acts"]) == (52, 3)


def test_pilot_freezes_selection_before_independent_development(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This is an orchestration fixture, never environment qualification or playing evidence.
    score_path = Path(
        "configs/training-objective/sts2-v0.111.0-ironclad-a8-native-bootstrap-v1.json"
    )
    score_document = json.loads(score_path.read_text())
    (tmp_path / "score.json").write_text(json.dumps(score_document))
    score = load_training_score_spec(tmp_path / "score.json")
    q = EngineQualificationConfig(document={}, root=tmp_path)
    cfg: dict[str, Any] = {
        "stage": "bounded_policy_only_pilot",
        "workspace": "artifacts/pilot-fixture",
        "worker_qualification_config": "workers.json",
        "training_spec": {"path": "score.json"},
        "seed_manifest": {"path": "seeds.json", "id": "synthetic-seeds"},
        "environment_manifest": {"id": score.scope.ruleset_manifest_id},
        "helpers_sha256": {},
        "implementation_sha256": {},
        "worker_report": {"id": "synthetic-workers"},
        "network": {"dimension": 128, "hidden_units": 4, "seed": 0},
        "maximum_wall_seconds": 1800,
        "maximum_decisions": 10,
        "episode_wall_seconds": 60,
        "workers": 2,
        "learning": {
            "rollout_panels": [list(range(i * 32 + 1, (i + 1) * 32 + 1)) for i in range(8)],
            "confirmation_seeds": list(range(501, 517)),
            "development_seeds": list(range(601, 617)),
            "confirmation_every": 4,
            "sampling_seed": 1,
            "ppo": {**settings(), "epochs": 1},
        },
    }
    seeds = {
        "seeds": [
            {"id": i, "seed": f"{prefix}{i}", "partition": part}
            for prefix, part, ids in (
                ("TRN", "train", range(1, 257)),
                ("CNF", "confirmation", range(501, 517)),
                ("DEV", "development", range(601, 617)),
            )
            for i in ids
        ]
    }
    launched: list[str] = []
    root = tmp_path / cfg["workspace"]
    for name in learning.IMPLEMENTATION:
        p = tmp_path / "src/spireshift" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("synthetic source placeholder")

    class Worker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.workspace: Path = args[2]
            self.workspace.mkdir()
            self.closed = False

        def episode(self, seed: str, **kwargs: Any) -> dict[str, Any]:
            launched.append(seed)
            if seed.startswith("DEV"):
                assert (root / "selection-freeze.json").is_file()
                assert (root / "selected-checkpoint.json").is_file()
            visible = public()
            return {
                "status": "terminal",
                "seed": seed,
                "victory": False,
                "privileged_fixture": False,
                "recovered": False,
                "native_ending_evidence_agrees": True,
                "completed_acts": 0,
                "maximum_floor": int(seed[3:]) % 9 + 1,
                "cpu_seconds": 0.01,
                "decisions": [
                    {
                        "public_input": visible,
                        "public_key": "synthetic",
                        "choice": kwargs["chooser"](visible),
                    }
                ],
            }

        def close(self) -> None:
            self.closed = True

        def stop(self) -> None:
            self.closed = True

    monkeypatch.setattr(learning, "_require_native_launch_support", lambda: None)
    monkeypatch.setattr(learning, "_running_games", lambda: [])
    monkeypatch.setattr(learning, "load_learning_config", lambda *a: cfg)
    monkeypatch.setattr(learning, "load_worker_config", lambda *a: {"base_run_recipe": "unused"})
    monkeypatch.setattr(
        learning, "_run_inputs", lambda *a: {"objective": score.evaluation_objective.as_dict()}
    )
    monkeypatch.setattr(learning, "identified", lambda *a: seeds)
    monkeypatch.setattr(learning, "_shared_snapshot", lambda *a: {})
    monkeypatch.setattr(learning, "immutable_checks", lambda *a: {"synthetic_only": True})
    monkeypatch.setattr(learning, "audit_worker_experience", lambda *a: {"synthetic_only": True})
    monkeypatch.setattr(learning, "EngineWorker", Worker)
    result = learning.run_neural_experiment(q, tmp_path / "unused.json", node=score_path)
    assert result["status"] == "bounded_pilot_complete"
    assert result["planned_games"] == result["recorded_games"] == len(launched) == 336
    assert result["sampled_decisions_verified"] == 256
    assert result["completed_games"] == 336 and result["failed_games"] == 0
    assert len(result["rounds"]) == 8 and result["adaptive_controller_allowed"] is False
    freeze = json.loads((root / "selection-freeze.json").read_text())
    assert freeze["development_opened"] is False
    assert freeze["model_id"] == result["selected_model_id"]
    assert result["panels"][-1]["model_id"] == result["selected_model_id"]
    assert result["panels"][-2]["model_id"] == result["initial_model_id"]
    assert result["panels"][-2]["panel"] == "development-initial"
    assert result["panels"][-1]["panel"] == "development-selected"
