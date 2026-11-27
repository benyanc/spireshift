#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe="${1:-configs/native-compatibility/sts2-v0.111.0-a8-interface-control-v1.json}"
limits="$(uv run --no-sync python - "$recipe" <<'PY'
import json, sys
c=json.load(open(sys.argv[1])); print(c['workspace'])
print(c['session_limits']['wall_seconds']); print(c['session_limits']['cpu_seconds'])
PY
)"
workspace="$(printf '%s\n' "$limits" | sed -n '1p')"
wall="$(printf '%s\n' "$limits" | sed -n '2p')"
cpu="$(printf '%s\n' "$limits" | sed -n '3p')"
stem="$(basename "$recipe" .json)"
attempt=1
while [[ -e "artifacts/resources/${stem}-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
printf '%s\n' \
  'Checking the consolidated public interface with both frozen players; no fitting.' \
  'Close STS2. One fixed app is reused, with separate profiles and exact receipts.' \
  'Completed pairs are reused. Repeat this command after a clean pause.' \
  'Unknown/uncertain actions are preserved, never guessed or resubmitted.'
set +e
uv run --no-sync spireshift resources run \
  --kind other --report "artifacts/resources/${stem}-attempt-${attempt}.json" \
  --artifact-root "$workspace" --workers 1 \
  --max-wall-seconds "$wall" --max-cpu-seconds "$cpu" \
  --max-memory-bytes 4000000000 --max-storage-bytes 1000000000 \
  -- uv run --no-sync python -m spireshift.native_live_checkpoint_v2 "$recipe"
run_status=$?
set -e
if [[ -f "$workspace/report.json" ]]; then
  printf '%s\n' 'Checking all saved public frames for grouped gaps; no new games.'
  uv run --no-sync python -m spireshift.native_interface_audit "$recipe" --from-live
fi
exit "$run_status"
