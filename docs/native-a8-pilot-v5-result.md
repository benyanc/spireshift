# Native A8 pilot v5: reliable execution, no retained improvement

The owner completed all 336 planned attempts in 14.82 minutes. Every game ended normally;
there were no worker failures, retired workers or missing attempts. The game, host, runtime,
SDK and account-profile checks passed. No game apps were copied. Retained output was 300.35 MB,
peak memory 2.05 GB and CPU time 1,000.02 seconds, within every declared limit.

Training ran eight rounds on 256 training seeds, using 26,061 verified sampled decisions and
627 optimizer steps. Both actor and critic weights changed in every round. No round hit its
behavior-KL early-stop limit. These facts establish that the learner executed; they do not
establish better play.

## The starting checkpoint won selection

| Confirmation checkpoint | Wins / 16 | Average floor | Mean declared auxiliary return |
| --- | ---: | ---: | ---: |
| Initial seeded player | 0/16 | 7.5625 | 0.019681267 |
| After four training rounds | 0/16 | 6.8125 | 0.018462406 |
| After eight training rounds | 0/16 | 7.1875 | 0.019184959 |

The original rule chooses wins first, then the exact declared auxiliary score, then completion
rate, retaining the incumbent on ties. Neither tested trained checkpoint beat the initializer.
The runner correctly kept that initializer. Selection was frozen before development results.
This small confirmation panel does not prove that trained policies are worse across all seeds.

The development-initial and development-selected panels therefore ran the **same checkpoint**
with the same action-RNG streams. Both averaged 7.375 floors over 16 reserved seeds, with zero
wins and a best floor of 15. Their identical results are a repeat check of the starting player,
not evidence that a trained checkpoint generalized equally well. The saved assessor's zero
paired floor difference and zero-width floor interval must be read in that context. No trained
checkpoint was evaluated on development seeds. Do not retrospectively select a different one
using those seeds.

Across every recorded attempt there were zero wins, zero completed acts and a best floor of
17. Repeated confirmation/development seeds and changing behavior policies must not be pooled
as 336 independent trials of one fixed player. The result supports neither base readiness nor
adaptive thinking.

## Saved evidence checked

The separate saved-only assessment verified all 336 cases and 1,427 source files, including
ending evidence, deliveries, source at launch, checkpoint/update lineage, seed/RNG ownership
and the exact confirmation selection. It completed in 6.58 seconds, with no games, optimizer
updates or checkpoint changes. This is a post-result audit, not a new blind evaluation. It
rechecks saved audits and hashes; it does not recompute gradients or rerun the engine.

The frozen recipe is `configs/native-assessment/sts2-v0.111.0-a8-pilot-v5-v1.json`. The repeatable
saved checker is `scripts/assess-native-a8-pilot-v5.sh`; Codex has already run it. Numerical output
is in `artifacts/native-assessments/sts2-v0.111.0-a8-pilot-v5-v1/report.json`. Public references and
summary are in [the evidence record](evidence/native-a8-pilot-v5-assessment-v1.json).

## Next work

Prioritize a bounded training-data diagnosis under #143/#146 before another larger batch:

1. Measure whether the existing public encoding distinguishes consequential choices, how much
   hashing/clipping and hidden-unit saturation it exhibits, and whether it can learn controlled
   action preferences from actual training states. Compare candidate bindings and decision
   families; use no hidden engine state as learner input.
2. Inspect whole-run return variation, advantage/critic behavior and per-family policy movement.
   The current implementation assigns the final bootstrap run return to every decision, with a
   state-value baseline. This is a candidate credit-assignment bottleneck, not an established
   cause. Small raw rewards alone are not proof of a scaling bug: actor advantages are normalized.
3. Choose one evidence-backed change and freeze a separate recipe and success criterion. Keep
   current sources/results immutable, all current legal action families learnable, wins primary,
   A8 fixed and reserved evaluation independent. Do not repair a disappointing result by altering
   its selection rule, removing failures or restricting genuine optional actions.

No larger unchanged PPO/GA run, new mechanics sweep, adaptive controller or model promotion is
justified by this result. The next diagnostic can largely use saved training data; additional
native rollouts or long jobs require a separately declared experiment and owner handoff.
