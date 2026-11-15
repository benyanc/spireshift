# Varied situations from completed native training games

This separate saved-data tool prepares situations for a future teacher/curriculum
test. It does not change, follow or fit the running experience-budget comparison.
It launches no game, creates no app copies and updates no model or optimizer.

## Source and information boundary

The fixed source is the completed, independently audited 640-attempt structured-input
comparison. Only its **384 TRAIN attempts / 64 native worlds / 12 behavior-policy
cohorts** are decoded. Its 256 evaluation attempts are never used as situations.
The short control uses the predeclared first 32-game TRAIN cohort, not selected
successful runs. Neither collection reads the current experiment's output units.

Complete audited own-policy episodes, expected seeds, behavior identities, menus,
navigation and original source seals must verify. Partial, recovered, privileged,
foreign-policy, greedy or over-budget episodes stop extraction. Existing native
delivery/probability audits are reused; this tool does not recompute neural inference.
Each expected source attempt is accounted for; a bad source is not silently dropped.

The source environment remains explicit. These historical records precede the
combat relic-counter repair. Missing combat counter views remain unavailable;
the bank never invents zero counters or substitutes the current observation format.
Using a root under a different worker/environment requires a separate qualified
conversion/recollection. The current repaired experiment is unaffected.

## What gets sampled

Every genuine current choice is eligible, across all observed decision families.
Forced shop navigation and single-choice menus are counted separately. Optional
card skipping, extra rest choices, potion use and other current legal candidates
remain in the original menus. The sampler does not restrict what a future player
may do or imply that healing, upgrading or losing HP is correct or incorrect.

Descriptors include act/floor, health band, encounter/enemy identity, deck composition
with per-copy upgrade/displayed-cost ownership, relic identity and available counters.
They also mark structurally observed opportunities such as multiple targets,
zero-current-cost plays, card take/skip, healing/Smith, potion use and shop controls.
A zero-cost play is **not** asserted to be discounted without a verified original cost.
These descriptors organize examples; full original public inputs are retained by reference.

Sampling is deterministic and uses no saved root action, final floor, win, return,
logit or counterfactual outcome. First retain at most two states per public
family/act/floor/health/encounter bucket per episode. Remove exact public-input
duplicates across cohorts/worlds, using fixed provenance tie-breaking. Version 1
then balanced decision families but could still miss available later-game/boss roots.
**Active version 2 first reserves available family/act/floor, combat-encounter,
health and opportunity groups**, beginning with those supported by the fewest distinct
worlds, then balances remaining slots across families/inventories. Missing available
groups are explicitly reported. The original world split and sample caps stay fixed.
Caps are 12 roots per native world, two per world/family, 32 per split/family and
two per inventory/bucket. Long early fights cannot dominate merely by having more turns.

The bank requests at most **192 fitting / 64 validation situations**. Native worlds
are assigned 3:1 by a fixed salted ordering before state selection. All players,
arms and related records on a world stay in that same split. Exact public duplicates
cannot appear in both subsets. Shortages stay visible rather than being padded or
filled with invented states. This is deliberately balanced sampling, not an estimate
of the natural gameplay distribution or proof of complete mechanics coverage.

“Validation” here means withheld from a **future bank-based teacher/student fit**.
These are historical TRAIN worlds, already encountered by the parent players.
They are not fresh full-game evaluation worlds or guaranteed unfamiliar to the model.
Unobserved later-game states cannot be manufactured by this bank.

## Resolving and using an entry

`bank.json` holds compact descriptors and immutable episode/decision references,
with environment, behavior, case, public-menu, effective-menu and replay-prefix identities.
It does not duplicate trajectories or game apps. The resolver reconstructs the
original public and effective menus, verifies their identity and checks the exact
recorded prefix. Native seeds, prefix actions and provenance are separate from
`student_input` / `effective_student_input`; they must never be passed to the policy.
The recorded root action is not supplied as an optimal-action label.

`native_situation_resolve.resolve(root, report_path, situation_id)` performs saved-only
resolution. It does **not** launch or qualify a native replay. A later planner must
replay and verify the exact source environment/menu before branching. A fixed-world
teacher remains explicitly privileged; it is not public-belief search. Old records
are not fresh on-policy PPO data. No teacher collection or imitation follows automatically.

