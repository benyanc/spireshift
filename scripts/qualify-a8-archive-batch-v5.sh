#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1

echo 'Close STS2 before this archive qualification. Allow up to nine minutes.'
echo 'Four clean continuations start from Neow and verify prior inputs and deliveries. Zero updates.'
exec uv run --no-sync python -m spireshift.native_a8_archive_batch_v5 --run "$@"
