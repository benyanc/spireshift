#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1

echo 'Audit saved victories and replay only fresh journals that pass source screening.'
echo 'Close STS2 before live replay. The frozen game and full checkpoint states are read-only.'
echo 'Keep development and final-test seeds reserved. Zero optimizer updates.'
exec uv run --no-sync python -m spireshift.native_a8_archive_batch --run "$@"
