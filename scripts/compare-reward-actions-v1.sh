#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
batch_root="artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/reward-bridges-v8"
resource_report="artifacts/resources/reward-comparisons-v1.json"
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
batch_config="configs/engine-qualification/sts2-v0.111.0-reward-bridges-v8.json"

node_runtime="${SPIRESHIFT_NODE:-${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
if [[ ! -x "$node_runtime" ]]; then
  node_runtime="$(command -v node || true)"
fi
if [[ ! -x "$node_runtime" ]]; then
  printf '%s\n' 'No usable Node runtime found. Set SPIRESHIFT_NODE to its absolute path.'
  exit 1
fi

if [[ -f "$batch_root/batch.json" ]]; then
  printf '%s\n' 'This batch already has a saved result. Displaying it; no games follow.'
  uv run python - "$batch_root/batch.json" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({key: result.get(key) for key in (
    "status", "planned_cases", "completed_cases", "failed_cases", "not_attempted_cases",
    "independent_seeds", "seed_scenario_pairs", "repeated_public_prefixes_identical",
    "wall_seconds", "error", "full_run_attempts", "training_allowed", "report_id",
)}, indent=2))
sys.exit(0 if result["status"] == "reward_comparisons_pass" else 1)
PY
  uv run spireshift engine verify-reward-bridges "$qualification" "$batch_config" --node "$node_runtime"
  exit 0
fi
if [[ -e "$batch_root" || -e "$resource_report" ]]; then
  printf '%s\n' 'An earlier attempt is incomplete. Preserve its files and share the output; no restart follows.'
  exit 1
fi

printf '%s\n' 'Checking space and pinned inputs before creating this fresh reward batch; no games run during preflight.'
uv run spireshift engine preflight-reward-bridges "$qualification" "$batch_config" --node "$node_runtime"

printf '%s\n' \
  'Comparing Calling Bell and Cauldron pickup/claims: four A8 seed/scenario pairs, each twice.' \
  'Expected duration: 6–9 minutes. Limits: 15 minutes, 8 GB memory, 6 GB files including the app pool.' \
  'Close any running STS2 game. One fixed app is reused; each check gets a fresh small save profile.' \
  'Checks cover the curse, relic claims, reward skipping, a full potion belt, discard/replacement and tutorial confirmations.' \
  'These are declared serialized test fixtures, not naturally completed runs or learning data.' \
  'First difference stops the batch. Interrupted/changed apps block reuse; evidence stays preserved.' \
  'No full runs, training, automatic restart or next experiment follow.'

uv run spireshift resources run \
  --kind other \
  --report "$resource_report" \
  --artifact-root "$batch_root" \
  --artifact-root artifacts/engine-working-apps \
  --workers 1 \
  --max-wall-seconds 900 \
  --max-cpu-seconds 1800 \
  --max-storage-bytes 6000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run spireshift engine compare-reward-bridges "$qualification" "$batch_config" \
    --node "$node_runtime" --output "$batch_root/summary.json"

printf '%s\n' 'Comparisons finished. Rechecking saved evidence; no game launch or training follows.'
uv run spireshift engine verify-reward-bridges "$qualification" "$batch_config" \
  --node "$node_runtime" --output "$batch_root/saved-verification.json"
printf '%s\n' 'Share the comparison and saved-verification summaries above; no next stage follows.'
