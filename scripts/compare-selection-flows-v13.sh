#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
printf '%s\n' 'Checking four targeted compatibility cases with the map-transition guard; both players and Adam stay unchanged.' \
  'Close STS2. One fixed app is reused. Expect about 20–30 minutes; each pair has ten minutes plus a separate shutdown reserve.' \
  'The finite panel has a 90-minute outer cap; exact repository checks have a separate ten-minute allowance.' \
  'Completed controls are reused. Interrupted cases are preserved and never retried. No training or automatic next stage follows.'
recipe="configs/native-compatibility/sts2-v0.111.0-a8-map-settling-panel-v1.json"
workspace="$(uv run --no-sync python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
p=Path(json.loads(Path(sys.argv[1]).read_text())['workspace'])
if not p.resolve().is_relative_to(Path.cwd()/'artifacts/native-selection-flows'):raise SystemExit('Invalid panel workspace')
print(p)
PY
)"
attempt=1
while [[ -e "artifacts/resources/map-settling-panel-v1-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/map-settling-panel-v1-attempt-${attempt}.json" \
  --artifact-root "$workspace" --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 5400 --max-cpu-seconds 14400 --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python scripts/modal-panel-session-v1.py "$recipe"
