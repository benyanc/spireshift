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

## Expanded curriculum v2

The pilot completed all 32 cases, but every source was floor 2 at combat decision zero, every one of
the 4,032 continuations lost, and the two eight-sample halves selected the same action in only 18 of
32 states. It remains useful for loader and loss-function smoke tests. It is not a production model
dataset.

Curriculum v2 discovers exact decision-type occurrences. A combat occurrence no longer counts a
combat-selection observation, and train and validation use disjoint complete-run partitions. Each
frozen case records its source floor and act. Every requested coordinate that cannot be reached by
the public continuation policy is retained in `unreachable_coordinates`; discovery never improves
its apparent coverage by silently dropping misses.

The production discovery specifications are:

- `configs/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json`: 64 ranked train runs;
- `configs/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json`: 24 ranked validation
  runs.

They request multiple occurrences of path, combat, combat-selection, reward, event, rest, shop,
treasure, card-selection, and relic-selection decisions. Their content-addressed outputs must pass
the prespecified state, source-floor, and decision-type minimums before teacher generation starts.
Run discovery yourself through the resource wrapper:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-discovery-v2.json \
  --artifact-root artifacts/bootstrap/discovery-train-v2 \
  --workers 1 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 3600 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap discover-states \
    configs/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json \
    artifacts/bootstrap/discovery-train-v2/state-set.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json
```

Use the validation specification and distinct `discovery-validation-v2` paths for the held-out
artifact. Do not start scaled teacher generation until both discovery reports and state sets have
been inspected. The generator itself enforces their structural thresholds before scheduling a
single rollout.

The completed discovery artifacts are frozen at:

- `manifests/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json`, state-set ID
  `sha256:df1f686764bf14ea0022d5d8425b039917b775e93acadfd12caf02033be45ab6`;
- `manifests/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json`, state-set ID
  `sha256:7cdf551662333a1f9320811a739ca904d992beec9b297271517d16366a9a7c40`.

Train contains 545 cases, 529 unique public states, 64 complete-run seeds, seven source floors, and
eight decision types. Validation contains 204 cases, 202 unique states, 24 complete-run seeds, six
source floors, and seven decision types. All structural gates pass, all 88 runs terminate within
the discovery limit, and the partitions share no run seeds. They share five public state hashes:
four forced one-action event states and one three-action opening relic state. This is reported as a
small validation limitation; it does not violate complete-run split ownership.

For each candidate, v2 preserves every paired outcome and adds a pairwise preference matrix,
normalized soft policy target, progress-utility standard error, paired preference margin, selected
winner confidence, and first-half versus second-half winner agreement. `policy_target_weight`
downweights unstable states; one-candidate states receive zero policy weight. A one-hot target is
retained only for audit compatibility, and `hard_target_eligible` is false unless the winner is
unique, sufficiently confident, and stable across halves. Model training must consume either the
confidence-aware pairwise matrix or `soft_policy_target` with `policy_target_weight`, rather than
the audit-only one-hot field.
`load_curriculum_policy_examples` is the verified boundary for model code: it refuses legacy or
invalid datasets and exposes the soft distribution, weight, pairwise matrix, and hard-label
eligibility alongside the public compositional model input.

After generation, `signal_assessment` applies the remaining prespecified thresholds for effective
labeled-state count, half-split agreement, and reached-floor occupancy. It reports terminal-head
promotion separately. Both victories and non-victories are required, so an all-loss dataset can
pass an auxiliary-policy gate but can never promote the terminal value head or satisfy readiness.

The train set has 2,255 candidates and schedules 36,080 simulations at 16 paired samples per
candidate. Run it through the resource wrapper:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-teacher-v2.json \
  --metrics artifacts/resources/bootstrap-train-teacher-v2-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-train-v2 \
  --workers 8 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 40000 \
  --max-storage-bytes 5000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-train-v2 \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-train-curriculum-v2.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --samples-per-candidate 16 \
    --workers 8 \
    --worker-timeout 120
```

Validation has 865 candidates and schedules 13,840 simulations. Run it after train completes:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-validation-teacher-v2.json \
  --metrics artifacts/resources/bootstrap-validation-teacher-v2-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-validation-v2 \
  --workers 8 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 40000 \
  --max-storage-bytes 5000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-validation-v2 \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-validation-curriculum-v2.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --samples-per-candidate 16 \
    --workers 8 \
    --worker-timeout 120
