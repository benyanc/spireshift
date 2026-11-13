# Complete-turn teacher result

The owner completed the finite pilot successfully. **The comparison machinery works,
but this pilot has not established better play or reliable better-turn targets.** Both
players, their full optimizer states and the coarse credit predictor remain unchanged.
The [collection design](native-complete-turn-teacher.md) and its original preparation
evidence remain preserved. [Portable result evidence](evidence/native-complete-turn-teacher-result-v1.json)
records the completed result separately.

## What completed

All **569 native attempts** finished: 65 proposals, followed by **504 scored branches**
covering 63 distinct complete-turn plans with eight paired continuation streams each.
Exact trace deduplication removed 16 comparisons from the declared 585-attempt upper
bound. All eight source positions remain in the denominator; there are no failures,
skips, app copies, optimizer updates or full-run wins.

The 504 scored branches contain five act clears and reach floor 22 at best. These are
dependent counterfactual samples from **eight original hidden worlds**, not a new
player's win rate or 504 independent seeds. Plan selection did not use proposal scores.
No nested-selection choices occurred in this pilot, so it adds no native coverage of
those boundaries.

Across the 55 alternative plans and eight paired streams, final bootstrap returns are:

| Compared with the reference turn | Paired outcomes |
| --- | ---: |
| Higher | 25 |
| Lower | 65 |
| Tied | 350 |

That is **79.5% ties**. The greedy reference has the highest sampled average, including
ties, in six of eight positions. Two positions have identical returns for every plan
and continuation. The smallest one-sided improvement sign p-value is **0.1445**; no
alternative passes the original within-position improvement rule. Keep that rule
unchanged. Zero admitted preferences does not prove that every noisy target is useless,
but it does not support treating these alternatives as trusted improvements.

## Why different turns can still teach the same lesson

Saved proposal traces show that **40 alternatives reach a different exact public
boundary from the reference**. Of these, 18 still have identical paired final returns.
Differences are therefore not explained entirely by reordered moves reaching the same
observed state. Exact public equality is a narrow diagnostic, not a hidden-state or
semantic equivalence proof.

The clearest example is the Byrdonis elite position. One proposed turn leaves **28 HP
against 53 enemy HP**; ending immediately leaves **20 HP against 84 enemy HP**. Despite
these materially different situations, all eight continuations after each plan die on
floor 7, giving identical floor/act-based training returns. The boss position likewise
has ten distinct public boundary states, but all 104 scored branches die on floor 17.

This is evidence that the present experiment cannot distinguish some consequences of
a turn. It does **not** prove that the better-looking state wins under stronger play,
that more HP is always strategically better, or that continuation alone is the cause.
These source positions may already be difficult to recover, candidate quality is
limited, and the unchanged weak continuation may erase a temporary advantage.

The more promising sampled differences remain uncertain. In one normal fight, a plan's
only gain is one continuation reaching floor 15 instead of 9; its leave-one-stream-out
mean gain includes zero. In another, several positive means are strongly influenced by
one act clear. These post-hoc checks describe fragility; they do not create new labels
or justify discarding rare outcomes.

## Verification and cost

A **33.56-second saved-only assessment** verifies 569 sealed receipts and **33,426 source
files**, reconstructs exact bindings, native terminal evidence, auxiliary returns,
candidate freezing and every comparison table. It decodes **9,942 proposal decisions**
and verifies all 65 proposal boundaries and their 225 turn steps. Both complete
model/Adam byte seals agree, with counters still **5,658 / 6,045**.

All 85,090 decision counts come from sealed headers. The assessment does not reconstruct
the 504 scored continuation histories or every policy probability. Their trace and
native journal bytes verify; delivery semantics were audited during collection. The
earlier 39-branch control independently reconstructed its 6,077 decisions. Repeating the
full pilot's policy inference is estimated at roughly 7.6 minutes from that control,
so Codex did not launch it. This is an explicit verification scope, not a new blocker
requiring another long run before interpreting the outcome tables.

The three collection resource sessions total **28.71 wall minutes**, **1,391.65 CPU
seconds**, **425.44 MB peak memory** and **850.26 MB cumulative output**. The main
report's 130.96-second value covers only its final session. Cumulative storage is not
summed. No game, training, promotion, push or GitHub Actions follows this assessment.

The current repository check passes **1,979 tests**, strict types on 396 source
files, formatting/lint and the C# protocol contract in **119.65 seconds**. Tracked
changes are result documentation only; the frozen collectors and learner are intact.

## Next work

1. **Test a bounded combat planner as a continuation and candidate source.** Compare
   it against the unchanged continuation using frozen roots/plans, native transitions,
   declared computation limits and outcome-blind candidate generation. First qualify
   a short control and measure cost; only then freeze one finite owner-run experiment.
   Complete-fight survival, postfight health and loss location are diagnostics; genuine
   full-run outcomes and the declared bootstrap score remain explicit. Do not silently
   introduce HP rewards or declare a search policy stronger before measuring it.
2. **Use numerical supervision only after feedback is measurably more informative.**
   Compare any proposed targets with the reference, keep uncertainty and source-world
   separation, and test a bounded student intervention on fresh complete games. Fork
   both exact weights and every Adam moment. All supplied legal decision families
   remain learnable; fixed-world teacher episodes are separate from ordinary PPO.
3. **Do not scale this unchanged collection.** More repetitions of the same weak
   continuation, a relaxed preference threshold or another critic grid is not the
   next step. Other difficulties, large GA batches and adaptive thinking remain
   deferred; base readiness still precedes the adaptive controller.

**No command is needed for the completed collection.** A new long command will be
provided only after the next bounded experiment is implemented and qualified.
