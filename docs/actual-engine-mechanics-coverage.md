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
- The first plan generated **1,824 cases**. After its repairs, the new plan generates **1,849**:
  1,773 card contexts for all 596 non-mock cards, including nine configured Mad Science forms
  (normal resources, funded resources and first upgrade where supported), 65 non-mock combat
  potions, and eleven named interaction regressions. Token/event/foreign cards are included. Repeated or unlimited
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

The original short stage completed **15/15 checks**, followed by the owner's complete sweep:
**1,824/1,824 cases**, **1,691 exercised effects**, **83 observed prerequisite blocks** and
**50 failures**. It took **44 minutes 11 seconds**, about 0.50 CPU-hours, **370.49 MB** peak
process-tree memory and **356.87 MB** retained evidence. It created zero app copies and reached
every planned case; its failed exit code reports the observed gaps, not an interrupted sweep.
The original short-stage [evidence](evidence/actual-engine-mechanics-coverage-v1.json) remains
unchanged.

## What the complete sweep found and repaired

The 50 failures share three causes, rather than 50 separately missing game mechanics:

- **45 disabled multiplayer cards:** fifteen AnyAlly cards across three contexts. Native target
  geometry includes the owner, while CanPlay correctly denies use with NoLivingAllies. Combat
  surface v4 preserves that disabled card and reason without inventing an ally action. It still
  rejects malformed target lists and unexpectedly playable unsupported multiplayer cards.
- **Three invalid Mad Science fixtures:** its raw template has no chosen type or extra effect.
  Host v32 obtains all nine initialized forms from native Tinker Time option previews, clones
  them with the native engine, and applies native upgrades. The effects stay native. This
  exercises configured private preview clones, not the full naturally played event path.
- **Two Particle Wall delivery checks:** returning the card to the hand is intended behavior.
  Native manual-play history for the exact new card play confirms delivery even when the card
  stays in hand. Old history, autoplay and another card cannot confirm this receipt. That
  evidence stays private; the model sees the resulting current public state.

The focused repaired panel completes **90/90 checks**: **44 exercised effects**, **46 correctly
observed prerequisite blocks**, zero failures, **127.81 seconds**, **306.20 MB** peak process-tree
memory and **19.08 MB** retained evidence. It covers every former failing card/context, all nine
configured forms, prior short controls, and two plays of the **same physical Particle Wall**.
All nine forms have distinct public type/description pairs. All 1,824 original case hashes and
all 90 repaired case hashes verify; the old results are preserved.

Two fresh repaired builds match their source/assembly pins; the original game DLL stays unchanged.
The repository check passes **1,339 tests** plus formatting, types and the C# protocol contract;
19 focused new Node checks pass. [Sweep and repair evidence](evidence/actual-engine-mechanics-coverage-repairs-v1.json)
contains aggregate counts and identities without publishing the raw game catalog. The new full
sweep has **not** started. Focused success does not relabel it as passed or permit training.

## One next command

Close the game and run:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/check-native-mechanics-coverage-v2.sh
```

Allow roughly **40–90 minutes**; the first complete sweep took 44 minutes. The new plan has
1,849 cases and reuses its 90 verified same-plan controls. The hard limits are four hours,
14,400 CPU seconds, 4 GB memory and 4 GB evidence.
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

After the full repaired recheck, assess any remaining failures without discarding their denominator.
Complete remaining declared requirements, including outside-combat potions, bounded
random action sequences and same-build lifecycle checks. The new all-pool learning path requires
the frozen complete sweep plus resolved requirements; diagnostics cannot grant learning admission.
Then bind a new environment/model lineage, qualify workers and a short neural control before
preparing another owner-run A8 pilot. Existing models/results are never silently resumed on changed
inputs. Strong-base readiness still precedes adaptive thinking.
