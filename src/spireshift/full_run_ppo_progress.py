"""Display round outcomes without changing the frozen PPO learner or its artifacts."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from pathlib import Path
from typing import TextIO

from spireshift.core.manifest import manifest_identifier
from spireshift.full_run_ppo import PPOConfig, load_ppo_config
from spireshift.training_objective import RunStatus, TrainingOutcome

ROUND_LINE = re.compile(
    r"(?:Round (\d+)/\d+|Saved round (\d+)): (\d+)/(\d+) "
    r"(?:games recorded\.|saved games; (\d+) new attempts\.)"
)
FINISHED = {RunStatus.VICTORY, RunStatus.LOSS}


def progress_rank(outcome: TrainingOutcome) -> tuple[bool, int, int]:
    """A full win comes first; unfinished or failed games never become the best game."""
    return (
        outcome.status == RunStatus.VICTORY,
        outcome.completed_acts,
        outcome.maximum_floor,
    )


def describe_game(outcome: TrainingOutcome) -> str:
    status = "WIN" if outcome.status == RunStatus.VICTORY else "loss"
    acts = "act" if outcome.completed_acts == 1 else "acts"
    return f"floor {outcome.maximum_floor}, {outcome.completed_acts} {acts} ({status})"


class RoundProgress:
    def __init__(self, config: PPOConfig, output: Path) -> None:
        self.config = config
        self.output = output
        self.read_paths: set[Path] = set()
        self.outcomes: dict[tuple[int, int], tuple[str, TrainingOutcome]] = {}
        self.reported_rounds: set[int] = set()
        self.best: tuple[int, TrainingOutcome] | None = None

    def read_saved_outcomes(self) -> None:
        # Read only small, completed case metadata. Never open traces or debug journals,
        # replay games, fit a model, write artifacts or poll a running experiment.
        for name in ("case.json", "failure.json"):
            for path in (self.output / "cases").glob(f"*/{name}"):
                if path in self.read_paths:
                    continue
                case = json.loads(path.read_text(encoding="utf-8"))
                binding = case["binding"]
                if binding["partition"] != "train" or binding["behavior"] != "sampled_softmax":
                    self.read_paths.add(path)
                    continue
                if (
                    binding["ruleset_manifest_id"] != self.config.ruleset.manifest_id
                    or binding["split_manifest_id"] != self.config.splits.manifest_id
                    or binding["training_spec_id"] != self.config.score.spec_id
                    or path.parent.name != manifest_identifier(binding)[7:]
                ):
                    raise ValueError("saved sampled game's experiment binding differs")
                outcome = TrainingOutcome.from_mapping(case["outcome"])
                if outcome.seed != binding["seed"]:
                    raise ValueError("saved sampled game's seed differs")
                key = (outcome.seed, binding["sampling_seed"])
                if key in self.outcomes:
                    raise ValueError("duplicate completed/failure result for a sampled game")
                self.outcomes[key] = (binding["model_id"], outcome)
                self.read_paths.add(path)

    def summary(self, round_index: int) -> str:
        self.read_saved_outcomes()
        learning = self.config.document["learning"]
        seeds = learning["rollout_seed_panels"][round_index]
        games = []
        models = set()
        for seed in seeds:
            sampling_seed = int.from_bytes(
                hashlib.sha256(
                    f"{learning['sampling_rng_seed']}|{round_index}|{seed}".encode()
                ).digest()[:8],
                "big",
            )
            model_id, outcome = self.outcomes[(seed, sampling_seed)]
            models.add(model_id)
            games.append(outcome)
        if len(models) != 1:
            raise ValueError("one sampled round contains different players")
        finished = [game for game in games if game.status in FINISHED]
        wins = sum(game.status == RunStatus.VICTORY for game in games)
        failures = len(games) - len(finished)
        mean_floor = sum(game.maximum_floor for game in games) / len(seeds)
        best = (
            max(sorted(finished, key=lambda game: game.seed), key=progress_rank)
            if finished
            else None
        )
        if best is not None and (
            self.best is None or progress_rank(best) > progress_rank(self.best[1])
        ):
            self.best = (round_index, best)
        best_text = describe_game(best) if best is not None else "no finished games"
        ever = (
            f"{describe_game(self.best[1])}, round {self.best[0] + 1}, seed {self.best[1].seed}"
            if self.best is not None
            else "no finished games"
        )
        return (
            f"Round {round_index + 1}/{learning['maximum_rounds']} summary: "
            f"wins {wins}/{len(seeds)} | best game: {best_text} | "
            f"average floor {mean_floor:.2f} | failures/caps {failures}.\n"
            f"Best sampled game so far: {ever}."
        )

    def observe(self, line: str) -> str | None:
        match = ROUND_LINE.fullmatch(line)
        if match is None:
            return None
        number, saved_number, done, total, new_attempts = match.groups()
        if done != total or (new_attempts is not None and int(new_attempts) != 0):
            return None
        round_index = int(number or saved_number) - 1
        panels = self.config.document["learning"]["rollout_seed_panels"]
        if round_index in self.reported_rounds or not 0 <= round_index < len(panels):
            return None
        self.reported_rounds.add(round_index)
        try:
            if int(total) != len(panels[round_index]):
                raise ValueError("round's recorded game count differs from its recipe")
            return self.summary(round_index)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Console diagnostics must not interrupt training or hide its original error.
            return (
                f"Round {round_index + 1} progress summary unavailable: {exc}. Training continues."
            )


class ProgressOutput(io.TextIOBase):
    def __init__(self, stream: TextIO, progress: RoundProgress) -> None:
        self.stream = stream
        self.progress = progress
        self.pending = ""

    def write(self, text: str) -> int:
        self.stream.write(text)
        self.pending += text
        while "\n" in self.pending:
            line, self.pending = self.pending.split("\n", 1)
            summary = self.progress.observe(line)
            if summary is not None:
                self.stream.write(summary + "\n")
                self.stream.flush()
        return len(text)

    def flush(self) -> None:
        self.stream.flush()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    # Dispatch the exact existing command in this process: its resource guard, owner
    # lock, exit status, seed panels and frozen implementation remain authoritative.
    from spireshift.cli import main as cli_main

    command = ["full-run", "train-ppo", str(args.config), str(args.output_dir)]
    if args.resume:
        command.append("--resume")
    try:
        progress = RoundProgress(load_ppo_config(args.config), args.output_dir)
    except (OSError, ValueError, KeyError, TypeError):
        return cli_main(command)
    with redirect_stdout(ProgressOutput(sys.stdout, progress)):
        return cli_main(command)


if __name__ == "__main__":
    raise SystemExit(main())
