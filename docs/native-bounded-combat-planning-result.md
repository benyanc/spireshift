# Bounded combat-planning result

The owner completed the finite native Ironclad/A8 comparison. It ran cleanly, but
**does not establish a stronger player or sufficiently reliable better-turn labels**.
The planner modestly improves sampled floor and encounter survival; full wins remain
zero, act-clearing branches decrease, and paid search has not been separated from
simply following the existing policy greedily. Neither player was trained here.

The [original design](native-bounded-combat-planning.md) and its
[qualification evidence](evidence/native-bounded-combat-planning-v1.json) remain
preserved. The [result evidence](evidence/native-bounded-combat-planning-result-v1.json)
records this completed collection and the separate saved-only assessment.

## Measured outcomes

All **756/756 new native attempts** finish: 252 combat proposals and 504 selected-plan
evaluations. Reuse 504 verified old baseline episodes. There are zero failed/skipped
branches, blocked initial turns, app copies, full wins or optimizer updates. All
shared-input/account checks pass. Both original weights and every Adam moment remain
unchanged, including counters **5,658 / 6,045**.

These are **eight original TRAIN worlds, 63 initial turns and eight conditional
continuation streams per turn**. The 504 evaluations are dependent counterfactual
branches, not 504 independent fresh games. The source states were selected by public
conditions, not future outcomes; their difficulty is not representative of all A8 runs.

| Diagnostic | Original continuation | Selected combat plan |
| --- | ---: | ---: |
| Full-run wins | 0/504 | 0/504 |
| Alive exits from the tested encounter | 332/504 | 344/504 |
| Average maximum floor | 11.377 | 11.784 |
| Branches clearing an act | 5/504 | 3/504 |
| Highest floor | 22 | 22 |
| Mean declared bootstrap return | 0.025742 | 0.026040 |
| Mean charged CPU seconds per case | 2.125 | 10.464 |

The average floor gain is **0.407** and bootstrap-return gain **0.000299**. Against
its own paired baseline, the planner has **96 higher / 34 lower / 374 tied returns**.
Those comparisons use the declared whole-run score, which includes acts as well as
floors; they are not counts of full wins or independent training improvements.

Four source worlds have identical paired returns under both methods. Three worlds
have positive mean return changes and one has a negative change. In the floor-12
elite source, planning increases alive exits from 43/56 to 56/56 and mean floor from
13.875 to 15.071, but act-clearing branches fall from two to zero. Its mean bootstrap
return therefore decreases. This is a concrete reason to retain full-run evaluation
instead of equating local survival or higher HP with strategic improvement.

## Is this useful teaching feedback?

Relative to each method's own frozen reference initial turn, the 55 alternative
turns give 440 paired comparisons:

- Original continuation: **25 higher / 65 lower / 350 tied** returns, 79.5% ties.
- Selected combat plans: **39 higher / 84 lower / 317 tied**, 72.0% ties.

These counts answer whether alternative *initial turns* differ, not whether planning
beats the original continuation. The unchanged admission rule accepts **zero
better-than-reference preferences**. The smallest sign-test p among alternatives
with positive mean differences remains **0.1445**. Two source worlds remain flat
across every tested initial turn and continuation. More differentiated returns alone
do not establish reliable improvement targets or justify silently weakening the rule.

The plans see one fixed hidden world per source position. Repeated future policy
streams do not supply additional independent draw orders. This remains an explicitly
privileged teacher, ineligible for ordinary PPO or public-belief optimality claims.
Future plan observations cannot be added to a student's current public inputs.

## What did the search actually add?

Of 63 selected remainders, **51 use proposal zero**, the unchanged policy's greedy
combat continuation. Twelve choose a sampled proposal instead: one rescues survival
over the greedy proposal and eleven finish alive with higher HP. Eleven initial
turns produce four exactly identical proposals. All four tried proposals die for
20 initial turns; this does not prove those positions are unwinnable.

The original comparator samples its combat actions at temperature 0.8. The new arm
both changes that behavior and selects among four plans. Consequently this pilot
does **not isolate the incremental value of search over an always-greedy combat
continuation**. The 51/63 count motivates that cheaper control; it is not a measured
fresh-game result for such a player. The extra survival or HP can also trade away
potions and other future resources, which the tactical selector does not price.

Every selected evaluation is charged all four search episodes plus its own episode,
without amortization, within the original **128-CPU-second ceiling**. Mean charged
cost is about **4.93 times** the baseline, although neither arm approaches the cap.
The largest selected-case charge is 18.730 seconds. The shared ceiling is not equal
actual CPU spending. Search costs average 8.472 seconds per initial turn and peak
at 15.186 seconds; no case is excluded for budget exhaustion.

## Verification and resource use

The separate saved-only assessment verifies **756 receipts / 63,175 source files**,
all branch bindings, genuine terminal evidence, declared returns, CPU charges,
frozen tactical selection and every comparison table. It decodes **252 proposal
histories / 38,460 decisions**, reconstructs 2,453 combat-remainder steps and all
252 encounter exits, and checks both complete model/Adam seals. Runtime is
**130.06 seconds**, peak memory 158.86 MB, with no new games or fitting.

This assessment does not repeat neural inference or reconstruct every scored
continuation probability. All retained journal bytes verify; collection's native
delivery audits remain preserved. It does not claim an independent semantic reaudit
of native delivery. The earlier short control reconstructed all its probabilities,
and its exact baseline/duplicate traces matched. The main pilot contains no new
duplicate/baseline control attempts; its null control fields are not fresh passes.

The three collection sessions total **37.76 wall minutes / 1,842.17 CPU seconds**,
465.16 MB peak memory and **1.282 GB final cumulative output**, with no app copies.
Do not sum cumulative output across sessions or report only the last session as the
whole experiment. Physical collection CPU is separate from per-evaluation accounting
that intentionally recharges reused searches eight times.

Private assessment: `artifacts/native-combat-planning/result-assessment-v1/report.json`.
Original report: `artifacts/native-combat-planning/sts2-v0.111.0-a8-pilot-v1/report.json`.
Both are sealed separately; the original collector and all previous evidence remain
unchanged.

The repository check passes **2,025 tests, with four skipped**, strict types on
406 files, formatting/lint and the C# protocol in **119.54 seconds**. Tracked changes
are documentation only; the private saved-data assessment creates no game or update.

## Next work

1. **Isolate cheap combat behavior before expanding search.** Prepare a bounded
   matched comparison of sampled versus greedy combat from both preserved players,
   with identical noncombat policy, declared RNG streams and fresh whole-game seeds.
   If comparing search on these old roots, include an always-greedy remainder arm.
   Keep full wins, acts, floors, failures and actual CPU separate. Do not optimize
   another setting against these already inspected eight worlds.
2. **Require useful continuation before another teacher expansion.** Use the
   control to choose a better continuation or revise candidate generation. Do not
   automatically collect more of this four-proposal method, widen a critic grid,
   convert HP into a learner reward, or admit its rejected preferences. Any new
   teacher/student method needs separate frozen evidence and whole-world validation.
3. **Return to bounded student learning when the targets support it.** Fork both
   exact full states, preserve every Adam moment, leave all legal families learnable
   and test fresh complete games. Fixed-world counterfactual supervision remains
   separate from ordinary PPO. No promotion or adaptive-budget controller follows
   this result; foundation readiness is still unpassed.

**No owner command is needed for the completed comparison.** No new long run,
training, model promotion, push or GitHub Actions follows this assessment.
