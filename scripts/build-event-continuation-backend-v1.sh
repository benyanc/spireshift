#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_event_config=configs/backend-repair/sts2-v0.107.1-event-continuation-v1.json
spireshift_event_output=artifacts/backend-repair/event-continuation-v1-retry1
spireshift_event_candidate=artifacts/backend/evangambit-v0.107.1-full-run-repair-v3-retry1
if [[ -f "$spireshift_event_output/build-report.json" ]]; then
  printf 'Event repair build already complete. Checking its saved result; no rebuild or training.\n'
  uv run spireshift full-run show-backend-repair "$spireshift_event_config"
  exit 0
fi

spireshift_event_attempt=1
while [[ -e "artifacts/resources/event-continuation-backend-v1-attempt-$spireshift_event_attempt.json" || -L "artifacts/resources/event-continuation-backend-v1-attempt-$spireshift_event_attempt.json" || -e "artifacts/resources/event-continuation-backend-v1-attempt-$spireshift_event_attempt-metrics.json" || -L "artifacts/resources/event-continuation-backend-v1-attempt-$spireshift_event_attempt-metrics.json" ]]; do
  spireshift_event_attempt=$((spireshift_event_attempt + 1))
done
printf 'Building the event continuation repair; all 32 regressions are required.\n'
printf 'Caps: 30 minutes elapsed, 7,200 CPU seconds, 12 GB memory, 4 GB artifacts.\n'
printf 'The capability check makes zero game attempts. No training or automatic follow-up.\n'
uv run spireshift resources run \
  --kind teacher_generation \
  --report "artifacts/resources/event-continuation-backend-v1-attempt-$spireshift_event_attempt.json" \
  --metrics "artifacts/resources/event-continuation-backend-v1-attempt-$spireshift_event_attempt-metrics.json" \
  --artifact-root "$spireshift_event_output" \
  --artifact-root "$spireshift_event_candidate" \
  --workers 2 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 4000000000 \
  --max-memory-bytes 12000000000 \
  -- \
  uv run spireshift full-run build-backend-repair "$spireshift_event_config"
