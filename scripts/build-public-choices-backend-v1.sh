#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_choice_config=configs/backend-repair/sts2-v0.107.1-public-choices-v1.json
spireshift_choice_output=artifacts/backend-repair/public-choices-v1
spireshift_choice_candidate=artifacts/backend/evangambit-v0.107.1-full-run-repair-v2
if [[ -f "$spireshift_choice_output/build-report.json" ]]; then
  printf 'Public-choice build already complete. Checking its saved result; no rebuild or training.\n'
  uv run spireshift full-run show-backend-repair "$spireshift_choice_config"
  exit 0
fi

spireshift_choice_attempt=1
while [[ -e "artifacts/resources/public-choices-backend-v1-attempt-$spireshift_choice_attempt.json" || -L "artifacts/resources/public-choices-backend-v1-attempt-$spireshift_choice_attempt.json" || -e "artifacts/resources/public-choices-backend-v1-attempt-$spireshift_choice_attempt-metrics.json" || -L "artifacts/resources/public-choices-backend-v1-attempt-$spireshift_choice_attempt-metrics.json" ]]; do
  spireshift_choice_attempt=$((spireshift_choice_attempt + 1))
done
printf 'Building the separate public-menu repair; all 23 synthetic regressions are required.\n'
printf 'Caps: 30 minutes elapsed, 7,200 CPU seconds, 12 GB memory, 4 GB artifacts.\n'
printf 'The native capability check makes zero game attempts. No training or automatic admission follows.\n'
uv run spireshift resources run \
  --kind teacher_generation \
  --report "artifacts/resources/public-choices-backend-v1-attempt-$spireshift_choice_attempt.json" \
  --metrics "artifacts/resources/public-choices-backend-v1-attempt-$spireshift_choice_attempt-metrics.json" \
  --artifact-root "$spireshift_choice_output" \
  --artifact-root "$spireshift_choice_candidate" \
  --workers 2 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 4000000000 \
  --max-memory-bytes 12000000000 \
  -- \
  uv run spireshift full-run build-backend-repair "$spireshift_choice_config"
