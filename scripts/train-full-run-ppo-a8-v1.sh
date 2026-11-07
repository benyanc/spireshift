#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

spireshift_ppo_config=configs/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v1.json
spireshift_ppo_root=artifacts/full-run-ppo/sts2-v0.107.1-public-a8-pilot-v1
if [[ -f "$spireshift_ppo_root/ppo-report.json" ]]; then
  printf 'Training already complete. Reading the saved result; no further games or training.\n'
  uv run spireshift full-run show-ppo "$spireshift_ppo_config" "$spireshift_ppo_root"
  exit 0
fi
spireshift_ppo_attempt=1
while [[ -e "artifacts/resources/full-run-ppo-a8-v1-attempt-$spireshift_ppo_attempt.json" || -L "artifacts/resources/full-run-ppo-a8-v1-attempt-$spireshift_ppo_attempt.json" || -e "artifacts/resources/full-run-ppo-a8-v1-attempt-$spireshift_ppo_attempt-metrics.json" || -L "artifacts/resources/full-run-ppo-a8-v1-attempt-$spireshift_ppo_attempt-metrics.json" ]]; do
  spireshift_ppo_attempt=$((spireshift_ppo_attempt + 1))
done
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
printf 'Training the whole A8 player: 64 sampled games per round, at most 24 rounds and 2,112 total planned game attempts, 8 workers.\n'
printf 'Checking greedy play every 4 rounds; freezing the selected player before 64 independent development seeds.\n'
printf 'Stops on a confirmed training plateau after at least 12 rounds, or at the cap. No adaptive controller or automatic follow-up.\n'
printf 'Per-launch caps: 60 minutes elapsed, 20,000 CPU seconds, 12 GB memory, 4 GB artifacts. Re-running explicitly resumes saved work with a new resource report.\n'
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/full-run-ppo-a8-v1-attempt-$spireshift_ppo_attempt.json" \
  --metrics "artifacts/resources/full-run-ppo-a8-v1-attempt-$spireshift_ppo_attempt-metrics.json" \
  --artifact-root "$spireshift_ppo_root" \
  --workers 8 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 20000 \
  --max-storage-bytes 4000000000 \
  --max-memory-bytes 12000000000 \
  -- \
  uv run --extra evangambit spireshift full-run train-ppo \
    "$spireshift_ppo_config" "$spireshift_ppo_root" --resume
