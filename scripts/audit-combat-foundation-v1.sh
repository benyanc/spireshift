#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Owner-run only: source verification and data coverage, no engine, optimizer or follow-up.
spireshift_combat_root=artifacts/combat-foundation/sts2-v0.107.1-base-v2-audit-v1
spireshift_combat_report="$spireshift_combat_root/combat-foundation-audit.json"
spireshift_combat_config=configs/combat-foundation/sts2-v0.107.1-base-v2-audit-v1.json
if [[ -L "$spireshift_combat_report" || ( -e "$spireshift_combat_report" && ! -f "$spireshift_combat_report" ) ]]; then
  printf 'Refusing to replace existing audit output: %s\n' "$spireshift_combat_report" >&2
  exit 1
fi
if [[ -f "$spireshift_combat_report" ]]; then
  printf 'Audit already complete. Displaying its saved result; no source audit follows.\n'
  uv run spireshift model show-combat-foundation "$spireshift_combat_report" --config "$spireshift_combat_config"
  exit 0
fi

spireshift_attempt=1
while [[ -e "artifacts/resources/combat-foundation-base-v2-audit-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/combat-foundation-base-v2-audit-v1-attempt-$spireshift_attempt.json" || -e "artifacts/resources/combat-foundation-base-v2-audit-v1-attempt-$spireshift_attempt-metrics.json" || -L "artifacts/resources/combat-foundation-base-v2-audit-v1-attempt-$spireshift_attempt-metrics.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Checking existing combat lessons, one worker, 10-minute cap. No games or training follow.\n'
uv run spireshift resources run \
  --kind other \
  --report "artifacts/resources/combat-foundation-base-v2-audit-v1-attempt-$spireshift_attempt.json" \
  --metrics "artifacts/resources/combat-foundation-base-v2-audit-v1-attempt-$spireshift_attempt-metrics.json" \
  --artifact-root "$spireshift_combat_root" \
  --workers 1 \
  --max-wall-seconds 600 \
  --max-cpu-seconds 1200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 4000000000 \
  -- \
  uv run spireshift model audit-combat-foundation \
    "$spireshift_combat_config" \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --output "$spireshift_combat_report"
