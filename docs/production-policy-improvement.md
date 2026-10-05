# Cycle-safe production policy improvement

The accepted base-v2 policy remains the production foundation. It reached farther than the simple
baseline but won zero of 32 frozen test runs. Base-v3 also won zero runs and did not improve mean
maximum floor, so this iteration collects new evidence with base-v2 rather than promoting base-v3
or deploying tactical search.

The production DAgger collector runs complete train-owned trajectories with the shared
`PublicNoOpActionGuard`. It records every decision and preserves fallback and cycle evidence. It
selects at most ten actionable states per run for later teacher labeling:

- rare states relative to the verified base-v2 curriculum;
- high-entropy decisions where base-v2 is uncertain;
- three of each run's deepest actionable states, so early easy decisions do not dominate.

Selection used 32 fresh train runs at offsets 136-167. These complete runs do not overlap the
base-v2 reference curriculum or the earlier intervention window. All 32 runs terminated without a
failure, cycle, or decision limit. The collector selected 320 unique states across five decision
types and 13 source-floor bins, including 96 terminal-frontier states. The frozen state set is
`sha256:23771cca8a8154abb6d8cb696ee4d63d21bac1409aa4a9e2dfa62162752b82a1`.

The collection still contained zero victories, so it does not unblock terminal-value training. It
does clear the coverage and liveness gate for paired teacher labeling. The selected states contain
1,114 legal candidates; at 16 paired samples per candidate, teacher labeling scheduled 17,824
bounded counterfactual simulations. Each continuation now uses the same public no-op fallback as
the collector and records its fallback evidence in a production DAgger teacher schema.

Teacher labeling completed all 320 states and 17,824 simulations in 25 minutes 28 seconds. Every
continuation terminated; none required the fallback. The labels contain progress variation in 111
states, 20 hard-target-eligible states, 19.82 effective labeled states, and 91.56% paired-winner
agreement between sample halves. The dataset passed complete verification as
`sha256:59fcdfab13431b78171c4609d7807dccddae99ce81caa3c52c8602ac5e1ce507`.

The new dataset and accepted base-v2 curriculum have identical policy, ruleset, objective, teacher,
and sampling configurations. Their 112 complete-run seeds are disjoint. They are therefore eligible
for one verified composition containing 1,299 labeled states. Composition verifies about 1.3 GB of
existing evidence and may take more than a minute even though it performs no simulation or training.

Composition completed in 111 seconds. The resulting 1,299 cases contain 4,799 candidates, 76,784
paired simulations, 569 progress-varying states, 45 hard-target-eligible states, 51.62 effective
labeled states, and 86.07% half-split winner agreement. All 320 new DAgger states are unique relative
to the earlier curriculum; the composed corpus has 1,268 unique public states. Its dataset identity
is `sha256:bf26c88358111fd70a1a30c8e9bd59be29080a3d69d93d3714223955545c22ac`. The composition resource
report is `sha256:d143b606b347f2b66abf88ffff3eef58ac9c36de8befb33fec0dbf8d3bff6269`.
Full integrity verification then checked all 1,299 cases with no errors and confirmed the same
dataset identity. The verification resource report is
`sha256:a28896bfa0ba558cc2b9705342893fdb1372b0801d0bf0508857a9bf8da28235`.

The completed collection also converted the tactical diagnostic into 15 causal preferences: 11
favor the counterfactual action, one favors the original action, and three remain low-weight ties.
These preferences remain separate from the larger DAgger state set, with their original report
identities preserved. The v4 training adapter verifies them against the original intervention
cases, reconstructs their public-state inputs, and applies them only to the policy head. They cannot
alter the terminal-value, tactical-risk, or maximum-floor heads. Complete-run model-selection
subfolds also remain separate for this causal evidence.

Base-v4 training completed in 481 seconds. Its checkpoint is
`sha256:bec02c5f8808d1b9780eece83da16848017105366c1382f655860fb39227a215`, its training report is
`sha256:37f08f7457a7f82f40cff407931cd64aeb7c9ffaaccdd2bcaf5144dca7fbecdb`, and the resource report is
`sha256:e1e96dfc0ea86305fa55202e6869f0cdffcbb628ed041d93bf33104d11b73eff`.

The raw base-v4 policy is rejected. On the frozen validation curriculum its pairwise cross-entropy
was 0.7720, decisive-pair accuracy was 46.24%, and only the regret check passed. However, its
decisive accuracy on the 12 non-tied causal preferences rose to 66.67%, compared with 16.67% for
base-v2. The new evidence taught the intended distinction but overwhelmed broader policy quality.

`model blend-curriculum` now performs a deterministic recovery step. It evaluates a fixed grid of
policy-weight interpolations from base-v2 to base-v4 on the same validation curriculum, then chooses
the largest base-v4 share that passes every predeclared auxiliary policy check. It blends only the
policy head; the base-v4 auxiliary heads and complete causal provenance remain unchanged. The full
grid and its validation and causal metrics are stored in the versioned checkpoint and report, while
the frozen test split remains untouched.

The selected base-v5 policy uses 55% base-v4 and 45% base-v2. It passes all four policy checks with
0.6637 pairwise cross-entropy, 69.89% decisive-pair accuracy, and 0.002499 mean progress regret. On
the causal evidence it reaches 58.33% decisive accuracy, assigns 50.68% mean probability to the
search action when beneficial, and only 29.30% when harmful. The verified base-v5 checkpoint is
`sha256:3cd6aa0351b3b206e4d692e620a5bdee568f10dee152bd2d697bde226a8b06d8`; its report is
`sha256:7f992ad6eee798736f58a2d356febcebca310e35e79d852696257f6b7b465a1c`.

