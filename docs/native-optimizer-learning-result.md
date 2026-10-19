# Native A8 optimizer learning-curve result

Assessed 2026-10-18. The finite comparison is complete: **340/340 sealed units,
2,368/2,368 game attempts, zero failed games and zero app copies**. It preserves the
frozen Ironclad/A8 v0.111.0 environment, whole-run bootstrap score and public action loop.
No checkpoint is promoted and no readiness or adaptive-controller pass is granted.

## Observed progress

Each player receives 512 training games. Each numerical initializer has 16 development
seeds, paired across methods and checkpoints, separate from training. There are two
numerical initializers. Results below average those two 16-game panels.

| Training games per player | Standard: 32-game batches, 3 passes | Candidate: 128-game batches, up to 9 passes |
| ---: | ---: | ---: |
| 0 | 6.28125 | 6.28125 |
| 128 | 6.93750 | 7.21875 |
| 256 | 7.62500 | 7.65625 |
| 384 | 7.81250 | 7.25000 |
| 512 | **9.09375** | **7.40625** |

These are mean maximum floors, not win probabilities. The standard method gains
2.8125 floors, approximately 44.8% relative to its initial mean floor. The candidate
gains 1.125 floors. Standard's final mean exceeds the candidate's by 1.6875 floors.
The average standard curve is still rising at the finite endpoint; it does not
establish how far further training will improve it.

| Player | Initial mean floor | Final mean floor | Change | Final full wins |
| --- | ---: | ---: | ---: | ---: |
| Standard, initializer 2 | 6.3125 | 8.8750 | +2.5625 | 0/16 |
| Standard, initializer 3 | 6.2500 | 9.3125 | +3.0625 | 0/16 |
| Candidate, initializer 2 | 6.3125 | 7.5625 | +1.2500 | 0/16 |
| Candidate, initializer 3 | 6.2500 | 7.2500 | +1.0000 | 0/16 |

For the standard players, 20/32 paired development seeds reach a higher floor than
their own initializer, nine tie and three regress. Both training replicates improve.
This is useful evidence of learning auxiliary progress, beyond just fitting saved
advantages. It is a small development study, not population-level algorithm superiority
or an untouched final benchmark. Both methods have **zero wins in their 32 final
development attempts**; all 320 development attempts across checkpoints are also
winless, and those repeated panels are not 320 independent game seeds.

The standard method's best sampled training game reaches **floor 27, one completed
act**. Its frozen development players reach at most floor 17 and complete no act.
A sampled training success must not be presented as reliable frozen-player ability.
There are zero full wins across all 2,368 attempts. Strong full-run play remains unmet.

## What the comparison says about the method

Keep the standard 32-game / three-pass setup as the candidate for the next confirmation.
The larger-batch/reuse bundle underperforms it in both replicates at the same game
budget. The earlier saved-data study's better in-sample fit did not translate to the
best independent play in this experiment.

The bundle changes two things: independent games per batch and passes through each
batch. Standard updates after every 32 games, with 16 batches per player; the candidate
updates after every 128, with four batches. The candidate uses more fitting work.
The result cannot isolate batch size, reuse, update frequency or another mechanism
as the cause. It does not prove that larger batches or additional passes are generally
harmful. No learning-rate, reward, actor input, model size or action restriction changed.

Actual work across two players per method:

| Method | Training games | Training decisions | Fits | Optimizer steps | Epoch stops |
| --- | ---: | ---: | ---: | ---: | --- |
| Standard | 1,024 | 115,937 | 32 | 2,766 | All at 3 passes |
| Candidate | 1,024 | 110,347 | 8 | 7,794 | All at 9 passes |

Neither method reaches its existing per-update KL stop in these fits. Parameter
updates occur; the standard actor is not disconnected or permanently frozen.
More numerical work alone is not the objective. Genuine terminal wins remain primary.

## Integrity and measured cost

A separate read-only assessment checks **340 receipts / 25,409 source seals**, opens
all 2,368 compact episode headers and reconstructs seed ownership, model/Adam chains,
terminal outcomes, score values, collection summaries, all learning curves and the
final paired comparison. It decodes no raw trajectories, launches no games and performs
no optimization. The original report and every historical source/config remain unchanged.
The assessment takes **23.71 seconds / 122.47 MB** peak RAM.

The actual experiment uses 15 successful resource-tracked sessions totaling
**8,389.71 wall seconds (2 h 19 min 50 s)** and 8,524.26 CPU seconds. Peak memory is
**1.136 GB**, retained output **2.402 GB**, and no app copies are created. The final
report's 59.16 seconds describes only its last session, not the entire experiment.

Exact source report: `sha256:5be34f750d8bbe3fc17066446e556c403cf3bc5be8cf985eda2fa8a71826ea44`.
[Machine-readable assessment/evidence](evidence/native-optimizer-learning-curve-result-v1.json).
The completed training command now only verifies its saved result; do not rename its
workspace, clear evidence or replay the completed plan.

## Next work

1. Prepare an independent, frozen comparison of **both final standard players against
   their own original players**, using a new reserved panel of at least 64 complete-run
   seeds per initializer. Keep evaluation behavior, temperature, rules and run budgets
   matched, retain failures, and report paired floors and genuine wins. No selection
   among intermediate checkpoints or tuning on the completed panels.
2. If progress repeats, continue the standard players with their **complete saved Adam
   state** and fresh training seeds in a bounded learning curve. There is now evidence
   supporting that measured continuation; this is not the earlier both-methods-flat case.
   Declare the new horizon, stop rule, fresh evaluation panels and resource caps before
   execution. Preserve the two initializers rather than choosing whichever looks best.
3. Use the saved-record diagnostic to target action-credit or qualified teacher work if
   independent progress disappears or the continued player plateaus. Combat still supplies
   most choices, while run-level decisions have little practice. More games are an
   experiment, not a promise of full wins. GA, difficulty expansion and adaptive thinking
   remain deferred.

The confirmation is the next implementation item. No new long experiment or training
extension has been launched by Codex, and there is no pending command to rerun this
completed comparison.
