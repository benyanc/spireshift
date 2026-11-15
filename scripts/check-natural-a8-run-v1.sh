#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
recipe="configs/engine-qualification/sts2-v0.111.0-natural-shipped-a8-run-v1.json"
node_runtime="${SPIRESHIFT_NODE:-${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
if [[ ! -x "$node_runtime" ]]; then node_runtime="$(command -v node || true)"; fi
if [[ ! -x "$node_runtime" ]]; then
  printf '%s\n' 'Set SPIRESHIFT_NODE to an available Node runtime.'
  exit 1
fi
run_root="$(uv run python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["workspace"])
PY
)"
resource_report="$(uv run python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
print(json.loads(Path(sys.argv[1]).read_text())["resource_report"])
PY
)"
pool_root="$(uv run python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
recipe=json.loads(Path(sys.argv[1]).read_text())
policy=json.loads(Path(recipe["working_app_config"]).read_text())
print(Path(policy["workspace"]).parent)
PY
)"
if [[ -f "$run_root/summary.json" ]]; then
  printf '%s\n' 'This run has a saved result. Auditing it; no new game or retry follows.'
  uv run spireshift engine verify-new-run "$qualification" "$recipe" --node "$node_runtime"
  uv run python - "$run_root/summary.json" <<'PY'
import json,sys
from pathlib import Path
sys.exit(0 if json.loads(Path(sys.argv[1]).read_text())["status"] == "natural_shipped_run_pass" else 1)
PY
  exit 0
fi
if [[ -e "$run_root" || -e "$resource_report" ]]; then
  printf '%s\n' 'An earlier attempt is incomplete. Preserve its files and share the output; no automatic retry follows.'
  exit 1
fi
printf '%s\n' 'Checking the fixed app, exact inputs, saved starting reference and fresh output path; no game during preflight.'
uv run spireshift engine preflight-new-run "$qualification" "$recipe" --node "$node_runtime"
if [[ "${1:-}" == "--preflight-only" ]]; then exit 0; fi
if [[ $# -gt 0 ]]; then printf '%s\n' 'Only --preflight-only is supported.'; exit 1; fi
printf '%s\n' \
  'Playing one natural Ironclad/A8 game through the normal menus with a simple diagnostic policy.' \
  'Expected duration: approximately 5–10 minutes. Game cap: 15 minutes; whole command cap: 16 minutes.' \
  'Limits: 30 CPU minutes, 8 GB memory, 4 GB tracked storage including the existing shared app and profile area.' \
  'Close any running STS2 game. One fixed app is reused with a fresh private profile.' \
  'Progress appears every 25 gameplay actions. An ordinary loss is a valid environment check.' \
  'The first unsupported state or uncertain action stops the run. All evidence is preserved.' \
  'No training, automatic retry, next experiment or admission follows.'
set +e
uv run spireshift resources run \
  --kind rollout --report "$resource_report" \
  --artifact-root "$run_root" --artifact-root "$pool_root" \
  --artifact-root "$HOME/Library/Application Support/SpireShift/engine-profiles" \
  --workers 1 --max-wall-seconds 960 --max-cpu-seconds 1800 \
  --max-storage-bytes 4000000000 --max-memory-bytes 8000000000 -- \
  uv run spireshift engine compare-new-run "$qualification" "$recipe" --node "$node_runtime"
run_exit=$?
set -e
if [[ -f "$run_root/summary.json" ]]; then
  printf '%s\n' 'Rechecking saved observations and action receipts; no new game follows.'
  uv run spireshift engine verify-new-run "$qualification" "$recipe" --node "$node_runtime"
fi
printf '%s\n' 'Share the summaries above. No next stage follows.'
exit "$run_exit"
