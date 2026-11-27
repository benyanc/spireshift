"""Restore 673 sealed units and full Adam; run only unattempted capacity-study games."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_capacity_session_v1 as original
from spireshift import native_qualified_learning_session_v1 as base
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_a8_tactical_session import frozen
from spireshift.native_capacity_inputs_v1 import load as load_parent
from spireshift.native_capacity_inputs_v2 import MODULE, SCHEMA, assessment, context, load
from spireshift.native_capacity_recovery_v1 import FAILED, game_task
from spireshift.native_context_journal import ChunkJournal
from spireshift.native_curriculum_config import THREADS
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command


class ContinuationJournal(ChunkJournal):
    def __init__(
        self, root: Path, cfg: dict[str, Any], parent: dict[str, Any], proof: dict[str, Any]
    ):
        super().__init__(root, cfg)
        self.original = ChunkJournal(root, parent)
        self.imports = proof["inherited_units"]

    def path(self, key: str) -> Path:
        if key == FAILED:
            raise ValueError("Never reopen the failed potion world")
        return self.original.path(key) if key in self.imports else super().path(key)

    def completed(self, key: str, request: dict[str, Any]) -> dict[str, Any] | None:
        if key == FAILED:
            raise ValueError("Never replay the failed potion world")
        if key in self.imports:
            result = self.original.completed(key, request)
            if result is None or result["report_id"] != self.imports[key]:
                raise ValueError("A sealed historical unit changed; never repeat it")
            return result
        return super().completed(key, request)

    def begin(self, key: str, request: dict[str, Any]) -> Path:
        if key == FAILED or key in self.imports:
            raise ValueError("Never collect or fit a historical unit again")
        return super().begin(key, request)


def excluded(
    proof: dict[str, Any], task: dict[str, Any], state: tuple[HeadState, str]
) -> dict[str, Any]:
    if {"task": task, "behavior_state_id": state[1]} != proof["failed_request"]:
        raise ValueError(
            "The failed-cell exclusion changed world, round or complete behavior state"
        )
    return {
        "seal_id": proof["report_id"],
        "task": task,
        "model_id": state[0].model.model_id,
        "outcome": "failed",
        "training_excluded": True,
        "failure": "preserved_native_potion_queue_stop",
    }


class Session(original.Session):
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        if control:
            raise ValueError("Reuse the sealed capacity controls; no duplicate games or updates")
        super().__init__(root, cfg, control, deadline)
        self.proof = assessment(root, cfg)
        self.store = ContinuationJournal(root, cfg, load_parent(root), self.proof)

    def unchanged(self) -> None:
        from spireshift.engine_native import _shared_snapshot
        from spireshift.native_a8_boss_checks import SHARED_PROFILE

        if load(self.root) != self.cfg or frozen(self.root, self.ctx) != self.before:
            raise ValueError("The capacity continuation, build or frozen full states/Adam changed")
        if _shared_snapshot(Path.home() / SHARED_PROFILE) != self.profile:
            raise ValueError("The personal game profile changed")

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
        if f"{partition}-{index:04d}-p{p}-{arm}" == FAILED:
            result = excluded(self.proof, game_task(seed, index, p, round_index, arm), state)
            self.cohort_counts.setdefault(f"{partition}-p{p}-{arm}", Counter())["failed"] += 1
            self.game_counts.setdefault(f"{partition}-p{p}", Counter())["failed"] += 1
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
            "historical_menus_relabelled": False,
            "failed_prefix_used_as_training": False,
        }


def control_receipt(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    return _original_control(root, load_parent(root))


_original_control = original.control_receipt


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
        control_receipt(root, cfg)
        restored = identified(root / "artifacts/native-policy-capacity/resume-check-v2.json")
        if (
            restored["status"] != "capacity_prefix_restored_before_first_unstarted_game"
            or restored["config_id"] != manifest_identifier(cfg)
            or restored["source_assessment_id"] != proof["report_id"]
            or restored["first_unstarted_game"] != "train-0155-p3-expanded"
            or restored["inherited_units_restored"] != 673
            or restored["optimizer_updates_restored"] != 2429
            or restored["games_launched"] != 0
            or restored["optimizer_updates"] != 0
        ):
            raise ValueError("Require the exact no-game/full-Adam restore control")
        if args.mode == "saved":
            print(
                json.dumps(
                    {
                        "status": "capacity_continuation_inputs_verified",
                        "assessment_id": proof["report_id"],
                        "games_launched": 0,
                        "optimizer_updates": 0,
                    }
                )
            )
            return 0
        area = root / cfg["workspace"]
        area.mkdir(parents=True, exist_ok=True)
        if args.execute is None:
            attempt = time.time_ns()
            print(
                "Restore 633 games / 39 fits / 2,429 copy updates. Preserve the failed cell. "
                "Only 3,462 unstarted training games and 768 fresh comparisons remain. "
                "Allow about 12–22 hours; 48-hour cap. Keep STS2 closed. "
                "Originals and finals/full Adam stay frozen.",
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
                artifact_roots=[area],
                limits=ResourceLimits(**cfg["limits"]),
            )
            print(json.dumps(tracked.report))
            return 0 if tracked.exit_code == 0 and tracked.report["cap"] is None else 2
        if _running_games():
            raise ValueError("Close STS2 and wait for other native workers")
        with (
            patch.multiple(base, context=context, load=load, play=play),
            patch.multiple(
                original, Session=Session, SCHEMA=SCHEMA, control_receipt=control_receipt
            ),
        ):
            result = original.execute(
                root, cfg, False, time.monotonic() + cfg["limits"]["wall_seconds"] - 10
            )
        print(
            json.dumps(
                {k: v for k, v in result.items() if k not in {"sources", "training", "chunk_seals"}}
            )
        )
        return 0 if result["status"] in {original.COMPLETE, "paused"} else 2
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
