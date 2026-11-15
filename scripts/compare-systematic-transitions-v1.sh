#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe=configs/native-compatibility/sts2-v0.111.0-a8-systematic-owner-v1.json
workspace="$(uv run --no-sync python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
p=Path(json.loads(Path(sys.argv[1]).read_text())['workspace'])
if p.is_absolute() or not (Path.cwd()/p).resolve().is_relative_to(Path.cwd()/'artifacts/native-systematic-comparison'):
 raise SystemExit('Invalid transition workspace')
print(p)
PY
)"
printf '%s\n' 'Close STS2. Four targeted save-based comparisons; no full games or training.' \
  'Rest/Smith and repeated rest choices; Happy Flower cycles from two saved counter values.' \
  'Expect about 5–12 minutes; the 30-minute cap includes repository checks and verification.' \
  'One fixed app, isolated profiles, original game DLL unchanged. Interrupted attempts are never retried.'
attempt=1
while [[ -e "artifacts/resources/systematic-transitions-v1-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/systematic-transitions-v1-attempt-${attempt}.json" \
  --artifact-root "$workspace" \
  --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 1800 --max-cpu-seconds 3600 \
  --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python -m spireshift.native_systematic_panel_v1 "$recipe"
