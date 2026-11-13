#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only: fixed saved-data pilot, no engine, collection or automatic next round.
spireshift_neural_root=artifacts/models/sts2-v0.107.1-base-v11
spireshift_neural_config=configs/neural-combat/sts2-v0.107.1-base-v2-neural-v1.json
spireshift_neural_checkpoint="$spireshift_neural_root/checkpoint.json"
spireshift_neural_report="$spireshift_neural_root/training-report.json"
for spireshift_result in "$spireshift_neural_checkpoint" "$spireshift_neural_report"; do
  if [[ -L "$spireshift_result" || ( -e "$spireshift_result" && ! -f "$spireshift_result" ) ]]; then
    printf 'Refusing to replace existing output: %s\n' "$spireshift_result" >&2
    exit 1
  fi
done
if [[ -f "$spireshift_neural_checkpoint" && -f "$spireshift_neural_report" ]]; then
  printf 'Neural training already complete. Verifying its saved result; no retraining or games follow.\n'
  uv run spireshift model show-neural-combat-training "$spireshift_neural_root" --config "$spireshift_neural_config"
  exit 0
fi
if [[ -e "$spireshift_neural_checkpoint" || -e "$spireshift_neural_report" ]]; then
  printf 'Partial result preserved in %s. Share the earlier output before retrying.\n' "$spireshift_neural_root" >&2
  exit 1
fi
spireshift_attempt=1
while [[ -e "artifacts/resources/neural-combat-base-v11-train-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/neural-combat-base-v11-train-v1-attempt-$spireshift_attempt.json" || -e "artifacts/resources/neural-combat-base-v11-train-v1-attempt-$spireshift_attempt-metrics.json" || -L "artifacts/resources/neural-combat-base-v11-train-v1-attempt-$spireshift_attempt-metrics.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
# Set before importing NumPy: one worker must not become an unreported BLAS thread pool.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
printf 'Training one compact neural combat policy: one worker, 40 epochs, 30-minute cap. No game attempts or automatic follow-up.\n'
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/neural-combat-base-v11-train-v1-attempt-$spireshift_attempt.json" \
  --metrics "artifacts/resources/neural-combat-base-v11-train-v1-attempt-$spireshift_attempt-metrics.json" \
  --artifact-root "$spireshift_neural_root" \
  --workers 1 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 3600 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra neural spireshift model train-neural-combat-policy "$spireshift_neural_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --output-dir "$spireshift_neural_root"
