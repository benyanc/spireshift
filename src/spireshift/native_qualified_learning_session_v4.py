"""Finish unstarted study cells after saved and fresh normal-start verifier controls pass."""

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
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_compatibility_inputs import check_sources
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_qualified_learning_inputs_v2 import RECIPE as ORIGINAL
from spireshift.native_qualified_learning_inputs_v4 import (
    MODULE,
    PARENT,
    SCHEMA,
    assessment,
    context,
    load,
)
from spireshift.native_qualified_learning_readiness_v2 import EXCLUDED
from spireshift.native_qualified_learning_readiness_v2 import RECIPE as READINESS
from spireshift.native_qualified_learning_recovery_v1 import task
from spireshift.native_qualified_learning_session_v3 import ContinuationJournal as OriginalJournal
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command


class ContinuationJournal(OriginalJournal):
    def path(self, key: str) -> Path:
        if key in EXCLUDED:
            raise ValueError("Preserve both failed cells; never reopen their worker paths")
        return super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key in EXCLUDED:
            raise ValueError("Never replay either excluded game")
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key in EXCLUDED:
            raise ValueError("Never replay either excluded game")
        return super().begin(key, request)


def excluded_game(
    proof: dict[str, Any], game_task: dict[str, Any], state: tuple[HeadState, str]
) -> dict[str, Any]:
    if {"task": game_task, "behavior_state_id": state[1]} != proof[
        "excluded_training_requests"
    ].get(game_task["key"]):
        raise ValueError("The exclusion changed its world, round or full behavior state")
    return {
        "seal_id": proof["report_id"],
        "task": game_task,
        "model_id": state[0].model.model_id,
        "outcome": "failed",
        "training_excluded": True,
        "failure": "preserved_saved_checker_stop",
    }


class Session(previous.Session):
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        if control:
            raise ValueError("The exact fresh controls have already passed; never repeat them")
        super().__init__(root, cfg, control, deadline)
        self.proof = assessment(root, cfg)
        self.store = ContinuationJournal(
            root, cfg, json.loads((root / ORIGINAL).read_text()), self.proof
        )

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
        if key in EXCLUDED:
            result = excluded_game(self.proof, task(seed, index, p, round_index), state)
            self.game_counts.setdefault(f"train-p{p}", Counter())["failed"] += 1
            return result
        return super().game(seed, index, p, round_index, partition, arm, state)

    def run(self) -> dict[str, Any]:
        current = self.starting.copy()
        rounds, count = self.cfg["plan"]["rounds"], self.cfg["plan"]["worlds_per_round"]
        print(
            "Restoring sealed games and full Adam states. Saved rounds do not repeat updates.",
            flush=True,
        )
        for r in range(1, rounds + 1):
            seeds = self.cfg["plan"]["training"][(r - 1) * count : r * count]
            for p in (2, 3):
                rows = [
                    self.game(seed, (r - 1) * count + i, p, r, "train", "learner", current[p])
                    for i, seed in enumerate(seeds, 1)
                ]
                key = f"fit-p{p}-r{r:03d}"
                saved = (self.store.path(key) / "done.json").exists()
                current[p] = self.learn(p, r, rows, current[p])
                if not saved:
                    result = self.training[-1]
                    outcomes = dict(Counter(x["outcome"] for x in rows))
                    print(
                        f"New fit round {r}/{rounds}, player {p}: {outcomes}; "
                        f"Act 1 clears {result['act1_clears']}/{len(rows)}; "
                        f"{result['work']['optimizer_updates']} new updates",
                        flush=True,
                    )
        for i, seed in enumerate(self.cfg["plan"]["development"], 1):
            for p in (2, 3):
                for arm, state in (("original", self.starting[p]), ("fitted", current[p])):
                    row = self.game(seed, i, p, rounds, "development", arm, state)
                    self.evaluation[seed, p, arm] = row
                    label = "frozen-start" if arm == "original" else "trained-round-64"
                    print(f"Development {i}/32 p{p} {label}: {row['outcome']}", flush=True)
        self.unchanged()
        return {
            "status": previous.COMPLETE,
            "final_states": {str(p): current[p][1] for p in (2, 3)},
            "inherited_completed_units": len(self.proof["inherited_units"]),
            "inherited_optimizer_updates": self.proof["inherited_optimizer_updates"],
            "new_optimizer_updates": sum(r["work"]["optimizer_updates"] for r in self.training)
            - self.proof["inherited_optimizer_updates"],
            "excluded_training_units": list(EXCLUDED),
            "failed_training_cells_retained": 2,
            "failed_games_are_not_training_labels": True,
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
            raise ValueError("Use the pinned numerical runtime")
        cfg = load(root)
        proof = assessment(root, cfg)
        resume = identified(root / cfg["resume_check_workspace"] / "report.json")
        check_sources(root, resume["sources"])
        if (
            resume["status"] != "restored_exact_prefix_stopped_before_first_unstarted_game"
            or resume["config_id"] != manifest_identifier(cfg)
            or resume["first_unstarted_game"] != "train-0573-p3-learner"
            or resume["games_launched"] != 0
            or resume["optimizer_updates"] != 0
        ):
            raise ValueError("Require the passing exact restore-to-first-new-game check")
        control = identified(root / cfg["verifier_controls"]["path"])
        if frozen(root, context(root, cfg)) != control["frozen_checks"]:
            raise ValueError("The frozen game or original full checkpoints/Adam changed")
        if args.mode == "saved":
            print(
                json.dumps(
                    {
                        "status": "saved_continuation_and_fresh_controls_verified",
                        "assessment_id": proof["report_id"],
                        "control_id": control["report_id"],
                        "games_launched": 0,
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        original = json.loads((root / ORIGINAL).read_text())
        parent = json.loads((root / PARENT).read_text())
        ready = json.loads((root / READINESS).read_text())
        area = root / cfg["workspace"]
        area.mkdir(parents=True, exist_ok=True)
        if args.execute is None:
            attempt = time.time_ns()
            print(
                "Reuse 1,146 sealed games and 3,813 copy updates. Preserve two failed cells. "
                "Run only 900 unstarted training games "
                "and the original 128 fresh comparison games. "
                "Expect 3–5 hours. Frozen source weights/full Adam and game remain unchanged.",
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
                artifact_roots=[
                    root / original["workspace"],
                    root / parent["workspace"],
                    root / ready["workspace"],
                    root / cfg["resume_check_workspace"],
                    area,
                ],
                limits=ResourceLimits(**cfg["limits"]),
            )
            print(json.dumps(tracked.report))
            return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        with (
            ChunkJournal(root, original).lock(),
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
