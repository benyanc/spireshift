"""Restore the sealed normalization prefix and run only its unstarted cells."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from spireshift import native_capacity_session_v1 as capacity
from spireshift import native_normalization_session_v1 as original
from spireshift import native_qualified_learning_session_v1 as base
from spireshift.core.manifest import manifest_identifier
from spireshift.engine_learning import identified
from spireshift.engine_native import _running_games
from spireshift.native_a8_head_policy import HeadState
from spireshift.native_capacity_recovery_v1 import game_task
from spireshift.native_capacity_session_v2 import excluded
from spireshift.native_curriculum_config import THREADS
from spireshift.native_normalization_fit_v1 import fit
from spireshift.native_normalization_inputs_v1 import load as load_parent
from spireshift.native_normalization_inputs_v2 import MODULE, SCHEMA, assessment, context, load
from spireshift.native_normalization_recovery_v1 import FAILED
from spireshift.native_normalized_actor_v1 import load as load_state
from spireshift.native_normalized_actor_v1 import using_correction_scoring
from spireshift.native_qualified_learning_worker_v3 import play
from spireshift.native_sealed_continuation_v1 import SealedPrefixJournal
from spireshift.resource_tracking import ExperimentKind, ResourceLimits, run_tracked_command

RESTORE = "artifacts/native-hidden-normalization/restore-check-v2/report.json"
_initial_control = capacity.control_receipt


def control_receipt(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    with patch.object(capacity, "CONTROL", original.CONTROL):
        return _initial_control(root, load_parent(root))


class Session(original.Session):
    def __init__(self, root: Path, cfg: dict[str, Any], control: bool, deadline: float):
        if control:
            raise ValueError("Do not repeat historical learning controls")
        super().__init__(root, cfg, control, deadline)
        self.proof = assessment(root, cfg)
        self.store = SealedPrefixJournal(
            root, cfg, load_parent(root), self.proof["inherited_units"], frozenset({FAILED})
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
        if f"{partition}-{index:04d}-p{p}-{arm}" == FAILED:
            result = excluded(self.proof, game_task(seed, index, p, round_index, arm), state)
            result["failure"] = "preserved_native_deferred_discard_stop"
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
            "failed_prefix_used_as_training": False,
            "historical_menus_relabelled": False,
        }


@contextmanager
def bindings() -> Iterator[None]:
    with (
        using_correction_scoring(),
        patch.multiple(original, Session=Session, context=context, load=load, SCHEMA=SCHEMA),
        patch.multiple(base, context=context, load=load, load_state=load_state, play=play),
        patch.multiple(
            capacity, load=load, load_state=load_state, fit=fit, control_receipt=control_receipt
        ),
    ):
        yield


def readiness(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    proof = assessment(root, cfg)
    restored = identified(root / RESTORE)
    if (
        restored["status"] != "normalization_prefix_restored_before_first_unstarted_game"
        or restored["config_id"] != manifest_identifier(cfg)
        or restored["source_assessment_id"] != proof["report_id"]
        or restored["first_unstarted_game"] != "train-0994-p2-normalized"
        or restored["inherited_units_restored"] != 4234
        or restored["optimizer_updates_restored"] != 15252
        or restored["games_launched"] != 0
        or restored["optimizer_updates"] != 0
    ):
        raise ValueError("Require the exact no-game full-state restoration control")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("saved", "run"), nargs="?", default="run")
    parser.add_argument("--execute", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        if any(os.environ.get(n) != "1" for n in THREADS):
            raise ValueError("Use the pinned numerical runtime")
        cfg = load(root)
        proof = readiness(root, cfg)
        control_receipt(root, cfg)
        if args.mode == "saved":
            print(
                json.dumps(
                    {
                        "status": "normalization_continuation_inputs_verified",
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
                "Close STS2. Restore 3,984 sealed games, 249 fits and 15,252 copy updates. "
                "Preserve the capped game and failed world. Only 111 unstarted training and 768 "
                "fresh comparison games remain. Allow 3–5 hours; 48-hour outer cap. "
                "Frozen game/originals/full source Adam. No failed replay or automatic follow-up.",
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
        with bindings():
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