The admitted-backend smoke is frozen as
[`production-model-inference-smoke-v5-v0.107.1.json`](evidence/production-model-inference-smoke-v5-v0.107.1.json),
with identity `sha256:8106e3ef385162c9f29f1ce76f6c0c6a86273bc12bbafe99befa426674c23bb6`.
All eight decisions were candidate-aligned, legal, and public-state only. Median inference latency
was 4.83 ms and maximum latency was 6.98 ms.

## Frozen candidate comparison

The operator-run base-v5 versus accepted base-v2 comparison completed all 64 trajectories on the
same 32 frozen test seeds. The aggregate is
`sha256:dba706efaf6ae0ef4e4c3cef63286e438365af09d2ff27abaa7ce9b8d4d40106`; its verified resource
report is `sha256:8547248f863761353cb41560a60e677e0547b55b0e0b8f6e7653630b717b1e09`. The run took 41.37
seconds, used 45.11 CPU seconds, and produced 6,470 transitions.

Both policies completed and terminated every run without a cycle, decision-limit stop, fallback, or
failure. Neither policy won any run. Base-v5 reached mean maximum floor 7.594 versus 7.281 for
base-v2, a paired difference of +0.3125 floors. Base-v5 reached farther on 13 seeds, tied on 13, and
reached a lower floor on 6. An exact two-sided sign test over the 19 non-tied pairs gives p=0.167. A
fixed-seed percentile bootstrap over the paired mean gives a descriptive 95% interval from -0.219 to
+0.875 floors. The result is compatible with a small improvement but does not establish one.

Base-v5 is therefore retained as a reproducible experimental candidate and is not promoted over
base-v2. The causal preferences changed policy behavior in the intended direction, and the recovery
blend prevented the broad validation regression, but the frozen run evidence remains statistically
inconclusive and terminal-victory evidence remains entirely absent. The terminal-value head,
learned-PUCT readiness, and adaptive-compute claims remain blocked. No further run belongs to this
work item.

The next bounded experiment is the
[train-only terminal-trajectory discovery](terminal-trajectory-discovery.md). It uses the accepted
base-v2 checkpoint and sparse, reproducible legal alternatives to determine whether the existing
policy is one or two decisions away from a winning run. It does not promote base-v5, consume held-out
seeds, or unblock terminal-value training without both winning and losing complete trajectories.

That experiment completed 384 train-only attempts with 1,426 actual non-argmax actions and 372 unique
action traces. All 384 runs ended in defeat, and no run passed floor 13. Increasing exploration from
2% to 10% reduced mean maximum floor from 7.047 to 6.867. Sparse independent sampling is therefore
rejected, terminal-value training remains blocked, and no held-out evaluation is authorized. The
next foundation package must search over coherent run trajectories and first establish Act 1 boss
reach and clear as an auxiliary milestone without replacing terminal victory as the project goal.

Coherent trajectory search subsequently reached the Act 1 boss on one train seed. Teacher
continuations from that trajectory failed the frozen useful-signal gate, so that dataset remains
excluded. The alternative [strict mutation preference collection](run-level-trajectory-search.md)
now contains 79 verified action comparisons across 16 complete train runs, including 25 floor/boss
improvements. This completes the multi-run evidence prerequisite for a conservative, anchored
policy-only update. These comparisons require a separate integration beyond the existing
`train-curriculum` command.

The [anchored trajectory-policy trainer](trajectory-policy-training.md) now provides that separate
integration. Its frozen first recipe uses 68 eligible preferences and the original base-v2 anchor
corpus. The owner-run base-v6 experiment completed but failed its frozen development-validation
regret limit: regret increased by 0.000303308823, above the allowed 0.0002. Choices changed on
26/204 states. The selected update ranked the preferred new action ahead in only 1/18 selection
comparisons. Base-v6 is rejected and has not been promoted. Issue #42's
[saved policy diagnosis](trajectory-policy-diagnosis.md) completed in 38.852 wall seconds and
reconciled the rejection. All 15 harmful changes occur at starting Ancient choices; 24 starting
choices switch from option 2 to option 0, while all 69 combat choices stay unchanged. The two path
changes improve auxiliary regret. There is no measured win-rate improvement from this audit.
Public option IDs are present but are encoded numerically, and actions are represented primarily
by phase and position. [Issue #125](https://github.com/benyanc/spireshift/issues/125) tests a separately
versioned identity-aware starting-event policy residual over immutable base-v2. The
[starting-option trainer](starting-option-policy-training.md) is implemented with a frozen recipe,
the existing all-204 development-validation checks, fitting-only option vocabulary and an owner-run
script capped at ten wall minutes. The owner-run base-v7 experiment completed in 47.33 seconds,
but none of its 40 epochs passed the unchanged advancement checks. It selected epoch zero and an
empty residual. Starting preference coverage was only three fitting runs and one selection run;
all 27 fitting option IDs were covered with no unseen IDs. The subsequent
[exhaustive starting-option evidence collector](starting-option-evidence.md), which evaluates all
options across 64 fresh train seeds. Its owner run completed all 192 terminal branches and passed
the frozen data-sufficiency gate with 172 eligible comparisons, but still no victories. The next
[starting-choice experiment](starting-evidence-policy-training.md) binds this evidence and the
unchanged source groups, parent and all-204 checks. The coding agent has launched no real-data
collection, training or game evaluation.

Accepted base-v2 remains the production checkpoint. Every source continuation still loses, so
terminal-value readiness and adaptive-search training remain blocked. The next update must
preserve the existing non-policy heads, distinguish meaningful advancement from weaker rank
tie-breakers, and protect broad policy quality with complete-run separation and held-out checks.
