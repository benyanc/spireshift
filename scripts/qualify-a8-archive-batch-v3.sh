#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 MKL_NUM_THREADS=1

echo 'Replay the declared Ironclad/A8 journals with verified reward matching.'
echo 'Close STS2 before starting. The script stops after archive qualification.'
exec uv run --no-sync python -m spireshift.native_a8_archive_batch_v3 --run "$@"
