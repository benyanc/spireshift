#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1

echo 'Close STS2 before this replay batch. It can take about 5 to 9 minutes.'
echo 'Each replay starts from Neow after verifying its earlier clean stop.'
exec uv run --no-sync python -m spireshift.native_a8_archive_batch_v4 --run "$@"
