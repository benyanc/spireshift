# ADR 0003: A8 learning before selectable difficulty

## Status

Accepted 2026-10-09 following the owner's explicit choice to retain A8 and prioritize a workflow
that trains a useful player. This supersedes the A0 recommendation in the preceding audit's
planning notes. It changes current implementation priority and future experiment scope, not
historical experiment identities, the terminal objective or the whole-run compute allowance.

## Decision

Keep Ironclad and the frozen v0.107.1 simulator's fixed Ascension 8 rules for the next learning
workflow. Genuine selectable A0 or other difficulties are deferred under #142. They do not block
the A8 simulator repair, a fresh learning recipe, outcome-trained neural updates or foundation work.
Difficulty support should follow a useful A8 player, unless the owner reprioritizes it.

The historical pilot declared A0 while running A8-like fixed rules. Preserve its configuration,
score, reports, models and negative findings. Do not rewrite the score, rename its results or
resume its population under a repaired environment. The new path must bind actual A8 scope to
the repaired native/source/adapter, the complete public-menu policy format and a fresh lineage.
The old runner's A0 requirement is historical, not a reason to implement another difficulty.

Complete the required environment validation/admission and disclose its coverage limits before
fresh training. The existing native tests, captured event checks and source-rule audit establish
their stated scope only. They do not establish complete live-game fidelity or a trained win.
UI playback and unobserved live behavior remain separately visible work, not proof of model quality.

## Useful learning workflow

Use complete-run experience and actual outcomes to improve the unified policy across combat,
routes, rewards, deck choices, events, shops, rest and other supplied legal decisions. All model
parameters can change substantially; no permanent closeness to the weak historical policy or
per-phase teacher-agreement requirement is introduced.

Implement and compare actual-return neural updates and direct neural-weight evolution under
declared budgets. PPO requires genuinely sampled actions and saved behavior probabilities; old
greedy evolution traces are not PPO samples. Each method needs independent confirmation before
scaling. More games or a larger population alone are not evidence that the workflow learns.

For each bounded iteration:

1. Freeze the A8 profile, score/objective, representation, exploration, learning rounds, training
   and confirmation seed panels, compute caps and plateau stop before launching.
2. Play complete training runs and retain losses, failures, caps and all actual collection/update
   cost. Learn only from training-owned experience, without hidden future information.
3. Freeze the selected player before development comparison; measure it and its initializer on
   independent complete-run seeds at equal whole-run decision budgets. Keep final-test seeds sealed.
4. Report full wins first, with act/floor progress, failures and cost as diagnostics. Repeatable
   held-out progress can justify another developmental round; it is not a competence claim.
5. Revise a stalled method from evidence rather than repeatedly scale a failing recipe. Progress
   toward genuine full wins and the frozen foundation scorecard before adaptive thinking.

`terminal-victory-v1` remains the evaluation objective. ADR 0002's bounded auxiliary bootstrap
score stays separate from binary environment rewards; its historical A0 scope is superseded only
for new recipes. Difficulty is a fixed environment setting, not a reward to maximize.

## Execution boundary

Codex runs short jobs using saved timings and explicit caps. The owner launches and monitors work
expected to take five minutes or more. Provide one concrete command when a long stage is ready.
This decision launches no training, game attempts, source repair, model promotion or publication.
