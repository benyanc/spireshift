#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only: one finite cohort, verification, analysis; no automatic training.
spireshift_study_root=artifacts/repeatability/sts2-v0.107.1-base-v2-train-v1
spireshift_study="$spireshift_study_root/starting-repeatability.json"
spireshift_config=configs/starting-repeatability/sts2-v0.107.1-base-v2-train-v1.json

if [[ -L "$spireshift_study" || ( -e "$spireshift_study" && ! -f "$spireshift_study" ) ]]; then
  printf 'Refusing to replace existing study output: %s\n' "$spireshift_study" >&2
  exit 1
fi
if [[ -f "$spireshift_study" ]]; then
  printf 'Study already completed. Displaying its saved result; no source audit or games will run.\n'
  uv run spireshift model show-starting-repeatability "$spireshift_study" --config "$spireshift_config"
  exit 0
fi

spireshift_attempt=1
while [[ -e "artifacts/resources/starting-repeatability-base-v2-train-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/starting-repeatability-base-v2-train-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Starting one bounded study: 192 fresh seeds, up to 576 branches, four workers, 30-minute cap. No training follows.\n'
uv run spireshift resources run \
  --kind rollout \
  --report "artifacts/resources/starting-repeatability-base-v2-train-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_study_root" \
  --workers 4 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 4000000000 \
  -- \
  uv run --extra evangambit spireshift model study-starting-repeatability \
    "$spireshift_config" \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir "$spireshift_study_root" \
    --resume
