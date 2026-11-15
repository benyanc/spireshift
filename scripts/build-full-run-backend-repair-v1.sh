#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_repair_config=configs/backend-repair/sts2-v0.107.1-full-run-completion-v1.json
spireshift_repair_output=artifacts/backend-repair/full-run-completion-v1
spireshift_repair_candidate=artifacts/backend/evangambit-v0.107.1-full-run-repair-v1
if [[ -f "$spireshift_repair_output/build-report.json" ]]; then
  printf 'Repair build already complete. Checking its saved result; no rebuild or training follows.\n'
  uv run spireshift full-run show-backend-repair "$spireshift_repair_config"
  exit 0
fi

spireshift_repair_attempt=1
while [[ -e "artifacts/resources/full-run-backend-repair-v1-attempt-$spireshift_repair_attempt.json" || -L "artifacts/resources/full-run-backend-repair-v1-attempt-$spireshift_repair_attempt.json" || -e "artifacts/resources/full-run-backend-repair-v1-attempt-$spireshift_repair_attempt-metrics.json" || -L "artifacts/resources/full-run-backend-repair-v1-attempt-$spireshift_repair_attempt-metrics.json" ]]; do
  spireshift_repair_attempt=$((spireshift_repair_attempt + 1))
done
printf 'Testing and building a separate simulator repair. No player training, game batch, or automatic admission.\n'
printf 'The launcher checks the installed test runtime; it needs no machine-wide setting.\n'
printf 'Caps: 30 minutes elapsed, 7,200 CPU seconds, 12 GB memory, 4 GB artifacts. Return the final report for assessment.\n'
uv run spireshift resources run \
  --kind teacher_generation \
  --report "artifacts/resources/full-run-backend-repair-v1-attempt-$spireshift_repair_attempt.json" \
  --metrics "artifacts/resources/full-run-backend-repair-v1-attempt-$spireshift_repair_attempt-metrics.json" \
  --artifact-root "$spireshift_repair_output" \
  --artifact-root "$spireshift_repair_candidate" \
  --workers 2 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 4000000000 \
  --max-memory-bytes 12000000000 \
  -- \
  uv run spireshift full-run build-backend-repair "$spireshift_repair_config"