After the current comparison is assessed, a separate experiment can select a finite
set of fitting roots, obtain trustworthy action comparisons, fit a student fork and
measure both withheld situations and fresh full games. Winning remains primary;
this bank contains neither action-quality labels nor demonstrated gameplay gains.

## Execution, storage and checks

Each completed source game seals a small immutable descriptor chunk. Clean pauses
resume those chunks; an interrupted uncommitted chunk/bank is preserved for inspection.
At most one raw episode history is retained. Existing trajectories are referenced,
not copied. Each launch has a **four-minute / one CPU thread / 1 GB memory cap**,
with no automatic continuation or next experiment. Initial extraction allows 250 MB
of output; coverage-only reselection allows 25 MB and reuses every sealed v1 candidate.

The recipe determines the same workspace used for caching, output and resource
accounting. Every source seal, both original full weight/Adam states, historical
forks and the running recipe's pinned code/config/helpers are checked unchanged.
Live output units are not inspected and their legitimately changing checkpoints
are not opened or locked.

The active bank command is `bash scripts/build-native-situation-bank-v2.sh`; it
requires the already completed v1 candidate bank and preserves it. An already
completed result is verified/displayed without more extraction. The historical v1
builder supports `--control` and `--max-new-games` for its sealed initial extraction.
Codex may run a job expected to finish under five minutes; longer work remains owner-run.
Both versions are complete locally, so no additional owner command is needed.

See [qualification evidence](evidence/native-training-situation-bank-v1.json) and
the current [backlog](backlog.md). Completing this bank is not a readiness pass,
checkpoint promotion or reason to start adaptive-controller training.

## Completed extraction and coverage correction

The 32-game integration control finishes in **22.69 seconds**, with all 14 observed
decision families represented. The initial bank finishes in **72.22 seconds**, using
**192.14 MB peak memory / 46.82 MB generated files**. All 384 source attempts verify;
there are 55,642 decisions, including 41,816 genuine choices. Episode thinning retains
14,121 references; exact deduplication leaves 6,480 public inputs, of which 256 are
selected. These are references to existing episodes, not new attempts or outcomes.

The first selection misses available validation later-game/boss situations. Review
finds 99 floor-17+ and 96 boss candidate references on the existing validation worlds.
Preserve that first bank, its recipes/code, world assignment and resolution audit;
do not interpret the omission as absence of source experience or change the split.

Coverage-only version 2 completes in **17.87 seconds / 150.83 MB peak / 8.25 MB output**,
reusing the exact candidate pool and 48/16 native-world split. It covers all **62 fit /
53 validation observed public groups**, with no unfilled available group and no cap
relaxation. This is coverage of declared sampling groups, not exhaustive mechanics.
The active bank has **256 roots / 14 families / 188 deck signatures / 109 relic-state
signatures**: 23 combat situations, 22 card take/skip menus, 18 rest menus (15 Heal/Smith),
19 shop situations (14 purchase/service controls), seven zero-current-cost-play
opportunities, 20 floor-17+ roots and four boss roots. Validation includes two floor-17+
roots and one boss; these tiny counts cannot establish later-game generalization.
All 23 combat roots retain the historical unavailable relic-counter view. No
current-format input, original base cost or missing game mechanic is invented.

A **67.10-second v1 saved-only resolution audit** verifies every original selected root's exact
original public/effective menu, complete recorded prefix, world grouping and separate
student/provenance boundary. It checks 34,618 protected source seals before/after,
uses 430.98 MB peak memory and writes four KB. It does not run native replays or
recompute the original neural probabilities. Both complete players and every Adam
moment remain unchanged. No new games, weights, training labels or adaptive controller
are produced. No further bank command is required; assess the running experiment next.

The separate **73.38-second v2 resolution audit** verifies all 256 corrected roots,
34,625 protected source seals and unchanged original world assignments, using
338.82 MB peak RAM / 4.32 KB output. It also checks that every declared available
sampling group is represented. All source/model/Adam checks pass. Final repository
verification passes **2,396 tests (five skipped), strict types on 506 files,
formatting/lint on 689 files and the C# protocol** in 145.30 seconds.
The first repository-check receipt remains preserved: it stopped on a test-helper
type annotation, corrected before the passing checks; no bank data or frozen
production source was changed by that annotation fix.
