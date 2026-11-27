# Outside-combat potions and the next native A8 pilot

The remaining finite mechanics requirements are implemented on frozen host **v33**, with the
original **v0.111.0 / 41cef1ea** game assembly unchanged. The next owner task is the separately
admitted **v4 native learning pilot**, starting from the original numerical initializer and
zero optimizer state. No long experiment was launched by Codex.

## Potion controls

The current public menu includes native potion use and discard outside combat, alongside map,
event, rest, shop, reward and choice controls. Legality comes from the current native potion,
owner, usage, custom check, belt slot and target facts. Combat-only and automatic potions cannot
be manually used outside combat. Optional Skip/leave controls remain selectable.

All five native AnyTime types are inventoried: Ambergris, Blood Potion, Entropic Brew, Foul
Potion and Fruit Juice. Healing, maximum HP, potion generation, gold and combat effects execute
through the original game models and action queue; the adapter does not implement these effects.

Foul Potion changes from AllEnemies in combat to TargetedNoCreature outside combat. The native
merchant target exists at the merchant approach, with the inventory closed. Opening the
inventory removes that target; closing restores it. The target binding includes the exact
current merchant presentation, room and potion copy. Stale copies, rooms and targets are rejected
before enqueueing. The real merchant awards the native gold bonus; the fake merchant starts its
native event fight and rewards path. Fake-merchant purchases and close/leave also use native
inventory models. Sold entries and unaffordable goods do not invent purchase controls.

The version-bound headless seam represents the absent merchant button/inventory and suppresses
the fake merchant's animation. It retains native Foul Potion usability checks and OnUse, event,
reward and purchase logic. This is native fixture evidence, **not a new shipped-app comparison**.
The shared frozen game/runtime are reused with private profiles; no game-app copies are made.

[Saved evidence](evidence/actual-engine-potions-and-native-learning-v1.json) records exact report
identities, resource measurements and the preserved failed control.

## Completed checks

- The reproducible v33 build has two matching fresh repaired artifacts and two matching baseline
  builds. Its game DLL and other native sources are unchanged; RunSimulator contains the reviewed
  merchant/potion presentation delta.
- **25/25 native potion cases** pass, including four ordinary AnyTime effects on map/rest/reward/
  shop screens, both merchant types, inventory open/close, disabled use, discard, and three stale
  operand rejections. The final batch took **27.28 seconds**. Saved case/source/trace hashes verify.
- Two extra native merchant checks buy a normal-shop card or a fake-merchant relic, close the
  inventory and leave to the map. Both pass; the original unfunded probe stays preserved.
- The v33 lifecycle fixtures pass native act transitions, Architect dialogue and the zero-HP
  victory edge case. Fixtures supply **zero player wins and zero training examples**.
- The final worker panel passes **12/12 natural games**, including eight serial seeds and two
  parallel workers with reset/repeat checks. Semantic traces match, input/profile isolation and
  shutdown verify. Its wall time was **17.02 seconds**; these are environment checks, not wins.
- The new short learning control passes **4/4 games**, **228 verified sampled training decisions**
  and **six optimizer steps** in **14.66 seconds**. Both actor and critic change, checkpoints reload,
  and saved action/receipt/ending chains verify. All four games are losses; this is pipeline evidence.
- **548 saved observations** pass **1,644 ID-renaming comparisons**, including the new merchant and
  potion surfaces. The model never receives native references, environment seeds or hidden RNG.

The completed **1,849-case sweep remains a host-v32 result**. The composed gate rechecks every
saved case and preserved supplementary artifact, pins the same rules DLL, unchanged combat
projection and reviewed native-source delta, and requires the new potion/lifecycle/worker
controls. It does not relabel the old sweep as a v33 sweep or prove every interaction.

## Preserved failed control and evaluation policy

The first new short control made six updates from two games, then its greedy player failed on
legal shop open/close and defensive-combat loops. Both capped games, checkpoints, logs and worker
retirements remain recorded under control v7. They are not counted as normal losses or a pass.

Diagnostic policy v7 connects merchant inspection to the existing player-observable
`shop_inspected` history consumed by the encoder. Every action remains available to the learned
policy. A weak model choosing only its maximum-scoring action can still loop after a tiny update;
this remains a quality limitation rather than an interface failure to hide.

The new control and pilot explicitly evaluate the **categorical policy at temperature 0.8**,
which is also used for training. Each environment seed gets a fixed evaluation RNG stream reused
across initial/selected checkpoints; training streams are separate. This evaluates the declared
stochastic player, without forced exits, action filtering, relaxed liveness limits or unrecorded
fallbacks. Historical greedy results are not directly comparable. Greedy robustness remains a
later quality check before base readiness and adaptive thinking.

## One owner command

Run this from any directory when ready:

```bash
bash /Users/benjamin/.codex/.chatgpt-projects/g-p-6aadf2d496f48191b3d64a1e8aac269a/spireshift/scripts/train-native-a8-ppo-v4.sh
```

It starts fresh: **eight rounds × 32 training games**, confirmation and independent development
checks, **336 total planned attempts**, two isolated workers. Allow roughly **10–20 minutes**;
the cap is 30 minutes, 3,600 CPU seconds, 4 GB memory and 4 GB artifacts. Each batch prints wins,
average floor, best game and failures. Re-running a completed result only reads saved evidence;
unfinished workspaces are preserved for inspection. No automatic next experiment follows.

The binary full-run victory objective and whole-run CPU allowance are unchanged. Progress remains
an explicit bootstrap signal. This pilot has not run, no model is promoted, no playing-strength
improvement is established, and adaptive thinking remains blocked on a strong base learner.