```

These are sustained jobs and are intentionally left for the operator to start and observe. If a
job is interrupted or finishes with failed cases, use a new resource-report path and rerun the
inner command against the same artifact root with `--resume`. Resume validates that the backend,
state set, objective, and generation configuration are unchanged; archives the failed dataset and
case reports; reuses completed cases; and reruns only failed cases.

The admitted-backend contract smoke is recorded in
`docs/evidence/bootstrap-curriculum-v2-admitted-smoke.json`. It captured reward, path, combat zero,
and combat eight across floors 1 and 2; completed and verified 4/4 cases, 17 candidates, 68 paired
simulations, and 2,795 transitions; and correctly rejected terminal-head promotion because all 68
outcomes were losses. Its deliberately permissive smoke thresholds are not the production gates.

## Learned-policy late-run curriculum v3

The frozen-test base-v2 pilot reached a higher maximum floor than the progress baseline on 29 of
32 paired runs, tied three, and regressed on none, but both policies won zero runs. Curriculum v3
uses that admitted checkpoint to reach later train and validation states and as the continuation
policy for every paired candidate rollout. The remaining test seeds stay sealed.

Learned state sets record the model, training report, split, ruleset, and derived policy identities.
Worker requests additionally bind the local artifact paths and revalidate their content before
execution. Resume and dataset verification reject a different checkpoint, report, capture policy,
or continuation policy. Baseline v1/v2 artifacts retain their original schemas and task IDs.

The production discovery specifications are:

- `configs/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json`;
- `configs/bootstrap/sts2-v0.107.1-evangambit-validation-learned-curriculum-v3.json`.

They omit the earliest path, combat, reward, and selection occurrences where practical and request
later occurrences that the learned policy can now reach. Run the two discovery jobs independently;
they may run in parallel because each uses one process:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-discovery-v3.json \
  --artifact-root artifacts/bootstrap/discovery-train-v3 \
  --workers 1 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 3600 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap discover-states \
    configs/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json \
    artifacts/bootstrap/discovery-train-v3/state-set.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json
```

For validation, replace `train` with `validation` in the report, artifact root, specification, and
output paths.

Both discovery jobs completed within their resource caps and passed verification. The admitted
train state set is frozen at
`manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json`, ID
`sha256:07c21103e14a3e21a56bedfba936578071fc5fc1e084f764a0e583e04a7c4542`. It contains 711
cases, 686 unique public states, all 64 requested train seeds, 11 source floors through floor 11,
and nine decision types. Mean source floor is 3.487 and 354 cases (49.8%) are floor 4 or later.
Its resource report is
`sha256:383891a4fabfa2a46198d0fafa27f3ea4ccb0c22596ce2821889321cd99d821f`.

Validation is frozen at
`manifests/bootstrap/sts2-v0.107.1-evangambit-validation-learned-curriculum-v3.json`, ID
`sha256:75f35e8bc1e843853dd933e0fae8db406acddcc5a85e325522705a486b4ec7a6`. It contains 256
cases, 253 unique public states, all 24 requested validation seeds, 10 source floors through floor
10, and nine decision types. Mean source floor is 3.328 and 117 cases (45.7%) are floor 4 or later.
Its resource report is
`sha256:4f9c2eef0b52241e135a11f751485c2641ce44576a7e1b00a52b1a0e5b581a63`.

Train and validation share no run seeds. They share eight public-state hashes: seven forced
one-action floor-1 event states and one nine-action floor-1 card-selection state. This repeated
early observation is disclosed when interpreting held-out policy metrics; it does not violate
complete-run split ownership. Compared with v2, mean source floor increased from about 1.8 to at
least 3.3 and the floor-4-or-later share increased from 3.9-6.4% to 45.7-49.8%.

After admission, generate train and validation separately. These jobs are CPU-heavy and should run
sequentially with eight workers on the reference M4 Pro:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-teacher-v3.json \
  --metrics artifacts/resources/bootstrap-train-teacher-v3-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-train-v3 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 80000 \
  --max-storage-bytes 10000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-train-v3 \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-curriculum-v3.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --samples-per-candidate 16 \
    --workers 8 \
    --worker-timeout 120
