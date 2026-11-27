from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from test_full_run_ppo import small_config

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo import PPOConfig
from spireshift.full_run_ppo_progress import ProgressOutput, RoundProgress, main
from spireshift.training_objective import RunStatus


def save_outcome(
    root: Path,
    config: PPOConfig,
    round_index: int,
    seed_index: int,
    floor: int,
    acts: int = 0,
    status: RunStatus = RunStatus.LOSS,
    *,
    behavior: str = "sampled_softmax",
    sampling_seed: int | None = None,
    filename: str = "case.json",
) -> Path:
    learning = config.document["learning"]
    seed = learning["rollout_seed_panels"][round_index][seed_index]
    if sampling_seed is None:
        sampling_seed = int.from_bytes(
            hashlib.sha256(
                f"{learning['sampling_rng_seed']}|{round_index}|{seed}".encode()
            ).digest()[:8],
            "big",
        )
    binding = {
        "seed": seed,
        "model_id": f"player-{round_index}",
        "behavior": behavior,
        "sampling_seed": sampling_seed,
        "partition": "train",
        "ruleset_manifest_id": config.ruleset.manifest_id,
        "split_manifest_id": config.splits.manifest_id,
        "training_spec_id": config.score.spec_id,
    }
    path = root / "cases" / manifest_identifier(binding)[7:] / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "binding": binding,
                "outcome": {
                    "seed": seed,
                    "status": status,
                    "maximum_floor": floor,
                    "completed_acts": acts,
                    "decisions": 10,
                    "cpu_seconds": 1.0,
                },
            }
        )
    )
    return path


def test_complete_round_summary_counts_caps_and_keeps_original_output(tmp_path: Path) -> None:
    config = small_config()
    save_outcome(tmp_path, config, 0, 0, floor=17)
    save_outcome(tmp_path, config, 0, 1, floor=90, status=RunStatus.BUDGET)
    # Unrelated greedy results and another sampling stream cannot raise the displayed best.
    save_outcome(tmp_path, config, 0, 0, floor=500, behavior="greedy_argmax")
    save_outcome(tmp_path, config, 0, 0, floor=600, sampling_seed=1)
    sink = io.StringIO()
    progress = RoundProgress(config, tmp_path)
    writer = ProgressOutput(sink, progress)
    writer.write("Round 1/2: 1/2 games recorded.\n")
    writer.write("Round 1/2: 2/2 games")
    assert "summary:" not in sink.getvalue()
    writer.write(" recorded.\n")
    writer.write("Round 1/2: 2/2 games recorded.\n")
    writer.write('{"status": "completed"}\n')
    result = sink.getvalue()
    assert result.count("Round 1/2 summary:") == 1
    assert "best game: floor 17, 0 acts (loss)" in result
    assert "wins 0/2" in result
    assert "average floor 53.50 | failures/caps 1" in result
    assert "Best sampled game so far: floor 17" in result
    assert result.endswith('{"status": "completed"}\n')


def test_saved_rounds_rebuild_best_and_a_win_beats_a_higher_floor(tmp_path: Path) -> None:
    config = small_config()
    save_outcome(tmp_path, config, 0, 0, floor=20, acts=1)
    save_outcome(tmp_path, config, 0, 1, floor=12)
    save_outcome(tmp_path, config, 1, 0, floor=15, acts=3, status=RunStatus.VICTORY)
    save_outcome(tmp_path, config, 1, 1, floor=40, acts=2)
    progress = RoundProgress(config, tmp_path)
    assert progress.observe("Initial player confirmation: 2/2 games recorded.") is None
    assert progress.observe("Round 1 confirmation: 2/2 games recorded.") is None
    assert progress.observe("Frozen independent development: 2/2 games recorded.") is None
    first = progress.observe("Saved round 1: 2/2 saved games; 0 new attempts.")
    second = progress.observe("Saved round 2: 2/2 saved games; 0 new attempts.")
    assert first is not None and "floor 20, 1 act (loss)" in first
    assert second is not None and "wins 1/2" in second
    assert "best game: floor 15, 3 acts (WIN)" in second
    assert "Best sampled game so far: floor 15, 3 acts (WIN), round 2" in second


def test_failed_attempts_never_become_the_best_game(tmp_path: Path) -> None:
    config = small_config()
    save_outcome(tmp_path, config, 0, 0, floor=50, status=RunStatus.TRUNCATED)
    save_outcome(tmp_path, config, 0, 1, floor=0, status=RunStatus.ERROR, filename="failure.json")
    summary = RoundProgress(config, tmp_path).observe("Round 1/2: 2/2 games recorded.")
    assert summary is not None
    assert "wins 0/2 | best game: no finished games" in summary
    assert "failures/caps 2" in summary
    assert "Best sampled game so far: no finished games" in summary


def test_missing_saved_result_is_reported_without_interrupting_training(tmp_path: Path) -> None:
    config = small_config()
    save_outcome(tmp_path, config, 0, 0, floor=17)
    sink = io.StringIO()
    writer = ProgressOutput(sink, RoundProgress(config, tmp_path))
    writer.write("Round 1/2: 2/2 games recorded.\n")
    writer.write("Training's original message\n")
    assert "progress summary unavailable:" in sink.getvalue()
    assert sink.getvalue().endswith("Training's original message\n")


def test_duplicate_success_and_failure_cannot_count_as_two_games(tmp_path: Path) -> None:
    config = small_config()
    save_outcome(tmp_path, config, 0, 0, floor=17)
    save_outcome(tmp_path, config, 0, 0, floor=0, status=RunStatus.ERROR, filename="failure.json")
    save_outcome(tmp_path, config, 0, 1, floor=12)
    summary = RoundProgress(config, tmp_path).observe("Round 1/2: 2/2 games recorded.")
    assert summary is not None and "duplicate completed/failure" in summary
    assert "Training continues." in summary


def test_launcher_delegates_the_exact_command_and_preserves_failure_exit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    config = small_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.document))
    save_outcome(tmp_path, config, 0, 0, floor=17)
    save_outcome(tmp_path, config, 0, 1, floor=12)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    original_stdout = sys.stdout

    def command(args: list[str]) -> int:
        assert args == ["full-run", "train-ppo", str(config_path), str(tmp_path), "--resume"]
        print("Round 1/2: 2/2 games recorded.", flush=True)
        print('{"status": "error", "error": "synthetic worker failure"}')
        return 7

    monkeypatch.setattr("spireshift.cli.main", command)
    assert main([str(config_path), str(tmp_path), "--resume"]) == 7
    assert sys.stdout is original_stdout
    output = capsys.readouterr().out
    assert "Round 1/2 summary:" in output
    assert "synthetic worker failure" in output
    assert {path: path.read_bytes() for path in tmp_path.rglob("*.json")} == before
