#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe="${1:-configs/native-compatibility/sts2-v0.111.0-a8-live-control-v3.json}"
readarray_fallback="$(uv run --no-sync python - "$recipe" <<'PY'
import json, sys
c=json.load(open(sys.argv[1])); limits=c['session_limits']
print(c['workspace']); print(limits['wall_seconds']); print(limits['cpu_seconds'])
PY
)"
workspace="$(printf '%s\n' "$readarray_fallback" | sed -n '1p')"
wall="$(printf '%s\n' "$readarray_fallback" | sed -n '2p')"
cpu="$(printf '%s\n' "$readarray_fallback" | sed -n '3p')"
stem="$(basename "$recipe" .json)"
attempt=1
while [[ -e "artifacts/resources/${stem}-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
printf '%s\n' \
  'Checking frozen players through the shared input adapter and the official game.' \
  'Close any running game. Profiles are isolated; one fixed app is reused.' \
  'No fitting, optimizer updates, promotion or automatic follow-up.' \
  'Completed pairs are reused. Uncertain attempts are preserved and never retried.'
uv run --no-sync spireshift resources run \
  --kind other --report "artifacts/resources/${stem}-attempt-${attempt}.json" \
  --artifact-root "$workspace" --workers 1 \
  --max-wall-seconds "$wall" --max-cpu-seconds "$cpu" \
  --max-memory-bytes 4000000000 --max-storage-bytes 1000000000 \
  -- uv run --no-sync python -m spireshift.native_live_checkpoint "$recipe"
