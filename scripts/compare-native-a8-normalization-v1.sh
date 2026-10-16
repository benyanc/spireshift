#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_comparison=configs/native-normalization/sts2-v0.111.0-a8-comparison-v1.json
spireshift_qualification=configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json
spireshift_node="${SPIRESHIFT_NODE:-/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1

uv run --no-sync python -m spireshift.native_normalization_comparison "$spireshift_comparison"
printf 'Comparing unscaled and normalized inputs on Ironclad/A8: 336 games each, sequentially.\n'
printf 'Both use the same initial numerical weights, cross-fitted action credit, training seeds and PPO rules.\n'
printf 'Scaling can change the starting policy; each method evaluates its own starting and best trained players.\n'
printf 'Expected total: 25-40 minutes; each method has a 30-minute cap, two workers, 4 GB memory and 4 GB output cap.\n'
printf 'Fresh confirmation/development seeds; whole-run victory remains primary.\n'
printf 'One frozen game and shared code are reused; no app copies, automatic promotion or further experiment follows.\n'

for spireshift_arm in unscaled normalized; do
  spireshift_recipe=$(uv run --no-sync python - "$spireshift_comparison" "$spireshift_arm" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    print(json.load(stream)["arms"][sys.argv[2]]["path"])
PY
)
  IFS=$'\t' read -r spireshift_workspace spireshift_workers spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
    uv run --no-sync python - "$spireshift_recipe" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
limits = recipe["resource_limits"]
print("\t".join(str(v) for v in (recipe["workspace"], recipe["workers"],
    limits["wall_seconds"], limits["cpu_seconds"], limits["storage_bytes"],
    limits["resident_memory_bytes"])))
PY
  )
  if [[ -f "$spireshift_workspace/summary.json" ]]; then
    printf '%s method already completed; preserving its saved result.\n' "$spireshift_arm"
    continue
  fi
  if [[ -e "$spireshift_workspace" || -L "$spireshift_workspace" ]]; then
    printf 'Preserve unfinished evidence at %s; no automatic restart.\n' "$spireshift_workspace" >&2
    exit 1
  fi
  spireshift_attempt=1
  while [[ -e "artifacts/resources/native-a8-normalization-$spireshift_arm-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-a8-normalization-$spireshift_arm-v1-attempt-$spireshift_attempt.json" ]]; do
    spireshift_attempt=$((spireshift_attempt + 1))
  done
  printf 'Starting %s method. Each batch reports wins, average floor, best game and failures.\n' "$spireshift_arm"
  uv run --no-sync spireshift resources run \
    --kind training \
    --report "artifacts/resources/native-a8-normalization-$spireshift_arm-v1-attempt-$spireshift_attempt.json" \
    --artifact-root "$spireshift_workspace" \
    --workers "$spireshift_workers" \
    --max-wall-seconds "$spireshift_wall" \
    --max-cpu-seconds "$spireshift_cpu" \
    --max-storage-bytes "$spireshift_storage" \
    --max-memory-bytes "$spireshift_memory" \
    -- uv run --no-sync --extra neural spireshift engine train-native-ppo \
      "$spireshift_qualification" "$spireshift_recipe" --node "$spireshift_node"
done
printf 'Both methods finished. Showing saved development results; no new games follow.\n'
uv run --no-sync python -m spireshift.native_normalization_comparison "$spireshift_comparison"
