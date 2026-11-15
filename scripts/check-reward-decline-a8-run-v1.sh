#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
qualification="configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json"
recipe="configs/engine-qualification/sts2-v0.111.0-natural-shipped-a8-reward-decline-v1.json"
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--preflight-only" ) ]]; then
  printf '%s\n' 'Only --preflight-only is supported.'; exit 1
fi
node_runtime="${SPIRESHIFT_NODE:-${HOME}/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
if [[ ! -x "$node_runtime" ]]; then node_runtime="$(command -v node || true)"; fi
if [[ ! -x "$node_runtime" ]]; then printf '%s\n' 'Set SPIRESHIFT_NODE to an available Node runtime.'; exit 1; fi
recipe_fields=()
while IFS= read -r line; do recipe_fields+=("$line"); done < <(uv run python - "$recipe" <<'PY'
import json,sys
from pathlib import Path
recipe=json.loads(Path(sys.argv[1]).read_text())
first=json.loads(Path(recipe["cases"][0]["recipe"]).read_text())
policy=json.loads(Path(first["working_app_config"]).read_text())
print(recipe["workspace"])
print(recipe["resource_report"])
print(Path(policy["workspace"]).parent)
for key in ("max_wall_seconds","max_cpu_seconds","max_storage_bytes","max_memory_bytes"):
    print(recipe["resource_caps"][key])
PY
)
if [[ ${#recipe_fields[@]} -ne 7 ]]; then printf '%s\n' 'Could not read the pinned discovery recipe.'; exit 1; fi
run_root="${recipe_fields[0]}"
resource_report="${recipe_fields[1]}"
pool_root="${recipe_fields[2]}"
if [[ -f "$run_root/summary.json" ]]; then
  printf '%s\n' 'This discovery batch has a saved result. Auditing it; no new games follow.'
  uv run spireshift engine verify-natural-discovery "$qualification" "$recipe" --node "$node_runtime"
  exit 0
fi
if [[ -e "$run_root" || -e "$resource_report" ]]; then
  printf '%s\n' 'An earlier attempt is interrupted. Preserve its files for inspection; no automatic retry follows.'
  exit 1
fi
printf '%s\n' 'Checking the repaired seed, fixed app and saved starting reference; no game during preflight.'
uv run spireshift engine preflight-natural-discovery "$qualification" "$recipe" --node "$node_runtime"
if [[ "${1:-}" == "--preflight-only" ]]; then exit 0; fi
printf '%s\n' \
  'Playing one natural Ironclad/A8 diagnostic game on the previously blocked second seed.' \
  'Expected duration: 5–10 minutes. The game has a 15-minute cap; the command cap is 16 minutes.' \
  'Close any running STS2 game. One fixed app is reused; fresh private profiles and all evidence are retained.' \
  'Progress appears every 25 actions. The final case summary includes its ending or explicit failure reason.' \
  'Recoverable missing facts are logged; only existing verified exit/decline controls can continue the game.' \
  'A blocking unknown screen, uncertain delivery, repeated state or cap stops the game and is reported.' \
  'Integrity failures stop the batch. Recovered games do not count as clean passes or training examples.' \
  'Limits: 30 CPU minutes, 8 GB memory, 4 GB tracked storage including the existing shared app/profile area.' \
  'No training, automatic retry or next experiment follows.'
set +e
uv run spireshift resources run --kind rollout --report "$resource_report" \
  --artifact-root "$run_root" --artifact-root "$pool_root" \
  --artifact-root "$HOME/Library/Application Support/SpireShift/engine-profiles" \
  --workers 1 --max-wall-seconds "${recipe_fields[3]}" --max-cpu-seconds "${recipe_fields[4]}" \
  --max-storage-bytes "${recipe_fields[5]}" --max-memory-bytes "${recipe_fields[6]}" -- \
  uv run spireshift engine discover-natural-runs "$qualification" "$recipe" --node "$node_runtime"
run_exit=$?
set -e
if [[ -f "$run_root/summary.json" ]]; then
  printf '%s\n' 'Checking saved cases and the combined issue list; no new games follow.'
  uv run spireshift engine verify-natural-discovery "$qualification" "$recipe" --node "$node_runtime"
fi
printf '%s\n' 'Share the summaries above. No next stage follows.'
exit "$run_exit"
