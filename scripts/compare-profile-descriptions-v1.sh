#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
batch_config="configs/engine-qualification/sts2-v0.111.0-profile-bridges-v1.json"
resource_report="artifacts/resources/profile-description-comparisons-v1.json"
batch_root="$(uv run python - "$batch_config" <<'PY'
import json
import sys
from pathlib import Path
from spireshift.engine_native import _private_path
root = Path.cwd()
print(_private_path(root, json.loads(Path(sys.argv[1]).read_text())["workspace"]).relative_to(root))
PY
)"
node_runtime="${SPIRESHIFT_NODE:-${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
if [[ ! -x "$node_runtime" ]]; then
  node_runtime="$(command -v node || true)"
fi
if [[ ! -x "$node_runtime" ]]; then
  printf '%s\n' 'Set SPIRESHIFT_NODE to an executable local Node runtime.'
  exit 1
fi
if [[ -f "$batch_root/batch.json" ]]; then
  printf '%s\n' 'This profile panel has a saved result; no game attempts follow.'
  uv run python - "$batch_root/batch.json" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({key: result.get(key) for key in (
    "status", "planned_cases", "completed_cases", "failed_cases", "not_attempted_cases",
    "independent_seeds", "repeated_public_prefixes_identical", "error", "wall_seconds", "report_id",
)}, indent=2))
sys.exit(0 if result["status"] == "profile_comparisons_pass" else 1)
PY
  uv run spireshift engine verify-profile-bridges "$qualification" "$batch_config" --node "$node_runtime"
  exit 0
fi
if [[ -e "$batch_root" || -e "$resource_report" ]]; then
  printf '%s\n' 'Preserve this incomplete attempt and share its output; no automatic restart follows.'
  exit 1
fi
uv run spireshift engine preflight-profile-bridges "$qualification" "$batch_config" --node "$node_runtime"
printf '%s\n' \
  'Checking the frozen benchmark profile and public descriptions: four A8 seeds, each twice.' \
  'Expected duration: 5–8 minutes. Cap: 15 minutes, 8 GB memory, 6 GB tracked files.' \
  'Close STS2. One shared app is reused, with a new isolated benchmark progress profile per case.' \
  'This profile is fully unlocked with every act seen; tutorials stay enabled and unseen.' \
  'Each declared inspection fixture contains two assigned potions to verify exact visible descriptions.' \
  'First difference stops. Saved verification follows success; no full run, training or next job follows.'
uv run spireshift resources run \
  --kind other --report "$resource_report" \
  --artifact-root "$batch_root" --artifact-root artifacts/engine-working-apps \
  --workers 1 --max-wall-seconds 900 --max-cpu-seconds 1800 \
  --max-storage-bytes 6000000000 --max-memory-bytes 8000000000 \
  -- uv run spireshift engine compare-profile-bridges "$qualification" "$batch_config" \
     --node "$node_runtime" --output "$batch_root/summary.json"
uv run spireshift engine verify-profile-bridges "$qualification" "$batch_config" \
  --node "$node_runtime" --output "$batch_root/saved-verification.json"
printf '%s\n' 'Share the final comparison and saved-audit summaries; no next stage follows.'
