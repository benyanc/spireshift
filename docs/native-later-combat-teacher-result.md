# Later-turn teacher result

The 456-branch collection completed. Its saved receipts, terminal returns and action
tables agree. **It has not improved either player:** no fitting occurred, no alternative
passed the frozen improvement rule, and no full game was won. Keep both original
players, complete Adam states and the current coarse value predictor unchanged.

## What was collected

All 57 offered actions across eight later combat positions were tried with eight
continuation-policy streams each. Every branch reached its intended position and ended
normally; there were no failed or skipped branches. These are **eight original hidden
worlds**, with repeated conditional continuations, rather than 456 independent seeds.
Inputs to a future student remain public. The fixed-world teacher remains explicitly
privileged, ineligible for ordinary PPO or public-belief search claims.

The collector used two resource sessions: **1,380.85 seconds total wall time** (about
23 minutes), 1,127.77 CPU seconds, 391.79 MB peak RAM and 674.54 MB cumulative output.
The final report's 577-second field is the last collector session, not the full
experiment. Cumulative storage is not added across sessions. No game apps were copied.

Three branches cleared an act and reached floor 21; none won a full run. Repeated
branches and a best sampled outcome do not establish an improved policy.

## Strength of the lessons

Against each position's frozen current choice, the 392 paired alternative comparisons
contain **23 higher returns, 79 lower returns and 290 ties**. Thus 74.0% tie. Six menus
have different sampled action means; two have exactly the same return for every branch.
The sole boss position and one elite position are completely flat.

The original fight-entry teacher had 78.1% ties and also six varied/two flat menus.
Different positions and source worlds prevent interpreting that difference as a
controlled improvement from later-turn selection. The smallest one-sided improvement
sign p-value is 0.3633; **zero alternatives pass the unchanged preference rule**.
That rule tests outperformance frequency, not optimal expected return.

There is evidence about poor choices, but its practical value is limited here:

- At one elite position, ending the turn loses to the current choice in all eight
  paired continuations; average maximum floor is 12.125 versus 16.125. The current
  temperature-0.8 policy already gives that end-turn action only **0.0066% probability**.
- At another position, end turn loses in seven continuations and ties in one; average
  floor is 6 versus 8.75. Its current probability is already only **0.1011%**.
- At one position, the best sampled alternative beats the reference in only one
  continuation and ties in seven. Removing that stream removes the measured gain.
- A different apparent best action loses its positive mean advantage when one stream
  is omitted. Two apparent improvements are heavily influenced by rare act clears.

The reverse-direction counts and leave-one-stream-out checks are **post-hoc descriptive
diagnostics**, not newly admitted labels or independent confirmation. Rare successes
stay in the data. They should not be deleted, nor should their sample maxima be treated
as reliable best-action targets. The largest reported gains have paired standard
errors comparable to or larger than their mean advantage.

Zero admitted preferences alone does not make action tables useless. A separately
declared exploratory loss could use uncertain means and negative examples. In this
particular collection, however, the clearest negative lessons concern actions the
player already almost never chooses. Blindly fitting those examples, repeating this
same collection at scale, or choosing the largest sampled mean is not a convincing
next improvement step.

## Verification performed

The short saved-only assessment verifies **all 456 immutable branch receipts and
28,943 protected source files**. It checks exact task/world/model/score bindings,
episode header and compressed trace seals, clean native ending fields, and recomputes
all terminal returns and complete action tables, including uncertainty and the original
preference rule. Both original player/Adam states retain their exact bytes and counters
(5,658 and 6,045). A separate check reconstructs all eight current public-root policy
distributions; each greedy choice agrees with its frozen reference.

The receipt/outcome assessment takes **17.49 resource seconds**, 11.49 CPU seconds and
150.95 MB peak RAM, with zero games or optimizer updates. Full continuation inference
over the 68,524 declared decisions is **not rerun** by this assessment. Native journal
bytes are verified; native delivery semantics were checked during collection and are
not independently reaudited here. The earlier 24-branch control reconstructed all
3,950 of its policy decisions. Do not confuse that control with a complete main-pilot
behavior reconstruction, or this assessment with a learning validation.

This result update changes documentation and portable metrics only. Formatting/lint
and strict types pass. The full repository suite reaches its **240-second wall cap**
before finishing, with no test failure reported before the stop; that is not a fresh
full pass. Its resource report is retained. The earlier implementation check passed
1,927 tests. No longer check, native game or training run is started to complete this
documentation update.

Private saved results:

- `artifacts/native-later-teacher/sts2-v0.111.0-a8-pilot-v2/report.json`
- `artifacts/native-later-teacher/result-assessment-v2/report.json`
- `artifacts/native-later-teacher/result-assessment-v2/policy-opportunity.json`
- `artifacts/resources/native-later-combat-teacher-pilot-v2-1.json`
- `artifacts/resources/native-later-combat-teacher-pilot-v2-2.json`
- `artifacts/resources/native-later-teacher-result-assessment-v2-1.json`
- `artifacts/resources/native-later-teacher-result-repository-check-v2-1.json`

## Next work

1. **Change the unit of feedback to a coherent remainder of a combat turn.** Prepare
   a small, separately versioned teacher comparing legal sequences through end turn,
   rather than forcing one card and immediately handing control back to the same
   weak continuation. Freeze candidate generation, public root selection and budgets
   before collecting outcomes. Preserve existing controls and data; make no claim
   that coherent turns are already proven better.
2. **Keep outcomes honest and check for useful signal first.** Use native transitions,
   source/world ownership, repeated continuation streams, full-run outcomes and the
   declared auxiliary score. Do not add handwritten HP/upgrade rewards, manufacture
   positive preferences or call fixed-world branches fresh on-policy games. If the
   revised finite pilot is still flat, assess stronger continuation before scaling.
3. **Only then test a bounded numerical learning intervention.** Public-only student
   inputs, uncertain action/sequence targets, whole-source-world fit/selection and
   fresh whole-game gameplay at equal compute are required. Fork both players and
   every Adam moment; keep all legal decision families learnable. Full victories
   remain primary and readiness still precedes adaptive thinking.

No collector rerun, training or long audit is requested for this completed result.
The next implementation is the small coherent-turn teacher, not another unchanged
critic grid or a larger copy of this experiment. See [backlog](backlog.md),
[original collection design](native-later-combat-teacher.md) and
[portable result evidence](evidence/native-later-combat-teacher-result-v2.json).
