#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only: all 64 inspected attempts, one worker, no search or training.
spireshift_diagnostic_root=artifacts/diagnostics/sts2-v0.107.1-base-v10-combat-confirmation-v1
spireshift_diagnostic_config=configs/combat-replay-diagnostic/sts2-v0.107.1-base-v10-confirmation-v1.json
spireshift_diagnostic_report="$spireshift_diagnostic_root/diagnostic.json"
if [[ -L "$spireshift_diagnostic_report" || ( -e "$spireshift_diagnostic_report" && ! -f "$spireshift_diagnostic_report" ) ]]; then
  printf 'Refusing to replace existing diagnostic output: %s\n' "$spireshift_diagnostic_report" >&2
  exit 1
fi
if [[ -f "$spireshift_diagnostic_report" ]]; then
  printf 'Diagnosis already saved. Checking it; no games or training follow.\n'
  uv run spireshift model show-combat-confirmation-diagnosis "$spireshift_diagnostic_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir "$spireshift_diagnostic_root"
  exit 0
fi
spireshift_diagnostic_attempt=1
while [[ -e "artifacts/resources/combat-confirmation-base-v10-diagnostic-v1-attempt-$spireshift_diagnostic_attempt.json" || -L "artifacts/resources/combat-confirmation-base-v10-diagnostic-v1-attempt-$spireshift_diagnostic_attempt.json" || -e "artifacts/resources/combat-confirmation-base-v10-diagnostic-v1-attempt-$spireshift_diagnostic_attempt-metrics.json" || -L "artifacts/resources/combat-confirmation-base-v10-diagnostic-v1-attempt-$spireshift_diagnostic_attempt-metrics.json" ]]; do
  spireshift_diagnostic_attempt=$((spireshift_diagnostic_attempt + 1))
done
printf 'Diagnosing the same 64 attempts: one worker, 10-minute job cap. No training or automatic follow-up.\n'
uv run spireshift resources run \
  --kind rollout \
  --report "artifacts/resources/combat-confirmation-base-v10-diagnostic-v1-attempt-$spireshift_diagnostic_attempt.json" \
  --metrics "artifacts/resources/combat-confirmation-base-v10-diagnostic-v1-attempt-$spireshift_diagnostic_attempt-metrics.json" \
  --artifact-root "$spireshift_diagnostic_root" \
  --workers 1 \
  --max-wall-seconds 600 \
  --max-cpu-seconds 1200 \
  --max-storage-bytes 250000000 \
  --max-memory-bytes 4000000000 \
  -- \
  uv run --extra evangambit spireshift model diagnose-combat-confirmation "$spireshift_diagnostic_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --output-dir "$spireshift_diagnostic_root" \
    --resume
