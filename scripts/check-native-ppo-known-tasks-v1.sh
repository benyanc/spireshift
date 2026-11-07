#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_recipe=configs/native-controls/ppo-known-tasks-v1.json
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
spireshift_workspace=$(uv run --no-sync python - "$spireshift_recipe" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    print(json.load(stream)["workspace"])
PY
)
if [[ -f "$spireshift_workspace/report.json" ]]; then
  printf 'Showing the saved synthetic learning control; no fitting or games follow.\n'
  uv run --no-sync python -m spireshift.native_learning_control "$spireshift_recipe"
  exit 0
fi
printf 'Testing the unchanged PPO learner on three tiny artificial tasks, three seeds each.\n'
printf 'Expected 1-3 minutes; hard cap three minutes, one numerical thread, 1 GB memory.\n'
printf 'No Steam/game workers, native trajectories, production checkpoints or app copies.\n'
printf 'Only final synthetic players are scored; a failed learning check remains a saved result.\n'

spireshift_attempt=1
while [[ -e "artifacts/resources/native-ppo-known-tasks-v1-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-ppo-known-tasks-v1-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
uv run --no-sync spireshift resources run \
  --kind training \
  --report "artifacts/resources/native-ppo-known-tasks-v1-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers 1 \
  --max-wall-seconds 180 \
  --max-cpu-seconds 180 \
  --max-storage-bytes 20000000 \
  --max-memory-bytes 1000000000 \
  -- uv run --no-sync python -m spireshift.native_learning_control "$spireshift_recipe"
