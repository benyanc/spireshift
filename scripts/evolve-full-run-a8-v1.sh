#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_evolution_config=configs/full-run-evolution/sts2-v0.107.1-public-a8-ppo-seeded-v1.json
spireshift_evolution_root=artifacts/full-run-evolution/sts2-v0.107.1-public-a8-ppo-seeded-v1
spireshift_evolution_prefix=a8-actor-evolution-v1
if [[ -f "$spireshift_evolution_root/evolution-report.json" ]]; then
  printf 'This experiment is complete. Reading saved outcome metadata; no new games or evolution.\n'
  uv run python -m spireshift.full_run_a8_evolution \
    "$spireshift_evolution_config" "$spireshift_evolution_root" --show
  exit 0
fi

spireshift_evolution_budget=$(uv run python -m spireshift.full_run_a8_evolution_budget \
  "$spireshift_evolution_config" "$spireshift_evolution_root" artifacts/resources "$spireshift_evolution_prefix") || {
    printf '%s\n' "$spireshift_evolution_budget"
    exit 1
  }
read -r spireshift_evolution_wall spireshift_evolution_cpu spireshift_evolution_storage spireshift_evolution_memory <<< "$spireshift_evolution_budget"
spireshift_evolution_attempt=1
while [[ -e "artifacts/resources/$spireshift_evolution_prefix-attempt-$spireshift_evolution_attempt.json" || -L "artifacts/resources/$spireshift_evolution_prefix-attempt-$spireshift_evolution_attempt.json" || -e "artifacts/resources/$spireshift_evolution_prefix-attempt-$spireshift_evolution_attempt-metrics.json" || -L "artifacts/resources/$spireshift_evolution_prefix-attempt-$spireshift_evolution_attempt-metrics.json" ]]; do
  spireshift_evolution_attempt=$((spireshift_evolution_attempt + 1))
done
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
printf 'Evolving the complete A8 neural player: 16 candidates on the same 16 games per generation, at most 16 generations and 5,632 attempts.\n'
printf 'All 4,384 actor weights can change. The saved PPO player and initializer are retained; no adaptive thinking or automatic follow-up.\n'
printf 'Checking apparent improvements every two generations on 128 separate train seeds; freezing the player before 128 fresh development seeds per distinct player.\n'
printf 'Generation summaries show the best candidate and confirmed player. Re-running explicitly resumes saved work; it does not reset the total budget.\n'
printf 'Remaining stage caps: %s elapsed seconds, %s CPU seconds, 12 GB memory and 4 GB artifacts.\n' "$spireshift_evolution_wall" "$spireshift_evolution_cpu"
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/$spireshift_evolution_prefix-attempt-$spireshift_evolution_attempt.json" \
  --metrics "artifacts/resources/$spireshift_evolution_prefix-attempt-$spireshift_evolution_attempt-metrics.json" \
  --artifact-root "$spireshift_evolution_root" \
  --workers 8 \
  --max-wall-seconds "$spireshift_evolution_wall" \
  --max-cpu-seconds "$spireshift_evolution_cpu" \
  --max-storage-bytes "$spireshift_evolution_storage" \
  --max-memory-bytes "$spireshift_evolution_memory" \
  -- \
  uv run --extra evangambit python -m spireshift.full_run_a8_evolution \
    "$spireshift_evolution_config" "$spireshift_evolution_root" --resume
