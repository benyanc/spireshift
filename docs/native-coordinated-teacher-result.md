# Earlier-turn coordinated teacher result

The bounded comparison completes cleanly. Search finds useful natural combat
lessons, including a lost fight that becomes a win, but **coordinated search has
no demonstrated advantage over the simpler method**. No student has been fitted
and no full-game improvement has been measured. Both original players and every
Adam moment/counter remain exact at **5,658 / 6,045** updates.

## Completed work

All **576 planned work units** are sealed: **533 native paths / 43 unavailable
proposals**, with **zero failed or capped paths**. An unavailable proposal means
the finite search has no eligible extension; it is not an attempted or failed
game. All **32 comparison cells / eight worlds** and their confirmations verify.
There are 16 references, 469 candidate paths and 48 confirmation replays. Early
and later entries share the same world; branches and entries are not independent
samples. This is eight local fight comparisons, not 533 full-game attempts.

All four implementation checks pass. The report's `control_checks_passed: false`
is intentional: that field applies only to the separate qualification-control
stage. The main status is `coordinated_teacher_complete`; it needs no rerun.

A **171.85-second saved-only audit** verifies **105,961 sealed source files**,
reconstructs all **576 requests/receipts and proposal lineages**, and reproduces
every cell and paired comparison. It independently recomputes **1,175 action
distributions/choices** and re-audits **64 native journals** for all references
and confirmations, including the selected plans. Nonselected candidate journals
retain their original sealed native audits; they are not all independently
re-audited in this assessment. Both full original state hashes/Adam counters
match. No native game, refit or optimizer update runs during the assessment.

## What the search found

Each column below describes plans selected after observing native fight outcomes.
The fitting and held-out splits each contain four worlds, balanced across players.

| World split | Greedy reference fights won | Single-change early / later | Coordinated early / later |
| --- | ---: | ---: | ---: |
| Fitting: four worlds | 1 | 2 / 2 | 2 / 2 |
| Held out: four worlds | 2 | 3 / 3 | 3 / 3 |

Both methods rescue the same fitting fight and the same held-out fight. Neither
rescues the other three losing reference worlds. Bounded failure to find a rescue
does not prove those positions are unwinnable.

Ending HP for the selected winning plans is shown below; **L** means fight loss.
An early/later pair is two entry points into the same fight, not two new worlds.

| World | Split / player | Reference | Single early / later | Coordinated early / later |
| --- | --- | ---: | ---: | ---: |
| 148 | Fitting / 2 | L | 23 / 23 | 17 / 17 |
| 192 | Fitting / 2 | 31 | 43 / 41 | 48 / 41 |
| 202 | Fitting / 3 | L | L / L | L / L |
| 164 | Fitting / 3 | L | L / L | L / L |
| 247 | Held out / 2 | 37 | 50 / 50 | 46 / 37 |
| 232 | Held out / 2 | L | L / L | L / L |
| 175 | Held out / 3 | L | 8 / 8 | 8 / 8 |
| 188 | Held out / 3 | 29 | 29 / 44 | 29 / 42 |

The two improved fitting worlds both belong to **player 2**. Their selected early
coordinated plans each change two decisions: one rescues a loss and the other
saves **17 HP**. Single-change search also supplies useful fitting plans, including
the better 23-HP rescue. Player 3 supplies no improved fitting world in this bank.
Its useful held-out examples remain excluded from fitting.

On held-out worlds, both methods select three winning fights at either entry.
Single-change search improves **two early / three later** worlds; coordinated
search improves **two early / two later**. Among already-won reference fights,
single-change search saves **13 early / 28 later HP in total**, versus **9 / 13**
for coordinated search. These are small, dependent, fixed-world local comparisons;
they do not establish a population-level method ranking or full-run utility.

## Why additional changes do not automatically help

The methods spend their 16 proposal slots differently. Single-change search
tests up to 16 first changes. Coordinated search tests only four first changes,
then spends its remaining slots extending those lineages. It can miss a useful
initial alternative that the wider method tests.

The fitting rescue makes this concrete: none of the first four early single
changes wins. Coordinated extension finds a two-change win at 17 HP, while the
wider method finds a one-change win at candidate 10 with 23 HP. In the other
improved fitting fight, extending a lineage improves 43 HP to 48 HP. Coordinated
planning therefore can help within its explored lineages without dominating a
wider search under the same slot limit. This is measured coverage, not a reason
to claim every coordinated loss is caused by insufficient width.

Earlier access also does not uniformly improve the best found plan. For example,
world 188's later search finds a benefit missed at the early entry. With finite,
different proposal menus, the earlier search does not exhaustively contain the
later search. This does not imply that early decisions lack strategic importance.

All compared selected wins have equal recorded non-HP resource views within each
entry. That makes the observed HP comparisons more interpretable, but the resource
view is not a complete strategic value measure. Search remains privileged to the
fixed hidden world; public student inputs do not expose that hidden information.

## Next learning test

Do not repeat or enlarge this completed collection merely to find more favorable
results. The next proposed work is a **small, separately declared student-transfer
comparison** using the two useful fitting worlds, with explicit limited coverage:

1. Freeze fitting-only lessons. A combined teacher may choose the better verified
   plan from the two methods using fitting outcomes only. Do not import held-out
   plans, relax the historical v1 gate or relabel these branches as ordinary PPO.
2. Compare teaching those plans with cloning the original reference behavior and
   leaving the original player unchanged. Use balanced whole-world weighting and
   fixed work. Experimental copies may use both preserved numerical initializers
   on the same lesson bank; that does not create additional independent worlds.
3. Check whether copied players learn the meaningful changed choices and complete
   the natural fights, then freeze all finals before fresh full-game evaluation.
   Keep combat/noncombat evaluation behavior and compute matched. Terminal wins
   remain primary; fight HP and floors remain diagnostics.

Two fitting fights can support a transfer diagnostic, but they do not constitute
a broad curriculum or establish readiness. A new recipe must declare the student
intervention and its assessment before any fitting. No optimizer updates, model
promotion, adaptive controller or next experiment follow automatically. The old
natural-v1 curriculum and both original full states remain untouched.

## Resource accounting

The four collection sessions total **2,640.92 wall seconds (44.02 minutes) /
1,947.80 CPU seconds**, with **643.66 MB peak memory / 1.425 GB final cumulative
output**. Do not sum cumulative storage. The final report's 239.10-second unit-loop
duration describes only the last session's loop, not the complete collection.
The frozen game, runtime, SDK, support cache, banks and historical evidence remain
shared; **zero game apps** are copied.

Repository verification passes again: **2,471 tests / five skips**, formatting,
lint, strict types and the C# protocol build, in **137.76 total wall seconds**.
Only result/handoff documents and portable evidence change. The collector,
recipes, learner, native worker and original full model/optimizer files remain
unchanged.

See [implementation](native-coordinated-teacher.md),
[control evidence](evidence/native-coordinated-control-v2.json) and
[main result evidence](evidence/native-coordinated-teacher-result-v2.json).
