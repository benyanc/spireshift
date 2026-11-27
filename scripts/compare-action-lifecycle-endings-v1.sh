#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe=configs/native-compatibility/sts2-v0.111.0-a8-action-lifecycle-endings-v1.json
workspace="$(uv run --no-sync python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
p=Path(json.loads(Path(sys.argv[1]).read_text())['workspace'])
if p.is_absolute() or not (Path.cwd()/p).resolve().is_relative_to(Path.cwd()/'artifacts/native-action-lifecycles'):
 raise SystemExit('Invalid tutorial/text ending workspace')
print(p)
PY
)"
printf '%s\n' 'Close STS2. Two fresh natural pairs, one for each original player, under the audited lifecycle and qualified potion completion repairs.' \
  'Original game v0.111.0 / 41cef1ea; CLI56 / Connector29 / worker24 / converter16 / layout12.' \
  'No fixture saves, training, forced outcomes, or retries of historical worlds/actions.' \
  'Allow about 5–15 minutes; 40-minute outer cap includes exact repository checks and saved verification.' \
  'Each pair has ten minutes. Each host keeps 128 gameplay CPU seconds and a 384-choice guard.' \
  'Exact playable inputs/menus, native ending facts, full public reads, summary proof and clean resets are required.' \
  'Limits stay incomplete. Uncertain delivery is preserved. No automatic next experiment follows.'
attempt=1
while [[ -e "artifacts/resources/action-lifecycle-endings-v1-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/action-lifecycle-endings-v1-attempt-${attempt}.json" --artifact-root "$workspace" \
  --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 2400 --max-cpu-seconds 7200 \
  --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python -m spireshift.native_action_lifecycle_endings "$recipe"
