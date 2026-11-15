# Natural multi-turn combat teacher result

The finite collection completes cleanly, but **the prepared curriculum should not
start**. The tested teacher supplies too few improved fitting plans for this
declared comparison. This is a teacher-signal result, not a failed training run:
there are no optimizer updates, student checkpoints or fresh full-game evaluations.
Both original players and their full Adam states remain unchanged at **5,658 /
6,045** updates. The original design and qualification evidence remain preserved.

## What completed

All **12 planned natural worlds** finish with exact replay and no missing root,
technical failure or capped branch. The **190 native attempts** comprise 12 greedy
references, **154 alternatives** and 24 independent process replays confirming the
reference and selected traces. There are **166 nonconfirmation paths**, not 190
independent fights or worlds. No game app is copied. These are remaining-fight
outcomes in fixed hidden worlds, not complete-run victories.

| World split | Reference fights won | Selected fights won | Improved worlds before length filter | Usable improved worlds |
| --- | ---: | ---: | ---: | ---: |
| Fitting: 8 worlds | 6 | 6 | 1 | 0 |
| Held out: 4 worlds | 2 | 2 | 2 | 2 |

The selected improvements preserve **seven HP** in the fitting example and
**two / seven HP** in the held-out examples. All already won their fights.
Every alternative at each of the four losing reference worlds also loses; the
bounded search finds no death-to-win rescue. That does not prove those positions
are unwinnable or that the reference is optimal.

## Why the gate fails

Four winning fitting plans satisfy the minimum four meaningful choices across
two observed player rounds, with enough enemy and deck variety. **None of those
four improves the original reference.** The declared test requires two improved
fitting worlds; held-out improvements cannot supply fitting labels or rescue it.

The one improved fitting example exits at **35 HP instead of 28 HP**, across two
rounds and **three meaningful choices**. The four-choice cutoff excludes it from
this specific multi-turn test. That cutoff is a study-design choice, not a general
claim that three-choice lessons cannot teach a network. Even counting this valid
shorter improvement would provide only **one** of the declared two fitting
improvements. Simply removing the length filter does not make the frozen study
pass. A second winning fitting example has only two choices in one remaining round.

No higher-HP winning alternative is rejected by the recorded resource guards.
Recorded non-HP resource views remain equal across all tested alternatives at
their respective roots. Relaxing potion/deck/relic/gold/max-HP guards would not
add better fitting plans here. These views still omit some strategic effects;
equal recorded resources are not proof of equivalent future utility.

## What this says about the method

The collector, exact replay and local comparison work on these natural positions.
The teacher remains weak: each proposal changes **one decision**, then hands the
remaining fight back to the same greedy player. Trying this at decisions in
several turns is not the same as searching several coordinated changes. Every
root also inherits its already-played prefix, so earlier damage, resources or
card choices may constrain what is recoverable. This is a plausible limitation,
not a demonstrated cause of every loss.

This collection does not test the ability to learn from stronger natural plans.
Running the gated curriculum now would either mostly clone unchanged behavior
or require a post-hoc change to its comparison. More epochs or a larger ordinary
PPO batch do not create missing teacher targets. The earlier complete-turn teacher
also supplied weak full-run preferences; repeating either unchanged recipe is
not the next experiment.

## Resources and next work

The two collection sessions total **1,094.18 wall seconds (18.24 minutes) /
784.30 CPU seconds**, with **444.58 MB peak memory** and **495.58 MB final
cumulative output**. The final report's 184.65-second unit-loop duration is not
the complete collection time; cumulative storage is not summed across sessions.

The separate **99.65-second saved-only assessment** verifies **83,768 sealed
source files / 190 receipts**, reconstructs **3,124 action distributions and
actions**, checks confirmation equality and reproduces the unchanged fitting-only
gate. It rechecks the recorded native audit and its sealed journal identity; it
does not rerun the engine or independently repeat every native delivery audit.
Both full parent states remain sealed, and the curriculum workspace is absent.
Of 154 alternatives, **131 (85.1%)** tie their reference's recorded outcome and
resource view. These dependent within-world paths are not independent samples.
No native replay, value refit or optimizer step runs during this assessment. See
[portable result evidence](evidence/native-natural-combat-result-v1.json).

Repository verification passes **2,451 tests / five skips**, lint, formatting,
strict types and the C# protocol build in **138.01 seconds** under a four-minute
cap. Tracked changes are result/handoff documentation and portable evidence;
the qualified collector, recipes, learner and saved game/model data are unchanged.
GitHub #35 / #143 / #146 carry the current result with earlier history preserved.

Next design a **separate bounded teacher coverage/recoverability test**: compare
the existing single-change continuation with plans making coordinated decisions,
and consider first-turn entry before the damaged prefixes. Use only fitting/TRAIN
worlds for method development, fresh withheld worlds for the new assessment and
explicit native attempt/time budgets. Keep the old result, useful short examples
and all original full states. Treat stronger search as an untested intervention;
qualify actual useful lessons before student fitting and fresh full games.
Specify treatment of short successful plans prospectively rather than making the
completed v1 gate pass retroactively.

**No owner command is needed now.** The v1 curriculum remains unstarted; do not
rerun the completed collection, move held-out lessons into fitting or relax its
thresholds automatically. Local HP gains remain auxiliary, with terminal full-run
victory and the fixed CPU budget still binding.
