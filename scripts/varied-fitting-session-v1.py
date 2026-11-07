"""Owner entry point for one fitting-only session with fixed numeric threads."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    for name in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "MKL_NUM_THREADS",
    ]:
        os.environ[name] = "1"
    from spireshift.native_fitting_session import owner_main

    return owner_main(Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    raise SystemExit(main())
