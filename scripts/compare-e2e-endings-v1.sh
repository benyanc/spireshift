#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
recipe=configs/native-compatibility/sts2-v0.111.0-a8-e2e-endings-v1.json
workspace="$(uv run --no-sync python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
p=Path(json.loads(Path(sys.argv[1]).read_text())['workspace'])
if p.is_absolute() or not (Path.cwd()/p).resolve().is_relative_to(Path.cwd()/'artifacts/native-e2e-qualification'):
 raise SystemExit('Invalid natural-ending workspace')
print(p)
PY
)"
printf '%s\n' 'Close STS2. Two natural checkpoint pairs, one per original player, on fresh declared worlds.' \
  'Frozen game/CLI/connector/ordinary worker/converter unchanged. No fixture saves, training or forced outcomes.' \
  'A real ending is required. A choice, time or compute limit remains incomplete.' \
  'Expect about 5–15 minutes; 40-minute outer cap includes checks and raw verification.' \
  'Each pair has 10 minutes; each host keeps the 128 CPU-second budget and a 384-choice guard.' \
  'The terminal result/persistent state/all public reads must match; official Continue must reach its native summary.' \
  'Interrupted or uncertain cases are preserved without retry. No automatic next experiment follows.'
attempt=1
while [[ -e "artifacts/resources/e2e-endings-v1-attempt-${attempt}.json" ]]; do attempt=$((attempt+1)); done
exec uv run --no-sync spireshift resources run --kind other \
  --report "artifacts/resources/e2e-endings-v1-attempt-${attempt}.json" --artifact-root "$workspace" \
  --artifact-root artifacts/engine-working-apps/sts2-v0.111.0-41cef1ea-macos-arm64-v1 \
  --workers 1 --max-wall-seconds 2400 --max-cpu-seconds 7200 \
  --max-memory-bytes 4000000000 --max-storage-bytes 4000000000 \
  -- uv run --no-sync python -m spireshift.native_e2e_live "$recipe"
