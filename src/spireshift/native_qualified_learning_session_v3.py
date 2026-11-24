"""Continue sealed normal-start PPO; never replay the preserved failed-verification cell."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_qualified_learning_session_v1 as previous
from spireshift.engine_native import _running_games
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_qualified_learning_inputs_v3 import (
    MODULE,
    PARENT,
    SCHEMA,
    assessment,
    context,
    load,
)
from spireshift.native_qualified_learning_recovery_v1 import FAILED, task
from spireshift.native_qualified_learning_worker_v2 import play
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command


class ContinuationJournal(ChunkJournal):
    def __init__(
        self, root: Path, recipe: dict[str, Any], parent: dict[str, Any], proof: dict[str, Any]
    ):
        super().__init__(root, recipe)
        self.original = ChunkJournal(root, parent)
        self.imports = proof["inherited_units"]

    def path(self, key: str) -> Path:
        if key == FAILED:
            raise ValueError("The failed unit stays diagnostic; never reopen its path")
        return self.original.path(key) if key in self.imports else super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key == FAILED:
            raise ValueError("Never replay the failed-verification game")
        if key in self.imports:
            result = self.original.completed(key, request)
            if result is None or result["report_id"] != self.imports[key]:
                raise ValueError("Never replay or update a missing or changed imported unit")
            return result
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key == FAILED or key in self.imports:
            raise ValueError("Never replay or update a historical unit")
        return super().begin(key, request)


def excluded_game(
    proof: dict[str, Any], game_task: dict[str, Any], state: tuple[HeadState, str]
) -> dict[str, Any]:
    if {"task": game_task, "behavior_state_id": state[1]} != proof["failed_request"]:
        raise ValueError("The diagnostic exclusion changed world, round or behavior state")
    return {
        "seal_id": proof["report_id"],
        "task": game_task,
        "model_id": state[0].model.model_id,
        "outcome": "failed",
        "training_excluded": True,
        "failure": "preserved_legacy_card_answer_verifier_stop",
    }


class Session(previous.Session):
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        if control:
            raise ValueError("Reuse the verified control; do not rerun its games or updates")
        super().__init__(root, cfg, control, deadline)
        self.proof = assessment(root, cfg)
        parent = json.loads((root / PARENT).read_text())
        self.store = ContinuationJournal(root, cfg, parent, self.proof)

    def game(
        self,
        seed: str,
        index: int,
        p: int,
        round_index: int,
        partition: str,
        arm: str,
        state: tuple[HeadState, str],
    ) -> dict[str, Any]:
        key = f"{partition}-{index:04d}-p{p}-{arm}"
        if key == FAILED:
            result = excluded_game(self.proof, task(seed, index, p, round_index), state)
            counts = self.game_counts.setdefault("train-p3", Counter())
            counts["failed"] += 1
            return result
        return super().game(seed, index, p, round_index, partition, arm, state)

    def run(self) -> dict[str, Any]:
        result = super().run()
        return {
            **result,
            "inherited_completed_units": len(self.proof["inherited_units"]),
            "inherited_optimizer_updates": self.proof["inherited_optimizer_updates"],
            "new_optimizer_updates": sum(row["work"]["optimizer_updates"] for row in self.training)
            - self.proof["inherited_optimizer_updates"],
            "excluded_training_units": [FAILED],
            "failed_training_cells_retained": 1,
            "failed_game_is_not_a_training_label": True,
            "source_assessment_id": self.proof["report_id"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("saved", "run"), nargs="?", default="run")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if any(os.environ.get(name) != "1" for name in THREADS):
            raise ValueError("Use the pinned single-thread numerical runtime")
        cfg = load(root)
        proof = assessment(root, cfg)
        if frozen(root, context(root, cfg)) != proof["frozen_checks"]:
            raise ValueError("The frozen build or original checkpoints/full Adam changed")
        if args.mode == "saved":
            print(
                json.dumps(
                    {
                        "status": "saved_continuation_verified",
                        "report_id": proof["report_id"],
                        "games_launched": 0,
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        parent = json.loads((root / PARENT).read_text())
        area = root / cfg["workspace"]
        area.mkdir(parents=True, exist_ok=True)
        if args.execute is None:
            attempt = time.time_ns()
            print(
                "Reuse 1,146 games and 3,813 copy updates. Preserve one failed cell. "
                "Run only 901 unstarted training games, then 128 fresh comparison games. "
                "Allow 3–5 hours. Original checkpoints/full Adam and the game stay frozen.",
                flush=True,
            )
            tracked = run_tracked_command(
                command=[
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    "-B",
                    "-m",
                    MODULE,
                    "run",
                    "--execute",
                    str(attempt),
                ],
                working_directory=root,
                experiment_kind=ExperimentKind.TRAINING,
                report_path=area / f"resources-{attempt}.json",
                artifact_roots=[root / parent["workspace"], area],
                limits=ResourceLimits(**cfg["limits"]),
            )
            print(json.dumps(tracked.report))
            return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        # Hold the predecessor lease through continuation, child shutdown and final checks.
        with (
            ChunkJournal(root, parent).lock(),
            patch.multiple(
                previous,
                MODULE=MODULE,
                SCHEMA=SCHEMA,
                load=load,
                context=context,
                Session=Session,
                play=play,
            ),
        ):
            result = previous.execute(
                root, cfg, False, time.monotonic() + cfg["limits"]["wall_seconds"] - 15
            )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "training", "chunk_seals"}}
            )
        )
        return 0 if result["status"] in {previous.COMPLETE, "paused"} else 2
    except (ValueError, OSError, KeyError, TimeoutError) as exc:
        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(exc),
                    "original_optimizer_updates": 0,
                    "automatic_follow_up": False,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