```

For validation generation, replace `train` with `validation` in the report, metrics, artifact root,
state-set, and output paths. Do not retrain the model until both generated datasets verify and pass
their auxiliary-policy signal gates.

The completed production generation found 22.718 effective labeled train states against the
prespecified threshold of 24.0. Every other train gate passed, and validation passed all gates with
10.5 effective states against its threshold of 8.0. Keep the train threshold unchanged and add the
prespecified 16-run supplement from ranked train positions 64 through 79. `--run-offset 64` makes
those complete-run seeds disjoint from the original 64-run train curriculum:

```bash
uv run --extra evangambit spireshift bootstrap discover-states \
  configs/bootstrap/sts2-v0.107.1-evangambit-train-learned-supplement-v3.json \
  artifacts/bootstrap/discovery-train-v3-supplement/state-set.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
  --backend evangambit \
  --upstream-root artifacts/backend/evangambit-v0.107.1 \
  --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
  --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
  --policy-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
  --run-offset 64
```

The frozen supplement state set is
`manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-supplement-v3.json`, ID
`sha256:ebdbb798da5a82cba5a27936207e6e8972a4039ac1cd1194b11cb3d5c806a49c`. It contains 268
unique states from all 16 requested runs, spans eight source floors through floor 8 and nine
decision types, overlaps none of the original train run seeds, and has no step-limited runs.

Generate the supplement with the same teacher settings as the original train dataset:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-teacher-v3-supplement.json \
  --metrics artifacts/resources/bootstrap-train-teacher-v3-supplement-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-train-v3-supplement \
  --workers 8 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 40000 \
  --max-storage-bytes 5000000000 \
  --max-memory-bytes 32000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-train-v3-supplement \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-train-learned-supplement-v3.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --samples-per-candidate 16 \
    --workers 8 \
    --worker-timeout 120
```

After generation completes, combine it with the original train dataset. Composition fully verifies
both inputs, rejects overlapping run seeds, keeps the stricter threshold from either component,
recomputes all summaries and content identities, and hard-links immutable case evidence where the
filesystem supports it:

```bash
uv run spireshift bootstrap combine-curricula \
  artifacts/bootstrap/teacher-train-v3-combined \
  artifacts/bootstrap/teacher-train-v3/bootstrap-teacher-dataset.json \
  artifacts/bootstrap/teacher-train-v3-supplement/bootstrap-teacher-dataset.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json
```

Use `artifacts/bootstrap/teacher-train-v3-combined/bootstrap-teacher-dataset.json` as the training
dataset only if its emitted `auxiliary_policy_signal_pass` is true. Dataset verification caches
checkpoint validation by resolved path, modification time, and size, so every worker request still
binds the exact learned-policy identity without reparsing the model for every task.

## Terminal-frontier curriculum v4

The v3 learned-policy curricula improved maximum floor but produced no victories in 74,224 paired
simulations. Treating every non-victory as a loss would also mislabel rollout caps as defeats. The
v4 protocol targets the missing terminal signal directly while preserving complete-run split
ownership.

Discovery follows the frozen base-v3 policy through unused train and validation seeds. For each run,
it keeps at most eight of the deepest states at floor 7 or later that have at least two legal
actions. The selection is made only from public state and retains the exact decision coordinate for
replay. This concentrates teacher work near each run's terminal frontier without selecting on
teacher outcomes or inspecting the sealed test partition.

The versioned signal contract distinguishes three outcome classes: victory, defeat, and censored.
A capped rollout is censored and cannot satisfy the defeat threshold. Terminal-head promotion also
requires states where every action has at least one completed outcome and the sampled terminal win
rates differ across actions. Production training refuses a v4 train or validation dataset that
fails these prespecified gates, and it still requires both classes in the train fit split, train
selection split, full train set, and held-out validation set.

The discovery specifications use ranked train positions 80 through 239 and validation positions 24
through 99, avoiding every complete-run seed used by the v3 curricula. These two read-only model
scans write to separate locations and may be launched in parallel. They are sustained jobs and must
be started and observed by the operator:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-frontier-discovery-v4.json \
  --artifact-root artifacts/bootstrap/discovery-train-frontier-v4 \
  --workers 1 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap discover-states \
    configs/bootstrap/sts2-v0.107.1-evangambit-train-terminal-frontier-v4.json \
    artifacts/bootstrap/discovery-train-frontier-v4/state-set.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --run-offset 80
