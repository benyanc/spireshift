#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_event_audit_config=configs/backend-repair/sts2-v0.107.1-event-integration-audit-v1.json
spireshift_event_audit_output=artifacts/compatibility/full-run-event-integration-v1
if [[ -f "$spireshift_event_audit_output/integration-audit.json" ]]; then
  printf 'Audit saved. Checking the result; no game replays or training.\n'
  uv run spireshift full-run show-event-integration "$spireshift_event_audit_config"
  exit 0
fi

spireshift_event_audit_attempt=1
while [[ -e "artifacts/resources/full-run-event-integration-v1-attempt-$spireshift_event_audit_attempt.json" || -e "artifacts/resources/full-run-event-integration-v1-attempt-$spireshift_event_audit_attempt-metrics.json" ]]; do
  spireshift_event_audit_attempt=$((spireshift_event_audit_attempt + 1))
done
printf 'Replaying all 89 inspected training failures, including four corrected event endpoints.\n'
printf 'Expected time: about two minutes. Hard cap: four minutes and 240 CPU seconds.\n'
printf 'One worker, 8 GB memory, 2 GB artifacts. No training, admission or automatic follow-up.\n'
uv run spireshift resources run \
  --kind rollout \
  --report "artifacts/resources/full-run-event-integration-v1-attempt-$spireshift_event_audit_attempt.json" \
  --metrics "artifacts/resources/full-run-event-integration-v1-attempt-$spireshift_event_audit_attempt-metrics.json" \
  --artifact-root "$spireshift_event_audit_output" \
  --workers 1 \
  --max-wall-seconds 240 \
  --max-cpu-seconds 240 \
  --max-storage-bytes 2000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift full-run audit-event-integration "$spireshift_event_audit_config"
