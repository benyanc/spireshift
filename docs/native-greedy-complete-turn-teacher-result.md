# Fresh-training-world greedy complete-turn teacher result

The owner finished the finite collection. **The collector works, but the tested
turns still do not supply reliable better-than-reference imitation targets.** Both
round-60 players, all their weights and every Adam moment remain unchanged, with
counters **5,658 / 6,045**. This experiment performed no learning updates.

The [original design](native-greedy-complete-turn-teacher.md) and its pre-collection
qualification evidence remain preserved. The [portable result evidence](evidence/native-greedy-complete-turn-teacher-result-v1.json)
records the completed collection and separate saved-only assessment.

## Completion and the misleading failure label

All **469 scheduled native attempts** ended cleanly: eight natural source games,
53 turn proposals and **408 scored continuations**. Seven sources supplied eligible
combat positions, producing **51 distinct plans**. Source `1910003`, assigned to
player 3, died on floor 5 without reaching an eligible public position. Its saved
public history verifies that absence. It stays in the original eight-world
denominator; it is not replaced, retried or described as a successful comparison.

There are **zero failed games, skipped branches, blocked roots, app copies or
optimizer updates**. Every shared-input/account check passes. The final collector
status is `native_greedy_turn_teacher_complete_with_gaps`: its frozen command returns
exit code 1 for any unavailable source, even when every actual game ended cleanly.
The resource wrapper therefore records `failed`. Preserve that report and explain
the status; it is not a game crash, an interrupted batch or resource exhaustion.
**No rerun is needed.** Future runner status handling should distinguish an absent
eligible position from a failed game without changing this historical result.

Usable roots comprise **six normal fights and one elite**, with four roots from
player 2 and three from player 3. These are seven conditional positions from eight
fresh TRAIN worlds, not a representative full-game test, seven independent training
replicates or coverage of every fight type. The eight streams per plan vary later
noncombat decisions inside the same original hidden world.

## Teaching signal

The 408 scored branches produce **zero full wins and zero act clears**. Against
the seven frozen greedy reference turns, the 44 alternatives yield:

| Paired final bootstrap return | Count |
| --- | ---: |
| Higher | 23 |
| Lower | 28 |
| Tied | 301 |
| Total | 352 |

That is **85.5% ties**. Nine alternatives have a higher sampled mean return, eight
have a lower mean and 27 tie. These repeated counterfactuals are dependent samples,
not 352 independent worlds. Do not compare this tie rate causally with the older
teacher pilots: both the source worlds and the continuation behavior changed.

The strongest alternative improves six streams and ties two, with no observed
regressions. It raises mean floor **9.125 → 10.875** at source `1910007`, but its
one-sided sign p-value **0.015625** exceeds the original nine-alternative adjusted
threshold **0.005556**. All **zero admitted preferences** remain rejected under the
unchanged rule. Post-hoc reversal of worse alternatives does not rescue a trusted
target either; the smallest reversed sign p-value is 0.0625 before adjustment.

This does not establish that all raw numerical samples are useless for learning,
or that the promising alternative is ineffective. It establishes that this small
pilot does not justify treating any tested turn as a trusted improvement. Do not
relax the gate, relabel branches as ordinary PPO or automatically train an imitation
student from these rejected preferences.

## What the saved fights reveal

All **51 plans have identical current-fight public traces across their eight
streams**. Greedy combat makes the same decisions until that fight ends; the
additional streams are not new independent combat outcomes. At six roots, every
tested plan survives the fight. At the elite root, every plan dies. Immediate
fight-survival labels therefore do not distinguish actions within these roots.

Health consequences do vary. Relative to the reference, 56 paired cases exit with
more HP, 112 with less and 184 with equal HP, recording zero HP for a terminal loss
without an alive exit. **120 of the 168 cases with different exit HP still end on
the same final floor.** These are post-hoc diagnostics, not rewards or approved
training labels; equal floors alone do not mean equal public states or resources.

