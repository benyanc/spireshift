"""Pin numerical threads before importing the separate curriculum owner entry."""

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
    from spireshift.native_win2_session import owner_main

    return owner_main(Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError) as exc:
        import json

        print(
            json.dumps(
                {
                    "status": "stopped_preserving_evidence",
                    "error": str(exc),
                    "optimizer_updates": 0,
                    "automatic_follow_up": False,
                }
            )
        )
        raise SystemExit(2) from exc
