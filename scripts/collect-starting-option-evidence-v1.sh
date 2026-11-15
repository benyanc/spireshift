#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only. Complete results are inspected; partial seed cases are resumed.
spireshift_config=configs/starting-option-evidence/sts2-v0.107.1-base-v2-train-v1.json
spireshift_split=manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json
spireshift_manifest=artifacts/backend/evangambit-v0.107.1-admitted.json
spireshift_output=artifacts/starting-options/sts2-v0.107.1-base-v2-train-v1

if [[ -e "$spireshift_output/starting-option-evidence.json" ]]; then
  printf 'Collection already finished. Verifying saved results; no games will run.\n'
  uv run spireshift model verify-starting-option-evidence \
    "$spireshift_output/starting-option-evidence.json" "$spireshift_config" \
    --split-manifest "$spireshift_split" --manifest "$spireshift_manifest"
  exit 0
fi

# Each attempt keeps its resource report; completed seed cases remain immutable.
spireshift_attempt=1
while [[ -e "artifacts/resources/starting-option-evidence-base-v2-train-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
uv run spireshift resources run \
  --kind rollout \
  --report "artifacts/resources/starting-option-evidence-base-v2-train-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_output" \
  --workers 4 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 3600 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 4000000000 \
  -- \
  uv run --extra evangambit spireshift model collect-starting-option-evidence \
    "$spireshift_config" \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest "$spireshift_split" \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest "$spireshift_manifest" \
    --output-dir "$spireshift_output" \
    --resume
