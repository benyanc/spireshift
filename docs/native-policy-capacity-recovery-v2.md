# Capacity-study potion queue repair and continuation

The owner run stopped in round 10 on November 24, 2026. The saved audit verifies
**633 complete training games, 39 full model/Adam fits and 2,429 updates on copies**.
All 633 outcomes are losses. No fresh development game has started.

| Initializer | 32-unit games / Act 1 clears | 128-unit games / Act 1 clears |
| --- | --- | --- |
| 2 | 160 / 12 | 160 / 12 |
| 3 | 160 / 11 | 153 / 7 |

Neither method cleared Act 2. These changing training policies and the incomplete
round do not establish a capacity winner. The fixed, fresh evaluation remains
the comparison. The original game, host60, runtime, SDK, original checkpoints,
source finals and every original Adam state remain unchanged.

## Framework defect and bounded repair

The excluded unit is `train-0154-p3-expanded`. End Turn left a required card
selector open in Act 2. `turn_owner` still said `player`, but `is_play_phase` was
false. The belt advertised discard. Native `DiscardPotionGameAction.ActionType`
is `CombatPlayPhaseOnly` in combat; `UsePotionAction` uses the same classification.
`ActionQueueSet.EnqueueWithoutSynchronizing` cancels these actions while ending
the player turn or canceling combat actions. This cancellation reached the
headless Godot stub's missing `Callable.From(Func<bool>)` overload.

The new support assembly links the unchanged card-cleanup and merchant-map
adapters. It reads the actual player's native queue cancellation flags before
advertising **either** potion operation, and checks again before dispatch. It
does not infer eligibility from the visible owner, selector type, encounter,
potion name or seed. A paused queue gathering a player choice can still accept
discard; a canceling queue cannot. Existing owner, slot, target, usage, custom
permission and already-queued checks remain in force. Outside combat the native
action is `NonCombat`, so combat cancellation flags do not remove these controls.

The repair does not enqueue canceled actions, change game rules, suppress native
errors or pretend cancellation is delivery. It leaves the frozen game/host/stub
assemblies intact. General stub support for other cancellation paths is not
qualified by this repair. Connector36 has the related eligibility omission;
its existing parity evidence does not cover this post-End-Turn combination.
Targeted official Connector correction and paired verification remain under #149.
This source-grounded native repair enables the native-only learning continuation;
it grants no new official-game qualification or claim of complete mechanics.

## Checks

Two independent builds produced the same support DLL. Three fresh native
fixtures verify 14 public gameplay deliveries and 17 complete observations:

- A player-turn required card choice retains legal discard. The native queue
  accepts it once, the exact bottle remains unavailable for duplicate discard,
  and it is removed after the child answer resumes the queue.
- An End Turn card choice retains its owner and has no potion controls. Direct
  use and discard probes are rejected before enqueue; native state is unchanged.
  Answering the child reaches the next player turn and restores potion controls.
- Outside combat, use heals and removes the exact bottle; discard removes the
  other bottle. Blood Potion heals exactly 16 HP in all three cases.

All three profiles reset cleanly. Separate production learner checks run one
fresh normal-start game at each width: 177 and 198 verified native choices,
both genuine losses, zero updates, exact full-state/Adam reload and clean resets.
The fixtures provide no learning labels. Local diagnostic setup aborts in
`control-1` through `control-4`, and the first production harness assertion stop,
are preserved; the passing controls use different fresh worlds.

The saved prefix audit checks all 673 clean units, their exact requests,
behavior checkpoints, evidence hashes, native outcome/reset seals and all four
full optimizer lineages. The failed prefix remains diagnostic, with no clean
ending or close invented. A separate restore check must recover those units
and stop before `train-0155-p3-expanded`, launching zero games or updates.

See [machine-readable evidence](evidence/native-policy-capacity-recovery-v2.json).

## Owner continuation

Run from the same frozen checkout, with STS2 closed:

```bash
bash scripts/continue-a8-policy-capacity-v2.sh
```

Allow about 12–22 hours, with the unchanged 48-hour outer cap. The new recipe
restores all 633 games and 39 fits without repeating optimizer work. It retains
the failed cell in the denominator and excludes its partial experience from
fitting. The pending round uses its completed siblings and only previously
unstarted games. No historical world is replayed or replaced.

There are **3,462 unstarted training games and 768 unstarted evaluation games**.
Architecture initialization, full Adam carryover, inputs, PPO, objectives,
training/evaluation worlds, round-64 candidate selection and guards remain fixed.
Both widths use the repaired adapter for every new game. Historical menus and
behavior probabilities remain recorded as observed; they are not relabeled.
Actual optimizer work is reported, not claimed equal. Capped, failed and missing
cells remain explicit. A new incomplete unit stops and preserves its evidence.
There is no automatic promotion, controller fitting or final-test use.
