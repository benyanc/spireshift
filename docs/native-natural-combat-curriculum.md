# Natural multi-turn combat teacher and curriculum test

This is the next bounded learning intervention after the delayed-decision control.
It asks whether verified lessons from naturally reached fights can improve the
preserved Ironclad/A8 players. The existing learned baseline, full-run objective,
actor capacity and observation contract remain unchanged. Both original complete
players and all their Adam moments/counters **5,658 / 6,045** remain read-only.

There are two separate owner stages. **Teacher collection ends before student
fitting starts.** Assess its useful lessons first. The curriculum/fresh-game stage
is implemented but cannot use an incomplete or insufficient main teacher collection.
Neither stage promotes a checkpoint or starts adaptive thinking automatically.

## Natural situations and ownership

Saved-only preparation reads all **256 completed TRAIN attempts** from round two
of the repaired experience comparison's larger arm, across both fixed parents.
It opens no development episode and selects no root using final floor, victory,
return or a counterfactual outcome. Every source is sealed by the completed study.
The historical situation bank is preserved; its missing combat-counter views are
not silently migrated. These newer sources already have the qualified v11 inputs.

The sampler finds **1,389 candidate positions**. It selects two control worlds,
eight fitting worlds and four held-out worlds, with one root per world. Whole-world
assignment precedes fitting/held-out selection. Each parent contributes four fitting
and two held-out roots. A deterministic public-descriptor diversity rule covers
encounter/enemy, health, deck/relic and floor differences without inspecting outcomes.
The two high-health normal control positions are excluded from the main study.

The main set contains **12 distinct decks / 11 relic-state signatures**, six normal
fights, four elites and two bosses, spanning floors **5–17**. Health is low in two,
middle in eight and high in two roots. Five offer zero-current-cost plays; that
does not assert a discount without a verified base cost. Selected sources collectively
cover eight of 18 available encounter/floor/health groups, not exhaustive mechanics.

A root requires public player round at least two, floor at least five, three to
16 current candidates and at least two play/use options. The largest selected
prefix is 223 decisions; the declared maximum is 512. This is a sampling limit,
not a mask on later action menus. Nested selections and every actually offered
action remain available throughout the fight and fresh full games.

## Teacher search and verification

Each branch mounts its original native seed in a separate process/profile and
replays every saved prefix action. Public inputs, card costs, targets and order
must match exactly before it reaches the root. The shared frozen game, runtime,
SDK and support cache are reused; no game app is copied.

At each main root:

1. Record the preserved parent's greedy continuation through the whole remaining
   fight, including later turns and nested card choices.
2. Freeze at most **16 first-divergence proposals** from that reference's public
   menus. Visit choices across its first three observed rounds; try up to two
   alternative actions at a visited decision, then follow the same parent greedily.
   A proposal may change later-turn decisions, not just the root action. The
   candidate budget/ranking does not inspect candidate outcomes. This is bounded
   trajectory improvement, not exhaustive planning or a public-belief search.
3. Select an observed local improvement if one exists. Otherwise retain the
   reference; a failed or capped path never receives a successful label.
4. Replay both the reference and the selected entire fight separately. Their
   public action traces, outcome and retained resource views must reproduce.

The upper bound is **19 branches per root / 228 main native attempts**. Fewer are
possible when the reference has fewer eligible decisions. Duplicate confirmations
check deterministic replay in one hidden world; they are not additional independent
worlds or a statistical proof of strategic superiority.

The native room-reward transition establishes a fight win; player death establishes
a loss. Escape, another reward or merely leaving combat is not labelled a victory.
Unknown ownership fails closed. Each fight is bounded by 192 actions, 12 observed
player rounds, 60 wall seconds and the existing whole-run CPU ceiling. Every
attempt retains its journals and exact source snapshots. Native delivery, subset
UI and ordered public relic counters are checked before a completed branch is sealed.

A failed/capped branch blocks that root's remaining proposals. Its original root
denominator stays visible; the next planned world may continue only after proven
worker shutdown. Failed roots are not replaced or retried. A prefix/confirmation
mismatch or more than two technical failures stops for inspection. Uncommitted
units and unexpected files are preserved rather than overwritten on restart.

## Local teaching criterion and its limits

A candidate is a local improvement if it wins where the reference dies, or both
win and it exits with more native HP while retaining the reference's remaining
potion multiset and no recorded deck/relic-identity, gold or maximum-HP disadvantage.
Potion identities and multiplicity matter; equal potion counts are insufficient.
These are explicit guards on a **local teaching hypothesis**, not handwritten
per-action rewards or a replacement for terminal full-run victory.

The guards do not price all future costs: draw/RNG changes, relic charges, future
deck value and potion opportunity cost can still matter. A higher-HP exit is not
asserted to improve a full run. The native engine owns effects; the collector does
not approximate card interactions from descriptions. Future state/outcome data
remain labels/provenance, never additional student inputs.

Main fitting requires at least **four verified winning fitting worlds**, at least
four meaningful choices and two player rounds per usable plan, **two strict local
improvements**, two enemy-set identities and three deck signatures. Only TRAIN
fitting roots determine this gate. Held-out successes cannot rescue a failed gate.
Insufficient teaching evidence is a completed collection result, not permission to
relax thresholds, expand search or train automatically.

## Matched curriculum and evaluation

Both parents produce two experimental copies with exact inherited weights and
complete Adam state:

