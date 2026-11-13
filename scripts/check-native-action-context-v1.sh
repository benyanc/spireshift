#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_recipe=configs/native-controls/action-context-v1.json
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
  printf 'Checking the saved representation comparison; no fitting or games follow.\n'
  uv run --no-sync python -m spireshift.native_action_context_study "$spireshift_recipe"
  exit 0
fi
if [[ -e "$spireshift_workspace" || -L "$spireshift_workspace" ]]; then
  printf 'Preserve unfinished evidence at %s; no automatic restart.\n' "$spireshift_workspace" >&2
  exit 1
fi
printf 'Testing three public encodings on the same finite health-dependent task, three seeds each.\n'
printf 'All start with the same action probabilities, numerical weights and network size.\n'
printf 'Teacher and PPO use matched actual work within each encoding. Across encodings, KL stopping may differ.\n'
printf 'Expected 1-3 minutes, hard cap four minutes, one numerical thread, 1 GB memory.\n'
printf 'Only the synthetic teacher sees correct-action labels. No native games or production training follow.\n'
spireshift_attempt=1
while [[ -e "artifacts/resources/native-action-context-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-action-context-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
uv run --no-sync spireshift resources run \
  --kind training \
  --report "artifacts/resources/native-action-context-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers 1 \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- uv run --no-sync python -m spireshift.native_action_context_study "$spireshift_recipe"
