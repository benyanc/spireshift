#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only: the 32 seeds reserved before neural fitting, two frozen policies.
spireshift_confirmation_root=artifacts/evaluations/sts2-v0.107.1-base-v11-neural-fresh-train-v1
spireshift_confirmation_config=configs/combat-confirmation/sts2-v0.107.1-base-v11-neural-fresh-train-v1.json
spireshift_confirmation_report="$spireshift_confirmation_root/production-policy-evaluation.json"
if [[ -L "$spireshift_confirmation_report" || ( -e "$spireshift_confirmation_report" && ! -f "$spireshift_confirmation_report" ) ]]; then
  printf 'Refusing to replace existing comparison output: %s\n' "$spireshift_confirmation_report" >&2
  exit 1
fi
if [[ -f "$spireshift_confirmation_report" ]]; then
  printf 'Neural comparison already saved. Checking it; no games or training follow.\n'
  uv run spireshift model show-combat-confirmation "$spireshift_confirmation_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir "$spireshift_confirmation_root"
  exit 0
fi
spireshift_confirmation_attempt=1
while [[ -e "artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-$spireshift_confirmation_attempt.json" || -L "artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-$spireshift_confirmation_attempt.json" || -e "artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-$spireshift_confirmation_attempt-metrics.json" || -L "artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-$spireshift_confirmation_attempt-metrics.json" ]]; do
  spireshift_confirmation_attempt=$((spireshift_confirmation_attempt + 1))
done
# Keep a declared serial comparison from acquiring an unreported numerical thread pool.
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
printf 'Comparing neural base-v11 with accepted base-v2: 64 simulated game attempts, one worker, 30-minute job cap. No training or automatic follow-up.\n'
uv run spireshift resources run \
  --kind rollout \
  --report "artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-$spireshift_confirmation_attempt.json" \
  --metrics "artifacts/resources/neural-combat-base-v11-confirmation-v1-attempt-$spireshift_confirmation_attempt-metrics.json" \
  --artifact-root "$spireshift_confirmation_root" \
  --workers 1 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 10000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift model confirm-combat-policy "$spireshift_confirmation_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --output-dir "$spireshift_confirmation_root" \
    --resume
