#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_relational_config=configs/full-run-ppo/sts2-v0.107.1-public-a8-relational-v3.json
spireshift_relational_root=artifacts/full-run-ppo/sts2-v0.107.1-public-a8-relational-v3
spireshift_relational_prefix=full-run-relational-a8-v3
if [[ -f "$spireshift_relational_root/ppo-report.json" ]]; then
  printf 'This experiment is complete. Reading saved outcome metadata; no new games or training.\n'
  uv run python -m spireshift.full_run_relational_ppo \
    "$spireshift_relational_config" "$spireshift_relational_root" --show
  exit 0
fi

spireshift_relational_budget=$(uv run python -m spireshift.full_run_a8_evolution_budget \
  "$spireshift_relational_config" "$spireshift_relational_root" artifacts/resources "$spireshift_relational_prefix") || {
    printf '%s\n' "$spireshift_relational_budget"
    exit 1
  }
read -r spireshift_relational_wall spireshift_relational_cpu spireshift_relational_storage spireshift_relational_memory <<< "$spireshift_relational_budget"
spireshift_relational_attempt=1
while [[ -e "artifacts/resources/$spireshift_relational_prefix-attempt-$spireshift_relational_attempt.json" || -L "artifacts/resources/$spireshift_relational_prefix-attempt-$spireshift_relational_attempt.json" || -e "artifacts/resources/$spireshift_relational_prefix-attempt-$spireshift_relational_attempt-metrics.json" || -L "artifacts/resources/$spireshift_relational_prefix-attempt-$spireshift_relational_attempt-metrics.json" ]]; do
  spireshift_relational_attempt=$((spireshift_relational_attempt + 1))
done
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
printf 'Testing the repaired A8 inputs: 128 sampled games per round, at most 8 rounds and 1,920 planned attempts.\n'
printf 'Status amounts, relic counters and card upgrades stay attached to their owners. Same 256-input, 16-hidden-unit network; all actor weights and decision types can learn.\n'
printf 'Confirming every two rounds on 128 separate training seeds; freezing the player before 128 fresh paired development seeds.\n'
printf 'Round summaries show best game, average floor, wins and failures. No adaptive controller, promotion, final test or automatic follow-up.\n'
printf 'Remaining total stage caps: %s elapsed seconds, %s CPU seconds, 12 GB memory and 4 GB artifacts. Explicit resumption keeps prior costs and failures.\n' "$spireshift_relational_wall" "$spireshift_relational_cpu"
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/$spireshift_relational_prefix-attempt-$spireshift_relational_attempt.json" \
  --metrics "artifacts/resources/$spireshift_relational_prefix-attempt-$spireshift_relational_attempt-metrics.json" \
  --artifact-root "$spireshift_relational_root" \
  --workers 8 \
  --max-wall-seconds "$spireshift_relational_wall" \
  --max-cpu-seconds "$spireshift_relational_cpu" \
  --max-storage-bytes "$spireshift_relational_storage" \
  --max-memory-bytes "$spireshift_relational_memory" \
  -- \
  uv run --extra evangambit python -m spireshift.full_run_relational_ppo \
    "$spireshift_relational_config" "$spireshift_relational_root" --resume
