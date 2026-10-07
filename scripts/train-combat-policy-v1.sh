#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only. One saved-data verification/training job; no gameplay or follow-up.
spireshift_combat_root=artifacts/models/sts2-v0.107.1-base-v9
spireshift_combat_config=configs/combat-policy/sts2-v0.107.1-base-v2-combat-residual-v1.json
spireshift_combat_checkpoint="$spireshift_combat_root/checkpoint.json"
spireshift_combat_report="$spireshift_combat_root/training-report.json"
for spireshift_result in "$spireshift_combat_checkpoint" "$spireshift_combat_report"; do
  if [[ -L "$spireshift_result" || ( -e "$spireshift_result" && ! -f "$spireshift_result" ) ]]; then
    printf 'Refusing to replace existing training output: %s\n' "$spireshift_result" >&2
    exit 1
  fi
done
if [[ -f "$spireshift_combat_checkpoint" && -f "$spireshift_combat_report" ]]; then
  printf 'Training already complete. Checking its saved result; no source audit or retraining follows.\n'
  uv run spireshift model show-combat-policy-training "$spireshift_combat_root" --config "$spireshift_combat_config"
  exit 0
fi
if [[ -e "$spireshift_combat_checkpoint" || -e "$spireshift_combat_report" ]]; then
  printf 'Partial training result preserved in %s. Share the earlier output before retrying.\n' "$spireshift_combat_root" >&2
  exit 1
fi
spireshift_attempt=1
while [[ -e "artifacts/resources/combat-policy-base-v9-train-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/combat-policy-base-v9-train-v1-attempt-$spireshift_attempt.json" || -e "artifacts/resources/combat-policy-base-v9-train-v1-attempt-$spireshift_attempt-metrics.json" || -L "artifacts/resources/combat-policy-base-v9-train-v1-attempt-$spireshift_attempt-metrics.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Training one combat adjustment from saved lessons: one worker, 30-minute cap. No game attempts or automatic follow-up.\n'
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/combat-policy-base-v9-train-v1-attempt-$spireshift_attempt.json" \
  --metrics "artifacts/resources/combat-policy-base-v9-train-v1-attempt-$spireshift_attempt-metrics.json" \
  --artifact-root "$spireshift_combat_root" \
  --workers 1 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 3600 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run spireshift model train-combat-policy "$spireshift_combat_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --output-dir "$spireshift_combat_root"
