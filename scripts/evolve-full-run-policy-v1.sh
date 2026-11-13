#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Only the owner launches/monitors this finite experiment. Repeating this script resumes
# the identical population/seed schedule or displays its completed report.
spireshift_evolution_config=configs/full-run-evolution/sts2-v0.107.1-unified-pilot-v1.json
spireshift_evolution_root=artifacts/full-run-evolution/sts2-v0.107.1-unified-pilot-v1
if [[ -f "$spireshift_evolution_root/evolution-report.json" ]]; then
  printf 'Pilot already complete. Reading its saved result; no games or training follow.\n'
  uv run spireshift full-run show "$spireshift_evolution_config" "$spireshift_evolution_root"
  exit 0
fi

spireshift_evolution_attempt=1
while [[ -e "artifacts/resources/full-run-evolution-pilot-v1-attempt-$spireshift_evolution_attempt.json" || -L "artifacts/resources/full-run-evolution-pilot-v1-attempt-$spireshift_evolution_attempt.json" || -e "artifacts/resources/full-run-evolution-pilot-v1-attempt-$spireshift_evolution_attempt-metrics.json" || -L "artifacts/resources/full-run-evolution-pilot-v1-attempt-$spireshift_evolution_attempt-metrics.json" ]]; do
  spireshift_evolution_attempt=$((spireshift_evolution_attempt + 1))
done
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
printf 'Evolving the whole player: 16 candidates, up to 4 generations, at most 832 planned simulated games, 8 workers. Stops after 3 generations without confirmed improvement or at the job cap.\n'
printf 'Caps: 60 minutes elapsed, 20,000 CPU seconds, 12 GB memory, 3 GB artifacts. No automatic follow-up.\n'
uv run spireshift resources run \
  --kind training \
  --report "artifacts/resources/full-run-evolution-pilot-v1-attempt-$spireshift_evolution_attempt.json" \
  --metrics "artifacts/resources/full-run-evolution-pilot-v1-attempt-$spireshift_evolution_attempt-metrics.json" \
  --artifact-root "$spireshift_evolution_root" \
  --workers 8 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 20000 \
  --max-storage-bytes 3000000000 \
  --max-memory-bytes 12000000000 \
  -- \
  uv run --extra evangambit spireshift full-run evolve \
    "$spireshift_evolution_config" "$spireshift_evolution_root" --resume
