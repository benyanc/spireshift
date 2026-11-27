#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only: one residual training job, followed by saved-file verification.
spireshift_model_root=artifacts/models/sts2-v0.107.1-base-v8
spireshift_checkpoint="$spireshift_model_root/checkpoint.json"
spireshift_training_report="$spireshift_model_root/training-report.json"
spireshift_arguments=(
  configs/starting-option-policy/sts2-v0.107.1-base-v2-exhaustive-evidence-v1.json
  artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json
  "$spireshift_checkpoint"
  --parent-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json
  --report "$spireshift_training_report"
  --evidence artifacts/starting-options/sts2-v0.107.1-base-v2-train-v1/starting-option-evidence.json
  --evidence-config configs/starting-option-evidence/sts2-v0.107.1-base-v2-train-v1.json
  --anchor-assignment-report artifacts/models/sts2-v0.107.1-base-v7/training-report.json
  --train-report artifacts/bootstrap/teacher-train-v2/bootstrap-teacher-dataset.json
  --validation-report artifacts/bootstrap/teacher-validation-v2/bootstrap-teacher-dataset.json
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json
  --ruleset-manifest artifacts/backend/evangambit-v0.107.1-admitted.json
)

if [[ -f "$spireshift_checkpoint" && -f "$spireshift_training_report" ]]; then
  printf 'Training already completed. Verifying the saved result without retraining.\n'
  uv run spireshift model verify-starting-evidence-policy "${spireshift_arguments[@]}"
  exit 0
fi
if [[ -e "$spireshift_checkpoint" || -e "$spireshift_training_report" ]]; then
  printf 'Incomplete saved result in %s; preserved without overwriting. Share the previous output before retrying.\n' "$spireshift_model_root" >&2
  exit 1
fi

# Interrupted attempts keep their resource reports; never reuse an existing report path.
spireshift_attempt=1
while [[ -e "artifacts/resources/starting-evidence-policy-base-v8-train-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Training one starting-choice adjustment (10-minute training cap). Saved-input verification runs first.\n'
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/starting-evidence-policy-base-v8-train-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_model_root" \
  --workers 1 \
  --max-wall-seconds 600 \
  --max-cpu-seconds 1200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 4000000000 \
  -- \
  uv run spireshift model finetune-starting-evidence-policy "${spireshift_arguments[@]}"

printf 'Training finished. Checking the saved result against the original data; no retraining or game attempts.\n'
uv run spireshift model verify-starting-evidence-policy "${spireshift_arguments[@]}"
