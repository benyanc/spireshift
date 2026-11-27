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

The completed diversity arm can be reproduced with:

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

### Corrected diversity result

The owner-run diversity arm completed and independently verified all 16 cases, evaluated 1,872
terminal trajectories, applied all 1,856 mutations, and recorded no replay divergences. Mean best
floor was 9.1875, only 0.125 above the hash arm and 0.5625 below the score arm. It reached floor 15
and produced no boss reach, Act 1 clear, or victory. Strategic-trace diversity therefore did not
pass either advancement criterion at this budget.

The run used 1,308.17 wall seconds, 0.393 CPU-hours, 484 MB peak resident memory, and 166.6 MB of
artifact storage. Its frozen identities are:

- search report: `sha256:f01bc9677f1dbf70562be3f58b2e98fd250e8fd041a6bf5caeedb6dd99dd39ff`;
- independent verification: `sha256:d67ca15e7bc47f75eff4a376da2a3f9a2dfea719736962461d9393c64f8910f4`;
- resource report: `sha256:b3f5376c18e789ac83151d732894d03b305354ba3a74f45d32fc82d9a2ebd19b`.

The completed deterministic comparison can be reproduced with:

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

### Final ablation result

The verified comparison is `sha256:e836d246e9115b3b6960701b42ef2f8765ec0a2e60773971db8f759e386095bb`.
Public frontier scoring is the accepted strategy: it is the only arm to reach the boss and its
0.6875 mean-floor gain over hash ranking exceeds the 0.5 threshold. Diversity is rejected for this
stage because it lost the milestone and most of the score arm's aggregate gain at equal compute.

This completes the ranking ablation and authorizes using the score arm's boss-reaching trajectory
as train-only milestone evidence. It does not establish an Act 1 clear, terminal victory, or
terminal-value readiness. The next foundation package must replay, verify, and label the accepted
trajectory before another base-policy improvement cycle.

### Accepted milestone curriculum

The accepted seed-300 trajectory has now been replayed transition by transition against the exact
engine. The replay reproduced all 147 decisions, the seven applied mutations in its parent lineage,
the floor-17 boss encounter, and the final defeat without hidden-state resampling or divergence.
The frozen state set is
`manifests/bootstrap/sts2-v0.107.1-base-v2-milestone-trajectory-train-v1.json`, identified by
`sha256:97cae28b8f2e77ba4de5826a7c4bc16295e9a0b9d4e5c5ba32de27fcf556f9a6`.

The selection contains 28 unique train states: every mutation decision, one predecessor for each
mutation, and every floor-17 boss-combat state with at least two legal actions. None duplicates a
state in the verified 1,299-case production curriculum. The state set embeds the complete public
action trace so teacher generation reconstructs searched states directly rather than asking the
base policy to rediscover a path it did not originally choose. Every captured state is bound to its
global trajectory index, source hash, legal-action count, selected action, and next-state hash.

Teacher output from this state set uses dataset schema v7 and remains train-only. Boss reach is
recorded only as discovery provenance; the target utility and terminal-value labels continue to use
environment terminal victory.

The owner-run teacher job completed and independently verified all 28 cases. It evaluated 2,224
candidate continuations across 74,154 transitions with no failures. Nine states had candidate
progress variation across five maximum-floor bins, and half-split winner agreement was 96.43%.
All 2,224 continuations were terminal defeats, however, and the dataset produced only 0.7708
effective labeled states against the frozen minimum of 1.0. Dataset
`sha256:8a48a422038365921ac4e46211645780d7cfa008a711d1a2c46567d7e9ca6033`
therefore fails the auxiliary-policy signal gate. It must not be combined with the production
curriculum, and the threshold must not be lowered after observing the result.

### Strict mutation preferences

