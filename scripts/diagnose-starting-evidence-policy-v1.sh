#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run saved-file audit only. No optimizer, simulation, collection, or replay.
spireshift_diagnostic_root=artifacts/diagnostics/sts2-v0.107.1-base-v8-starting-evidence-v1
spireshift_diagnostic="$spireshift_diagnostic_root/diagnostic.json"
spireshift_diagnostic_config=configs/starting-evidence-diagnostic/sts2-v0.107.1-base-v8-v1.json

if [[ -f "$spireshift_diagnostic" ]]; then
  printf 'Audit already completed. Checking and displaying its saved report; source files are not audited again.\n'
  uv run spireshift model show-starting-evidence-diagnosis \
    "$spireshift_diagnostic" --diagnostic-config "$spireshift_diagnostic_config"
  exit 0
fi
if [[ -e "$spireshift_diagnostic" || -L "$spireshift_diagnostic" ]]; then
  printf 'Refusing to replace existing diagnostic output: %s\n' "$spireshift_diagnostic" >&2
  exit 1
fi

# Preserve previous resource reports after interruptions; never reuse their filenames.
spireshift_attempt=1
while [[ -e "artifacts/resources/starting-evidence-base-v8-diagnostic-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Auditing saved starting-choice evidence (10-minute cap); no training or game attempts.\n'
uv run spireshift resources run \
  --kind other \
  --report "artifacts/resources/starting-evidence-base-v8-diagnostic-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_diagnostic_root" \
  --workers 1 \
  --max-wall-seconds 600 \
  --max-cpu-seconds 600 \
  --max-storage-bytes 50000000 \
  --max-memory-bytes 4000000000 \
  -- \
  uv run spireshift model diagnose-starting-evidence-policy \
    configs/starting-option-policy/sts2-v0.107.1-base-v2-exhaustive-evidence-v1.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    artifacts/models/sts2-v0.107.1-base-v8/checkpoint.json \
    --parent-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --report artifacts/models/sts2-v0.107.1-base-v8/training-report.json \
    --evidence artifacts/starting-options/sts2-v0.107.1-base-v2-train-v1/starting-option-evidence.json \
    --evidence-config configs/starting-option-evidence/sts2-v0.107.1-base-v2-train-v1.json \
    --anchor-assignment-report artifacts/models/sts2-v0.107.1-base-v7/training-report.json \
    --train-report artifacts/bootstrap/teacher-train-v2/bootstrap-teacher-dataset.json \
    --validation-report artifacts/bootstrap/teacher-validation-v2/bootstrap-teacher-dataset.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --ruleset-manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --resource-report artifacts/resources/starting-evidence-policy-base-v8-train-v1-attempt-1.json \
    --diagnostic-config "$spireshift_diagnostic_config" \
    --output "$spireshift_diagnostic"
