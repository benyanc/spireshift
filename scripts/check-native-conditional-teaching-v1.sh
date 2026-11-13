#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_recipe=configs/native-controls/conditional-teaching-v1.json
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
IFS=$'\t' read -r spireshift_workspace spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run --no-sync python - "$spireshift_recipe" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    recipe = json.load(stream)
limits = recipe["resource_limits"]
print("\t".join(str(v) for v in (recipe["workspace"], limits["wall_seconds"],
    limits["cpu_seconds"], limits["storage_bytes"], limits["resident_memory_bytes"])))
PY
)
if [[ -f "$spireshift_workspace/report.json" ]]; then
  printf 'Showing the saved conditional-learning comparison; no fitting or games follow.\n'
  uv run --no-sync python -m spireshift.native_conditional_control "$spireshift_recipe"
  exit 0
fi
if [[ -e "$spireshift_workspace" || -L "$spireshift_workspace" ]]; then
  printf 'Preserve unfinished synthetic evidence at %s; no automatic restart.\n' "$spireshift_workspace" >&2
  exit 1
fi
printf 'Comparing direct teaching and PPO on the same small health-dependent task, three seeds.\n'
printf 'Matched actual optimizer steps and input presentations; teacher alone receives correct-action labels.\n'
printf 'Expected 1-3 minutes; hard cap three minutes, one numerical thread, 1 GB memory.\n'
printf 'No native games, episode files, production players or app copies are used. No automatic next experiment.\n'
spireshift_attempt=1
while [[ -e "artifacts/resources/native-conditional-teaching-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-conditional-teaching-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
uv run --no-sync spireshift resources run \
  --kind training \
  --report "artifacts/resources/native-conditional-teaching-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers 1 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- uv run --no-sync python -m spireshift.native_conditional_control "$spireshift_recipe"
