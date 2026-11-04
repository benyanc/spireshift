#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
plan="configs/native-compatibility/sts2-v0.111.0-a8-broader-panel-v1.json"
mapfile_compat="$(uv run --no-sync python - "$plan" <<'PY'
import json,sys
from pathlib import Path
root=Path.cwd(); plan=json.loads(Path(sys.argv[1]).read_text())
cfg=json.loads((root/plan['recipe']['path']).read_text())
for name in (plan['workspace'],cfg['workspace']):
 p=Path(name)
 if p.is_absolute() or not (root/p).resolve().is_relative_to(root/'artifacts/native-selection-flows'):
  raise SystemExit('Invalid broader compatibility workspace')
 print(name)
PY
)"
coordination="$(printf '%s\n' "$mapfile_compat" | sed -n '1p')"
workspace="$(printf '%s\n' "$mapfile_compat" | sed -n '2p')"
printf '%s\n' 'Close STS2. This checks the same qualified build on two fresh worlds and both frozen players.' \
  'Four pairs, up to 128 choices per host or a genuine ending; one fixed app and isolated profiles.' \
  'Expect about 20–35 minutes. The 90-minute outer cap includes checks and saved verification.' \
  'Completed units are reused after a clean pause. Uncertain attempts stop without retry.' \
  'No training, model promotion or automatic next experiment follows.'
attempt=1
while [[ -e "artifacts/resources/broader-compatibility-v1-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/broader-compatibility-v1-attempt-${attempt}.json" \
  --artifact-root "$coordination" --artifact-root "$workspace" \
  --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 5400 --max-cpu-seconds 14400 \
  --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python -m spireshift.native_broader_compatibility_v1 "$plan" --run
