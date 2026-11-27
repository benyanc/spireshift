# Controlled teaching result

The comparison is complete. **Both players learn and independently execute the
two useful multi-turn lessons, but full-game play does not improve.** Preserve the
original players, all copied finals and their complete optimizer states. Do not
promote a winner, enlarge this unchanged test or launch another experiment automatically.

## What completed

All **295 planned work units** are sealed: two exact imports, 64 fitting epochs
across four copies, the all-finals barrier, **36 natural-fight checks** and
**192 fresh full games**. Each trained copy receives exactly **64 optimizer
updates**, for **256 updates total**. All finals are fixed before evaluation;
no epoch, learning setting or model is selected from evaluation outcomes.

All 36 fight checks complete. Of 192 full-game attempts, **191 terminate normally
and one reference-copy game reaches the declared 4,096-decision cap**. There are
no unattempted cases. The capped case stays in the original denominator with
zero win/progress value; it is not retried or replaced. Thus
`all_evaluations_clean: false` is accurate, while the experiment itself is complete.
The control-only `control_checks_passed` field is not a main-stage admission.

Both original full players remain exact at **5,658 / 6,045 Adam updates**.
Experimental finals end at **5,722 / 6,109**, with the critic and credit predictor
unchanged. This is categorical imitation of public action labels, not ordinary
PPO or a test that validates full-run value/credit prediction.

## Learning and execution work on the taught situations

The two source worlds both come from player 2. Both numerical initializers learn
the same bank; this does not create four independent training worlds.

| Player | Fitting world | Original fight | Reference-copy fight | Improved-plan copy |
| --- | --- | --- | --- | --- |
| 2 | 148 | Loss | Loss | Win, 23 HP |
| 3 | 148 | Loss | Loss | Win, 23 HP |
| 2 | 192 | Win, 31 HP | Win, 31 HP | Win, 48 HP |
| 3 | 192 | Win, 36 HP | Win, 31 HP | Win, 48 HP |

Both improved-plan copies reproduce the **entire taught public-state/action
sequence** in both worlds: 27 raw actions in the rescue fight and 11 in the other
fight, with 20/eight meaningful choices respectively. No improved action is
forced during these checks. The same original opening is replayed to the root,
then each evaluated player makes all remaining decisions independently.
These use the same fixed hidden worlds and exact openings as the lessons.
Successful replay is compatible with memorizing those two examples; it does not
by itself establish broad tactical understanding.

Every changed target becomes its player's greedy choice. Player 2's final
probabilities are **87.9%, 98.0%, 97.7%**, and player 3's are **83.6%, 97.1%, 97.4%**.
Full-plan teacher loss falls **0.6844 → 0.0399** and **1.5526 → 0.0602**. The
reference copies also learn their own demonstrations, lowering their loss to
0.0371/0.0588. These are successful action-learning/execution controls, not full wins.

## Held-out fights show limited transfer

Each version wins the same **two of four held-out fights per player**. Teaching
rescues neither held-out losing fight. There are some HP gains in already-won
fights, so it would be inaccurate to say that nothing transfers.

| Held-out world | Player | Original HP | Reference-copy HP | Improved-plan HP |
| --- | ---: | ---: | ---: | ---: |
| 247 | 2 | 37 | 37 | 46 |
| 247 | 3 | 20 | 50 | 48 |
| 188 | 2 | 40 | 36 | 42 |
| 188 | 3 | 29 | 12 | 29 |

Worlds 232 and 175 remain losses in all versions. HP is a local auxiliary measure,
and these are repeated fixed-world root checks with their exact original openings.
They do not establish better complete-run strategy. No held-out plan is imported
as a fitting label or used to select a checkpoint.

## Full-game improvement is not established

All versions play the same **32 new native worlds**, with two fixed initializers:
64 attempts per version, 192 total. Combat is greedy; noncombat is sampled using
the same existing behavior-stream/navigation rules. Shared actor updates can
change probabilities in both combat and noncombat.

| Version | Full wins | Runs completing an act | Mean maximum floor | Failed/capped games |
| --- | ---: | ---: | ---: | ---: |
| Untouched originals | 0/64 | 5/64 | 13.2500 | 0 |
| Reference copies | 0/64 | 2/64 | 12.6406 | 1 |
| Improved-plan copies | 0/64 | 0/64 | 12.5156 | 0 |

The primary paired improved-plan-minus-reference floor difference is **−0.125**,
with a world-clustered 95% interval **[−0.9844, +0.7031]**. Against untouched
originals it is **−0.7344 [−2.0000, +0.4219]**. The observed floor means are worse;
these intervals still include zero. Do not claim a reliably quantified population
floor regression from this small panel.

