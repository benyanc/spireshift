# Production bootstrap teacher

The first production training data must solve a practical cold-start problem: a weak continuation
policy produces almost no full-run victories, so terminal labels alone cannot yet distinguish most
early actions. The bootstrap teacher keeps terminal victory as the primary objective and adds
public, versioned progress diagnostics that can teach a useful representation and cheap policy.

## Frozen train denominator

The production state set is
`manifests/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json`. It contains combat-decision zero
from the first 32 SHA-256-ranked training runs in the frozen 1,000-run split. Its state-set ID is
`sha256:82296066af173dce00b4685c8698aa246d50d21ab0cf2eae326e0c8c0fffeeec`.

Every case pins the complete run seed, public state hash, and legal-action count. The 32 states expose
252 candidates, from 5 to 12 per state. Validation and sealed test runs are rejected before work
starts. Every listed state remains in the denominator when capture, simulation, or evidence writing
fails.

The source specification can be checked without running simulations:

```bash
uv run spireshift bootstrap freeze-states \
  configs/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json \
  /tmp/sts2-bootstrap-train-pilot-v1.json \
  --split-manifest \
  manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json
```

## Teacher and targets

`public-progress-bootstrap-v1` is a transparent public-state continuation policy. Its combat card
priority starts from EvanGambit's MIT-licensed `starter-aggressive` evaluation policy at pinned
revision `37e4264`. SpireShift adds public map and rest-site choices so full runs do not rely on the
upstream policy's first-legal noncombat fallback. The implementation copies only the small declared
priority table and does not read backend-private state.

At a frozen state, each legal candidate receives the same set of hidden-world seeds. A worker
restores the public checkpoint, verifies that hidden resampling did not change the observation or
legal actions, applies one candidate, and follows the continuation policy. The immutable result
records binary terminal reward plus:

- maximum and final floor;
- milestone reach probabilities for floors 1, 8, 16, 24, 32, 40, 48, 56, and 64;
- act completion;
- final HP, maximum HP, gold, potion count, and relic count; and
- transition, CPU, wall-time, patch, ruleset, seed, and policy identities.

Candidate selection is lexicographic: terminal win rate first, then maximum floor, act completion,
final HP, and source order. The derived progress utility is always below `1.0` for a loss. It is an
auxiliary curriculum label and is never emitted as environment reward, readiness evidence, or a
headline gameplay result.

## Bounded production pilot

This is a sustained job. Start and observe it manually through the resource wrapper:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-teacher-v0.107.1-pilot.json \
  --metrics artifacts/resources/bootstrap-teacher-v0.107.1-pilot-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-v0.107.1-pilot \
  --workers 8 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 20000 \
  --max-storage-bytes 5000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-v0.107.1-pilot \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-train-pilot-v1.json \
    --split-manifest \
    manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --samples-per-candidate 16 \
    --workers 8 \
    --worker-timeout 120
```

The command schedules exactly 4,032 paired simulations. A seven-simulation production integration
smoke completed all candidates, wrote 292 transitions, occupied two floor bins, and produced
within-state action variation. Based on that smoke and the prior 27,456-simulation benchmark, plan
for roughly 10–30 minutes on the current machine. Realized resource evidence is authoritative.

If the process is interrupted before the final dataset report, rerun the inner command with
`--resume`, preferably through a new resource report. Completed cases are reused. Failed `case.json`
files are renamed and preserved before a new numbered attempt is made.

## Verification and interpretation

The lightweight verifier checks content identities, linked hashes, frozen train ownership, paired
seeds, binary terminal reward, aggregates, and all worker evidence without rerunning simulations:

```bash
uv run --extra evangambit spireshift bootstrap verify \
  artifacts/bootstrap/teacher-v0.107.1-pilot/bootstrap-teacher-dataset.json \
  --split-manifest \
  manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
  --output artifacts/bootstrap/teacher-v0.107.1-pilot/verification.json
```

Before training, require `failed_cases` to be zero, at least two occupied maximum-floor bins, and
nonzero `states_with_candidate_progress_variation`. Inspect candidate histograms for collapse and
confirm that all run seeds remain in the train partition. `--replay-cases N` adds exact simulation
replay and can itself become a sustained job; use it only after the generated data has enough signal
to justify that cost.
