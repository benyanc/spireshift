#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

batch_root="artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/shop-bridges-v1"
resource_report="artifacts/resources/shop-comparisons-v1.json"

if [[ -f "$batch_root/batch.json" ]]; then
  printf '%s\n' 'This batch already has a saved result. Displaying it; no new checks follow.'
  uv run python - "$batch_root/batch.json" <<'PY'
import json
import sys
from pathlib import Path
result = json.loads(Path(sys.argv[1]).read_text())
print(json.dumps({key: result.get(key) for key in (
    "status", "planned_cases", "completed_cases", "failed_cases", "not_attempted_cases",
    "independent_seeds", "seed_scenario_pairs", "repeated_public_prefixes_identical",
    "potion_tutorial_steps", "fresh_profile_required",
    "wall_seconds", "failed_case", "error", "privileged_fixture",
    "full_run_attempts", "training_allowed", "report_id",
)}, indent=2))
sys.exit(0 if result["status"] == "shop_comparisons_pass" else 1)
PY
  exit 0
fi

if [[ -e "$batch_root/in-progress.json" || -e "$resource_report" ||
      -e "$batch_root/summary.json" ]]; then
  printf '%s\n' 'An earlier attempt is incomplete. Its files are preserved; no restart follows.'
  printf '%s\n' 'Share the saved output so the failure can be assessed before another batch.'
  exit 1
fi

node_runtime="${SPIRESHIFT_NODE:-${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
if [[ ! -x "$node_runtime" ]]; then
  node_runtime="$(command -v node || true)"
fi
if [[ ! -x "$node_runtime" ]]; then
  printf '%s\n' 'No usable Node runtime found. Set SPIRESHIFT_NODE to its absolute path.'
  exit 1
fi

printf '%s\n' \
  'Comparing ordinary shops and Courier restocking on two A8 seeds, twice each: eight checks.' \
  'Expected duration: 8–12 minutes. Limits: 15 minutes, 8 GB memory, 4 GB generated files.' \
  'Close any running STS2 game. One disposable game runs at a time; each result prints.' \
  'The test uses an injected single-Strike, 1,000-gold shop fixture, with or without Courier.' \
  'It buys cards and potions, fills both potion slots, cancels/reopens removal, confirms it and exits.' \
  'Each settings-only profile has no copied tutorial progress. The first-potion popup must be clicked.' \
  'This measures those mechanics, not naturally reached rooms or player strength. Allow 3.5 GB free.' \
  'The first difference stops the batch and preserves its copy. Successful copies are removed after verification.' \
  'Reports, logs, profiles and saves remain. No full runs, training or automatic next stage follow.'

uv run spireshift resources run \
  --kind other \
  --report "$resource_report" \
  --artifact-root "$batch_root" \
  --workers 1 \
  --max-wall-seconds 900 \
  --max-cpu-seconds 1800 \
  --max-storage-bytes 4000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run spireshift engine compare-shop-bridges \
    configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json \
    configs/engine-qualification/sts2-v0.111.0-shop-bridges-v1.json \
    --node "$node_runtime" \
    --output "$batch_root/summary.json"

printf '%s\n' 'Shop comparisons finished. Share the summary above; no next stage follows.'
