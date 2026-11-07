#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
batch_config="configs/engine-qualification/sts2-v0.111.0-combat-effects-bridges-v1.json"
resource_report="artifacts/resources/combat-effects-comparisons-v1.json"
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
  printf '%s\n' 'This combat panel has a saved result; no game attempts follow.'
  uv run python - "$batch_root/batch.json" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({key: result.get(key) for key in (
    "status", "planned_cases", "completed_cases", "failed_cases", "not_attempted_cases",
    "independent_seeds", "seed_scenario_pairs", "repeated_public_prefixes_identical", "error", "wall_seconds", "report_id",
)}, indent=2))
sys.exit(0 if result["status"] == "combat_comparisons_pass" else 1)
PY
  uv run spireshift engine verify-combat-bridges "$qualification" "$batch_config" --node "$node_runtime"
  exit 0
fi
if [[ -e "$batch_root" || -e "$resource_report" ]]; then
  printf '%s\n' 'Preserve this incomplete attempt and share its output; no automatic restart follows.'
  exit 1
fi
uv run spireshift engine preflight-combat-bridges "$qualification" "$batch_config" --node "$node_runtime"
printf '%s\n' \
  'Comparing combat effects: two A8 seeds, two fixtures, each twice.' \
  'Expected duration: 6–9 minutes. Cap: 15 minutes, 8 GB memory, 6 GB tracked files.' \
  'Close STS2. One shared app is reused, with a new isolated benchmark progress profile per case.' \
  'This profile is fully unlocked with every act seen; tutorials stay enabled and unseen.' \
  'Assigned decks/potions and native-obtained Pen Nib test zero-cost skills, exhaust, Strength/Dexterity expiry and counters through turn two.' \
  'First difference stops. Saved verification follows success; no full run, training or next job follows.'
uv run spireshift resources run \
  --kind other --report "$resource_report" \
  --artifact-root "$batch_root" --artifact-root artifacts/engine-working-apps \
  --workers 1 --max-wall-seconds 900 --max-cpu-seconds 1800 \
  --max-storage-bytes 6000000000 --max-memory-bytes 8000000000 \
  -- uv run spireshift engine compare-combat-bridges "$qualification" "$batch_config" \
     --node "$node_runtime" --output "$batch_root/summary.json"
uv run spireshift engine verify-combat-bridges "$qualification" "$batch_config" \
  --node "$node_runtime" --output "$batch_root/saved-verification.json"
printf '%s\n' 'Share the final comparison and saved-audit summaries; no next stage follows.'
