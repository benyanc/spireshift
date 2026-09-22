from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from spireshift.rollouts import sha256_file, write_exclusive_json
from spireshift.search_workers import (
    SEARCH_WORKER_RESULT_SCHEMA_VERSION,
    SearchWorkerStatus,
    execute_search_task,
    load_search_task,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m spireshift.search_worker")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    status = SearchWorkerStatus.WORKER_ERROR
    message = "worker did not start"
    output: dict[str, object] | None = None
    task_id = "invalid-request"
    try:
        task = load_search_task(args.request)
        task_id = task.task_id
        output = execute_search_task(task)
        status = SearchWorkerStatus.COMPLETED
        message = "search simulation completed"
    except Exception as error:  # noqa: BLE001 - worker failures become immutable evidence.
        message = f"{type(error).__name__}: {error}"
    result = {
        "schema_version": SEARCH_WORKER_RESULT_SCHEMA_VERSION,
        "batch_id": args.batch_id,
        "task_id": task_id,
        "status": status.value,
        "worker_pid": os.getpid(),
        "message": message,
        "request_sha256": sha256_file(args.request),
        "cpu_seconds": time.process_time() - started_cpu,
        "wall_seconds": time.perf_counter() - started_wall,
        "output": output,
    }
    write_exclusive_json(args.result, result)
    return 0 if status is SearchWorkerStatus.COMPLETED else 1


if __name__ == "__main__":
    sys.exit(main())
