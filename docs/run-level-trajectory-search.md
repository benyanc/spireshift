# Milestone-conditioned run-level trajectory search

The accepted base-v2 policy reaches farther than the deterministic baseline but has produced no
terminal victories. Sparse independent exploration also failed: 384 train-only trajectories made
1,426 non-argmax decisions, yet none passed floor 13. This experiment replaces independent random
changes with coherent trajectory search.

For each train seed, generation zero is an exact base-v2 trajectory. Each later candidate replays a
retained parent's public-state-aligned prefix, changes one legal decision, and then returns to
base-v2. The beam keeps the four best distinct action traces across generations. A child can
therefore preserve useful earlier changes and add another later change. Retained outcomes are ranked
lexicographically by:

1. terminal full-run victory;
2. entry into Act 2;
3. reaching the Act 1 boss;
4. maximum floor;
5. a deterministic action-trace hash used only to break exact ties.

The environment's terminal-victory flag remains the only positive reward. Boss reach and Act 1
clear are auxiliary foundation signals and are never relabeled as victories.

## Frozen pilot

The v1 pilot uses 16 previously unused train seeds at ranked offsets 232 through 247. It runs at
most eight mutation generations, keeps a beam of four trajectories, and tries four mutations per
parent. The resulting upper bound is 1,872 trajectories before early stopping and duplicate-trace
removal. Work is parallel only across seeds, so parent selection remains deterministic.

The command performs an admitted-backend preflight before searching. It requires public `act` and
`floor` fields, accepts either `overgrowth` or `underdocks` as the seed-selected Act 1 region, uses
floor 17 as the Act 1 boss threshold, and recognizes `hive` as Act 2 entry. It never clones or
resamples hidden state. Exact reset-and-replay keeps the first pilot independent of the hidden-world
clone defect tracked in issue #105.

The retired v1 configuration incorrectly treated `underdocks` as the only Act 1 region and
`overgrowth` as Act 2. Its preflight failed in 0.61 seconds before any trajectory ran; the preserved
resource report is `sha256:37c9301994947d691f4c746ca7f33b6a3af69df072aecb08175ae3a10c24ea0e`.
The corrected v2 semantics follow the backend's explicit region order: Act 1 is Overgrowth or
Underdocks, then Hive, then Glory.

Cases are immutable and resumable at the seed boundary. They preserve every policy distribution,
selected action, parent, mutation, replay divergence, liveness event, no-op fallback, milestone,
generation incumbent, and content identity. The verifier recomputes identities, complete train-seed
coverage, parent order, exact-policy baseline behavior, monotonic incumbent ranks, summaries, and
readiness from the cases.

The project owner starts the sustained run. Run this single command from the repository root:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/trajectory-search-base-v2-act1-train-v2.json \
  --metrics artifacts/resources/trajectory-search-base-v2-act1-train-v2-metrics.json \
  --artifact-root artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v2 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 3000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model search-run-trajectories \
    configs/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v2.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v2 \
    --resume
