# Recovered A8 batch-size analysis

Assessed 2026-10-17 under #35 / #146. The owner's saved-data analysis completed
successfully. Larger groups do not clearly stabilize the proposed learning direction
in this finite pool. This does not demonstrate a better player or justify a larger
unchanged training run.

The proposed [direct-teaching/PPO follow-up](native-conditional-teaching.md) has now
completed. Neither method meets its contextual criterion; a local initialization
probe motivates testing explicit public context-by-candidate interactions next.

## What was measured

The analysis uses one frozen normalized behavior model and 256 distinct TRAIN games:
254 recovered complete episodes plus the two explicitly declared additions. The original
interrupted attempt stays counted: 257 diagnostic attempts, with four repeated control
starts accounted separately. Recovered data remains diagnostic only; it is not ordinary
PPO training admission. See [recovery and accounting](native-a8-memory-recovery.md).

Saved behavior likelihoods are reconstructed for all 26,060 decisions, including 19,499
decisions with more than one legal action. The independent numerical loss check passes
on four games / 549 decisions, with maximum actor-gradient error 6.29e-17. That independent
reference does **not** cover all 256 games.

Each comparison divides games into two disjoint groups, fits the return predictor and
advantage normalization separately within each group, and compares their proposed actor
changes before Adam updates. There are 32 predetermined partitions per size. An agreement
of +1 means the same direction, zero means perpendicular directions, and -1 means opposite
directions. A negative dot product is called an opposing pair; it does not mean every
individual weight or action preference reverses.

| Games in each group | Median game-driven agreement | Opposing game-driven pairs | Median agreement including exploration term | Opposing total pairs |
| --- | ---: | ---: | ---: | ---: |
| 4 | -0.027 | 53.1% | -0.069 | 53.1% |
| 8 | +0.040 | 46.9% | +0.012 | 43.8% |
| 16 | -0.096 | 59.4% | -0.097 | 62.5% |
| 32 | -0.017 | 53.1% | -0.094 | 62.5% |
| 64 | +0.020 | 50.0% | -0.053 | 59.4% |
| 128 | +0.061 | 37.5% | -0.093 | 65.6% |

At 128 games, the game-driven opposing fraction is lower than at 32, but median direction
agreement remains close to zero. The pattern is not uniformly improving with size. Even
the largest measured groups therefore do not supply clear evidence that increasing the
batch alone will repair learning. It remains possible that other policies, rewards,
parameterizations or larger independent collections behave differently.

The full 256-game exploration-gradient norm is 35.8% of the game-driven norm; their sum
has 0.937 agreement with the game-driven gradient. The exploration term is material,
but this does not show that it dominates or causes weak learning. Its effect differs
by group: at 128 games, including it worsens median agreement and opposing frequency.
No removal or coefficient change follows automatically. The earlier smaller-cohort
3.5–9.8% ratios belong to different pools/models and are not substituted here.

The largest game's share of summed contribution norms is 1.59%; the ratio of the summed
gradient norm to the sum of individual contribution norms is 0.0759. This describes
substantial cancellation without identifying one obviously dominant game. Neither
quantity is an effective sample size or a causal explanation of poor play.

## Limits and next work

Repeated partitions reuse the same finite pool and are correlated. They are not 32
independent replications, population confidence intervals, or a batch-size learning
trial. This is one checkpoint under one score and parameterization, before Adam,
minibatch reuse, clipping away from behavior, and later optimizer steps. No actual
policy gain, best batch size or unique causal defect is established.

The existing [known-task controls](native-ppo-known-task-controls.md) provide a more
specific unresolved gap: the same learner can improve on a constant delayed choice,
but did not learn to reverse its action when HP changes. The next work item is a
bounded direct-teaching versus reward-driven conditional control on the same inputs,
with matched and reported actual optimizer work, fixed settings and all attempts
preserved. This distinguishes available capacity/optimization from learning the
conditional rule through sampled outcomes. It is not a new game-mechanics sweep,
a native player promotion, or an adaptive-thinking prerequisite beyond the existing
foundation gate. Native training changes should follow a measured, specific result.

## Resources and saved-result verification

Owner analysis: **114.20 seconds**, 111.54 CPU seconds, **3.917 GB** peak resident memory,
**6.23 MB** retained in the recovery workspace; no cap was reached. The larger derivative
arrays are explicitly budgeted here. The preserved original 211.91 MB of source output
is outside this resource root; it was neither copied into it nor deleted. The successful
analysis is not a full native replay measuring the new collector's 256-game peak memory.

A separate short saved-result check verifies identities and **596 source-file seals**,
all recorded groups' disjointness/seed membership, medians and opposing fractions.
It recomputes these summaries, not the saved gradients, and launches no games or updates.
There is no new owner command at this handoff. The existing analysis wrapper now displays
the cached result. No trained player was produced; base readiness and adaptive thinking
remain unmet.

Recipe: `configs/native-gradient/sts2-v0.111.0-a8-stream-recovery-v1.json`.
Private result: `artifacts/native-gradient/sts2-v0.111.0-a8-stream-recovery-v1/gradient-report.json`.
Resource receipt: `artifacts/resources/native-a8-recovered-gradient-analysis-v1-attempt-1.json`.
Portable summary: `docs/evidence/native-a8-recovered-gradient-result-v1.json`.
