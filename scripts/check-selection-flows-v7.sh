#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe="${1:-configs/native-compatibility/sts2-v0.111.0-a8-selection-owner-read-offline-v3.json}"
launch="${2:-}"
readarray_compat="$(uv run --no-sync python - "$recipe" "$launch" <<'PY'
import json,sys
from pathlib import Path
from spireshift.native_launch_limits import load_launch
root=Path.cwd();p=Path(sys.argv[1]);c=json.loads(p.read_text())
if c['stage']=='saved_only_checks': wall,cpu=240,480
else:
 if not sys.argv[2]: raise SystemExit('Supply the separately versioned launch budget')
 limits=load_launch(root,Path(sys.argv[2]).resolve(),p.resolve(),c);wall,cpu=limits.wall_seconds,limits.cpu_seconds
print(c['workspace']);print(c['stage']);print(wall);print(cpu)
PY
)"
workspace="$(printf '%s\n' "$readarray_compat" | sed -n '1p')"
stage="$(printf '%s\n' "$readarray_compat" | sed -n '2p')"
wall="$(printf '%s\n' "$readarray_compat" | sed -n '3p')"
cpu="$(printf '%s\n' "$readarray_compat" | sed -n '4p')"
if [[ "$stage" == saved_only_checks ]]; then module=spireshift.native_flow_audit_v7; else module=spireshift.native_flow_live_v7; fi
runner=(uv run --no-sync python -m "$module" "$recipe")
if [[ "$stage" != saved_only_checks ]]; then runner+=(--launch "$launch"); fi
stem="$(basename "$recipe" .json)"; attempt=1
while [[ -e "artifacts/resources/${stem}-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/${stem}-attempt-${attempt}.json" --artifact-root "$workspace" --workers 1 \
  --max-wall-seconds "$wall" --max-cpu-seconds "$cpu" --max-memory-bytes 4000000000 --max-storage-bytes 1000000000 \
  -- "${runner[@]}"
