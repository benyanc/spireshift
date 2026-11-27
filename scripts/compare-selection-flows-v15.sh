#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
printf '%s\n' 'Checking the repaired CLI reward/map ownership against the unchanged official-game bridge.' \
  'Three fully completed cases are declared regressions under the new build; the stopped case uses fresh world 416.' \
  'Close STS2. One fixed app, isolated profiles. Both players and all Adam state remain unchanged.' \
  'Expect about 15–25 minutes. Ten minutes per pair plus shutdown reserve; 90-minute outer cap.' \
  'Previous results and markers remain preserved. No uncertain world is replayed; no training or automatic next stage follows.'
recipe="configs/native-compatibility/sts2-v0.111.0-a8-reward-map-panel-v1.json"
workspace="$(uv run --no-sync python - "$recipe" <<'PY'
import json, sys
from pathlib import Path
cfg = json.loads(Path(sys.argv[1]).read_text())
path = Path(cfg['workspace'])
if not path.resolve().is_relative_to(Path.cwd() / 'artifacts/native-selection-flows'):
    raise SystemExit('Invalid panel workspace')
print(path)
PY
)"
attempt=1
while [[ -e "artifacts/resources/reward-map-panel-v1-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/reward-map-panel-v1-attempt-${attempt}.json" \
  --artifact-root "$workspace" \
  --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 5400 --max-cpu-seconds 14400 --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python scripts/modal-panel-session-v3.py "$recipe"
