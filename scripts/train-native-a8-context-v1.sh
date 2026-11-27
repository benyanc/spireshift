#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_recipe="${1:-configs/native-controls/action-context-native-comparison-v1.json}"
spireshift_qualification=configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json
spireshift_node="${SPIRESHIFT_NODE:-/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
IFS=$'\t' read -r spireshift_workspace spireshift_stage spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run --no-sync python - "$spireshift_recipe" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
limits = recipe["resource_limits"]
print("\t".join(str(v) for v in (recipe["workspace"], recipe["stage"],
    limits["wall_seconds"], limits["cpu_seconds"], limits["storage_bytes"],
    limits["resident_memory_bytes"])))
PY
)
if [[ -f "$spireshift_workspace/report.json" ]]; then
  printf 'Checking the saved native context result; no games or fitting follow.\n'
  uv run --no-sync python -m spireshift.native_context_trial \
    "$spireshift_qualification" "$spireshift_recipe" --node "$spireshift_node"
  exit 0
fi
if [[ -e "$spireshift_workspace" || -L "$spireshift_workspace" ]]; then
  printf 'Preserve unfinished evidence at %s; no automatic restart or seed replay.\n' "$spireshift_workspace" >&2
  exit 1
fi
uv run --no-sync python -m spireshift.native_context_trial \
  "$spireshift_qualification" "$spireshift_recipe" --node "$spireshift_node" --preflight
if [[ "$spireshift_stage" == short_bridge_control ]]; then
  printf 'Checking native inference, sealed on-policy experience and fitting: eight games, two workers.\n'
  printf 'Expected under two minutes; three-minute cap. No larger trial follows.\n'
else
  printf 'Comparing original and situation-by-action inputs on Ironclad/A8, two training seeds.\n'
  printf '640 total planned games: four rounds of 32 per player, plus 16 starting and 16 final development games.\n'
  printf 'Both start with identical action probabilities. Same score, menus, seeds and PPO settings; actual work is reported.\n'
  printf 'Expected 25-40 minutes; one-hour cap, two workers, 4 GB memory and 6 GB generated files.\n'
fi
printf 'Close any running game. Shared frozen inputs are reused; no game app copies or automatic promotion.\n'
spireshift_name=$(basename "$spireshift_workspace")
spireshift_attempt=1
while [[ -e "artifacts/resources/$spireshift_name-attempt-$spireshift_attempt.json" || -L "artifacts/resources/$spireshift_name-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
uv run --no-sync spireshift resources run \
  --kind training \
  --report "artifacts/resources/$spireshift_name-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers 2 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- uv run --no-sync python -m spireshift.native_context_trial \
    "$spireshift_qualification" "$spireshift_recipe" --node "$spireshift_node"