For example, at source `1910006`, playing Cinder ends the fight at **42 HP**;
ending the turn immediately eventually exits at **20 HP**. All eight continuations
of both plans nevertheless die on floor **16**, producing identical full-run
bootstrap scores. This verifies a substantial consequence hidden by the current
outcome granularity, not a missing game effect in the recorded state.

Health is also an incomplete strategic target. At source `1910004`, the reference
exits at **53 HP** and averages floor **9.5**, whereas ending immediately exits at
**38 HP** and averages floor **11**. The strongest alternative at source `1910007`
also exits with less HP. These small fixed-world samples do not establish that
losing health is beneficial; they show why a simple HP-maximizing reward or local
health ranking cannot stand in for full-run evaluation. Other resources, later
choices, random outcomes and limited sample size still matter.

## Verification and resources

A **91.72-second saved-only assessment** verifies **469 sealed receipts / 64,766
source files** and decodes every episode, one at a time: **73,123 public decisions**.
It reconstructs public trace identities, first-eligible-root/no-root selection,
source prefixes, exact frozen turn steps and boundaries, native ending evidence,
declared returns, all CPU charges, stage freezes and every lesson table. It checks
**7,654 shared noncombat draws / 3,911 identical-input choices** across 352 pairs.
Both complete player/Adam files retain their original byte seals.

The assessment verifies the collector's sealed per-game native delivery and neural
inference receipts. It does not independently recompute every neural probability,
logit or value, or semantically reaudit native delivery. The earlier native control
did reconstruct all its choices. No game or fitting job was launched for this
assessment; peak memory is **252.44 MB**. Its first private audit attempt stopped
before verifying branches because it read player metadata from the wrapper recipe
instead of its bound behavior recipe; that failed receipt remains preserved. The
corrected saved-only audit passes without changing or retrying game evidence.

The three collection sessions total **38.04 wall minutes / 1,675.50 CPU seconds**,
**434.08 MB peak memory** and **797.71 MB final cumulative output**. The final
main-report duration covers only the last session; cumulative storage is not summed.
Physical proposal CPU totals **142.00 seconds**. Per-alternative accounting charges
all proposal CPU again to each evaluated alternative, without amortization, under
the unchanged 128-CPU-second whole-run objective. This is not a deployed-search
benefit measurement or a new player win rate.

The repository check passes **2,110 tests (four skipped)**, strict types on 424
source files, formatting/lint and the C# protocol in **129.50 seconds**. Tracked
changes are documentation and portable result evidence only; the frozen collector,
learner, models and optimizer states are intact. GitHub #35 / #143 / #146 carry
the current handoff with their earlier history preserved. No push or Actions ran.

## Next work

1. **Prepare a bounded auxiliary combat-consequence learning test.** Use saved
   public decisions and native observed transitions/outcomes as numerical targets,
   with explicit turn/encounter horizons. Test prediction and gradient direction,
   then generalization across whole source games, separating both fixed players.
   Contrast the additional feedback with the unchanged full-run-only learner.
   Later observations may be labels, never extra information in an earlier input.
   Keep all related branches and streams in the same split; seven roots are too
   few to claim broad generalization or justify a large model sweep.
2. **Keep tactical prediction separate from strategic utility.** Better prediction
   of HP, enemy damage, resources or fight endings does not prove better action
   selection. Preserve the primary full-run victory objective and existing bootstrap
   return. Any auxiliary loss needs its own versioned contract; do not introduce
   handwritten HP/Smith rewards or convert rejected preferences into trusted labels.
3. **Require an actual student intervention and fresh-game comparison.** After
   short fitting controls pass, fork both complete saved states and every Adam
   moment for one finite auxiliary-versus-control test. Evaluate full wins first,
   then acts/floors/failures/compute on fresh whole games. No automatic fit,
   unchanged teacher expansion, critic grid, checkpoint promotion or adaptive
   controller follows this result. GA and other difficulties remain deferred.

The next learning method is backlog work, not implemented or launched by this
assessment. No owner command is needed for the completed teacher collection.
