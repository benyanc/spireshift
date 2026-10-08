# SpireShift backlog

Updated 2026-10-08. This is the current order of work; GitHub holds the detailed acceptance
criteria and historical evidence. The owner launches and monitors all sustained collection,
training, simulations and evaluations. Planning updates do not start experiments.

**Current handoff:** the owner completed the [compact neural combat pilot](neural-combat-policy.md)
and its [paired gameplay comparison](neural-combat-confirmation.md). Base-v11 shows no clear
playing benefit: zero wins or first-boss reaches, with two unsupported card-choice failures.
The 30 completed pairs have one floor improvement, one regression and 28 ties. Base-v2 stays
accepted. The [discard-choice repair](neural-selection-repair.md) is implemented: the two
short smoke runs finish as normal losses, and all 168 earlier predictions match. The owner now
runs the separately versioned corrective comparison using the one command in that guide.
It uses inspected seeds and preserves the original failures; it does not retrain or promote
the model. #134 remains open for comparison review and the later learning cycle.

## Goal and current position

Build a player that wins complete runs, then teach it when to spend little, medium or substantial
thinking effort. The primary objective remains **terminal full-run victory probability under a
fixed whole-run computation budget**. A strong inexpensive base player comes first.

The framework for collecting lessons, training, replaying and comparing players exists. Playing
strength remains weak: the latest neural comparison produced zero wins and zero first-boss
reaches for both models across 32 attempted runs each. The candidate completed 30; its other two
attempts stopped at unsupported card-choice menus and remain in the original denominator.
Earlier base-v10 also failed to establish improvement; its public diagnosis verified all 64
replays without failures or mismatches.

Base-v2 is a sparse feature-based learned scorer. The recent combat adjustments are small
feature-based corrections. The compact neural combat candidate is now trained, with shared
public card properties and a trainable hidden layer. Its first gameplay comparison is complete
and has not established improvement. Saved-label improvement does not establish better play.
After the menu repair, further neural work needs a frozen, testable lesson-quality or coverage
intervention rather than repeated fitting of the same lessons.

## Current priorities

| Order | Work | GitHub items |
| --- | --- | --- |
| Next | Owner runs the corrected neural/base-v2 comparison on the same inspected seeds, then review failures and playing strength. The public discard-choice decoder and future failure classification are repaired; the original result remains preserved. | [#134](https://github.com/benyanc/spireshift/issues/134), parent [#78](https://github.com/benyanc/spireshift/issues/78) |
| Then | Freeze a bounded neural improvement round with better or broader action lessons and separate gameplay evaluation. Review the completed pilot before spending more training or teacher compute. | [#134](https://github.com/benyanc/spireshift/issues/134), parent [#78](https://github.com/benyanc/spireshift/issues/78) |
| When needed by that recipe | Fix the remaining hidden-world resampling compatibility issue before relying on the affected search path for labels. | [#105](https://github.com/benyanc/spireshift/issues/105) |
| Foundation milestone | Establish repeatable useful gameplay progress; then obtain wins and credible run-value/risk estimates. Preserve the frozen readiness gate and keep improving strategic choices as well as combat. | [#78](https://github.com/benyanc/spireshift/issues/78), readiness contract [#5](https://github.com/benyanc/spireshift/issues/5), [#46](https://github.com/benyanc/spireshift/issues/46) |
| After the foundation | Integrate full-run learned search and compare it against ordinary search at equal compute. | [#27](https://github.com/benyanc/spireshift/issues/27), [#28](https://github.com/benyanc/spireshift/issues/28), [#7](https://github.com/benyanc/spireshift/issues/7) |
| After useful search is demonstrated | Measure which decisions benefit from extra thinking, enforce the whole-run budget, and learn how much thinking to spend. | [#29](https://github.com/benyanc/spireshift/issues/29)–[#34](https://github.com/benyanc/spireshift/issues/34), [#36](https://github.com/benyanc/spireshift/issues/36) |
| Later research | Freeze the full pre-patch bundle, measure behavior after rule changes, and test recovery with limited new data/compute. | [#37](https://github.com/benyanc/spireshift/issues/37)–[#40](https://github.com/benyanc/spireshift/issues/40) |
| Final evidence | Compare compatible public/PPO baselines, refresh competition, run the final benchmark and publish a reproducible report/demo. | [#35](https://github.com/benyanc/spireshift/issues/35), [#49](https://github.com/benyanc/spireshift/issues/49), [#50](https://github.com/benyanc/spireshift/issues/50), [#41](https://github.com/benyanc/spireshift/issues/41), [#44](https://github.com/benyanc/spireshift/issues/44) |
| Optional product | Build the recommendation overlay and package the Advisor. This does not take priority over player quality. | [#16](https://github.com/benyanc/spireshift/issues/16), [#43](https://github.com/benyanc/spireshift/issues/43) |

[Issue #42](https://github.com/benyanc/spireshift/issues/42) continues to hold negative-result
analysis. The completed [#117](https://github.com/benyanc/spireshift/issues/117) and collection/
teacher components are reused by #134; a new framework is not required.

## Learning and evaluation rules

- Keep one character, a frozen game version and a fixed difficulty for the initial experiments.
  Ascension selects difficulty; Acts are chapters. Report higher difficulties separately after
  stable wins, rather than adding difficulty and floors to form a replacement reward.
- Combat survival, Act 1 completion, floors and HP provide auxiliary lessons and intermediate
  milestones. They can help distinguish all-loss attempts, but are not full-run victories.
  Zero positive victory labels still block a credible learned victory-value model.
- Freeze each recipe's rounds, seeds, exploration, teacher budgets and resource/plateau stops
  before launching it. Use many diverse train runs when affordable, compare alternatives with
  an explicit continuation policy, and measure the resulting player on separate development runs.
  More attempts under the same weak teacher do not guarantee better lessons.
- Keep final test seeds sealed, retain failures in denominators, and count all teacher and
  discarded-candidate costs. Reused development results are inspected evidence.
- Saved-data gates and gameplay tests serve different purposes. Do not promote a model merely
  because its training loss improves or relax a failed frozen gate to obtain an update.
- The next sustained stage should have one clear owner command with caps and preserved results.
  Resume supported work; explicitly restart interrupted fitting when no optimizer checkpoint
  exists. No coding agent starts or monitors it, and no indefinite loop or fallback runs.
- The owner explicitly authorized bounded short diagnostic/smoke jobs on 2026-10-08. This
  exception does not authorize the coding agent to start or monitor sustained experiments.

## Genetic algorithm: deferred option

[Issue #135](https://github.com/benyanc/spireshift/issues/135) preserves a bounded evolutionary
policy or neural–evolutionary hybrid experiment. Activate it only by an owner decision after
prespecified neural rounds plateau, or when it has a clear complementary exploration role.

Evolve compact policies/corrections/settings across multiple train seeds and compare against
neural training at matched total cost. Useful evolutionary decisions may be distilled back into
the neural policy. Existing trajectory mutation search improves a particular seed's run; this
future experiment must improve a policy that transfers to other seeds. It is not the main
research contribution and does not bypass the foundation gate.

## Preserved real-game milestone

The owner successfully launched the privately archived v0.107.1 app outside Steam's managed
library. The executable, installation identity, pinned bridge and read-only public menu were
verified. [The frozen-game guide](frozen-live-game.md) records the location and launcher.

Retesting after a normal future Steam update, checking save/profile isolation and watching a
useful trained policy through the guarded live adapter remain under
[#37](https://github.com/benyanc/spireshift/issues/37). Menu launch does not establish simulator
parity or model strength. The final pre-patch model/data/protocol bundle is still unfinished.