The accepted trajectory's seven mutations are exact one-action interventions against their direct
parents. SpireShift now replays all eight lineage trajectories, captures the public observation and
ordered legal actions needed to reconstruct each model input, and compares parent and child under
the same frozen lexicographic rank used by the accepted search. It emits a preference only when the
child strictly improves that rank. Ties and regressions remain in the artifact as explicit
exclusions.

The seed-300 artifact contains five strict improvements, one tie, and one regression. The deciding
components are maximum floor, boss reach, last-actionable player health, and distinct public states
on the deepest floor. Exact verification reproduced 1,031 lineage decisions, all ordered legal
actions, and all seven mutation points. The content identities are:

- preference set: `sha256:24a7356ac133d897cb974470c265449327e5d4c38939f0d19b2f9576b838d2a1`;
- verification: `sha256:e82541260660c10a2dcb28a181dcb65cf4bf6df85837e04738da741c9214826c`.

These are auxiliary policy preferences only. They contain zero positive terminal-victory labels.
All five come from one complete run, so the artifact records `training_ready: false` and cannot be
used for fitting or model selection until equivalent strict evidence exists from multiple train
runs. No model should be promoted from this trajectory alone.

### Completed multi-run preference collection

The owner-run collection completed on October 3, 2026. It exactly replayed the accepted lineages
from all 16 existing score-arm train runs: 111 trajectories and 10,308 decisions. The collection
contains 95 mutations, with 79 strict improvements, 15 ties, and one regression. Each run is stored
separately and content addressed. All 16 runs contribute at least four accepted preferences, so
the multi-run auxiliary evidence gate now reports `training_ready: true`.

The frozen identities are:

- collection: `sha256:351503bd4fccc47a25465f34cb49b2ed9915b6067cee6d575927b653df5987ff`;
- source search: `sha256:57ce9022cebbd968b41c7b5a378de45fb8c9f408e430c7f2a0555ba08c2288b0`;
- resource report: `sha256:3187cefc24b528db1677be49475c2061948a08bc0bcf0fcea7c32fa8fbd10989`.

The job used 110.36 wall seconds, 103.46 CPU seconds, 597 MB peak resident memory, and 1.94 MB of
artifact storage. It reached no resource limit. Subsequent artifact inspection checked both
schemas, every content identifier and file hash, train-seed ownership, source-search verification,
lineage references, public decision/action alignment, and every parent/child rank comparison.
That inspection performed no new engine replay. It found no duplicate or opposite state/action
preference pairs, and the resource report independently passed integrity verification.

The first differing rank components show why the 79 preferences must not all be treated as
equally strong training evidence:

| Deciding rank component | Strict preferences |
| --- | ---: |
| Boss reached | 1 |
| Maximum floor | 24 |
| Enemy health defeated fraction | 29 |
| Last actionable player health | 14 |
| Distinct public states on the deepest floor | 11 |

These preferences cover combat (42), reward (16), event (8), path (7), card selection (3), rest
site (2), and shop (1) decisions. They are selected improvements on fixed, seeded continuations;
they are not calibrated action win probabilities or independent samples of a stochastic outcome.
In particular, spending more decisions on the same floor is insufficient evidence of better play.

The collection completes [issue #123](https://github.com/benyanc/spireshift/issues/123). The next
foundation item is [issue #124](https://github.com/benyanc/spireshift/issues/124), conservative
policy-only integration into accepted base-v2. Before training, freeze the component filters and
weights, preserve complete-run fitting/selection
ownership, and anchor the update to the existing policy to guard against the broad regression
seen in base-v4. Keep the terminal-value, tactical-risk, and floor heads unchanged. Use a frozen
held-out validation protocol before any new test evaluation. The 11 state-count-only preferences
should remain audit evidence rather than direct policy targets; damage and health comparisons
must be reported separately from the 25 floor/boss improvements.

The collection contains zero positive terminal-victory labels. It supports a small auxiliary
policy-improvement experiment, not terminal-value readiness, checkpoint promotion, learned-PUCT
readiness, or adaptive-budget training. No new search, training, or full-run evaluation was
started during this assessment.
