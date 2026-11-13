# ADR 0008: Native-only admission for the win-focused A8 curriculum

## Status

Implemented November 5, 2026 for the owner's #152 request, under
[ADR 0007](0007-a8-base-competence-first.md). The owner requested short checks
and preparation of a longer collection command, with the build and original
full weights/Adam frozen. This decision grants no ordinary training, promotion,
official-game competence or adaptive-controller permission.

## Decision

Use `native_A8_win_curriculum_training_only_v1`, a separate versioned native
development scope. Preserve v0.111.0 / 41cef1ea, CLI56, Connector31, ordinary
worker24, converter16, layout12 and environment48. Preserve the incomplete
six-pair experiment, including VTV204's marker and its 3/1/2 denominator.
Its existing guard and blocked command remain unchanged. No new checkpoint
inherits an official live qualification from this curriculum.

Admission requires the exact new implementation and runtime, the previously
assessed public-input/action/reset evidence, frozen original full states, a
native model inventory bound to this game assembly, and the new short control.
The control must exercise all twelve native bosses across four act definitions,
later-act/rest/shop starts, ordered raw action reconstruction, successful new
native teaching data, fitting on disposable copies, exact full-Adam reload,
actual reloaded actions and a separate unseen-world loss check. Resource guards
must complete without a cap. Changed code, recipe bindings or evidence invalidate
the receipt. Historical failed controls stay preserved on their original worlds.

An isolated wrapper uses existing CLI save/load and native model acquisition
hooks to construct explicitly privileged training starts. It loads a real native
generated map and a connected route to its declared room, preserving the native
RNG. Its current-act route history is synthetic setup, not a claimed played
prefix. Native start identity, deck, act, boss ownership and clean shutdown are
checked. Enemy HP, enemy actions and current combat energy are never assigned.
Energy relics apply their genuine native effects and drawbacks. These starts are
excluded from normal-start evaluation and ordinary PPO experience.

Student inputs retain the unchanged public graph. Saves, seeds, native RNG state,
setup metadata and future branch outcomes do not enter student features. Fit
worlds alone provide labels. Independent development worlds use the same fixed
teacher-selection procedure for probes; their labels never enter fitting.
Final-test worlds remain unlaunched. Search selection and independent teacher
confirmation are recorded as privileged data collection, not on-policy samples.

Keep terminal full-run victory as the primary player objective. Prepared starts
use explicit training goals: finish the declared earlier act alive, or reach
the native completed-final-boss reward owner after an observed boss-combat
prefix. Those successes are never normal-start wins. The newly reached frozen
headless Architect completion fails before its victory ending; preserve that
known gap for targeted repair before normal-start victory validation. The
curriculum neither dispatches that failing completion for prepared goals nor
substitutes boss defeat for a natural terminal victory.
Keep the existing versioned objective/score and its 128 gameplay CPU-second guard;
add only separately declared operational wall, choice, memory and storage caps.
CPU allocation research is outside this scope.

The owner-run stage collects and audits the finite bank, then stops. Admission
of that bank requires meaningful successful coverage of every declared boss and
decision family, strict goal rescues and held-world successes. A blocked quality
report is a useful negative result, not permission to train weak labels. #134/#35
must separately prepare the actual base-learning stage after assessment. #146
owns fresh normal-start strength evaluation; #149 owns targeted interface checks
and real official validation at promising candidate milestones.

## Consequences

Later-game teaching can proceed without replaying the incomplete official
canary or modifying frozen game code. The short control demonstrates plumbing
and bounded generalization only. The prepared bank, successful boss starts and
lower imitation loss do not establish a player that wins complete A8 games.

See [the recipe, checks and owner handoff](../native-win-curriculum.md).
