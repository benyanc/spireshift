#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
batch_root="artifacts/engine-qualification/sts2-v0.111.0-macos-arm64-v1/bundle-bridges-v2"
resource_report="artifacts/resources/bundle-comparisons-v2.json"
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
batch_config="configs/engine-qualification/sts2-v0.111.0-bundle-bridges-v2.json"

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
    "independent_seeds", "seed_pack_pairs", "repeated_public_prefixes_identical",
    "wall_seconds", "error", "full_run_attempts", "training_allowed", "report_id",
)}, indent=2))
sys.exit(0 if result["status"] == "bundle_comparisons_pass" else 1)
PY
  uv run spireshift engine verify-bundle-bridges "$qualification" "$batch_config" --node "$node_runtime"
  exit 0
fi
if [[ -e "$batch_root" || -e "$resource_report" ]]; then
  printf '%s\n' 'An earlier attempt is incomplete. Preserve its files and share the output; no restart follows.'
  exit 1
fi

printf '%s\n' 'Checking space and pinned inputs before creating this fresh v2 batch; no games run during preflight.'
uv run spireshift engine preflight-bundle-bridges "$qualification" "$batch_config" --node "$node_runtime"

printf '%s\n' \
  'Comparing naturally offered Scroll Boxes packs: two A8 seeds, both packs, each twice.' \
  'Expected duration: 6–8 minutes. Limits: 15 minutes, 8 GB memory, 4 GB generated files.' \
  'Close any running STS2 game. Allow 3.5 GB free. One disposable game runs at a time.' \
  'Each case selects a pack, cancels its preview, reopens and confirms it, then checks the awarded cards.' \
  'The first difference stops the batch. Failed copies and all reports/logs/saves remain preserved.' \
  'Successful copies are removed after verification. No full runs, training or next experiment follow.'

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
  uv run spireshift engine compare-bundle-bridges "$qualification" "$batch_config" \
    --node "$node_runtime" --output "$batch_root/summary.json"

printf '%s\n' 'Comparisons finished. Rechecking saved evidence; no game launch or training follows.'
uv run spireshift engine verify-bundle-bridges "$qualification" "$batch_config" \
  --node "$node_runtime" --output "$batch_root/saved-verification.json"
printf '%s\n' 'Share the comparison and saved-verification summaries above; no next stage follows.'