```

Any best trajectory that reaches the boss or enters Act 2 is enough to justify a separate replay and
labeling package. A terminal victory additionally unblocks mixed terminal-value evidence once the
existing defeats are included. If no seed reaches the boss, the pilot stops; scaling the same search
is not authorized until the policy representation or environment milestone surface is audited.

## Frozen pilot result

The owner-run v2 pilot completed all 16 train seed cases and the independent verifier accepted all
16. It evaluated 1,872 terminal trajectories, applied all 1,856 requested mutations, and recorded no
replay divergences. The search improved mean maximum floor from 6.625 to 9.0625; 14 seeds improved,
none regressed, and the best trajectory reached floor 15. It produced no boss reaches, Act 1 clears,
or victories, so it did not pass the prespecified advancement gate.

The run used 1,323.42 wall seconds, 0.397 CPU-hours, 452 MB peak resident memory, and 155.8 MB of
artifact storage. The frozen identities are:

- search report: `sha256:8a21b3cece76507bce73a6c7b4790f6e734bbd7a773c349266b08905914881c5`;
- independent verification: `sha256:57da185ce5c164df21e6f1b308f3173b6652562120396699e5f6d37d75f18d79`;
- resource report: `sha256:24e4cbe5cf4599fb17c483a08eec2e969d91b4a34c46c6be40b58fedd21781da`.

Post-run analysis found 24 trajectories at floor 15 and no trajectory at floor 16 or 17. Only 37
of 1,856 child mutations improved maximum floor or a milestone over their parent. More importantly,
each generation contained many candidates tied at its deepest floor, while the v2 beam used an
action-trace hash to resolve those ties. No seed made a real rank improvement in generation eight.
The next experiment therefore needs a public-state measure of within-floor progress and diverse beam
retention before any larger trajectory-search run. More seeds or generations with the v2 ranking are
not justified by this result.

## Public frontier ranking ablation

Issue #120 keeps the v2 primary outcome order and replaces the hash only within trajectories tied on
victory, Act 1 clear, boss reach, and maximum floor. Every new trajectory records a versioned public
frontier containing player health, the last actionable health, decision type, encounter identity,
distinct states and decisions on the deepest floor, and public enemy-HP progress. Enemy HP uses the
admitted v0.107.1 observation layout: offset 80, stride 15, and at most six slots. The summary stores
no hidden state and is content identified independently of the trajectory.

The auxiliary order is encounter clear, enemy HP defeated fraction, current player health, last
actionable player health, and distinct public states on the floor. The diverse arm first retains one
trajectory per distinct non-combat strategic action trace within each primary-rank group, then fills
remaining beam slots by auxiliary rank. Diversity can therefore change only same-floor ties.

### Retired v3 diagnostic

The owner-run v3 score arm completed all 16 cases and its independent verification remains valid. It
raised mean best floor from 9.0625 to 9.125, reached floor 15, and found no boss reach, Act 1 clear,
or victory. The gain of 0.0625 is below the prespecified 0.5 advancement gate.

Post-run inspection found that every selected best trajectory reported 100% enemy-HP progress. The
v3 ranking read enemy HP from the final observation first. On a terminal defeat, EvanGambit clears
the enemy slots while retaining encounter identity, so terminal cleanup was incorrectly interpreted
as defeating the encounter. The frozen v3 report remains reproducible under its original contract,
but it is a retired diagnostic and must not be compared as the intended score arm. Its identities
are:

- search report: `sha256:a321adf0514e2ca4fe49e6db4e348d9a4ddbe4cb2931093bd70881343e408233`;
- independent verification: `sha256:f017db697ab8422eb29f06588b9e7fbbc591f02288a1d9c85f50566ba30a42f1`;
- resource report: `sha256:126b6ae1f4c5c803e3f408e493244425afd59b47b29168349e8806fe11d2f520`.

### Corrected v4 experiment

The v4 contract always takes enemy progress from the last actionable public state on the deepest
floor when one exists. This prevents a death transition from turning cleared vector slots into a
false encounter clear. The v3 schemas and configs remain available solely to verify the completed
artifact. The corrected score and diversity configurations keep exactly the same seeds, model,
mutation salt, and search budget as the v2 hash arm:

- corrected score config `sha256:f4686a81461f368731cdd64da4652242ffb2c4d8ac848c471d1fcf10e4ec527d`;
- corrected diversity config `sha256:1c2033da21d6abb694523f6d61f229e66b2d2ea32877b28e72afe101adb935c0`.

### Corrected score result

The owner-run corrected score arm completed all 16 cases and the independent verifier accepted all
16. It evaluated 1,872 terminal trajectories, applied all 1,856 mutations, and recorded no replay
divergences. Mean best floor was 9.75, which is 0.6875 above the equal-budget v2 hash arm and exceeds
the prespecified 0.5 material-improvement threshold. Fifteen seeds improved over their base-policy
trajectory and none regressed.

Seed 300 reached the Act 1 boss on floor 17, then died to Lagavulin Matriarch. Its last actionable
state had 11 of 80 player HP and 156 of 233 enemy HP. The enemy snapshot hash equals the last
actionable state hash for every selected best trajectory, and their defeated fractions vary rather
than collapsing to the false 100% value from v3. The result therefore passes the advancement gate
through both boss reach and material fixed-budget floor improvement.

The run used 1,293.65 wall seconds, 0.389 CPU-hours, 440 MB peak resident memory, and 164.9 MB of
artifact storage. Its frozen identities are:

- search report: `sha256:57ce9022cebbd968b41c7b5a378de45fb8c9f408e430c7f2a0555ba08c2288b0`;
- independent verification: `sha256:9507a58245e444a551a5f70bd880352345e3467b5645c9c2fcd7a920058a2bbe`;
- resource report: `sha256:f0e52d967a23db9dcd52d11b1244cfffe2112857de33b37302ad6b36116d3302`.

The completed score arm can be reproduced with:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/trajectory-search-base-v2-act1-frontier-score-train-v4.json \
  --metrics artifacts/resources/trajectory-search-base-v2-act1-frontier-score-train-v4-metrics.json \
  --artifact-root artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 3000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model search-run-trajectories \
    configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4 \
    --resume
```

The project owner starts and monitors sustained runs. The next run is the diversity arm:

```bash
uv run spireshift resources run \
  --kind rollout \
  --report artifacts/resources/trajectory-search-base-v2-act1-frontier-diverse-train-v4.json \
  --metrics artifacts/resources/trajectory-search-base-v2-act1-frontier-diverse-train-v4-metrics.json \
  --artifact-root artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v4 \
  --workers 8 \
  --max-wall-seconds 14400 \
  --max-cpu-seconds 50000 \
  --max-storage-bytes 3000000000 \
  --max-memory-bytes 16000000000 \
  -- \
  uv run --extra evangambit spireshift model search-run-trajectories \
    configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v4.json \
    artifacts/models/sts2-v0.107.1-base-v2/checkpoint.json \
    --report artifacts/models/sts2-v0.107.1-base-v2/training-report.json \
    --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
    --upstream-root artifacts/backend/evangambit-v0.107.1 \
    --manifest artifacts/backend/evangambit-v0.107.1-admitted.json \
    --output-dir artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v4 \
    --resume
```

Once both corrected runs exist, the deterministic comparison verifies all three reports and their
cases before comparing them:

```bash
uv run spireshift model compare-run-trajectory-search \
  artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v2/run-level-trajectory-search.json \
  artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4/run-level-trajectory-search.json \
  artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v4/run-level-trajectory-search.json \
  --legacy-config configs/trajectory-search/sts2-v0.107.1-base-v2-act1-train-v2.json \
  --frontier-config configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-score-train-v4.json \
  --diverse-config configs/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-diverse-train-v4.json \
  --split-manifest manifests/splits/sts2-v0.107.1-evangambit-seeds-000000-000999-v1.json \
  --output artifacts/trajectory-search/sts2-v0.107.1-base-v2-act1-frontier-ablation-v4.json
```

The comparison advances the best frontier strategy if either corrected arm reaches the boss or
clears Act 1, or improves mean maximum floor by at least 0.5 over the v2 hash arm. Otherwise it
records a stop decision and sends the project back to policy representation or environment work.
