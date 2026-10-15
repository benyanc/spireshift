# Native mechanics coverage before another A8 pilot

The v3 actual-engine pilot finished 336 attempts: 332 native normal endings and four isolated
failures. It made 627 PPO updates from 26,416 verified sampled decisions. No wins occurred.
The selected player's independent average floor was 8.75 versus the initializer's 7.4375;
counting the selected player's failure as zero gives 8.625. The paired interval includes zero.
This is a working learner with inconclusive generalization, not a strong foundation.

The owner requested this systematic pass on 2026-10-15. Ironclad/A8 must support resources and
cards acquired from any character. Inventorying every model is possible; proving every possible
card × relic × enemy × history combination is not the claim of this pass.

## What the implementation covers

- Join every class in the frozen game's generated registry to its live native ModelDb entry.
  There are **1,660 registered types**, with no missing or extra runtime classes in the check.
  Keep all characters, cards, relics, potions, powers, enemies, events, encounters and other
  families in the private inventory. Mocks are excluded using native flags, never name guesses.
- Generate **1,824 cases**: 1,749 card contexts for all 596 non-mock cards (normal resources,
  funded resources and first upgrade where supported), 65 non-mock combat potions, and ten
  named interaction regressions. Token/event/foreign cards are included. Repeated or unlimited
  upgrades and prerequisites absent from these contexts remain explicitly unexercised.
- Preserve **current** per-copy energy/star costs and native CanPlay results. Any hero can expose
  stars, ordered orbs, their current passive/evoke amounts and formatted hover text, and companion
  health/block/statuses/ownership. Native rules handle effects and cost interactions.
- Classify all ten native target types. Bind current enemy operands; keep native automatic
  self/player/Osty targeting; retain disabled single-player AnyAlly cards. Unknown targets stop
  that case. Non-creature potion targeting remains an explicit unsupported requirement.
- Fix reentrant card-choice completion: clear the old request before its continuation can install
  another. Recognize newly pending selections and reward-to-bundle choices during native waits.
- Refresh the ordinary public action menu after every choice. Repeated rest/shop actions, Skip,
  and mandatory selections retain their native legality. No action is forced into ordinary play.

The short native controls exercise Frost/Plasma on Ironclad, foreign stars, Osty, two successive
Glam/Headbutt selections, Enlightenment changing another card's cost from 5 to 1, claiming
Scroll Boxes through its nested bundle, four rest options with Miniature Tent/Shovel/Girya,
shop restocking/removal/exit, and declining a card reward. Extra controls cover an upgraded card,
an unplayable status, a star potion, a companion potion and an attack potion's selection.

The final short stage completes **15/15 checks**: 14 native effects and one expected unplayable
Dazed state, zero failures, **24.01 seconds** including resource tracking, **294.75 MB** peak
process-tree memory and **5.87 MB** retained evidence. The large sweep has not been launched.
The repository check passes **1,336 tests** plus formatting, types and the C# protocol contract;
23 focused Node checks pass. [Aggregate evidence](evidence/actual-engine-mechanics-coverage-v1.json)
keeps identities and limitations without publishing the raw game catalog.

## One next command

Close the game and run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/check-native-mechanics-coverage-v1.sh
```

Allow roughly **40–90 minutes**, extrapolated from short checks rather than a measured complete
sweep. The hard limits are four hours, 14,400 CPU seconds, 4 GB memory and 4 GB evidence.
Only the owner launches/monitors this larger stage. It does not train or start another experiment.

One native process runs at a time. Workers share frozen engine/runtime/SDK data and one verified
interface-code cache; mutable profiles, ledgers, logs and case evidence remain separate. There
are **zero app copies**. Complete cases, including the same-plan short controls, are hash-verified
and reused. An interrupted case or unverified process shutdown stops for inspection. A failed
case is preserved and not retried; other planned cases continue only after verified shutdown.
Progress prints every 25 cases, with each new gap printed immediately.

## Read the result correctly

`effect_exercised` means the native action and its immediate public successor/required choices
passed in this declared fixture. `observed_prerequisite_blocked` means native rules did not offer
the action in this context; this verifies its representation, **not its effects**. Failures,
remaining cases, metadata gaps, unsupported targets and untested requirement families stay visible.
A completed diagnostic can still have gaps. Fixture results are never player wins or PPO examples.

The private catalog, plan, per-case traces and summaries live at the recipe's workspace. Configs,
source pins, tests and aggregate evidence may enter Git; game binaries, model inventories, native
text, save files and raw traces stay private. Changed native or interface/Python implementations
require a new recipe/workspace; old failures remain intact.

After the sweep, group the actual failures by shared cause, fix those causes and add representative
regressions. Complete remaining declared requirements, including outside-combat potions, bounded
random action sequences and same-build lifecycle checks. The new all-pool learning path requires
the frozen complete sweep plus resolved requirements; diagnostics cannot grant learning admission.
Then bind a new environment/model lineage, qualify workers and a short neural control before
preparing another owner-run A8 pilot. Existing models/results are never silently resumed on changed
inputs. Strong-base readiness still precedes adaptive thinking.
