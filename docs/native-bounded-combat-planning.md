# Bounded combat-planning comparison

**Completed 2026-10-20.** The owner finished all 756 attempts. See the
[result and next work](native-bounded-combat-planning-result.md): modest floor and
encounter-survival gains, zero wins or admitted better-turn preferences. Both
players and full optimizer states remain unchanged. No new owner run is requested.
The design and qualification below describe the preserved original experiment.

This experiment tests whether a small sampled combat planner makes complete-turn
feedback more informative. It preserves both exact players and every Adam moment.
It collects comparisons; it does not fit or promote a model or change the coarse
credit predictor. The [preceding pilot](native-complete-turn-teacher-result.md)
motivates this test: different post-turn states often led to the same final floor.

## Frozen comparison

Reuse all eight original TRAIN worlds, their 63 frozen initial turns and **504
completed baseline branches**. Baseline receipts, native journals, terminal returns,
turn identities and original model/optimizer bytes must still verify. Read one saved
episode at a time; retain compact results and paths. No baseline game app or episode
is copied.

After each initial turn, the new planner tries exactly four combat remainders:

1. One greedy continuation from the unchanged policy.
2. Three independently sampled continuations from that policy at temperature 1.2.

Each remainder runs until an observed public encounter exit or native terminal
ending. It includes subsequent turns and nested selections, and uses native game
transitions for costs, targets, draws, potions and relic effects. Plans are capped
at 512 decisions and 8 MB. Unknown ownership, mismatched replay, truncation and caps
are failures, never partial successful plans. No fabricated end-turn or exit is used.

Every candidate is sealed at that boundary **before choosing a postcombat action**.
Workers then finish their games at the unchanged temperature 0.8 policy to close
and audit delivery normally. These later outcomes cannot rank candidates: the
selector accepts only proposal order, plan references, observed survival and HP.

Choose a remainder by **alive encounter exit, then remaining public HP, then fixed
proposal order**. An alive exit can include escape; it is not labeled a combat
victory. Native terminal endings have no invented HP. If every candidate dies,
the fixed first proposal wins the tie. Exact duplicate proposals still count toward
the four-attempt budget and their full cost is charged.

This is a deliberately small sampled planner. The tactical rule can spend valuable
potions or prefer health over other resources, so higher selected HP does not prove
better strategic play. The subsequent complete-run comparison is necessary.

## Evaluation and compute

Freeze all selections before any new scored evaluation. Replay each selected combat
remainder exactly, including public observations, current costs and target ordering.
Then return control to the original player for every later decision family. Evaluate
each initial turn with eight declared continuation streams paired with its original
baseline. Source prefixes and initial turns remain exact; proposal randomness is
separate from evaluation randomness. Forced combat actions consume the same one-draw
convention as the old policy's strategic choices, preserving each arm's postcombat
policy distribution. Fresh baseline controls must reproduce the original full public
action traces.

The objective remains terminal full-run victory under the same **128 CPU seconds
per complete-run case**. The four search proposals together may use at most 64 CPU
seconds, with a 32-second limit per search call. Every scored replay pays the **sum
of all four proposal episode CPU costs plus its own episode CPU**, without amortizing
the search across repeats. Even proposal closure and repeated source-prefix execution
are charged, conservatively. Delivery audit cost and experiment-wide measurements
remain separately reported by the resource wrapper, as in the original collector.
Both arms share the CPU ceiling; actual CPU spending can differ and remains in the
receipts. Summed per-case search charges intentionally count reused planning more
than once and must not be reported as physical experiment CPU usage.
Budget exhaustion blocks the affected plan; failed/unattempted evaluations retain
their original denominator and zero evaluation value. Uncertain delivery is not retried.

HP is a declared **planner selection heuristic**, not a new learner reward or a change
to the bootstrap return. The original whole-run floor/act bootstrap score and binary
win outcomes stay separate. Compare complete-run wins, paired floor/return changes,
encounter exits, failures, CPU cost and how often alternative turns still tie. Keep
the existing preference rule, uncertainty and full wins primary.

The main plan is **252 search attempts plus 504 selected-plan evaluations: at most
756 new native attempts**, reusing the 504 old baseline episodes. A failed item stops
its remaining attempts after verified worker retirement while other planned items
may continue. A source-prefix mismatch, changed evidence or uncertain shutdown stops
the experiment for inspection. No automatic repair or resubmission follows.

## Scope and qualification

These are privileged **fixed-world teacher counterfactuals**. There is one original
hidden world per source position; the eight streams vary future policy choices, not
hidden draw orders. A chosen future action sequence is not a public-belief planner
or an ordinary PPO episode. Student inputs may only use the public state at the
decision being taught; never concatenate later plan observations into that input.
This experiment is not an independent win-rate benchmark or a readiness pass.

The short control chooses one position per player by public menu size, prefix length
and root identity, keeping its reference turn and offered end-turn alternative.
This selection does not use their final scores. Four initial turns require 16 search
attempts, eight evaluations, two exact selected-plan repeats and two fresh original
baseline checks: **28 new attempts**, with eight old baseline episodes reused.

The main recipe requires this matching clean control and a saved audit reconstructing
every choice, probability, encounter boundary, candidate selection, CPU charge and
comparison table. Native delivery semantics are audited during collection; the
saved audit checks those journal bytes without claiming an independent semantic
reaudit. The main source/parameters are fixed before the control; only its report
and audit identities are bound afterward.

Workers share immutable frozen game, runtime, SDK and support files, with isolated
profiles and ledgers. **Zero app copies.** The owner-run pilot resumes complete
receipts across 15-minute sessions, with 2 GB memory and 4 GB retained-output caps.
The same command resumes only the finite comparison and displays a completed result.
No training, promotion, genetic search, other ascension or adaptive-controller run
follows automatically. The current backlog records the qualified handoff and one
specific next owner command.

## Qualified checks and owner run

The short native control completes **28/28 attempts**, with no failures, skips,
blocked plans, app copies or optimizer updates. Both repeated selected-plan traces
match, and both fresh original baselines reproduce their exact saved full public
traces. Two clean sessions total **247.23 wall seconds**, 158.20 CPU seconds,
372.93 MB peak memory and 56.26 MB cumulative output. This two-world control does
not establish stronger play: both methods have zero full wins and six alive
encounter exits among their eight scored branches.

The saved audit reconstructs all **4,338 public decisions**, probabilities, plans,
encounter boundaries, selection, total CPU charges and tables in **60.92 seconds**.
The full repository check passes **2,029 tests (50 new)**, strict types on 406 files,
formatting/lint and the C# protocol contract in **129.17 seconds**. Final preflight
verifies **51,213 original evidence files** and **34,547 control-source files**;
both exact full player/Adam states remain unchanged, with counters 5,658 / 6,045.
The main plan passes with native hosts disabled and creates no pilot workspace.
Only passed control/audit identities change from its predeclared template.

See [portable verification evidence](evidence/native-bounded-combat-planning-v1.json).
The finite pilot has now completed. The preserved entry point below displays the
saved result on repeat; it does not request another collection:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/compare-native-combat-planning-v1.sh
```

The original estimate was 60–90 minutes. Actual collection took **37.76 wall minutes**
over three sessions, reusing the 504 baseline episodes. The saved-only assessment
verifies the full denominator, selection, returns and costs. No fitting or next
experiment follows. Read the [completed result](native-bounded-combat-planning-result.md)
before considering another teacher or student run.
