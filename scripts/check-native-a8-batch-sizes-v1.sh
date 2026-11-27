#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_recipe=configs/native-gradient/sts2-v0.111.0-a8-frozen-pool-v2.json
spireshift_node="${SPIRESHIFT_NODE:-/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
spireshift_workspace=$(uv run --no-sync python - "$spireshift_recipe" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    print(json.load(stream)["workspace"])
PY
)
if [[ -f "$spireshift_workspace/gradient-report.json" ]]; then
  printf 'Batch checks already complete. Showing saved results; no games or fitting follow.\n'
  uv run --no-sync python -m spireshift.native_gradient_pool analyze "$spireshift_recipe"
  exit 0
fi
if [[ -e "$spireshift_workspace" || -L "$spireshift_workspace" ]]; then
  if [[ ! -f "$spireshift_workspace/summary.json" ]]; then
    printf 'Preserve unfinished collection at %s; no automatic restart.\n' "$spireshift_workspace" >&2
    exit 1
  fi
  uv run --no-sync python - "$spireshift_workspace/summary.json" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    result = json.load(stream)
if result["status"] != "frozen_collection_complete":
    raise SystemExit("Preserve the incomplete collection; no games or analysis follow.")
PY
else
  uv run --no-sync python -m spireshift.native_gradient_pool preflight "$spireshift_recipe"
fi
printf 'Checking batch sizes on 256 fresh Ironclad/A8 TRAIN games with one frozen player.\n'
printf 'Expected total: 15-25 minutes. Collection cap: 20 minutes, two workers, 4 GB memory.\n'
printf 'Analysis cap: 10 minutes, one worker, 8 GB memory. Retained output cap: 2 GB per stage.\n'
printf 'Close any open game. Frozen game/shared code are reused; no app copies.\n'
printf 'This measures independent 32/64/128-game groups. Player weights never change.\n'

for spireshift_stage in collect analyze; do
  if [[ "$spireshift_stage" == collect && -f "$spireshift_workspace/summary.json" ]]; then
    printf 'Collection already complete. Checking saved games; no new attempts.\n'
    continue
  fi
  IFS=$'\t' read -r spireshift_workers spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
    uv run --no-sync python - "$spireshift_recipe" "$spireshift_stage" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
collecting = sys.argv[2] == "collect"
limits = recipe["resource_limits" if collecting else "analysis_limits"]
print("\t".join(str(v) for v in (recipe["workers"] if collecting else 1,
    limits["wall_seconds"], limits["cpu_seconds"], limits["storage_bytes"],
    limits["resident_memory_bytes"])))
PY
  )
  spireshift_attempt=1
  spireshift_kind=other
  if [[ "$spireshift_stage" == collect ]]; then
    spireshift_kind=rollout
  fi
  while [[ -e "artifacts/resources/native-a8-batch-$spireshift_stage-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-a8-batch-$spireshift_stage-v1-attempt-$spireshift_attempt.json" ]]; do
    spireshift_attempt=$((spireshift_attempt + 1))
  done
  uv run --no-sync spireshift resources run \
    --kind "$spireshift_kind" \
    --report "artifacts/resources/native-a8-batch-$spireshift_stage-v1-attempt-$spireshift_attempt.json" \
    --artifact-root "$spireshift_workspace" \
    --workers "$spireshift_workers" \
    --max-wall-seconds "$spireshift_wall" \
    --max-cpu-seconds "$spireshift_cpu" \
    --max-storage-bytes "$spireshift_storage" \
    --max-memory-bytes "$spireshift_memory" \
    -- uv run --no-sync python -m spireshift.native_gradient_pool \
      "$spireshift_stage" "$spireshift_recipe" --node "$spireshift_node"
done
printf 'Independent-game batch checks finished. No player training or next experiment follows.\n'