```

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-validation-frontier-discovery-v4.json \
  --artifact-root artifacts/bootstrap/discovery-validation-frontier-v4 \
  --workers 1 \
  --max-wall-seconds 7200 \
  --max-cpu-seconds 7200 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 8000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap discover-states \
    configs/bootstrap/sts2-v0.107.1-evangambit-validation-terminal-frontier-v4.json \
    artifacts/bootstrap/discovery-validation-frontier-v4/state-set.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --run-offset 24
```

Inspect both emitted state sets before scheduling teacher rollouts. In particular, compare
`captured_coordinates`, `runs_with_eligible_coordinates`, decision types, source floors, and the
source maximum-floor histogram against the frozen signal thresholds. Teacher commands and resource
limits should be chosen from those realized state and candidate counts rather than estimated in
advance.

The completed discovery artifacts are frozen at:

- `manifests/bootstrap/sts2-v0.107.1-evangambit-train-terminal-frontier-v4.json`, state-set ID
  `sha256:9e09a8a180e15eb503a229ee8bd109ebf32ab7f9ba9e4f0aee747c8898d8463f`;
- `manifests/bootstrap/sts2-v0.107.1-evangambit-validation-terminal-frontier-v4.json`, state-set ID
  `sha256:55b4181550ad5c573f8caab52272a2aa8df2b4bf40de330832243a20029b593a`.

Train contains 674 unique states from 89 of 160 requested runs, ten source floors from 7 through
17, four decision types, and 3,725 legal candidates. Validation contains 311 unique states from 40
of 76 runs, eight source floors from 7 through 14, five decision types, and 1,771 legal candidates.
There is no complete-run seed or public-state hash overlap. Both state sets pass their prespecified
structural gates. The capture policy won none of its runs, so discovery alone does not satisfy the
terminal-signal gate.

Before production-scale labels, run a two-sample diagnostic teacher pilot. This schedules 7,450
train simulations and 3,542 validation simulations. Its purpose is to detect completed victories
and within-state terminal variation; its two samples per action are insufficient for final model
training. Run the jobs sequentially so their resource measurements and failures remain attributable:

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-train-frontier-teacher-v4-pilot.json \
  --metrics artifacts/resources/bootstrap-train-frontier-teacher-v4-pilot-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-train-frontier-v4-pilot \
  --workers 8 \
  --max-wall-seconds 3600 \
  --max-cpu-seconds 10000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-train-frontier-v4-pilot \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-train-terminal-frontier-v4.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --samples-per-candidate 2 \
    --workers 8 \
    --worker-timeout 120
```

```bash
uv run spireshift resources run \
  --kind teacher_generation \
  --report artifacts/resources/bootstrap-validation-frontier-teacher-v4-pilot.json \
  --metrics artifacts/resources/bootstrap-validation-frontier-teacher-v4-pilot-metrics.json \
  --artifact-root artifacts/bootstrap/teacher-validation-frontier-v4-pilot \
  --workers 8 \
  --max-wall-seconds 1800 \
  --max-cpu-seconds 6000 \
  --max-storage-bytes 1000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift bootstrap generate \
    artifacts/bootstrap/teacher-validation-frontier-v4-pilot \
    --states manifests/bootstrap/sts2-v0.107.1-evangambit-validation-terminal-frontier-v4.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --backend evangambit \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --policy-checkpoint artifacts/models/sts2-v0.107.1-base-v3/checkpoint.json \
    --policy-report artifacts/models/sts2-v0.107.1-base-v3/training-report.json \
    --samples-per-candidate 2 \
    --workers 8 \
    --worker-timeout 120
```

Do not train from these pilot datasets. First inspect `terminal_outcome_classes`,
`states_with_candidate_terminal_variation`, censored simulations, completed cases, and realized
resource use. If either partition still has no victories, adding samples to the same continuation
policy is unlikely to solve the blocker; improve the rollout policy or move the frontier closer to
terminal decisions instead.

The completed pilot produced zero victories in 10,926 completed continuations and stopped this
sampling path. The next versioned continuation and its single operator-started discovery command are
documented in [Combat-advancement continuation](combat-advancement.md).
