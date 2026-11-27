#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_recipe=configs/native-gradient/sts2-v0.111.0-a8-stream-recovery-v1.json
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
IFS=$'\t' read -r spireshift_workspace spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run --no-sync python - "$spireshift_recipe" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
limits = recipe["analysis_limits"]
print("\t".join(str(v) for v in (recipe["workspace"], limits["wall_seconds"],
    limits["cpu_seconds"], limits["storage_bytes"], limits["resident_memory_bytes"])))
PY
)
if [[ ! -f "$spireshift_workspace/union.json" ]]; then
  printf 'The verified recovered pool is not ready. No collection or analysis follows.\n' >&2
  exit 1
fi
if [[ -f "$spireshift_workspace/gradient-report.json" ]]; then
  printf 'Showing saved gradient results; no games or player updates follow.\n'
  uv run --no-sync python -m spireshift.native_gradient_stream analyze "$spireshift_recipe"
  exit 0
fi
printf 'Analyzing 256 saved diagnostic games: 254 recovered plus two bounded additions.\n'
printf 'The original interrupted attempt stays counted: 257 total diagnostic attempts.\n'
printf 'No games, app copies, policy training or automatic follow-up.\n'
printf 'Allow up to ten minutes. One numerical thread; 8 GB memory cap; 2 GB output cap.\n'
spireshift_attempt=1
while [[ -e "artifacts/resources/native-a8-recovered-gradient-analysis-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-a8-recovered-gradient-analysis-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
uv run --no-sync spireshift resources run \
  --kind other \
  --report "artifacts/resources/native-a8-recovered-gradient-analysis-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers 1 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- uv run --no-sync python -m spireshift.native_gradient_stream analyze "$spireshift_recipe"
printf 'Saved-game gradient analysis finished. Share the output; no next stage follows.\n'
