# Completed native training diagnostics

This is a separate saved-record tool, implemented while the owner reports the optimizer
learning curve running. It does not monitor that run, read its workspace, start a game,
update a policy or change training settings. The current experiment's source, recipe,
seed manifest and launcher hashes are checked before and after analysis.

The first recipe inspects **64 completed historical TRAIN games / 6,995 decisions**:
the two verified first-round 32-game cohorts used in the optimizer study. It compares
each behavior model with its saved standard update on identical old states. It does
not evaluate how the updated model plays new games, or describe the current running player.

## What the tool reports

- Observed action classes and legal opportunities: ending turns with plays remaining,
  taking/skipping card rewards, potion use/discard, shop controls/inspection/leave,
  offered rest options including Heal/Smith, and exits with unclaimed rewards.
- Before/after probability movement by decision family and opportunity, including
  observed health bands. Probabilities sum all candidates in the same reported class.
- Assigned credit, cross-fitted prediction quality, and probability movement aligned
  with that credit. Both cohorts reconstruct the saved optimizer study's normalization
  and clipped-surrogate measurements.
- Mandatory versus choice-bearing decisions, game-length weighting, effective game
  count from choice counts, and concentration of normalized absolute credit mass.
- Data-gradient contributions by family at the behavior checkpoint. These exclude
  exploration and Adam; vector norms can cancel and are not percentages of causal influence.
- Whole-run endings, final public interaction/encounter, and the last public enemies.
  The report does not invent an exact cause of death from the last observation.

Rest options are counted at every observed menu. The tool assumes neither one action
per rest site nor that an upgrade is always preferable to healing. Optional card skips,
outside-combat potion use and merchant targets remain distinct from taking a card.
Dynamic costs are not reconstructed: a play counts as available only because it appears
in the recorded legal menu, including zero-energy cases. Shop/service controls may open
another choice; selecting one is not automatically a completed purchase.

Unknown action classes remain visible as their structural verb/role. Absence or rarity
is reported as limited evidence, not proof of mechanics coverage. Decision counts are
not unique room/offer/turn counts. For end turns, the report separately counts chosen
end-turn actions so repeated card decisions do not inflate that denominator.

## Interpreting the learning signals

The declared bootstrap return is still separate from terminal victory. For game `g`,
the assigned raw advantage is `A_t = R_g - V_other_games(s_t)`. No game's outcome fits
its own state baseline. The existing update normalizes these values across **all**
source decisions, including mandatory menus. Positive credit does not establish that
the selected action caused a good ending.

A one-option menu has zero direct actor gradient. It can still affect global advantage
normalization, minibatch composition and critic fitting. The report shows how many real
choices would change normalized credit sign if mandatory menus were excluded from
normalization alone. This is arithmetic on existing records, not a changed update or
evidence that removing those menus would improve play.

The ridge state baseline already uses equal whole-game weighting. The actor's decision
averaging is a separate issue: longer games/combats supply more choice presentations.
The report exposes nominal choice weights and credit mass, without equating them to
the eventual Adam parameter change. Health comparisons are observational; states with
different HP also differ in other ways. None of these statistics supplies optimal-action
labels, a win-probability estimate, or a readiness pass.

## Integrity, resources and reuse

Only exact own-behavior TRAIN records from a completed, sealed source report are
accepted. Source game IDs/native seeds, model/encoder/environment/score identities,
case and compressed-trace hashes, menu order, selected probabilities and values verify.
Evaluation, partial, recovered, privileged, stale or duplicate records are rejected.
Private engine ending fields are not included in behavior or learning features.

The tool retains at most one raw episode at a time and uses exact compact sparse rows.
It has one numerical thread, a four-minute wall/CPU cap, 1 GB memory and 100 MB output.
It writes only to its own diagnostic workspace, seals completed cohorts and preserves
uncommitted work for inspection. Reopening a completed result verifies sources and
performs no further analysis. No dependencies are installed into the running environment.

The artifact contains `summary.md` for reading and `report.json` for detailed counts,
per-game weights, folds, outcomes and source seals. The configured command is
`bash scripts/diagnose-native-training-v1.sh` from the repository; the wrapper obtains
its workspace and limits from the pinned recipe. Codex can run this bounded saved-data
job. It is not an additional owner-run training stage or a prerequisite to completing
the current learning curve.

Recipe: `configs/native-controls/completed-training-diagnostics-v1.json`.
Measured evidence: [saved-record diagnostics](evidence/native-completed-training-diagnostics-v1.json).
Version 1 binds the completed optimizer probe's first-round cohorts. Applying it to a
different completed-report schema requires a separately versioned loader and source-bound
recipe; it does not automatically follow or tune a running experiment.

## First results

The 64-game analysis completes in **45.81 seconds**, using **291.23 MB** peak memory and
retaining **0.51 MB** of reports. All protected running-experiment files remain unchanged.
Reopening the saved report verifies its seals without recomputing diagnostics.

- Mandatory menus are 1,698/6,995 records (24.3%), with zero direct actor gradient. Removing
  them from normalization alone changes the feedback sign for only 9/5,297 genuine choices.
  There is no obvious large normalization failure from that arithmetic in these batches.
  This does not measure all effects of minibatch composition or critic fitting.
- Combat supplies 3,982/5,297 genuine choices (75.2%). Rest sites supply 19 and shops 88.
  Rare decision types have little independent practice; repeat menus are not new games.
- Card rewards are skipped on 30/181 observed opportunities. The model is allowed to
  decline cards. End turns with plays remaining are 39/1,254 chosen end turns (3.1%).
  Neither mandatory card-taking nor consistently ending turns early describes these
  historical records. This does not establish optimal play in the remaining decisions.
- The quarter of games with most choices supplies 32.1–34.0% of choices. Choice-count
  effective sample size is 28.8/30.6 out of 32 games; there is length imbalance, but the
  count distribution is not dominated by just one or two runs. Credit mass/gradients are
  separate measurements.
- Both updates change combat probabilities by about 0.04 mean total variation on old
  states. This supports a connected actor update, not stronger new-game play. Of 64
  losing runs, 63 are last observed in combat and one in an event; those observations
  do not isolate the cause of death.

These findings do not justify a new action restriction, HP reward or mid-run change.
Let the current independent learning curve finish unchanged. If it remains flat, use
this report to target better action-credit or teacher evidence, particularly combat
and the poorly represented run-level decisions, rather than assuming a bookkeeping fix
or an unbounded increase in games will suffice.
