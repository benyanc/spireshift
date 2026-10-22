# Saved-training diagnostics for the experience-budget comparison

This tool adapts the existing completed-training diagnostics to the new native
32-versus-128-game comparison. It does not start/resume that comparison, change
either player, fit a predictor or use fresh evaluation outcomes. Its reports live
in a separate workspace. The learning method and running experiment stay frozen.

## Fixed scope

Read the **four already sealed first-round TRAIN updates**: both fixed players,
both batch sizes. Main scope is **320 attempts / 128 native worlds**, with overlapping
worlds across arms and players, not 320 independent trials. The separate tiny control
uses its own 12 TRAIN attempts, never the six control evaluation games.

The source recipe, seeds, rules, objective, code and native helpers are pinned.
Completed receipts must reproduce the declared task, source predecessor/full Adam
state and collection identities. Every sealed source byte is checked. The loader
stops after the four declared first-round fits; it never opens second-round,
evaluation, active or uncommitted source units. It takes no source worker/session
lock, sends no signals and performs no native delivery or game attempts.

Retain every planned source attempt. Source failures stay visible in that denominator
and never supply fitted examples. Only complete, unprivileged, own-policy TRAIN
episodes can supply diagnostic samples; stale/evaluation/recovered records fail.
Keep at most one raw history, then retain exact compact encoder rows and small
per-game feedback vectors. Decode old observations under their original source
environment, without adding hidden facts or changing current legal menus.

## What the diagnostic establishes

1. Reconstruct every saved sampled choice, its probability, public/effective menu,
   navigation and per-world random stream under the exact pre-update player.
2. Restore the **saved** cross-fit coefficients, features and held/fitting game
   ownership. Recompute forecasts and assigned credit without fitting anything.
   A game's outcome cannot fit its own baseline. Reproduce source prediction
   metrics, normalization, decision counts and clean/planned denominators.
3. Apply the old and updated saved players to the **same old public situations**.
   Reuse the existing probability/gradient measurements: per-family movement,
   chosen-action feedback alignment, actual greedy-choice changes, HP bands,
   take/skip, rest options, potion use and shop controls. Report mandatory menus,
   per-game weighting, rare-choice counts and current data-gradient contributions.
   Counts are opportunities/decisions, not unique rooms or causal mistakes.
4. Report full deck/relic signature diversity and per-planned-game family coverage.
   This supplements the current experiment's union-of-definitions and credit-sign
   tables. Raw counts grow with batch size; they are not a quality score or reward.
5. Verify whether each player's nested shared TRAIN worlds actually have the same
   learning histories and original behavior model. Only for a fully matched clean
   pair, compare assigned feedback signs and value-error MSE on those same choices.
   Errors weight each shared game equally, then its choices. This isolates a saved
   feedback comparison; the eventual players still differ in training data/compute.

Policy credit remains `whole_run_bootstrap_return - predicted_return(state)` and
normalization uses the complete original fitting cohort, including mandatory menus.
The reported baseline predicts the declared bootstrap return, **not win probability**.
It is not an action-value oracle. Different credit signs may reflect different fitting
support or normalization; they do not tell us which action was better. Gradient norms
can cancel and exclude Adam/entropy effects, so they are not causal influence shares.

Both actor/critic weights and all Adam moments/counters are restored read-only.
The before/after step counts describe the **original saved training**, never new
updates made by this tool. No optimizer, baseline or policy fitting occurs.

## Interpretation and follow-up

This can distinguish disconnected updates, unexpected game weighting, weak coverage
and sensitivity of feedback to batch support. It cannot establish better new-game
play, identify an optimal rest/card choice, validate a new reward, or decide a winner
from in-sample movement. Fresh full-run comparison outcomes remain primary and must
be assessed separately after all planned evaluations finish. Unattempted placeholders
in an unfinished summary are not actual zero-floor/zero-win observations.

Do not use this report to retune the running experiment, select a checkpoint, create
imitation labels or start an adaptive controller. Any mechanism change or teacher/
curriculum follows the final controlled comparison as a separate intervention.

## Bounded execution and reuse

One cohort per session, **four-minute / 2 GB memory / 100 MB output caps**, one numeric
thread. Complete results seal separately and are reused on a clean rerun; interrupted
uncommitted evidence is preserved for inspection. A full owner launch processes the
same finite four-cohort plan with a 15-minute launch boundary, never another training
round. No app copies or large trajectory duplication are created.

One full saved-data command:

```bash
bash scripts/diagnose-native-experience-v1.sh
```

`--one` limits a short agent launch to one new cohort; `--control` selects the separate
tiny integration-control source. The main qualification processes only the first
32-game cohort; any remaining long analysis is owner-run. This command does not
continue gameplay. Use the existing comparison command separately if the owner-run
experiment itself needs a clean resume.

See [qualification evidence](evidence/native-experience-training-diagnostics-v1.json)
and the [experience comparison](native-experience-budget-comparison.md). No learned
player is promoted by these diagnostics.

## Qualification and current priority

The tiny saved-source integration control is complete: all four cohorts, **12
TRAIN attempts / 1,654 non-navigation decisions**, with no evaluation decoded,
baseline fitting or optimizer updates. Four capped sessions took 179.66 seconds
total. Both players' shared clean histories match; feedback comparisons on two
shared worlds per player qualify the wiring, not a statistical gameplay result.

The first main cohort, `fit-p2-batch32-r01`, is also complete: **32 clean TRAIN
games / 4,144 decisions / 3,160 genuine choices**. It reproduces the source update's
forecasts and raw feedback normalization, and measures 204 deck signatures / 67
relic-state signatures. Its saved source update used 99 optimizer steps; the audit
uses zero. The capped audit took **91.06 seconds**, with 297.09 MB peak RAM and
11.05 MB retained. The remaining three diagnostic cohorts contain 288 saved games
and stay owner-run. Passing checks cover 2,414 tests (five skipped), strict types,
formatting/lint and the C# protocol.

The 2026-10-22 gameplay-comparison snapshot is **584 / 832 attempts saved**, cleanly
paused, with no final report or active process. Fresh evaluation has not begun.
**Resume that existing comparison first**, using its guide's existing command.
Completing the optional saved-update audit is independent and does not advance
the remaining training or fresh-game evaluation. Neither source-batch probability
movement nor lower saved prediction error establishes a stronger player.
