# SpireShift backlog

Updated 2026-10-08 after the owner authorized full-run evolutionary/neural learning and the first
training-score implementation. GitHub holds detailed acceptance criteria and historical evidence.
The owner launches and monitors all sustained collection, training, simulations and evaluations.
Short local checks are allowed. Planning/implementation does not launch production experiments.

## Current handoff and direction

The owner completed the separately versioned [neural discard-choice corrective comparison](neural-selection-repair.md).
Both players finish all 32 attempts as terminal losses, with zero failures/truncations, zero wins
or first-boss reaches/Act 1 clears, and mean maximum floor 6.84375. There are 27 changed action
traces without demonstrated playing gain. This is inspected-seed compatibility evidence, not a
fresh/final benchmark. The original failures and old results remain preserved. Base-v2 is the
accepted historical baseline; base-v11 is unpromoted.

Comparison ID: `sha256:2bc12a35ee21e5ac285424cab8e19bcb236bb650c88d51aaa9d91e7ea8843ce6`.
Resource ID: `sha256:c8e246e7455f5df0913bc55d6585b694643aba26eabcf5186004c76f9947786d`.

**Implemented first item:** [#136](https://github.com/benyanc/spireshift/issues/136) supplies the
versioned [full-run bootstrap training score](full-run-training-score.md), pure saved-outcome
scorer, staging/evaluation rules and meaningful contract tests. No game attempts or fitting are
needed. **Next implementation: [#137](https://github.com/benyanc/spireshift/issues/137), one compact
neural player that can learn every decision family. There is no sustained owner command yet.**

Build a player that wins complete runs, then teach it when to spend little, medium or substantial
thinking effort. The primary evaluation objective remains **terminal full-run victory probability
under a fixed whole-run computation budget**. [ADR 0002](decisions/0002-full-run-bootstrap-training.md)
explicitly declares auxiliary learner returns for new bootstrap experiments, separate from the
real win/loss result. A strong inexpensive base player remains the foundation.

New experimental recipes may learn all policy components and depart substantially from weak
base-v2. Strategic learning no longer waits for combat-only improvement. Old saved lessons are
optional warm starts rather than permanent behavior targets. Legal/public-input checks,
independent evaluation, numerical stability and historical evidence preservation remain.

## Ordered implementation work

| Order | Work | GitHub items |
| --- | --- | --- |
| Implemented | Versioned bounded bootstrap score, win-first population ranking, failures/caps and terminal-only staging rules. | [#136](https://github.com/benyanc/spireshift/issues/136) |
| Next | Unified compact full-run neural policy, public features, legal candidate scoring and genome pack/unpack. | [#137](https://github.com/benyanc/spireshift/issues/137), parent [#78](https://github.com/benyanc/spireshift/issues/78), iteration [#134](https://github.com/benyanc/spireshift/issues/134) |
| Then | Reuse complete-run workers to collect actual returns, public milestones and diverse lessons from improving policies. | [#138](https://github.com/benyanc/spireshift/issues/138) |
| Individual methods | Bounded direct neural-weight evolution and outcome-trained PPO on the same full-run representation/score. | [#135](https://github.com/benyanc/spireshift/issues/135), [#35](https://github.com/benyanc/spireshift/issues/35) |
| First owner pilot | Freeze matched training budgets, seed panels, elite confirmation, scaling/plateau stops and equal decision-budget comparison. | [#140](https://github.com/benyanc/spireshift/issues/140) |
| If evidence supports it | Preserve evolved originals; test neural fine-tuning from new experience, then bounded alternating rounds. | [#139](https://github.com/benyanc/spireshift/issues/139) |
| When affected search is needed | Repair legal-action preservation during hidden-world resampling. Whole-run policy evolution does not require action-branch cloning. | [#105](https://github.com/benyanc/spireshift/issues/105) |
| Foundation milestone | Establish repeatable held-out progress, then wins and credible run-value/risk evidence. Apply the foundation scorecard before adaptive thinking. | [#78](https://github.com/benyanc/spireshift/issues/78), contract [#5](https://github.com/benyanc/spireshift/issues/5) |
| After the foundation | Integrate strategic/full-run learned search and demonstrate gains at equal compute. | [#46](https://github.com/benyanc/spireshift/issues/46), [#27](https://github.com/benyanc/spireshift/issues/27), [#28](https://github.com/benyanc/spireshift/issues/28), [#7](https://github.com/benyanc/spireshift/issues/7) |
| After useful search | Measure value of additional thinking, enforce whole-run spending and learn low/medium/high allocation. | [#29](https://github.com/benyanc/spireshift/issues/29)–[#34](https://github.com/benyanc/spireshift/issues/34), [#36](https://github.com/benyanc/spireshift/issues/36) |
| Later research | Freeze the final pre-patch bundle; measure zero-shot behavior and fixed-budget recovery after rule changes. | [#37](https://github.com/benyanc/spireshift/issues/37)–[#40](https://github.com/benyanc/spireshift/issues/40) |
| Final evidence | Reproduce public baselines, refresh competition and publish the final paired benchmark/report/demo. | [#49](https://github.com/benyanc/spireshift/issues/49), [#50](https://github.com/benyanc/spireshift/issues/50), [#41](https://github.com/benyanc/spireshift/issues/41), [#44](https://github.com/benyanc/spireshift/issues/44) |
| Optional product | Recommendation overlay and packaged Advisor, after player quality. | [#16](https://github.com/benyanc/spireshift/issues/16), [#43](https://github.com/benyanc/spireshift/issues/43) |

[#42](https://github.com/benyanc/spireshift/issues/42) retains negative-result analysis. Existing
adapters, public binding, rollouts, splits, accounting and owner scripts are reused. Closed
historical issues/recipes are not retroactively reclassified as successes.

## Learning and evaluation rules

- Keep one character, frozen game version and fixed difficulty for initial experiments. Ascension
  chooses difficulty, not an additive reward; report different difficulties separately later.
- Full-run wins remain primary in population ranking/evaluation. The versioned bootstrap learner
  score distinguishes losing runs. Floors/acts are intermediate progress, not a victory-value
  target, foundation pass or permission for adaptive thinking.
- Experimental policies may change every phase. Do not impose permanent proximity to base-v2,
  frozen strategic choices or improvement on every old teacher metric. Use new recipes and
  whole-run gameplay evidence rather than relax a failed historical gate.
- Compare gradient training and direct evolution of the same compact NN at matched total cost.
  Use common seed panels within generations, rotate train panels and confirm apparent elites.
  Preserve diversity and reevaluate fine-tuning before replacing an evolved player.
- Freeze panels, exploration, updates/generations, tuning, caps and plateau stops before launch.
  Training/development/final-test ownership is at the complete-run boundary. Inspected development
  results are disclosed; final-test seeds stay sealed.
- Keep failures/caps/truncations/missing outcomes in denominators and count all actual work,
  including discarded candidates and teacher/fine-tuning costs. Repeated actions earn no reward.
- Each sustained stage has one clear owner command, progress, immutable outputs, explicit resume
  and a definite stop. Only the owner launches and monitors it. Short synthetic/local checks do
  not authorize long collection, training or evaluation.

## Preserved real-game milestone

The owner launched the privately archived v0.107.1 app outside Steam's managed library. Its
executable, pinned bridge and read-only menu identity were verified. [The frozen-game guide](frozen-live-game.md)
records its launcher and location.

Retesting after a normal future Steam update, save/profile isolation and watching a useful trained
policy through the live adapter remain under [#37](https://github.com/benyanc/spireshift/issues/37).
A menu launch establishes neither model strength nor full simulator parity. The final pre-patch
model/data/protocol bundle remains unfinished.
