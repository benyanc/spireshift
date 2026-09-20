from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from spireshift.adapters.mock import MockSpireEnvironment
from spireshift.agents.baseline import PolicyOnlyBudgetController, TerminalVictoryPolicy
from spireshift.core.objective import load_objective
from spireshift.recording.jsonl import ImmutableJsonlRecorder
from spireshift.replay import verify_mock_replay
from spireshift.rollouts import (
    ROLLOUT_WORKER_RESULT_SCHEMA_VERSION,
    AttemptStatus,
    sha256_file,
    write_exclusive_json,
)
from spireshift.runner import RunResult, run_episode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m spireshift.rollout_worker")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--objective-config", required=True, type=Path)
    parser.add_argument("--record", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_result: RunResult | None = None
    replay_verified = False
    status = AttemptStatus.WORKER_ERROR
    message = "worker did not start"
    recorder: ImmutableJsonlRecorder | None = None
    try:
        recorder = ImmutableJsonlRecorder(args.record)
        run_result = run_episode(
            environment=MockSpireEnvironment(),
            policy=TerminalVictoryPolicy(),
            budget_controller=PolicyOnlyBudgetController(),
            recorder=recorder,
            objective=load_objective(args.objective_config),
            seed=args.seed,
        )
        recorder.close()
        recorder = None
        replay = verify_mock_replay(args.record)
        replay_verified = replay.valid
        if replay.valid:
            status = AttemptStatus.COMPLETED
            message = replay.message
        else:
            status = AttemptStatus.REPLAY_FAILED
            message = replay.message
    except Exception as error:
        status = AttemptStatus.WORKER_ERROR
        message = f"{type(error).__name__}: {error}"
    finally:
        if recorder is not None:
            recorder.close()

    result = {
        "schema_version": ROLLOUT_WORKER_RESULT_SCHEMA_VERSION,
        "batch_id": args.batch_id,
        "seed": args.seed,
        "attempt": args.attempt,
        "status": status.value,
        "worker_pid": os.getpid(),
        "message": message,
        "record_sha256": sha256_file(args.record) if args.record.is_file() else None,
        "victory": run_result.victory if run_result is not None else None,
        "decisions": run_result.decisions if run_result is not None else None,
        "compute_used": run_result.compute_used if run_result is not None else None,
        "replay_verified": replay_verified,
    }
    write_exclusive_json(args.result, result)
    return 0 if status is AttemptStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
