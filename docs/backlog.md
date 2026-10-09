# SpireShift backlog

Updated 2026-10-09 after the event native build and the new 89-case compatibility audit.
GitHub holds acceptance criteria and historical evidence. Codex may launch short builds, audits,
tests and jobs autonomously. The owner launches and monitors tasks expected to take five minutes
or more. Use saved timings to estimate duration and explicit caps to bound short jobs.

## Current handoff and direction

The owner completed 832 unified evolution attempts in 80.858 elapsed / 592.289 total CPU seconds.
Both players have zero full wins on 64 paired development seeds. The evolved player reaches mean
floor 9.46875 versus 11.0 initially, with 12 versus 8 failed attempts. No model is promoted.
[The diagnosis](full-run-pilot-v1-diagnosis.md) identifies premature Act 2 endings around floor 19,
stale combat-win flags, truncated public selections, a fourth reward encoding defect and an invalid
Ascension-0 label. The full-run guard correctly refused the premature wins. These defects block
more sustained learning and prevent a valid A0/full-game claim; larger training is not the next step.

[#141](https://github.com/benyanc/spireshift/issues/141) owns the repairs. The owner successfully
published the separate ending/reward candidate in 10.284 seconds; all nine targeted regressions
passed. The earlier missing-runtime failure and cached check remain preserved in
[runtime evidence](evidence/full-run-repair-runtime-check-v1.json). The owner then published the
public-choice candidate in 9.588 seconds with all 23 native synthetic regressions passing and its
actual public-list exports checked. It exposes every offered combat card, correct pile/generated
card identities, selected bundle and confirmation state, plus a source declaration of fixed A8.
The new versioned adapter and unified player consume these readouts, retaining every legal choice
and normal enemy targeting. Its fresh 4,384-parameter model can change every decision family.
Two short real native replays passed the previously reproduced fourth-reward and overflow-menu
errors: 410 transitions and 412 scored observations in 3.387 seconds, with no optimizer steps.
[Integration evidence](evidence/public-choice-integration-v2-evidence.json) preserves build, model,
adapter, configuration and replay identities. This is compatibility evidence, not playing strength
or real-game parity. The owner subsequently checked all 89 failed training attempts in 92.495 wall
/ 91.416 CPU seconds, replaying 11,947 transitions. **85 passed; four remain failed.** The successful
endpoints cover 65 overflow menus, seven premature endings, 12 bundle confirmations and one reward.

All four remaining cases stalled at Dense Vegetation or Punch Off: an unconditional fallback
offered action 3 on a committed fight page, while its handler accepts only action 0. Existing event
tests inspected slots 0–2 and missed this extra action. A third isolated source correction offers
only the accepted continuation on those pages and the matching Lantern Key page. All 32 targeted
managed regressions passed in 6.753 seconds, including nine new full-mask/progress/resource checks.
[Event repair evidence](evidence/event-continuation-repair-v1-evidence.json) retains the owner's
85/89 failed audit and the initial short-check compile failure as separate records. The corrected
native library subsequently published in 7.393 wall / 8.581 CPU seconds with all 32 tests passing.
Codex derived its separate public-adapter manifest and completed a new audit under a four-minute
cap: **89/89 passed**, 11,939 transitions, 89.677 wall / 88.861 CPU seconds. The four event cases
replay the exact saved prefix to the first rejected action, verify the removed button, then score
and execute the engine's sole continuation into the correct playable fight. Their 12 historical
noops are explicitly recorded as replaced; other action drift fails. All 89 original attempts
remain in the denominator, and the old 85/89 result is unchanged.
[Native integration evidence](evidence/event-native-integration-v1-evidence.json) preserves the
new native, public adapter, fresh model, original cases, audit and resource identities. Real-game
difficulty, endings and broader event-action conformance, plus re-admission, remain before learning.
The new native/adapter also passes all ten environment interface checks in a 0.825-second job.
[Interface/reference evidence](evidence/event-native-contract-v1-evidence.json) preserves that
result and its initial reporting failure. Existing real-game captures show initial options 0 and 1
at the three repaired events, while the current source still offers an extra skip there. All 32
saved full-run reference traces observe Act 1 only. These are concrete remaining action-parity
and later-act evidence gaps; passing the 89 inspected prefixes does not settle them.
All original engine binaries, results, recipes and failed cases are preserved; final test is sealed.

[#136](https://github.com/benyanc/spireshift/issues/136) supplies the versioned training score.
[#137](https://github.com/benyanc/spireshift/issues/137) now supplies a standalone whole-run neural
player with 4,384 mutable parameters and public candidate binding. [#138](https://github.com/benyanc/spireshift/issues/138)
has complete-run experience recording, separate train/development indices and saved-input checks.
The first direct neural-weight evolution pilot under [#135](https://github.com/benyanc/spireshift/issues/135)
has completed its owner pilot with rotating common training panels, independent elite confirmation
and a final 64-seed development comparison. That is infrastructure/negative evidence, not a
competent player, matched cross-method result or foundation readiness.

**Next implementation:** audit and repair the complete event action sets, verify fixed difficulty
and later-act endings against the frozen game, then re-admit the corrected identity before a fresh learning
recipe. The build and compatibility replay are complete; there is no command to run again.
Codex handles further short checks. Any stage expected to take five minutes or more gets one
specific owner command when it is ready. Finish #141 before a new learning recipe.

Earlier foundation evidence remains: the separately versioned [neural discard-choice comparison](neural-selection-repair.md)
had 32 normal terminal losses per player, zero wins/first-boss reaches/Act 1 clears, mean floor
6.84375 each and 27 changed traces without demonstrated gain. This is inspected-seed compatibility
evidence, not a fresh/final benchmark. Historical base-v2 remains accepted; base-v11 is unpromoted.
Comparison: `sha256:2bc12a35ee21e5ac285424cab8e19bcb236bb650c88d51aaa9d91e7ea8843ce6`.
Resources: `sha256:c8e246e7455f5df0913bc55d6585b694643aba26eabcf5186004c76f9947786d`.

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
| Blocking; native published, 89/89 compatibility checks pass | Verify difficulty/endings/complete event action sets against the frozen game, then re-admit before learning. | [#141](https://github.com/benyanc/spireshift/issues/141) |
| Implemented | Versioned bounded bootstrap score, win-first population ranking, failures/caps and terminal-only staging rules. | [#136](https://github.com/benyanc/spireshift/issues/136) |
| Implemented | Unified compact full-run neural policy, public features, legal candidate scoring and deterministic genome/gradients. | [#137](https://github.com/benyanc/spireshift/issues/137), parent [#78](https://github.com/benyanc/spireshift/issues/78), iteration [#134](https://github.com/benyanc/spireshift/issues/134) |
| Implemented; owner pilot saved | Complete-run public experience, actual returns, milestones, lineage, immutable split-specific indices and verification; original failures remain represented. | [#138](https://github.com/benyanc/spireshift/issues/138) |
| After repair | Direct neural-weight evolution pilot is negative/compromised by compatibility defects; no scaling yet. Outcome-trained PPO on the same verified model/score remains to implement. | [#135](https://github.com/benyanc/spireshift/issues/135), [#35](https://github.com/benyanc/spireshift/issues/35) |
| After repair and comparator | Freeze matched training budgets, seed panels, elite confirmation, scaling/plateau stops and equal decision-budget cross-method comparison. | [#140](https://github.com/benyanc/spireshift/issues/140) |
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
  The profile must match actual implemented engine rules, not just a configuration label. The
  first unified pilot's Ascension-0 claim is invalid and remains disclosed as historical evidence.
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
- Stages expected to take five minutes or more have one clear owner command, progress, immutable
  outputs, explicit resume and a definite stop. Only the owner launches and monitors those jobs.
  Codex may run shorter stages with explicit caps; the short audit does not authorize admission,
  promotion or a longer collection/training/evaluation job.

## Preserved real-game milestone

The owner launched the privately archived v0.107.1 app outside Steam's managed library. Its
executable, pinned bridge and read-only menu identity were verified. [The frozen-game guide](frozen-live-game.md)
records its launcher and location.

Retesting after a normal future Steam update, save/profile isolation and watching a useful trained
policy through the live adapter remain under [#37](https://github.com/benyanc/spireshift/issues/37).
A menu launch establishes neither model strength nor full simulator parity. The final pre-patch
model/data/protocol bundle remains unfinished.
