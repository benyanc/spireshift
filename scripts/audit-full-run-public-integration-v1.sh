#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_integration_config=configs/backend-repair/sts2-v0.107.1-public-integration-audit-v1.json
spireshift_integration_output=artifacts/compatibility/full-run-public-integration-v1
if [[ -f "$spireshift_integration_output/integration-audit.json" ]]; then
  printf 'Compatibility audit already complete. Checking its saved result; no game replays or training.\n'
  uv run spireshift full-run show-public-integration "$spireshift_integration_config"
  exit 0
fi

spireshift_integration_attempt=1
while [[ -e "artifacts/resources/full-run-public-integration-v1-attempt-$spireshift_integration_attempt.json" || -L "artifacts/resources/full-run-public-integration-v1-attempt-$spireshift_integration_attempt.json" || -e "artifacts/resources/full-run-public-integration-v1-attempt-$spireshift_integration_attempt-metrics.json" || -L "artifacts/resources/full-run-public-integration-v1-attempt-$spireshift_integration_attempt-metrics.json" ]]; do
  spireshift_integration_attempt=$((spireshift_integration_attempt + 1))
done
printf 'Checking all 89 previously failed training attempts with the repaired player.\n'
printf 'Caps: one worker, 30 minutes elapsed, 3,600 CPU seconds, 8 GB memory, 2 GB artifacts.\n'
printf 'Saved partial cases resume exactly; all remaining failures stay in the report.\n'
printf 'No training, promotion, admission or automatic follow-up.\n'
uv run spireshift resources run \
  --kind rollout \
  --report "artifacts/resources/full-run-public-integration-v1-attempt-$spireshift_integration_attempt.json" \
  --metrics "artifacts/resources/full-run-public-integration-v1-attempt-$spireshift_integration_attempt-metrics.json" \
  --artifact-root "$spireshift_integration_output" \
  --workers 1 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 3600 \
  --max-storage-bytes 2000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift full-run audit-public-integration "$spireshift_integration_config"
