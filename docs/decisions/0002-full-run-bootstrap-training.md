# ADR 0002: Full-run bootstrap training and unrestricted policy improvement

## Status

Accepted 2026-10-08 following the owner's authorization to update the learning plan and implement
the first score item (#136). This supersedes combat-only learning and permanent proximity to a
weak accepted policy for **new experimental recipes**, not historical experiment identities.

## Problem

The corrected neural/base-v2 comparison finished 32 runs per player without execution failures,
but neither player won or reached the first boss. Both averaged maximum floor 6.84375. Binary
all-loss feedback gives evolution no ranking signal. Repeated imitation of weak saved teachers,
frozen strategic choices and a tight distance limit from base-v2 are not a sufficient learning
loop. A new player must be able to learn whole-run trade-offs across every legal decision family.

## Decision

Keep `terminal-victory-v1` as the public environment/evaluation `ObjectiveSpec`: terminal victory
is one, ordinary loss/nonterminal transitions are zero, and the whole-run compute allowance is
128 CPU seconds for the initial profile. Introduce a separately versioned learner objective,
`full-run-progress-bootstrap-v1`, described by `TrainingScoreSpec`. Do not write the bootstrap
return into `Transition.reward`, imply it is a victory probability, or reinterpret old models.

For a recorded, ordinary terminal loss, let `A` be observable completed acts, `F` the maximum
observable **total run floor**, `N` the configured act count and `K` a floor-normalization scale:

```text
progress = (A + F / (F + K)) / (N + 1)
bootstrap learner return = 0.25 * progress
terminal victory learner return = 1
failed, truncated, stalled, missing or over-budget learner return = 0
```

The initial pinned Ironclad/A0 profile uses `N = 3`, `K = 16`. The scale is a training constant,
not an assertion that the game ends at floor 16. One act completion outweighs any floor-only
gain at the preceding act count. Floor progress saturates without an invented full-run floor
cap. Decisions, surviving turns, HP, gold, damage and repeated actions add no reward. `A` and
`F` are high-water progress counters derived by the recorder from public observations; act names
alone must not be interpreted as numeric act order. A boss reach alone is not an act clear.

Score one complete episode per planned seed with discount factor one. Missing/failed attempts
remain in the original panel denominator and receive no retained progress credit. An outcome
reported as a victory but exceeding the declared whole-run CPU allowance is a budget failure.

Evolutionary populations rank lexicographically by **win rate, mean auxiliary progress return,
then completion rate** on common seed panels. They must not rank by the mixed mean learner
return: that could sacrifice a small win-rate gain for many floor points. Gradient training may
use the bounded bootstrap return; it is explicitly a temporary proxy and does not mathematically
preserve the optimal win-only policy. Held-out win evaluation is therefore essential.

The initial staging trigger is at least three distinct training victories and three distinct
development victories, with at least 64 planned development runs and no missing/failed cases in
either panel. The panels must be disjoint. This modest trigger recommends testing the separately
declared `full-run-terminal-training-v1` stage, with loss progress weight zero. It is not a
statistical claim of superiority, foundation readiness, or an automatic launch. Changing these
constants creates a different content-addressed score configuration before the next experiment.

## Evaluation and implementation boundaries

- The unified compact player may learn every policy component and depart substantially from
  base-v2. No per-phase non-regression or old-teacher agreement requirement applies to its new
  experimental recipe. Numerical stability and legal/public-input checks still apply.
- Evolution and outcome-trained neural policies use the same representation, public information,
  training score, character, ruleset and difficulty. Baselines are measured, not behavior anchors.
- Freeze exact panels, exploration, rounds, tuning and total resource/plateau stops before a
  campaign. Use common train panels within generations and rotate panels between generations.
  Development/final-test ownership and source verification remain collector/benchmark duties.
- Compare final players at equal whole-run decision budgets and count all training, collection,
  discarded-candidate and fine-tuning work. Failure denominators cannot be reduced after launch.
- Terminal wins are the headline result. Floors/acts can justify another developmental iteration
  without becoming a full-run competence or adaptive-thinking claim. The existing foundation
  scorecard remains required before adaptive thinking; search readiness is evaluated separately.
- The pure scorer only checks saved normalized outcomes and identities. It does not authenticate
  gameplay, replay a source, collect data, update a model, or replace seed-manifest validation.
  The collector (#138) must bind the public progress/outcomes and seed ownership to actual runs.
- Only the owner launches and monitors sustained work. Every stage has one clear capped command,
  visible progress, immutable outputs, supported resume and a definite stop.

## Alternatives and limitations

Keeping binary all-loss feedback alone avoids a proxy but supplies no early evolutionary ranking.
An arbitrary weighted sum of floors, difficulty, HP and wins risks teaching local survival or
resource farming; difficulty remains a fixed experiment setting. This bounded progress score
is an explicit bootstrap hypothesis, not a guarantee of stronger play. If it stalls, change the
representation, exploration or next version of the score before blindly scaling games.

The first item delivers reusable scoring/configuration/contract tests only. The unified policy,
evolutionary optimizer, outcome-based neural trainer, experience collector and comparative pilot
remain separate work items. No games or training are required to validate this contract.
