#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1

echo 'Close STS2. Verify two saved victories and qualify three prior clean archive cases.'
echo 'Each case starts from Neow. The batch ends after four minutes. Zero optimizer updates.'
exec uv run --no-sync python -m spireshift.native_a8_archive_batch_v6 --run "$@"
