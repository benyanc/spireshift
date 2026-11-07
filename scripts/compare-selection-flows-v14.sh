#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
printf '%s\n' 'Reusing the completed 57-choice comparison; continuing only the three unstarted cases.' \
  'Close STS2. One fixed app, isolated profiles. Both players and all Adam state stay unchanged.' \
  'Expect about 15–25 minutes. Ten minutes per pair plus shutdown reserve; 90-minute outer cap.' \
  'The original failed summary and marker stay preserved. No completed or uncertain game is replayed.' \
  'No training, promotion or automatic next stage follows.'
recipe="configs/native-compatibility/sts2-v0.111.0-a8-map-settling-panel-v2.json"
mapfile_paths="$(uv run --no-sync python - "$recipe" <<'PY'
import json, sys
from pathlib import Path
from spireshift.native_compatibility_contract import verified
root = Path.cwd()
cfg = json.loads(Path(sys.argv[1]).read_text())
parent = json.loads(verified(root, cfg['parent_plan']).read_text())
for workspace in [cfg['workspace'], parent['workspace']]:
    path = Path(workspace)
    if not path.resolve().is_relative_to(root / 'artifacts/native-selection-flows'):
        raise SystemExit('Invalid panel workspace')
    print(path)
PY
)"
workspace="${mapfile_paths%%$'\n'*}"
case_workspace="${mapfile_paths#*$'\n'}"
attempt=1
while [[ -e "artifacts/resources/map-settling-panel-v2-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/map-settling-panel-v2-attempt-${attempt}.json" \
  --artifact-root "$workspace" --artifact-root "$case_workspace" \
  --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 5400 --max-cpu-seconds 14400 --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python scripts/modal-panel-session-v2.py "$recipe"