Other auxiliary measures also do not support promotion: versus originals, mean
act completion changes **−0.0781 [−0.1406, −0.0156]**, and the bootstrap training
return changes **−0.00546 [−0.01056, −0.00101]**. These are secondary measurements,
not replacements for the terminal-victory objective or a causal diagnosis.

The independent unit is the native world, clustering both fixed initializers;
192 attempts are not 192 independent worlds. Uncertainty does not cover a
population of training initializers. Resampling all-zero wins yields a zero-width
win-difference interval; that does not prove equal underlying win probabilities.

## What the diagnosis narrows down

A **73.21-second saved-only diagnosis** verifies **115,651 source seals / all
295 work-unit receipts**, reconstructs **615 frozen fight distributions/choices**,
and reproduces complete fresh-game comparisons and original full-state/Adam
imports. It changes no source, model or optimizer and launches no game.
Native delivery audits are reused from their sealed evidence, not rerun here.

The same 128-menu historical TRAIN probe exposes broad probability movement from
teaching two fights. On player 3, the improved-plan copy changes the greedy combat
choice on a world-balanced **81.8%** of the 14 selected combat states from 11
worlds. Shop top choices change on a world-balanced 50% of seven states/four worlds;
card-reward top choices change on 20% of 15 states/ten worlds. These small, balanced
probes are not natural gameplay rates. Movement does not prove that the changes
caused the full-game result, but makes shared-policy interference a real hypothesis
to isolate rather than assume away.

The capped reference-copy case is `SP1RESH1FTSTUDM021`, player 3, at floor five.
Its final public trace reaches round **1,004**, repeatedly playing Havoc/Defend
and ending turns while a Toadpole remains at ten HP. The public combat-pile read
places **all five Strikes and Bash in exhaust**; its remaining draw/discard/hand
cards offer no attack. Those pile identities already reach the public input:
checking only the summary pile counts would incorrectly suggest an adapter omission.
All saved behavior probabilities and native deliveries verify. This is a concrete
long-term action-consequence failure, not evidence of an unsupported action or a
reason to relax the cap. The partial game never becomes training data.

## Next work, in order

1. Preserve this completed result and its uncertainty. No promotion, unchanged
   rerun, new PPO round or adaptive-controller admission follows.
2. Use completed public records to qualify **card-zone ownership and exhaustion
   distinctions through the actual actor encoder**, holding the permanent deck
   constant. Public pile identities exist; check whether relevant distinctions
   survive encoding rather than inventing missing adapter fields. Distinct inputs
   do not require an untrained player to choose differently. Treat Havoc's removal
   of future attacks as a useful future multi-turn teaching situation.
3. Propose a bounded **more varied fitting-only teacher/student curriculum** with
   prospective world splits and fresh final evaluation. Match teaching work and
   retain the original/reference controls so broader evidence is tested separately
   from more optimizer steps. Do not reuse these 32 final evaluation worlds or
   convert held-out improvements into fitting labels.
4. Include a separately declared test of **shared-policy interference**, such as
   matching the original noncombat behavior during a combat-teaching evaluation.
   This is a diagnostic comparison, not a permanent action restriction or a demand
   that a weak original policy cannot change. Do not infer its answer from old-state
   probability movement alone.

The evidence points to narrow-data generalization/transfer as a limitation of
this teaching test. It does not establish that a broader curriculum alone will
solve full-run learning, nor that the old coarse value baseline is now adequate.

## Resource accounting

The three owner sessions total **2,038.83 wall seconds (33.98 minutes) / 1,474.81
CPU seconds**, with **719.50 MB peak RAM / 633.25 MB final cumulative output**.
Do not sum cumulative storage or interpret the last session's 515 seconds as the
whole experiment. Frozen app/runtime/SDK/cache reuse creates zero game app copies.
The diagnostic adds **25.61 MB** of reports, with **316.87 MB peak RAM** and zero
game or optimizer work. All original and trained full states remain preserved.

Repository verification passes **2,497 tests / five skips**, strict types on
**549 files**, format/lint and the C# protocol in **146.79 seconds**. Only result
and handoff documentation changes; numerical/worker/experiment implementations,
recipes and every saved full weight/Adam state remain unchanged.

See [experiment design](native-plan-teaching-test.md),
[diagnostic guide](native-teaching-diagnostics.md) and
[portable result evidence](evidence/native-plan-teaching-result-v1.json).
