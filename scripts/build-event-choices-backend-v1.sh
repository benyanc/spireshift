#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_choice_config=configs/backend-repair/sts2-v0.107.1-event-choices-v3.json
spireshift_choice_output=artifacts/backend-repair/event-choices-v1-retry2
spireshift_choice_candidate=artifacts/backend/evangambit-v0.107.1-full-run-repair-v4-retry2
if [[ -f "$spireshift_choice_output/build-report.json" ]]; then
  printf 'Event choice build already complete. Checking the saved result; no rebuild or training.\n'
  uv run spireshift full-run show-backend-repair "$spireshift_choice_config"
  exit 0
fi

spireshift_choice_attempt=1
while [[ -e "artifacts/resources/event-choices-backend-v1-attempt-$spireshift_choice_attempt.json" || -e "artifacts/resources/event-choices-backend-v1-attempt-$spireshift_choice_attempt-metrics.json" ]]; do
  spireshift_choice_attempt=$((spireshift_choice_attempt + 1))
done
printf 'Checking 109 captured event choice lists, 99 captured outcomes and 32 repair regressions.\n'
printf 'Expected build: seconds, based on three saved native builds; hard cap: four minutes.\n'
uv run spireshift resources run \
  --kind teacher_generation \
  --report "artifacts/resources/event-choices-backend-v1-attempt-$spireshift_choice_attempt.json" \
  --metrics "artifacts/resources/event-choices-backend-v1-attempt-$spireshift_choice_attempt-metrics.json" \
  --artifact-root "$spireshift_choice_output" \
  --artifact-root "$spireshift_choice_candidate" \
  --workers 2 \
  --max-wall-seconds 240 \
  --max-cpu-seconds 960 \
  --max-storage-bytes 4000000000 \
  --max-memory-bytes 12000000000 \
  -- \
  uv run spireshift full-run build-backend-repair "$spireshift_choice_config"