- **Reference cloning:** categorical imitation of the parent's original greedy
  fight choices on the same admitted fitting worlds.
- **Teacher cloning:** the same categorical loss and work on selected confirmed
  fight plans from those worlds.

Reference cloning controls for sharpening existing behavior and extra supervised
updates. A rescued root may contain a losing reference trace; that control is
explicitly the old behavior, not an optimal target. Both copies must also be
compared with the **untouched original** so that worsening a control cannot count
as a useful teaching gain.

The loss is cross-entropy on the chosen action distribution. Action scores are
**not regressed onto returns or HP**. This avoids the earlier consequence-learning
experiment's return-to-action-score regression. Every label binds to the exact
public menu, including nested choices. All actor layers remain mutable. No future
outcome, hidden world, goal, baseline answer or seed becomes an input feature.

Fitting uses **16 fixed epochs / four updates per epoch / 32 choices per update**,
for **256 total Adam steps / 8,192 choice presentations** on four copies. World
sampling is balanced, then positions are sampled within a fight; longer fights
do not automatically receive more weight. Every epoch saves the full model and
Adam state. The value head's numerical weights and existing coarse predictor stay
fixed. Copied Adam advances actor-only steps; dormant critic moments may decay.
The original optimizers are unchanged and are never reset or advanced.

All four final states freeze before any evaluation. Then test all three versions
of each parent on the **four withheld fights (24 native branches)** and **32 fresh
full-game seeds (192 attempts)**, with greedy combat and matched sampled noncombat
behavior. Teacher search is not used during evaluation. No held-out result selects
an epoch. The fresh panel is distinct from historical/source/control worlds.

Full wins remain primary, under the unchanged 128-CPU-second whole-run budget.
Acts, floors, failures and resources are reported separately. Failures retain zero
value in the original denominator. Paired intervals cluster the 32 worlds jointly
across the two fixed parents; there are not 192 independent worlds or a population
of independently trained initializers. Per-parent outcomes remain in sealed receipts.

## Qualification and next owner command

The saved-only root preparation completes in **58.66 seconds / 216.89 MB peak /
17.99 MB output**, with zero games or updates. A separate **52.56-second** native
probe verifies a three-round fight and identical full replay, with no app copies.

The teacher integration control completes **14 branches / two natural fights** in
**120.48 seconds**, with zero failed branches. Both reference fights already win;
the small search finds **no strict improvement**. This qualifies the collection
wiring, not the main teaching gate or a stronger teacher. The control's learning
stage separately tests fitting, exact continuation and evaluation on copies.
Its completed qualification receipts are recorded in the accompanying evidence.

The student integration control now completes **22 / 22 units / 32 copied-Adam
steps**, including six withheld-fight branches and six fresh full-game attempts.
All nine execution/fitting checks pass and every fitting loss decreases. There
are no technical failures. On the one fresh control world, each version wins
0/2 and averages floor 11; this is not performance evidence.

The first curriculum CLI launch pauses cleanly after six units / one epoch. Its
four complete model/Adam checkpoints are reused. A separate bounded driver invokes
the same curriculum API for only the **16 remaining units**, with the unchanged
240-second outer resource cap, including dependency reads. It does not reset a
player, modify the learner or replay a completed unit. Resource receipts preserve
both launches: **166.20 / 162.68 seconds**, cumulative **328.89 seconds**, peak
**590.00 MB** and final cumulative curriculum output **85.73 MB**. Do not sum the
two cumulative storage measurements or substitute the report's unit-loop-only
duration for total elapsed time. The separate teacher output is 55.00 MB.

An independent **72.95-second** saved-only assessment verifies **76,724 source files,
14 teacher / 22 curriculum receipts**, recomputes 176 teacher action distributions,
checks full parent imports/Adam lineage and reproduces fitting metrics. With no
teacher improvement in this control, both arms' final numerical weights and every
Adam moment are **bit-exact matches for each parent**; their withheld-fight and
fresh-game traces also match. This is an actual no-treatment control. It establishes
execution consistency, not useful teacher targets or stronger gameplay. The audit
launches no game, fit or update and verifies the main recipe read-only without
creating its workspace.

Repository checks pass: **2,451 tests / five skips**, formatting, lint, strict types
and the C# protocol build. The full check takes **127.86 seconds** under a
four-minute cap. These checks establish implementation consistency; the main
teacher's useful signal and fresh-game effect remain unmeasured.

The main collection is **not started**. Close STS2 and run only:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/test-natural-combat-curriculum-v1.sh
```

Allow approximately **15–30 minutes** from the smaller measured control, with
15-minute clean sessions. This launch collects teacher comparisons only; no fitting
or fresh-game evaluation follows it. Share the summary before the next stage.
The same command resumes sealed units after a clean pause. Interrupted or changed
units stop for inspection and are not automatically replayed.

One worker shares the frozen inputs. Each phase allows at most **2 GB memory /
3 GB generated files**. The existing 17.99-MB root bank, old source artifacts and
shared installed inputs are referenced outside that phase's output accounting.
Small Python/JavaScript source snapshots remain for reproducibility. No app,
runtime or SDK is cloned. A wrapper invocation has a finite three-session allowance;
it never proceeds from collection to curriculum automatically.

See [qualification evidence](evidence/native-natural-combat-curriculum-v1.json)
and the current [backlog](backlog.md). Diagnostic victories, fitting loss and local
HP improvements grant no readiness pass, promotion or adaptive-controller admission.
