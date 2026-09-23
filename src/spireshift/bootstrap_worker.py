from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from spireshift.bootstrap_teacher import load_bootstrap_task, write_bootstrap_worker_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m spireshift.bootstrap_worker")
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    task = load_bootstrap_task(args.request)
    return write_bootstrap_worker_result(
        batch_id=args.batch_id,
        task=task,
        request_path=args.request,
        result_path=args.result,
    )


if __name__ == "__main__":
    sys.exit(main())
