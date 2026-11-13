#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe="${1:-configs/native-compatibility/sts2-v0.111.0-a8-input-layout-offline-v5.json}"
settings="$(uv run --no-sync python - "$recipe" <<'PY'
import json, sys
c=json.load(open(sys.argv[1]))
print(c['workspace']); print(c['stage'])
print(c['session_limits']['wall_seconds']); print(c['session_limits']['cpu_seconds'])
PY
)"
workspace="$(printf '%s\n' "$settings" | sed -n '1p')"
stage="$(printf '%s\n' "$settings" | sed -n '2p')"
wall="$(printf '%s\n' "$settings" | sed -n '3p')"
cpu="$(printf '%s\n' "$settings" | sed -n '4p')"
if [[ "$stage" == "saved_only_checks" ]]; then
  module="spireshift.native_layout_audit_v3"
  printf '%s\n' 'Checking saved public layouts, reversible mappings and unchanged players. No games or fitting.'
else
  module="spireshift.native_live_checkpoint_v6"
  printf '%s\n' \
    'Checking matching public inputs and actual canonical seeds with unchanged players. One shared app.' \
    'Close STS2. No fitting or promotion. Repeat after a clean pause to reuse completed pairs.' \
    'Only explicit stale reads refresh. Submitted actions are never retried; uncertain attempts stay preserved.'
fi
stem="$(basename "$recipe" .json)"
attempt=1
while [[ -e "artifacts/resources/${stem}-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
uv run --no-sync spireshift resources run \
  --kind other --report "artifacts/resources/${stem}-attempt-${attempt}.json" \
  --artifact-root "$workspace" --workers 1 \
  --max-wall-seconds "$wall" --max-cpu-seconds "$cpu" \
  --max-memory-bytes 4000000000 --max-storage-bytes 1000000000 \
  -- uv run --no-sync python -m "$module" "$recipe"
