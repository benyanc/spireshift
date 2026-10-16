#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_pilot_config=configs/native-learning/sts2-v0.111.0-a8-pilot-v4.json
spireshift_qualification=configs/engine-qualification/sts2-v0.111.0-macos-arm64-v1.json
spireshift_node="${SPIRESHIFT_NODE:-/Users/benjamin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node}"
IFS=$'\t' read -r spireshift_workspace spireshift_workers spireshift_wall spireshift_cpu spireshift_storage spireshift_memory < <(
  uv run python - "$spireshift_pilot_config" <<'PY'
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
  printf 'This pilot has a saved result. Reading it; no new games or training follow.\n'
  uv run spireshift engine show-native-learning "$spireshift_qualification" "$spireshift_pilot_config"
  exit 0
fi
if [[ -e "$spireshift_workspace" || -L "$spireshift_workspace" ]]; then
  printf 'This pilot has unfinished evidence at %s. Preserve it for inspection; no automatic restart.\n' "$spireshift_workspace" >&2
  exit 1
fi

export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
uv run spireshift engine preflight-native-learning "$spireshift_qualification" "$spireshift_pilot_config"
spireshift_attempt=1
while [[ -e "artifacts/resources/native-a8-ppo-pilot-v4-attempt-$spireshift_attempt.json" || -L "artifacts/resources/native-a8-ppo-pilot-v4-attempt-$spireshift_attempt.json" ]]; do
  spireshift_attempt=$((spireshift_attempt + 1))
done
printf 'Starting afresh from the original seeded player; no trained weights or optimizer state are loaded.\n'
printf 'Training Ironclad/A8 on the frozen actual engine: 8 rounds of 32 sampled games, 336 total planned attempts.\n'
printf 'Two separate native workers share frozen inputs. No game app copies are created.\n'
printf 'Expect roughly 10-20 minutes; hard cap 30 minutes, 3,600 CPU seconds, 4 GB memory and 4 GB output.\n'
printf 'All evaluation uses the frozen policy distribution at temperature 0.8, with identical random streams per seed across checkpoints.\n'
printf 'Each batch shows wins, average floor, best game and failures. Checkpoint selection precedes independent development evaluation.\n'
printf 'An isolated failed game is preserved and excluded from training; its worker is retired and the next planned seed continues.\n'
printf 'At most two failed games are allowed per batch. Unverified shutdown, broken evidence or excess failures stop the pilot.\n'
printf 'No adaptive controller, checkpoint promotion or next experiment follows.\n'
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/native-a8-ppo-pilot-v4-attempt-$spireshift_attempt.json" \
  --artifact-root "$spireshift_workspace" \
  --workers "$spireshift_workers" \
  --max-wall-seconds "$spireshift_wall" \
  --max-cpu-seconds "$spireshift_cpu" \
  --max-storage-bytes "$spireshift_storage" \
  --max-memory-bytes "$spireshift_memory" \
  -- \
  uv run --extra neural spireshift engine train-native-ppo \
    "$spireshift_qualification" "$spireshift_pilot_config" --node "$spireshift_node"
