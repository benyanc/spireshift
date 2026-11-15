#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1

echo 'Use the pinned archive owner matcher on the declared native worlds.'
echo 'Close STS2 before fresh replay. The frozen game, checkpoint and Adam checks still apply.'
exec uv run --no-sync python -m spireshift.native_a8_archive_batch_v2 --run "$@"
